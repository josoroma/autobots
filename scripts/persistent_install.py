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
import hashlib
import json
import os
import secrets
import subprocess
import sys
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app_db import (
    BOOTSTRAP_ROW,
    MIGRATION_NAME,
    MIGRATIONS,
    ROLES,
    SEEDS,
    AppStack,
    bootstrap_plan,
    run_bootstrap,
)
from app_db import (
    STORAGE_SQL as STORAGE_SQL,  # scripts/qualify_persistent_apply.py reads it from here
)
from disposable_db import (
    PROJECT_PREFIX,
    Refused,
    Target,
    Unavailable,
    jwt,
    run,
    tool_env,
)
from harness_lib import parse_dotenv, project_root
from paid_run import (
    ACTIVE,
    OTHER_WORK,
    TERMINAL,
    Database,
    Ledger,
    LedgerEntry,
    PaidSession,
    goal_exit_code,
    http_json,
    logged_spawn,
    note_failed,
    refuse_other_work,
    reserve,
    settle,
)
from supabase_stack import (
    UPSTREAM,
    example_defaults,
    generated_values,
    listener_addresses,
    port_conflict,
    rendered_refusals,
)

DEFAULT_DIR = Path.home() / '.local/share/autobots-install'
PERSISTENT_FILES = (UPSTREAM / 'docker-compose.yml', Path('infra/supabase/compose.overlay.yaml'))
INSTALL_HISTORY = 'autobots_install.migrations'
PYTHON = Path('services/agent/.venv/bin/python')
OWNER_EMAIL = 'owner@autobots.invalid'
TEN_YEARS = 86400 * 3650
GOAL_SECONDS = 1000
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
    """An install env file's values, verbatim, quotes included, as the install has always read them
    (harness_lib.parse_dotenv, which names the open question about quoting)."""
    return parse_dotenv(path.read_text(), 'verbatim')


def read_record(directory: Path) -> Record:
    path = directory / 'install.json'
    if not path.is_file():
        raise Refused(f'no install is recorded at {directory}')
    data = json.loads(path.read_text())
    return Record(data['project'], data['install_id'], data['gateway_port'], data['db_port'], data['api_port'], data['web_port'], directory)


@dataclass
class InstallStack(AppStack):
    """The vendored release and overlay, without the disposable marking."""

    def compose(self, *arguments: str, timeout: float = 300.0, stdin: str | None = None,
                extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        files = [item for path in PERSISTENT_FILES for item in ('-f', str(self.root / path))]
        return run(['docker', 'compose', '-p', self.target.project, '--project-directory', str(self.root / UPSTREAM), *files, *arguments],
                   {**self.env(), **(extra_env or {})}, timeout, stdin)

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
    if not restored_copy and facts['port'].split() != [f'127.0.0.1:{record.db_port}']:
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
              'created_at': datetime.now(UTC).isoformat()}
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
    if facts['port'].split() != [f'127.0.0.1:{record.db_port}']:
        raise Refused(f"{requested} publishes its database at {facts['port']}, not the recorded 127.0.0.1:{record.db_port}")
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
    """Pending migrations in name order, each with its history row in one transaction, as the migration role,
    then the seed, then the pending bootstrap files as the superuser, each with its own history row (R-56,
    SQLI-07): storage.sql first, then the ordered files, by the rules app_db.bootstrap_plan keeps."""
    require_install(stack, record, requested, expected_class, restored_copy)
    folder = directory or root / MIGRATIONS
    listing = stack.migrator(f'select name, sha256 from {INSTALL_HISTORY};')
    if listing.returncode:
        raise Unavailable('the migration history is unreadable')
    recorded = dict(line.split('|') for line in listing.stdout.splitlines() if line)
    files = sorted(folder.glob('*.sql'))
    # All of it is checked first, so a refusal leaves the database exactly as it was.
    missing = sorted(name for name in set(recorded) - {path.name for path in files} if not name.startswith(BOOTSTRAP_ROW))
    if missing:
        raise Refused(f'{missing[0]} was applied and is not in this checkout, so this is an older revision')
    for path in files:
        if not MIGRATION_NAME.fullmatch(path.name):
            raise Refused(f'{path.name} is not named <14 digit timestamp>_<description>.sql')
        if path.name in recorded and recorded[path.name] != hashlib.sha256(path.read_bytes()).hexdigest():
            raise Refused(f'{path.name} changed after it was applied; never edit an applied migration')
    bootstrap_pending, refusal = bootstrap_plan(root, recorded)
    if refusal:
        raise Refused(refusal)
    applied: list[str] = []
    for path in files:
        if path.name in recorded:
            continue
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        result = stack.migrator(f"begin;\n{path.read_text()}\ninsert into {INSTALL_HISTORY} (name, sha256) values ('{path.name}', '{checksum}');\ncommit;\n")
        if result.returncode:
            raise Unavailable(f'{path.name} failed and was rolled back: {result.stderr.strip()[-200:]}')
        applied.append(path.name)
    seeded = stack.migrator(f'begin;\n{(root / SEEDS).read_text()}\ncommit;\n')
    if seeded.returncode:
        raise Unavailable(f'the reference seed failed: {seeded.stderr.strip()[-200:]}')
    bootstrapped, problem = run_bootstrap(stack, bootstrap_pending, INSTALL_HISTORY)
    if problem:
        raise Unavailable(problem)
    return {'status': 'applied', 'project': requested, 'applied': applied, 'bootstrap_applied': bootstrapped,
            'already_applied': len([name for name in recorded if not name.startswith(BOOTSTRAP_ROW)])}


