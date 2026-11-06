#!/usr/bin/env python3
"""The one persistent install on this Mac, and the only guarded path that changes its database. US-11.3.

Its record lives outside this repository (`install.json`, `stack.env` and `app.env`, private files), and a
row in the database holds the same identity. Every command that touches the database names the project,
and is refused before any change unless the name, the recorded identity, the container's own labels and
port, and that row all agree. There is no reset, and no command here removes a container or a volume.

Run with services/agent/.venv/bin/python, so `goal` can use the shared ledger. Exit codes: 0 done,
1 refused or failed, 2 prerequisite unavailable. Passing establishes neither H1 nor product acceptance.
"""
from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import time
from urllib import error, request
import uuid

from app_db import MIGRATION_NAME, MIGRATIONS, ROLES, SEEDS, AppStack
from disposable_db import PROJECT_PREFIX, Refused, Target, Unavailable, jwt, other_resources, run, tool_env
from harness_lib import project_root
from supabase_stack import UPSTREAM, example_defaults, generated_values, listener_addresses, port_conflict, rendered_refusals

DEFAULT_DIR = Path.home() / '.local/share/autobots-install'
PERSISTENT_FILES = (UPSTREAM / 'docker-compose.yml', Path('infra/supabase/compose.overlay.yaml'))
STORAGE_SQL = Path('supabase/bootstrap/storage.sql')
STORAGE_ROW = 'bootstrap/storage.sql'
PYTHON = Path('services/agent/.venv/bin/python')
HELPER = 'tests/db/live_goal_helper.py'
OWNER_EMAIL = 'owner@autobots.invalid'
TEN_YEARS = 86400 * 3650
GOAL_SECONDS = 1000
ACTIVE = {'queued', 'running', 'verifying', 'cancelling'}
SCHEMA = """create schema autobots_install;
create table autobots_install.identity (install_id text primary key, project text not null, created_at timestamptz not null default now());
create table autobots_install.migrations (name text primary key, sha256 text not null, applied_at timestamptz not null default now());
revoke all on schema autobots_install from public;
grant usage on schema autobots_install to autobots_migrator;
grant select on autobots_install.identity to autobots_migrator;
grant select, insert on autobots_install.migrations to autobots_migrator;
"""


@dataclass(frozen=True)
class Record:
    """What `install.json` says this install is. It holds no secret."""

    project: str
    install_id: str
    gateway_port: int
    db_port: int
    api_port: int
    web_port: int
    directory: Path

    @property
    def stack_env(self) -> Path:
        return self.directory / 'stack.env'

    @property
    def app_env(self) -> Path:
        return self.directory / 'app.env'