def release_images(root: Path) -> list[str]:
    """Each image the install's merged release and overlay name, so a service upstream adds without an overlay pin is
    pulled too (SQLI-11). Rendered with placeholder values, so no install is needed or read, and never printed."""
    values = {**example_defaults(root), **generated_values(55321, 55322)}
    stack = InstallStack(Target('autobots-images', 55322, 55321), root, root / UPSTREAM / 'docker-compose.yml', values=values)
    rendered = stack.compose('config', '--format', 'json', timeout=60)
    if rendered.returncode:
        raise Unavailable('Compose could not render the release and overlay')
    return sorted({str(service['image']) for service in json.loads(rendered.stdout)['services'].values()})


def pull_images(root: Path) -> int:
    """`make images`: the only pulls, and only when asked, since every service is pinned with pull_policy never.
    Stops at the first image that can't be pulled."""
    for image in release_images(root):
        print(f'pulling {image}', flush=True)
        if subprocess.run(['docker', 'pull', image], env=tool_env(), check=False).returncode:
            return 1
    return 0


def status(root: Path, record: Record) -> dict:
    """What is actually listening, for comparing with the recorded bindings."""
    bindings = {name: listener_addresses(port) for name, port in (('gateway', record.gateway_port), ('database', record.db_port), ('api', record.api_port), ('web', record.web_port))}
    return {'project': record.project, 'recorded': {'gateway': record.gateway_port, 'database': record.db_port, 'api': record.api_port, 'web': record.web_port},
            'listeners': bindings, 'identity_refusals': identity_refusals(install_stack(root, record), record, record.project)}


def reserve_goal(ledger_path: Path, limit: int) -> tuple[Ledger, LedgerEntry]:
    """Before any request: the goal's whole budget has to fit what's left of the shared cap."""
    return reserve(project_root(), ledger_path, f'install-goal:{datetime.now(UTC).isoformat()}', limit)


def install_session(root: Path, record: Record, stack: Database, application: Mapping[str, str], log_name: str) -> PaidSession:
    """The install's paid session (scripts/paid_run.py): its application values for the helper and the
    worker, which logs to `log_name` in the install's private logs."""
    env = {**tool_env(), **application, 'PYTHONPATH': str(root / 'services/agent/src'), 'PYTHONDONTWRITEBYTECODE': '1'}
    return PaidSession(root, stack, env, logged_spawn(root, env, record.directory / 'logs' / log_name))


def owner_workspace(session: PaidSession) -> str:
    workspace = session.sql("select workspace_id from public.workspace_members where role = 'owner' limit 1;")
    if workspace is None:
        raise Unavailable("could not read the owner's workspace, so nothing was sent")
    return workspace