def read_values(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text().splitlines():
        if line.strip() and not line.lstrip().startswith('#') and '=' in line:
            name, _, value = line.partition('=')
            values[name.strip()] = value.strip()
    return values


def read_record(directory: Path) -> Record:
    path = directory / 'install.json'
    if not path.is_file():
        raise Refused(f'no install is recorded at {directory}')
    data = json.loads(path.read_text())
    return Record(data['project'], data['install_id'], data['gateway_port'], data['db_port'], data['api_port'], data['web_port'], directory)


@dataclass
class InstallStack(AppStack):
    """The vendored release and overlay, without the disposable marking."""

    def compose(self, *arguments: str, timeout: float = 300.0, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
        files = [item for path in PERSISTENT_FILES for item in ('-f', str(self.root / path))]
        return run(['docker', 'compose', '-p', self.target.project, '--project-directory', str(self.root / UPSTREAM), *files, *arguments],
                   self.env(), timeout, stdin)

    def env(self) -> dict[str, str]:
        return {**tool_env(), **self.values}


def install_stack(root: Path, record: Record) -> InstallStack:
    values = read_values(record.stack_env)
    stack = InstallStack(Target(record.project, record.db_port, record.gateway_port), root, root / UPSTREAM / 'docker-compose.yml', values=values)
    stack.migrator_password, stack.runtime_password = values['AUTOBOTS_MIGRATOR_PASSWORD'], values['AUTOBOTS_RUNTIME_PASSWORD']
    return stack


def restored_copy_stack(root: Path, record: Record, project: str) -> AppStack:
    """A restored `autobots-disposable-*` copy of this install, which keeps its secrets and its identity row."""
    values = read_values(record.stack_env)
    stack = AppStack(Target(project, record.db_port, record.gateway_port), root, root / UPSTREAM / 'docker-compose.yml', values=values)
    stack.migrator_password, stack.runtime_password = values['AUTOBOTS_MIGRATOR_PASSWORD'], values['AUTOBOTS_RUNTIME_PASSWORD']
    return stack


def db_container_facts(project: str) -> dict[str, str]:
    """From Docker itself: this project's database container, its target label and its published port."""
    env = tool_env()
    found = run(['docker', 'ps', '--filter', f'label=com.docker.compose.project={project}', '--filter', 'label=com.docker.compose.service=db', '--format', '{{.ID}}'], env)
    ids = found.stdout.split()
    if found.returncode or len(ids) != 1:
        return {}
    label = run(['docker', 'inspect', '-f', '{{index .Config.Labels "autobots.target"}}', ids[0]], env).stdout.strip()
    port = run(['docker', 'port', ids[0], '5432/tcp'], env).stdout.strip()
    return {'label': label, 'port': port}


def identity_refusals(stack: AppStack, record: Record, requested: str, expected_class: str = 'persistent', restored_copy: bool = False) -> list[str]:
    """Every reason not to touch this database. Read-only, and it runs before any change."""
    if restored_copy:
        if not requested.startswith(PROJECT_PREFIX):
            return [f'a restored copy is always {PROJECT_PREFIX}*, and {requested} is not']
    elif requested != record.project:
        return [f'{requested} is not the recorded install, {record.project}']
    facts = db_container_facts(requested)
    if not facts:
        return [f'{requested} has no running database container']
    reasons = []
    wanted_label = 'disposable' if restored_copy or expected_class == 'disposable' else ''
    if facts['label'] != wanted_label:
        reasons.append(f"{requested} is labelled {facts['label'] or 'unmarked'}, and this path expects {wanted_label or 'unmarked'}")
    if not restored_copy and f'127.0.0.1:{record.db_port}' not in facts['port']:
        reasons.append(f"{requested} publishes its database at {facts['port']}, not the recorded 127.0.0.1:{record.db_port}")
    row = stack.sql('select install_id, project from autobots_install.identity;')
    if row.returncode or row.stdout.strip() != f'{record.install_id}|{record.project}':
        reasons.append(f'{requested} holds no identity row matching this install')
    if restored_copy:
        hold = stack.sql('select count(*) from app_private.installation_holds;')
        if hold.returncode or hold.stdout.strip() == '0':
            reasons.append('a restored copy must still hold its restore hold')
    return reasons


def require_install(stack: AppStack, record: Record, requested: str, expected_class: str = 'persistent', restored_copy: bool = False) -> None:
    reasons = identity_refusals(stack, record, requested, expected_class, restored_copy)
    if reasons:
        raise Refused('; '.join(reasons))


def private_write(path: Path, text: str) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w') as handle:
        handle.write(text)


def write_install(directory: Path, project: str, gateway_port: int, db_port: int, api_port: int, web_port: int, root: Path) -> Record:
    if project.startswith(PROJECT_PREFIX):
        raise Refused(f'{PROJECT_PREFIX}* names are for disposable targets')
    if (directory / 'install.json').exists():
        raise Refused(f'an install is already recorded at {directory}, and init never replaces one')
    held = [reason for reason in (port_conflict(port) for port in (gateway_port, db_port, api_port, web_port)) if reason]
    if held:
        raise Refused('; '.join(held))
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    os.chmod(directory, 0o700)
    for name in ('config/secrets', 'logs', 'backups', 'backup-key', 'provider-key-copy', 'reports'):
        (directory / name).mkdir(parents=True, mode=0o700, exist_ok=True)
    os.chmod(directory / 'config', 0o700)
    values = {**example_defaults(root), **generated_values(gateway_port, db_port)}
    secret = values['JWT_SECRET']
    expires = int(time.time()) + TEN_YEARS
    values.update(ANON_KEY=jwt(secret, {'role': 'anon', 'iss': 'supabase', 'exp': expires}),
                  SERVICE_ROLE_KEY=jwt(secret, {'role': 'service_role', 'iss': 'supabase', 'exp': expires}),
                  SITE_URL=f'http://127.0.0.1:{web_port}', AUTOBOTS_MIGRATOR_PASSWORD=secrets.token_hex(24), AUTOBOTS_RUNTIME_PASSWORD=secrets.token_hex(24))
    record = Record(project, str(uuid.uuid4()), gateway_port, db_port, api_port, web_port, directory)
    private_write(record.stack_env, ''.join(f'{name}={value}\n' for name, value in values.items()))
    base = f'http://127.0.0.1:{gateway_port}'
    runtime_url = f"postgresql://autobots_runtime:{values['AUTOBOTS_RUNTIME_PASSWORD']}@127.0.0.1:{db_port}/postgres"
    application = {
        'AUTOBOTS_INTERNAL_TOKEN': secrets.token_hex(32), 'AUTOBOTS_JWT_SECRET': secret, 'AUTOBOTS_DATABASE_URL': runtime_url,
        'AUTOBOTS_SUPABASE_URL': base, 'AUTOBOTS_SUPABASE_ANON_KEY': values['ANON_KEY'], 'AUTOBOTS_SERVICE_ROLE_KEY': values['SERVICE_ROLE_KEY'],
        'AUTOBOTS_STORAGE_BASE': base, 'AUTOBOTS_STORAGE_SERVICE': values['SERVICE_ROLE_KEY'], 'AUTOBOTS_CONFIG_ROOT': str(directory / 'config'),
        'AUTOBOTS_PROVIDER_MASTER_KEY_FILE': str(directory / 'config/secrets/master.key'), 'AUTOBOTS_BACKUP_DIR': str(directory / 'backups'),
        'AUTOBOTS_API_URL': f'http://127.0.0.1:{api_port}', 'AUTOBOTS_ALLOWED_ORIGIN': f'http://127.0.0.1:{web_port}', 'NODE_ENV': 'production'}
    private_write(record.app_env, ''.join(f'{name}={value}\n' for name, value in application.items()))
    private_write(directory / 'owner.env', f'OWNER_EMAIL={OWNER_EMAIL}\nOWNER_PASSWORD={secrets.token_urlsafe(24)}\n')
    public = {'project': project, 'install_id': record.install_id, 'gateway_port': gateway_port, 'db_port': db_port, 'api_port': api_port, 'web_port': web_port,
              'created_at': datetime.now(timezone.utc).isoformat()}
    private_write(directory / 'install.json', json.dumps(public, indent=2) + '\n')
    return record


def require_rendered_install(stack: InstallStack, root: Path) -> None:
    rendered = stack.compose('config', '--format', 'json', timeout=60)
    if rendered.returncode:
        raise Unavailable(f'Compose could not render the install: {rendered.stderr[-300:]}')
    reasons = rendered_refusals(json.loads(rendered.stdout), stack.target.project, root, marked=False)
    if reasons:
        raise Refused('; '.join(reasons))


def first_setup(stack: AppStack, root: Path, record: Record, requested: str, expected_class: str = 'persistent') -> None:
    """Roles and the identity row, once, on a database that has neither and no application tables."""
    if requested != record.project:
        raise Refused(f'{requested} is not the recorded install, {record.project}')
    facts = db_container_facts(requested)
    wanted = 'disposable' if expected_class == 'disposable' else ''
    if not facts or facts['label'] != wanted:
        raise Refused(f'{requested} is not running as a {expected_class} target')
    present = stack.sql("select to_regclass('autobots_install.identity'), to_regclass('public.runs');")
    if present.returncode or present.stdout.strip() != '|':
        raise Refused(f'{requested} already holds an identity or application tables, so setup never runs on it')
    roles = stack.sql(f"\\set migrator_password '{stack.migrator_password}'\n\\set runtime_password '{stack.runtime_password}'\n{(root / ROLES).read_text()}")
    if roles.returncode:
        raise Unavailable(f'the role bootstrap failed: {roles.stderr[-300:]}')
    written = stack.sql(f"begin;\n{SCHEMA}insert into autobots_install.identity (install_id, project) values ('{record.install_id}', '{record.project}');\ncommit;\n")
    if written.returncode:
        raise Unavailable(f'the identity could not be written: {written.stderr[-300:]}')


def guarded_apply(stack: AppStack, root: Path, record: Record, requested: str, expected_class: str = 'persistent', restored_copy: bool = False,
                  directory: Path | None = None) -> dict:
    """Pending files in name order, each with its history row in one transaction, as the migration role."""
    require_install(stack, record, requested, expected_class, restored_copy)
    folder = directory or root / MIGRATIONS
    listing = stack.migrator('select name, sha256 from autobots_install.migrations;')
    if listing.returncode:
        raise Unavailable('the migration history is unreadable')
    recorded = dict(line.split('|') for line in listing.stdout.splitlines() if line)
    files = sorted(folder.glob('*.sql'))
    # All of it is checked first, so a refusal leaves the database exactly as it was.
    for path in files:
        if not MIGRATION_NAME.fullmatch(path.name):
            raise Refused(f'{path.name} is not named <14 digit timestamp>_<description>.sql')
        if path.name in recorded and recorded[path.name] != hashlib.sha256(path.read_bytes()).hexdigest():
            raise Refused(f'{path.name} changed after it was applied; never edit an applied migration')
    applied: list[str] = []
    for path in files:
        if path.name in recorded:
            continue
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        result = stack.migrator(f"begin;\n{path.read_text()}\ninsert into autobots_install.migrations (name, sha256) values ('{path.name}', '{checksum}');\ncommit;\n")
        if result.returncode:
            raise Unavailable(f'{path.name} failed and was rolled back: {result.stderr.strip()[-200:]}')
        applied.append(path.name)
    seeded = stack.migrator(f'begin;\n{(root / SEEDS).read_text()}\ncommit;\n')
    if seeded.returncode:
        raise Unavailable(f'the reference seed failed: {seeded.stderr.strip()[-200:]}')
    if STORAGE_ROW not in recorded:
        digest = hashlib.sha256((root / STORAGE_SQL).read_bytes()).hexdigest()
        policy = stack.sql(f"begin;\n{(root / STORAGE_SQL).read_text()}\ninsert into autobots_install.migrations (name, sha256) values ('{STORAGE_ROW}', '{digest}');\ncommit;\n")
        if policy.returncode:
            raise Unavailable(f'the Storage policies failed: {policy.stderr.strip()[-200:]}')
    return {'status': 'applied', 'project': requested, 'applied': applied, 'already_applied': len([name for name in recorded if name != STORAGE_ROW])}


def status(root: Path, record: Record) -> dict:
    """What is actually listening, for comparing with the recorded bindings."""
    bindings = {name: listener_addresses(port) for name, port in (('gateway', record.gateway_port), ('database', record.db_port), ('api', record.api_port), ('web', record.web_port))}
    return {'project': record.project, 'recorded': {'gateway': record.gateway_port, 'database': record.db_port, 'api': record.api_port, 'web': record.web_port},
            'listeners': bindings, 'identity_refusals': identity_refusals(install_stack(root, record), record, record.project)}


def reserve_goal(ledger_path: Path, limit: int) -> tuple[object, dict]:
    """Before any request: the goal's whole budget has to fit what's left of the shared cap."""
    sys.path.insert(0, str(project_root() / 'services/agent/src'))
    from autobots.operations.reasoning_trial import SHARED_CAP_MICRO_USD  # noqa: PLC0415
    from autobots.operations.route_qualification import CapReached, Ledger  # noqa: PLC0415
    ledger = Ledger(ledger_path, SHARED_CAP_MICRO_USD)
    try:
        return ledger, ledger.reserve(f'install-goal:{datetime.now(timezone.utc).isoformat()}', limit)
    except CapReached:
        raise Refused(f'a goal limited to {limit} micro-USD would take the shared ledger, at {ledger.committed()}, past {ledger.cap}. Nothing was sent') from None


def http_json(method: str, url: str, headers: Mapping[str, str], body: Mapping | None = None) -> tuple[int, str]:
    data = None if body is None else json.dumps(body).encode()
    try:
        with request.urlopen(request.Request(url, data=data, method=method, headers=dict(headers)), timeout=30) as reply:
            return reply.status, reply.read().decode(errors='replace')
    except error.HTTPError as failure:
        return failure.code, failure.read().decode(errors='replace')


def goal(root: Path, record: Record, requested: str, key_file: Path, limit: int, ledger_path: Path, goal_text: str, required: list[dict]) -> int:
    """Reserve, admit through the install's API, run a worker with the switch on for this goal only, settle."""
    ledger, entry = reserve_goal(ledger_path, limit)
    stack = install_stack(root, record)
    try:
        require_install(stack, record, requested)
    except Refused:
        ledger.settle(entry, 0, 'not_started')  # type: ignore[attr-defined]
        raise
    application = read_values(record.app_env)
    owner = read_values(record.directory / 'owner.env')
    env = {**tool_env(), **application, 'PYTHONPATH': str(root / 'services/agent/src'), 'PYTHONDONTWRITEBYTECODE': '1'}

    def helper(*argv: str) -> str:
        done = subprocess.run([str(root / PYTHON), str(root / HELPER), *argv], env=env, capture_output=True, text=True, errors='replace', timeout=120, check=False)
        if done.returncode:
            raise Unavailable(f'{argv[0]} failed: {done.stderr.strip().splitlines()[-1][:300] if done.stderr.strip() else "no detail"}')
        return done.stdout.strip()

    def sql(statement: str) -> str:
        result = stack.runtime(statement)
        return result.stdout.strip().splitlines()[0] if result.returncode == 0 and result.stdout.strip() else ''

    report: dict = {'schema_version': 'autobots.install-goal/v1', 'started_at_utc': datetime.now(timezone.utc).isoformat(), 'project': record.project, 'model_transport': 'live OpenRouter',
                    'limit_micro_usd': limit, 'goal': goal_text, 'required_artifacts': required, 'not_established': ['H1', 'product acceptance', 'task quality beyond this goal']}
    charged: int | None = None
    worker = None
    run_id = ''
    try:
        report['key_usage_before_usd'] = float(helper('usage', str(key_file)))
        base = application['AUTOBOTS_SUPABASE_URL']
        code, reply = http_json('POST', f'{base}/auth/v1/token?grant_type=password', {'apikey': application['AUTOBOTS_SUPABASE_ANON_KEY'], 'Content-Type': 'application/json'},
                                {'email': owner['OWNER_EMAIL'], 'password': owner['OWNER_PASSWORD']})
        if code != 200:
            raise Unavailable(f'the owner could not sign in: {code}')
        token = json.loads(reply)['access_token']
        workspace = sql("select workspace_id from public.workspace_members where role = 'owner' limit 1;")
        if sql(f"select count(*) from app_private.provider_credentials where workspace_id = '{workspace}' and status = 'active';") == '0':
            helper('save', str(key_file), workspace)
        headers = {'X-Autobots-Internal': application['AUTOBOTS_INTERNAL_TOKEN'], 'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        api = f'http://127.0.0.1:{record.api_port}'
        code, reply = http_json('POST', f'{api}/v1/runs', {**headers, 'Idempotency-Key': secrets.token_hex(8)}, {'goal_text': goal_text, 'limit_micro_usd': limit, 'required_artifacts': required})
        report['admission'] = code
        if code != 202:
            raise Unavailable(f'the API refused the goal: {code} {reply[:200]}')
        run_id = json.loads(reply)['run_id']
        report['run_id'] = run_id
        handle = (record.directory / 'logs/worker-goal.log').open('a')
        # The switch is on for this one process only, and it's on nowhere else.
        worker = subprocess.Popen([str(root / PYTHON), '-m', 'autobots.operations.worker'], env={**env, 'AUTOBOTS_WORKER_INFERENCE': 'enabled'}, cwd=root,
                                  stdin=subprocess.DEVNULL, stdout=handle, stderr=handle, start_new_session=True)
        started = time.monotonic()
        timeline, last, final = [], '', ''
        while time.monotonic() - started < GOAL_SECONDS:
            final = sql(f"select status from public.runs where id = '{run_id}';")
            if final != last:
                timeline.append({'seconds': round(time.monotonic() - started, 1), 'status': final})
                print(f'{round(time.monotonic() - started)}s: {final}', flush=True)
                last = final
            if final and final not in ACTIVE:
                break
            committed = sql(f"select coalesce(sum(coalesce(charged_micro_usd, reserved_micro_usd)), 0) from app_private.model_invocations where root_run_id = '{run_id}';")
            if committed and int(committed) > limit:
                report['watchdog_fired'] = True
                worker.send_signal(signal.SIGKILL)
                break
            if worker.poll() is not None:
                report['worker_exited_early'] = worker.returncode
                break
            time.sleep(3)
        report['timeline'], report['status'] = timeline, final
        report['stop_reason'] = sql(f"select coalesce(stop_reason, 'none') from app_private.run_usage where run_id = '{run_id}';")
        report['verification'] = sql(f"select passed::text || ' ' || unmet::text from app_private.run_verifications where run_id = '{run_id}' order by created_at desc limit 1;")
        report['published'] = sql(f"select coalesce(string_agg(name || ' ' || sha256 || ' ' || size_bytes, ', '), 'none') from public.artifacts where run_id = '{run_id}' and status = 'published';")
        report['calls'] = sql(f"select count(*) from app_private.model_invocations where root_run_id = '{run_id}';")
        report['route'] = sql(f"select coalesce(string_agg(distinct profile || ' ' || wire_id, ', '), 'none') from app_private.model_invocations where root_run_id = '{run_id}';")
        spent = sql(f"select coalesce(sum(coalesce(charged_micro_usd, reserved_micro_usd)), 0) from app_private.model_invocations where root_run_id = '{run_id}';")
        unsettled = sql(f"select count(*) from app_private.model_invocations where root_run_id = '{run_id}' and charged_micro_usd is null;")
        report['committed_micro_usd'] = int(spent or 0)
        report['calls_without_a_reported_charge'] = int(unsettled or 0)
        charged = int(spent) if spent else None
    finally:
        if worker is not None and worker.poll() is None:
            worker.send_signal(signal.SIGTERM)
            try:
                report['worker_exit'] = worker.wait(60)
            except subprocess.TimeoutExpired:
                worker.kill()
                report['worker_exit'] = 'killed after 60 seconds'
        # With no run admitted nothing was sent. With a run and no total, the whole budget stays held.
        if run_id:
            ledger.settle(entry, charged, 'settled' if charged is not None else 'uncertain')  # type: ignore[attr-defined]
        else:
            ledger.settle(entry, 0, 'not_started')  # type: ignore[attr-defined]
        report['shared_ledger_committed_micro_usd'] = ledger.committed()  # type: ignore[attr-defined]
        report['workers_claiming_inference_afterward'] = sql("select count(*) from app_private.worker_heartbeats where claims_inference and state <> 'stopped' and beat_at > now() - interval '60 seconds';")
    time.sleep(60)  # OpenRouter's figure can lag, so this checks the ledger and doesn't replace it.
    report['key_usage_after_usd'] = float(helper('usage', str(key_file)))
    durable, logged = helper('leaks', str(key_file), str(record.directory / 'logs')).split()
    report['key_found'] = {'durable_rows': int(durable), 'log_files': int(logged)}
    out = record.directory / 'reports' / f'goal-{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")}.json'
    private_write(out, json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    return 0 if report.get('status') == 'succeeded' else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install-dir', type=Path, default=DEFAULT_DIR)
    commands = parser.add_subparsers(dest='command', required=True)
    init = commands.add_parser('init', help='choose the identity, ports and files, and touch no database')
    init.add_argument('--project', required=True)
    for name, default in (('gateway', 55321), ('db', 55322), ('api', 8001), ('web', 3000)):
        init.add_argument(f'--{name}-port', type=int, default=default)
    for name in ('up', 'setup', 'status', 'reset'):
        commands.add_parser(name).add_argument('--project', required=True)
    apply = commands.add_parser('apply', help='apply pending migrations, only to the identified install')
    apply.add_argument('--project', required=True)
    apply.add_argument('--restored-copy', action='store_true', help='the target is a restored, held copy of this install')
    apply.add_argument('--reset', action='store_true', help='always refused')
    paid = commands.add_parser('goal', help='one real goal, under the shared cap. It spends money')
    paid.add_argument('--project', required=True)
    paid.add_argument('--paid', action='store_true')
    paid.add_argument('--key-file', type=Path, default=Path('.env'))
    paid.add_argument('--limit-micro-usd', type=int, required=True)
    paid.add_argument('--ledger', type=Path, default=Path('.checks/decision-0009/ledger.json'))
    arguments = parser.parse_args(argv)
    root = project_root()
    try:
        if arguments.command == 'init':
            record = write_install(arguments.install_dir, arguments.project, arguments.gateway_port, arguments.db_port, arguments.api_port, arguments.web_port, root)
            print(json.dumps({'status': 'recorded', 'project': record.project, 'directory': str(record.directory)}))
            return 0
        if arguments.command == 'reset' or getattr(arguments, 'reset', False):
            raise Refused('this install is never reset. Nothing was changed')
        record = read_record(arguments.install_dir)
        if arguments.command == 'up':
            if arguments.project != record.project:
                raise Refused(f'{arguments.project} is not the recorded install, {record.project}')
            stack = install_stack(root, record)
            require_rendered_install(stack, root)
            started = stack.compose('up', '-d', '--wait', '--wait-timeout', '240', timeout=300)
            if started.returncode:
                raise Unavailable(f'the stack did not start: {started.stderr[-300:]}')
            print(json.dumps({'status': 'started', 'project': record.project}))
            return 0
        if arguments.command == 'setup':
            first_setup(install_stack(root, record), root, record, arguments.project)
            print(json.dumps({'status': 'set_up', 'project': record.project}))
            return 0
        if arguments.command == 'status':
            print(json.dumps(status(root, record), indent=2))
            return 0
        if arguments.command == 'apply':
            target: AppStack = restored_copy_stack(root, record, arguments.project) if arguments.restored_copy else install_stack(root, record)
            print(json.dumps(guarded_apply(target, root, record, arguments.project, restored_copy=arguments.restored_copy)))
            return 0
        if not arguments.paid:
            raise Refused('this makes billed calls, and needs --paid')
        from live_goal import GOAL, REQUIRED  # noqa: PLC0415
        return goal(root, record, arguments.project, (root / arguments.key_file).resolve(), arguments.limit_micro_usd, root / arguments.ledger, GOAL, REQUIRED)
    except Refused as refusal:
        print(f'REFUSED before any change: {refusal}', file=sys.stderr)
        return 1
    except Unavailable as problem:
        print(f'ERROR: {problem}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