def save_key_unless_active(session: PaidSession, key_file: Path, workspace: str) -> None:
    active = f"select count(*) from app_private.provider_credentials where workspace_id = '{workspace}' and provider = 'openrouter' and status = 'active';"
    if session.sql(active) == '0':
        session.helper('save', str(key_file), workspace)


def spend_clock(session: PaidSession) -> str:
    started_at = session.sql('select clock_timestamp();')
    if started_at is None:
        # Every spend check filters on this, so without it the watchdog could never fire.
        raise Unavailable('could not read the database clock, so nothing was sent')
    return started_at


def spent_since(started_at: str) -> str:
    """Everything committed on the install since `started_at`, whichever run spent it."""
    return f"select coalesce(sum(coalesce(charged_micro_usd, reserved_micro_usd)), 0) from app_private.model_invocations where created_at >= '{started_at}';"


def record_unsettled(session: PaidSession, started_at: str, report: dict) -> None:
    unsettled = session.sql(f"select count(*) from app_private.model_invocations where created_at >= '{started_at}' and charged_micro_usd is null;")
    if unsettled is None:
        note_failed(report, 'the unsettled count could not be read')
    else:
        report['calls_without_a_reported_charge'] = int(unsettled)


def write_report(record: Record, kind: str, report: Mapping) -> None:
    out = record.directory / 'reports' / f'{kind}-{datetime.now(UTC).strftime("%Y%m%dT%H%M%S")}.json'
    private_write(out, json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


def goal(root: Path, record: Record, requested: str, key_file: Path, limit: int, ledger_path: Path, goal_text: str, required: list[dict]) -> int:
    """Reserve, admit through the install's API, run a worker with the switch on for this goal only, settle."""
    ledger, entry = reserve_goal(ledger_path, limit)
    stack = install_stack(root, record)
    try:
        require_install(stack, record, requested)
    except Refused:
        ledger.settle(entry, 0, 'not_started')
        raise
    application = read_values(record.app_env)
    owner = read_values(record.directory / 'owner.env')
    session = install_session(root, record, stack, application, 'worker-goal.log')
    report: dict = {'schema_version': 'autobots.install-goal/v1', 'started_at_utc': datetime.now(UTC).isoformat(), 'project': record.project, 'model_transport': 'live OpenRouter',
                    'limit_micro_usd': limit, 'goal': goal_text, 'required_artifacts': required, 'not_established': ['H1', 'product acceptance', 'task quality beyond this goal']}
    charged: int | None = None
    run_id = ''
    final = ''
    try:
        refuse_other_work(session.sql(OTHER_WORK))
        report['key_usage_before_usd'] = float(session.helper('usage', str(key_file)))
        token = session.sign_in(application['AUTOBOTS_SUPABASE_URL'], application['AUTOBOTS_SUPABASE_ANON_KEY'], owner['OWNER_EMAIL'], owner['OWNER_PASSWORD'])
        workspace = owner_workspace(session)
        save_key_unless_active(session, key_file, workspace)
        started_at = spend_clock(session)
        spend = spent_since(started_at)
        headers = {'X-Autobots-Internal': application['AUTOBOTS_INTERNAL_TOKEN'], 'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        api = f'http://127.0.0.1:{record.api_port}'
        code, reply = http_json('POST', f'{api}/v1/runs', {**headers, 'Idempotency-Key': secrets.token_hex(8)}, {'goal_text': goal_text, 'limit_micro_usd': limit, 'required_artifacts': required})
        report['admission'] = code
        if code != 202:
            raise Unavailable(f'the API refused the goal: {code} {reply[:200]}')
        run_id = json.loads(reply)['run_id']
        report['run_id'] = run_id
        status = f"select status from public.runs where id = '{run_id}';"
        session.start_worker()
        watched = session.watch(lambda: {'status': session.sql(status) or ''}, lambda current: bool(current['status']) and current['status'] not in ACTIVE,
                                limit, spend, GOAL_SECONDS)
        # Recorded first, so a read below that raises can't lose why the watch ended.
        watched.record(report)
        # Stopped before anything is read, since it can still dispatch while it drains.
        session.stop_worker(report)
        final = session.sql(status) or ''
        report['status'] = final
        report['stop_reason'] = session.sql(f"select coalesce(stop_reason, 'none') from app_private.run_usage where run_id = '{run_id}';")
        report['verification'] = session.sql(f"select passed::text || ' ' || unmet::text from app_private.run_verifications where run_id = '{run_id}' order by created_at desc limit 1;")
        report['published'] = session.sql(f"select coalesce(string_agg(name || ' ' || sha256 || ' ' || size_bytes, ', '), 'none') from public.artifacts where run_id = '{run_id}' and status = 'published';")
        report['calls'] = session.sql(f"select count(*) from app_private.model_invocations where created_at >= '{started_at}';")
        report['route'] = session.sql(f"select coalesce(string_agg(distinct profile || ' ' || wire_id, ', '), 'none') from app_private.model_invocations where root_run_id = '{run_id}';")
        charged = session.spend_after(watched, spend, report)
        record_unsettled(session, started_at, report)
    finally:
        session.stop_worker(report)
        # A run that isn't finished can spend again on resume, so its whole budget stays held.
        settle(ledger, entry, bool(run_id), {'goal': final}, charged, report)
        try:
            report['workers_claiming_inference_afterward'] = session.sql("select count(*) from app_private.worker_heartbeats where claims_inference and state <> 'stopped' and beat_at > now() - interval '60 seconds';")
        except (Unavailable, subprocess.SubprocessError, OSError) as problem:
            note_failed(report, type(problem).__name__)
        write_report_needed = bool(run_id)
        # A failure on the way out still leaves what was seen and spent.
        failure = sys.exc_info()[0]
        if write_report_needed and failure is not None:
            report['failed_with'] = failure.__name__
            absent = [name for name in ('status', 'timeline', 'committed_micro_usd', 'calls') if report.get(name) in (None, '', [])]
            report['not_checked'] = ['key usage after the run', 'the key in stored rows or logs', *absent]
            try:
                write_report(record, 'goal', report)
            except OSError as problem:
                print(f'the report could not be written: {type(problem).__name__}', file=sys.stderr)
    if write_report_needed:
        session.after_run_checks(key_file, record.directory / 'logs', report)
    write_report(record, 'goal', report)
    return goal_exit_code(report, achieved=report.get('status') == 'succeeded')


# Decision 0023 E6: what the owner asked to see in their app, all of it real. Spend, in micro-USD.
EXAMPLES_LIMIT = 450_000
EXAMPLE_RUNS = (
    {'goal_text': 'Work out what US$1,000 grows to at 6% a year, compounded yearly, after 1, 5 and 10 years. '
                  'Save a short markdown table of the three figures as growth.md.',
     'limit_micro_usd': 100_000},
    {'goal_text': 'In under 150 words, explain why keeping an AI agent\'s run records on your own Mac matters. '
                  'Save it as brief.md.',
     'limit_micro_usd': 100_000, 'run_profile': 'openrouter_sol', 'expert': 'Brief writer'},
)
# Each listed vendor becomes the research step's whole goal, so it says what to find and to save it.
EXAMPLE_WORKFLOW = ('Vendor due diligence', {'in': [
    'Supabase, as the database and auth vendor for a small local-first app: summarise its pricing model, security '
    'posture and lock-in risk in under 200 words, save that as supabase.md with save_artifact, and complete your task citing it.']},
    250_000)
Sql = Callable[[str], str | None]


def grant_publish(sql: Sql, api: str, headers: Mapping[str, str], workspace: str, names: tuple[str, ...]) -> list[str]:
    """Decision 0023 E7: a seeded Expert that saves but can't publish gets one new version with
    `publish_artifact` added, through the API. Nothing is removed, and earlier versions stay."""
    granted = []
    for name in names:
        row = sql(f"select e.id || ' ' || e.latest_version || ' ' || v.config::text from public.experts e join public.expert_versions v "
                  f"on v.expert_id = e.id and v.version = e.latest_version where e.workspace_id = '{workspace}' and e.name = '{name}';")
        if not row:
            continue
        expert, version, config = row.split(' ', 2)
        current = json.loads(config)
        if 'publish_artifact' in current.get('tools', []) or 'save_artifact' not in current.get('tools', []):
            continue
        current['tools'] = [*current['tools'], 'publish_artifact']
        body = {'expected_version': int(version), 'config': {key: current[key] for key in ('purpose', 'instructions', 'tools', 'tool_groups', 'skills', 'role_bindings') if key in current}}
        code, reply = http_json('POST', f'{api}/v1/experts/{expert}/versions', {**headers, 'Idempotency-Key': secrets.token_hex(8)}, body)
        if code != 201:
            raise Unavailable(f'{name} could not be given publish_artifact: {code} {reply[:200]}')
        granted.append(name)
    return granted


def cancel_unstarted(sql: Sql, api: str, headers: Mapping[str, str], workspace: str, goals: list[str]) -> int:
    """Cancels this command's own queued example runs that never made a model call, through the API."""
    cancelled = 0
    for goal_text in goals:
        quoted = goal_text.replace("'", "''")
        rows = sql(f"select coalesce(string_agg(r.id || ' ' || r.version, ','), '') from public.runs r where r.workspace_id = '{workspace}' "
                   f"and r.status = 'queued' and r.goal_text = '{quoted}' and not exists "
                   "(select 1 from app_private.model_invocations m where m.root_run_id = r.id);") or ''
        for row in filter(None, rows.split(',')):
            run, version = row.split(' ')
            code, _ = http_json('POST', f'{api}/v1/runs/{run}/cancel', {**headers, 'Idempotency-Key': secrets.token_hex(8)}, {'expected_version': int(version)})
            if code != 200:
                raise Unavailable(f'an earlier queued example run could not be cancelled: {code}')
            cancelled += 1
    return cancelled


def examples_done(current: Mapping[str, str]) -> bool:
    """Every goal run terminal, and the workflow terminal or stopped at its approval gate. This is the
    examples' outcome (Decision 0023 E6): what the system actually did, a failed run included, which a
    rerun repeats."""
    goals_done = all(status in TERMINAL for label, status in current.items() if label != 'workflow')
    return goals_done and current.get('workflow') in TERMINAL | {'waiting_approval'}


def examples(root: Path, record: Record, requested: str, key_file: Path, ledger_path: Path) -> int:
    """The concept seed, two goal runs and one workflow execution that stops at its approval gate, with
    one worker that has inference on for this command only. Everything is under one reservation."""
    ledger, entry = reserve_goal(ledger_path, EXAMPLES_LIMIT)
    stack = install_stack(root, record)
    try:
        require_install(stack, record, requested)
    except Refused:
        ledger.settle(entry, 0, 'not_started')
        raise
    application = read_values(record.app_env)
    owner = read_values(record.directory / 'owner.env')
    session = install_session(root, record, stack, application, 'worker-examples.log')
    sql = session.sql
    report: dict = {'schema_version': 'autobots.install-examples/v1', 'started_at_utc': datetime.now(UTC).isoformat(), 'project': record.project,
                    'model_transport': 'live OpenRouter', 'limit_micro_usd': EXAMPLES_LIMIT,
                    'not_established': ['H1', 'product acceptance', 'task quality']}
    goals = [spec['goal_text'] for spec in EXAMPLE_RUNS]
    api = f'http://127.0.0.1:{record.api_port}'
    headers: dict[str, str] = {}
    workspace = ''
    runs: dict[str, str] = {}
    finals: dict[str, str] = {}
    charged: int | None = None
    try:
        token = session.sign_in(application['AUTOBOTS_SUPABASE_URL'], application['AUTOBOTS_SUPABASE_ANON_KEY'], owner['OWNER_EMAIL'], owner['OWNER_PASSWORD'])
        workspace = owner_workspace(session)
        headers = {'X-Autobots-Internal': application['AUTOBOTS_INTERNAL_TOKEN'], 'Authorization': f'Bearer {token}', 'Content-Type': 'application/json',
                   'X-Autobots-Workspace': workspace}
        report['cancelled_from_an_earlier_attempt'] = cancel_unstarted(sql, api, headers, workspace, goals)
        refuse_other_work(sql(OTHER_WORK))
        report['key_usage_before_usd'] = float(session.helper('usage', str(key_file)))
        save_key_unless_active(session, key_file, workspace)
        seeded = subprocess.run([str(root / PYTHON), '-m', 'autobots.operations.concept_seed', '--workspace', workspace], env=session.env,
                                capture_output=True, text=True, errors='replace', timeout=120, check=False)
        if seeded.returncode:
            raise Unavailable(f'the concept seed failed: {seeded.stderr.strip()[-300:]}')
        report['seed'] = json.loads(seeded.stdout.strip().splitlines()[-1])
        report['experts_given_publish'] = grant_publish(sql, api, headers, workspace, ('Market watcher', 'Research analyst'))
        started_at = spend_clock(session)
        spend = spent_since(started_at)
        for index, spec in enumerate(EXAMPLE_RUNS):
            quoted = spec['goal_text'].replace("'", "''")
            if (sql(f"select count(*) from public.runs where workspace_id = '{workspace}' and goal_text = '{quoted}' and status = 'succeeded';") or '0') != '0':
                continue  # A rerun doesn't repeat an example that already succeeded.
            body = {key: value for key, value in spec.items() if key != 'expert'}
            if 'expert' in spec:
                # HM-02: an Expert runs through a direct session, as the composer starts one.
                expert = sql(f"select id from public.experts where workspace_id = '{workspace}' and name = '{spec['expert']}';")
                code, reply = http_json('POST', f'{api}/v1/sessions', {**headers, 'Idempotency-Key': secrets.token_hex(8)},
                                        {'kind': 'direct', 'experts': [{'expert_id': expert}]})
                if code not in (200, 201):
                    raise Unavailable(f'the API refused the session for example run {index + 1}: {code} {reply[:200]}')
                body['session_id'] = json.loads(reply)['id']
            code, reply = http_json('POST', f'{api}/v1/runs', {**headers, 'Idempotency-Key': secrets.token_hex(8)}, body)
            if code != 202:
                raise Unavailable(f'the API refused example run {index + 1}: {code} {reply[:200]}')
            runs[f'goal {index + 1}'] = json.loads(reply)['run_id']
        name, inputs, budget = EXAMPLE_WORKFLOW
        flow, version = (sql(f"select id || ' ' || latest_version from public.workflows where workspace_id = '{workspace}' and name = '{name}';") or ' ').split(' ')
        code, reply = http_json('POST', f'{api}/v1/workflows/{flow}/executions', {**headers, 'Idempotency-Key': secrets.token_hex(8)},
                                {'version': int(version or 0), 'inputs': inputs, 'budget_micro_usd': budget})
        if code != 201:
            raise Unavailable(f'the API refused the workflow execution: {code} {reply[:200]}')
        runs['workflow'] = json.loads(reply)['run_id']
        report['runs'] = runs

        def statuses() -> dict[str, str]:
            return {label: sql(f"select status from public.runs where id = '{run}';") or '' for label, run in runs.items()}

        session.start_worker()
        watched = session.watch(statuses, examples_done, EXAMPLES_LIMIT, spend, GOAL_SECONDS)
        watched.record(report)
        session.stop_worker(report)
        finals = statuses()
        report['status'] = finals
        report['artifacts'] = {label: sql(f"select coalesce(string_agg(name || ' ' || size_bytes, ', '), 'none') from public.artifacts where run_id = '{run}' and status = 'published';")
                               for label, run in runs.items()}
        report['routes'] = {label: sql(f"select coalesce(string_agg(distinct profile, ', '), 'none') from app_private.model_invocations where root_run_id = '{run}';")
                            for label, run in runs.items()}
        report['pending_approvals'] = sql(f"select count(*) from public.approval_requests where run_id = '{runs['workflow']}' and status = 'pending';")
        report['calls'] = sql(f"select count(*) from app_private.model_invocations where created_at >= '{started_at}';")
        charged = session.spend_after(watched, spend, report)
        record_unsettled(session, started_at, report)
    except Unavailable:
        if session.worker is None and runs:
            report['cancelled_after_failure'] = cancel_unstarted(sql, api, headers, workspace, goals)
            ids = ', '.join(f"'{run}'" for run in runs.values())
            if sql(f'select count(*) from app_private.model_invocations where root_run_id in ({ids});') == '0':
                runs.clear()  # No inference worker ran, so nothing was sent for them.
        raise
    finally:
        session.stop_worker(report)
        # A run that can still go on keeps the whole reservation held.
        settle(ledger, entry, bool(runs), finals, charged, report)
    if runs:
        session.after_run_checks(key_file, record.directory / 'logs', report)
    write_report(record, 'examples', report)
    return goal_exit_code(report, achieved=examples_done(finals))


def screens(root: Path, record: Record, requested: str, grep: str) -> int:
    """Decision 0023: read-only browser checks of the running install, signed in as its owner. The
    owner's values are read here and passed only to the browser process, never printed or logged."""
    stack = install_stack(root, record)
    require_install(stack, record, requested)
    sys.path.insert(0, str(root / 'scripts'))
    from qualify_web import BROWSERS
    from suites import INSTALL_CURRENT_PROJECT
    from toolchain import child_env, find_tools
    browsers = root / BROWSERS
    if not any(browsers.glob('chromium-*')):
        raise Unavailable(f'no browser under {BROWSERS}; install the pinned one deliberately')
    owner = read_values(record.directory / 'owner.env')
    out = root / '.checks/install-screens'
    out.mkdir(parents=True, exist_ok=True)
    report = out / 'playwright.json'
    report.unlink(missing_ok=True)
    env = {**child_env(root, find_tools(root), verifying=True), 'PLAYWRIGHT_BROWSERS_PATH': str(browsers),
           'AUTOBOTS_WEB_URL': f'http://127.0.0.1:{record.web_port}', 'AUTOBOTS_WEB_REPORT': str(report), 'AUTOBOTS_WEB_OUTPUT': str(out / 'results'),
           'AUTOBOTS_TEST_SCREENSHOTS': str(out), 'AUTOBOTS_TEST_OWNER_EMAIL': owner['OWNER_EMAIL'], 'AUTOBOTS_TEST_OWNER_PASSWORD': owner['OWNER_PASSWORD']}
    argv = [str(root / 'apps/web/node_modules/.bin/playwright'), 'test', '--project', INSTALL_CURRENT_PROJECT, '--config', 'playwright.config.ts']
    if grep:
        argv += ['-g', grep]
    done = subprocess.run(argv, env=env, cwd=root / 'apps/web', capture_output=True, text=True, errors='replace', timeout=600, check=False)
    passwords = (owner['OWNER_PASSWORD'],)
    output = done.stdout[-4000:]
    for value in passwords:
        output = output.replace(value, '[redacted]')
    print(output)
    return 0 if done.returncode == 0 else 1


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
    commands.add_parser('images', help="pull each image the release and overlay pin, for make images; reads no install")
    apply = commands.add_parser('apply', help='apply pending migrations, only to the identified install')
    apply.add_argument('--project', required=True)
    apply.add_argument('--restored-copy', action='store_true', help='the target is a restored, held copy of this install')
    apply.add_argument('--reset', action='store_true', help='always refused')
    shown_examples = commands.add_parser('examples', help='Decision 0023 E6: real examples in the owner workspace, under the shared cap. It spends money')
    shown_examples.add_argument('--project', required=True)
    shown_examples.add_argument('--paid', action='store_true')
    shown_examples.add_argument('--key-file', type=Path, default=Path('.env'))
    shown_examples.add_argument('--ledger', type=Path, default=Path('.checks/decision-0009/ledger.json'))
    shown = commands.add_parser('screens', help='read-only browser checks of the running install, as its owner')
    shown.add_argument('--project', required=True)
    shown.add_argument('--grep', default='')
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
        if arguments.command == 'images':
            return pull_images(root)
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
        if arguments.command == 'screens':
            return screens(root, record, arguments.project, arguments.grep)
        if arguments.command == 'examples':
            if not arguments.paid:
                raise Refused('this makes billed calls, and needs --paid')
            return examples(root, record, arguments.project, (root / arguments.key_file).resolve(), root / arguments.ledger)
        if not arguments.paid:
            raise Refused('this makes billed calls, and needs --paid')
        from live_goal import GOAL, REQUIRED
        return goal(root, record, arguments.project, (root / arguments.key_file).resolve(), arguments.limit_micro_usd, root / arguments.ledger, GOAL, REQUIRED)
    except Refused as refusal:
        print(f'REFUSED before any change: {refusal}', file=sys.stderr)
        return 1
    except Unavailable as problem:
        print(f'ERROR: {problem}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
