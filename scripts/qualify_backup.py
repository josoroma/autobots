#!/usr/bin/env python3
"""Exercises the backup and restore runbook between two disposable Compose projects.

The source stands in for the persistent stack, which isn't configured on this machine. No model is called
and the credential is an arranged fake. Exit 0 passed, 1 a case failed, 2 a prerequisite is missing.

Each scenario is a function of one BackupRun, run in the order SCENARIOS states, since later ones use the
backup, the restored copy and the runs earlier ones leave (refactor plan R-65, SCRP-05).
"""
from __future__ import annotations

import hashlib
import json
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app_db import (
    BOOTSTRAP_ROW,
    MIGRATION_NAME,
    AppRun,
    AppStack,
    app_project,
    apply_bootstrap,
    bootstrap_files,
    start_app,
)
from disposable_db import PROJECT_PREFIX, Refused, Target, Unavailable, tool_env
from disposable_db import run as run_command
from harness_lib import project_root
from local_backup import restored_values
from qualification.children import CHECK_PYTHON as PYTHON
from qualification.children import last_json, launch, parse_report, run_child_check
from qualification.net import http
from qualification.ops import Ops, api_call, conditions, durable_counts, exited, wait
from qualification.owners import bootstrap_owner, password_token
from qualification.records import Cases
from qualification.report import finish
from qualification.scenarios import run_scenarios

REPORT = Path('.checks/backup/qualification.json')
# Where a failed child check's stderr is kept (qualification/children.py).
ERR_DIR = Path('.checks/backup')
FAKE_CREDENTIAL = 'sk-or-arranged-' + secrets.token_hex(24)
# The operations, backup and upgrade qualifiers' fixture workers run a scripted model (qualification/profiles.py).
MODEL_TRANSPORT = 'mock'
EMAIL_A, EMAIL_B = 'owner-a@example.invalid', 'owner-b@example.invalid'


def recorded_migrations(history: Sequence[str]) -> list[str]:
    """The migration rows of a manifest's history list. local_backup lists every row of the history table,
    and since R-56 that holds bootstrap rows; an install's history held bootstrap/storage.sql before
    that. Counting by the migration name pattern reads every one of those manifests the same way."""
    return [name for name in history if MIGRATION_NAME.fullmatch(name)]


def recorded_bootstrap(history: Sequence[str]) -> list[str]:
    return [name for name in history if name.startswith(BOOTSTRAP_ROW)]


def backup_tool(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(root / PYTHON), str(root / 'scripts/local_backup.py'), *arguments], env={**tool_env(), 'PYTHONDONTWRITEBYTECODE': '1'},
                          cwd=root, capture_output=True, text=True, errors='replace', timeout=500, check=False)


def env_text(stack: AppStack) -> str:
    return ''.join(f'{name}={value}\n' for name, value in stack.values.items())


@dataclass
class BackupRun:
    """What the scenarios share: the source stack and its processes, the backup's files and keys, the restored copy,
    and what a scenario leaves for a later one."""

    root: Path
    app: AppRun
    ops: Ops
    logs: Path
    work: Path
    api_port: int
    restored_project: str
    restored_gateway: int
    restored_db: int
    passwords: dict[str, str] = field(default_factory=lambda: {email: secrets.token_urlsafe(24) for email in (EMAIL_A, EMAIL_B)})
    applied: int = 0
    workspace_a: str = ''
    interrupted: str = ''
    pending: str = ''
    # The source's durable counts just before its backup, which nothing after it may change.
    counts: str = ''
    taken: subprocess.CompletedProcess[str] | None = None
    back: subprocess.CompletedProcess[str] | None = None
    manifest: dict[str, Any] = field(default_factory=dict)
    restored_stack: AppStack | None = None
    restored_ops: Ops | None = None
    token_a: str = ''

    @property
    def stack(self) -> AppStack:
        return self.app.stack

    @property
    def backup_dir(self) -> Path:
        return self.work / 'backups/first'

    @property
    def backup_key(self) -> Path:
        return self.work / 'backup-keys/backup.key'

    @property
    def key_dir(self) -> Path:
        return self.work / 'provider-keys'

    @property
    def master_key(self) -> Path:
        return self.work / 'live/secrets/master.key'

    @property
    def env_file(self) -> Path:
        return self.work / 'stack.env'

    @property
    def marker(self) -> Path:
        return self.work / 'in-call'

    @property
    def take(self) -> tuple[str, ...]:
        return ('backup', '--project', self.stack.target.project, '--env-file', str(self.env_file), '--out', str(self.backup_dir),
                '--backup-key', str(self.backup_key), '--key-dir', str(self.key_dir), '--master-key', str(self.master_key))

    def restored(self) -> tuple[AppStack, Ops]:
        if self.restored_stack is None or self.restored_ops is None:
            raise RuntimeError('the restore scenario made no restored copy')
        return self.restored_stack, self.restored_ops


def source_content(run: BackupRun, cases: Cases) -> None:
    """Real content, from the real loop: finished, interrupted and pending work, and a credential."""
    root, stack, ops, marker = run.root, run.stack, run.ops, run.marker
    run.applied = start_app(stack, root)
    _, problem = apply_bootstrap(stack, root)
    if problem:
        raise Unavailable(f'the bootstrap files failed: {problem}')
    owner_a = bootstrap_owner(root, run.app.base, stack.values['SERVICE_ROLE_KEY'], ops.url, EMAIL_A, run.passwords[EMAIL_A])
    bootstrap_owner(root, run.app.base, stack.values['SERVICE_ROLE_KEY'], ops.url, EMAIL_B, run.passwords[EMAIL_B])
    run.workspace_a = owner_a['workspace_id']
    finished_run = ops.admit(run.workspace_a)
    worker = ops.fixture_worker('finish-worker', 0, 30, marker)
    finished = wait(lambda: ops.sql(f"select status from public.runs where id = '{finished_run}';") == 'succeeded', 60)
    worker.send_signal(signal.SIGTERM)
    exited(worker, 30)
    marker.unlink(missing_ok=True)
    run.interrupted = ops.admit(run.workspace_a)
    worker = ops.fixture_worker('cut-worker', 6, 1, marker)
    wait(marker.exists, 40)
    worker.send_signal(signal.SIGTERM)
    exited(worker, 40)
    worker = ops.fixture_worker('classify-worker', 0, 30, marker, 'resume')
    paused = wait(lambda: ops.sql(f"select status from public.runs where id = '{run.interrupted}';") == 'paused', 40)
    worker.send_signal(signal.SIGTERM)
    exited(worker, 30)
    run.pending = ops.admit(run.workspace_a)
    run.master_key.parent.mkdir(parents=True, mode=0o700)
    seeded = launch([str(root / PYTHON), str(root / 'tests/db/restore_check.py'), 'seed', run.workspace_a, str(run.master_key), FAKE_CREDENTIAL], env=ops.env, timeout=60, label='the credential seed')
    cases.arrange('a fake credential sealed with the provider key', seeded)
    cases.check('the source holds real content (arranged credential)', 'finished, paused, queued, a sealed fake key', f'{finished}, {paused}, seed exit {seeded.returncode}', finished and paused and seeded.returncode == 0)
    run.env_file.write_text(env_text(stack) + f'AUTOBOTS_MIGRATOR_PASSWORD={stack.migrator_password}\nAUTOBOTS_RUNTIME_PASSWORD={stack.runtime_password}\n')
    run.env_file.chmod(0o600)
    made = backup_tool(root, 'keygen', '--out', str(run.backup_key))
    wrong = backup_tool(root, 'keygen', '--out', str(run.work / 'wrong.key'))
    cases.check('a backup key is generated, private', '0600', oct(run.backup_key.stat().st_mode & 0o777), made.returncode == 0 and wrong.returncode == 0 and run.backup_key.stat().st_mode & 0o777 == 0o600)


def refused_backups(run: BackupRun, cases: Cases) -> None:
    """Refused while anything can still write, and nothing stops."""
    root, ops, backup_dir = run.root, run.ops, run.backup_dir
    worker = ops.spawn('live-worker', [str(root / PYTHON), '-m', 'autobots.operations.worker'])
    wait(lambda: ops.sql("select count(*) from app_private.worker_heartbeats where state = 'running';") == '1', 20)
    refused = backup_tool(root, *run.take)
    still = ops.sql('select 1;')
    cases.check('a live worker refuses the backup, and nothing stops', 'exit 1, database up, no backup', f'{refused.returncode}, {still}, {backup_dir.exists()}', refused.returncode == 1 and still == '1' and not backup_dir.exists())
    worker.send_signal(signal.SIGTERM)
    exited(worker, 20)
    inside = backup_tool(root, 'backup', '--project', run.stack.target.project, '--env-file', str(run.env_file), '--out', str(backup_dir), '--backup-key', str(run.backup_key), '--key-dir', str(backup_dir / 'keys'), '--master-key', str(run.master_key))
    cases.check('a key directory inside the backup is refused', 'exit 1', inside.returncode, inside.returncode == 1 and not backup_dir.exists())


def backup_taken(run: BackupRun, cases: Cases) -> None:
    root, ops, stack, backup_dir = run.root, run.ops, run.stack, run.backup_dir
    run.counts = counts = durable_counts(ops)
    run.taken = taken = backup_tool(root, *run.take)
    if taken.returncode:
        raise Unavailable(f'the backup failed: {taken.stderr[-400:]}')
    run.manifest = manifest = json.loads((backup_dir / 'manifest.json').read_text())
    source_after = wait(lambda: ops.sql('select 1;') == '1', 60)
    cases.check('the source is back after its backup, with the same records', counts, f'{source_after}, {durable_counts(ops)}', source_after and durable_counts(ops) == counts)
    expected_components = {'configuration', 'volume:db-data', 'volume:storage-data'}
    names = set(manifest['components'])
    cases.check('the manifest is versioned and names every component', 'autobots.backup/v1 with database, Storage and configuration', f"{manifest['schema_version']}, {sorted(names)}", manifest['schema_version'] == 'autobots.backup/v1' and expected_components <= names)
    history = manifest['facts']['migrations']
    # The manifest lists history rows by name, and the files are in apply order, so they're compared as sets.
    bootstrapped = [BOOTSTRAP_ROW + path.name for path in bootstrap_files(root)]
    cases.check('the manifest binds versions, migrations, bootstrap files and artifact hashes', 'images, compose hashes, migrations, bootstrap rows, hashes',
                f"{len(manifest['images'])} images, {len(manifest['compose_files'])} files, {len(recorded_migrations(history))} migrations, "
                f"{recorded_bootstrap(history)}, {len(manifest['facts']['artifacts'])} artifacts",
                manifest['images'] and manifest['compose_files'] and len(recorded_migrations(history)) == run.applied
                and sorted(recorded_bootstrap(history)) == sorted(bootstrapped) and manifest['facts']['artifacts'])
    modes = {path.name: oct(path.stat().st_mode & 0o777) for path in backup_dir.iterdir()}
    cases.check('backup files are private', 'all 0600 in 0700', f'{oct(backup_dir.stat().st_mode & 0o777)}, {sorted(set(modes.values()))}', backup_dir.stat().st_mode & 0o777 == 0o700 and set(modes.values()) == {'0o600'})
    kept_key = run.key_dir / 'provider-master.key'
    same = kept_key.read_bytes() == run.master_key.read_bytes()
    cases.check('the provider key is kept apart from the backup', 'outside the directory, 0600, same bytes', f'{oct(kept_key.stat().st_mode & 0o777)}, {same}, inside {kept_key.is_relative_to(backup_dir)}', same and kept_key.stat().st_mode & 0o777 == 0o600 and not kept_key.is_relative_to(backup_dir))
    haystack = b''.join(path.read_bytes() for path in backup_dir.iterdir())
    found = [name for name, value in (('jwt secret', stack.values['JWT_SECRET']), ('postgres password', stack.values['POSTGRES_PASSWORD']), ('runtime password', stack.runtime_password),
                                      ('service key', stack.values['SERVICE_ROLE_KEY']), ('fake credential', FAKE_CREDENTIAL), ('owner email', EMAIL_A), ('master key', run.master_key.read_bytes().hex())) if value.encode() in haystack]
    plain_markers = [marker_ for marker_ in (b'PG_VERSION', b'postgresql.conf') if marker_ in haystack]
    cases.check('nothing in the backup reads in the clear', 'no secret, no database file names', f'{found or "none"}, {plain_markers or "none"}', not found and not plain_markers)


def refused_restores(run: BackupRun, cases: Cases) -> None:
    """A damaged or foreign backup stops before Docker is touched."""
    root, project, backup_dir = run.root, run.stack.target.project, run.backup_dir

    def refused_restore(directory: Path, key: Path, name: str, label: str, marker_text: str = '') -> None:
        result = backup_tool(root, 'restore', '--backup', str(directory), '--backup-key', str(key), '--project', name, '--gateway-port', str(run.restored_gateway), '--db-port', str(run.restored_db))
        created = run_command(['docker', 'volume', 'ls', '--filter', f'label=com.docker.compose.project={name}', '--format', '{{.Name}}'], tool_env()).stdout.split() if name != project else []
        detail = result.stderr.strip()[-80:]
        cases.check(label, 'exit 1, nothing created', f'{result.returncode}, {len(created)} volumes, {detail}', result.returncode == 1 and not created and marker_text in result.stderr)

    refused_restore(backup_dir, run.backup_key, project, 'a restore onto its own source is refused', 'source')
    refused_restore(backup_dir, run.backup_key, 'autobots-real', 'a restore outside the disposable namespace is refused')
    refused_restore(backup_dir, run.work / 'wrong.key', run.restored_project, 'the wrong backup key is refused')
    flipped = run.work / 'flipped'
    shutil.copytree(backup_dir, flipped)
    victim = flipped / run.manifest['components']['volume:db-data']['file']
    data = bytearray(victim.read_bytes())
    data[len(data) // 2] ^= 1
    victim.write_bytes(bytes(data))
    refused_restore(flipped, run.backup_key, run.restored_project, 'a changed component is refused')
    edited = run.work / 'edited'
    shutil.copytree(backup_dir, edited)
    (edited / 'manifest.json').write_text((edited / 'manifest.json').read_text().replace('"schema_version"', '"schema_version" ', 1))
    refused_restore(edited, run.backup_key, run.restored_project, 'a changed manifest is refused')


def restore(run: BackupRun, cases: Cases) -> None:
    """The real restore, to its own project, ports and volumes."""
    root, stack, backup_dir, restored_project = run.root, run.stack, run.backup_dir, run.restored_project
    run.back = back = backup_tool(root, 'restore', '--backup', str(backup_dir), '--backup-key', str(run.backup_key), '--project', restored_project, '--gateway-port', str(run.restored_gateway), '--db-port', str(run.restored_db))
    if back.returncode:
        raise Unavailable(f'the restore failed: {back.stderr[-500:]}')
    # Owned as soon as it exists, so a later failure still removes the copy.
    restored_stack = AppStack(Target(restored_project, run.restored_db, run.restored_gateway), root, root / 'infra/supabase/upstream/docker-compose.yml',
                              values=restored_values(stack.values, run.restored_gateway, run.restored_db))
    restored_stack.migrator_password, restored_stack.runtime_password = stack.migrator_password, stack.runtime_password
    run.restored_stack = restored_stack
    run.app.project.own(restored_stack)
    result = last_json(back.stdout)
    if result is None:
        raise Unavailable(f'the restore printed no result: {back.stdout.strip()[-200:]}')
    held_at = run_command(['docker', 'exec', f"{restored_project}-db-1", 'psql', '-U', 'supabase_admin', '-d', 'postgres', '-X', '-A', '-t', '-c', "select to_char(created_at at time zone 'utc', 'YYYY-MM-DD\"T\"HH24:MI:SS.US') from app_private.installation_holds;"], tool_env()).stdout.strip()
    rest_started = run_command(['docker', 'inspect', '-f', '{{.State.StartedAt}}', f'{restored_project}-rest-1'], tool_env()).stdout.strip()[:26]
    cases.check('the hold is written before other services start', 'hold earlier than the REST service', f'{held_at}, {rest_started}', bool(held_at) and bool(rest_started) and held_at < rest_started)
    verified = backup_tool(root, 'verify', '--backup', str(backup_dir), '--backup-key', str(run.backup_key), '--key-dir', str(run.key_dir), '--project', restored_project)
    printed = parse_report(verified.stdout)
    facts = printed[0]['cases'] if printed is not None else []
    failed = [fact['id'] for fact in facts if not fact['passed']]
    cases.check("the operator's own verify command passes on the restore", 'exit 0, all facts match', f"exit {verified.returncode}, {len(facts)} facts, failed {failed or 'none'}", verified.returncode == 0 and facts and not failed)
    records = [json.loads(line) for line in (backup_dir / 'restores.jsonl').read_text().splitlines()]
    last = records[-1] if records else {}
    cases.check('each restore and its verification are recorded where Operations reads them', 'not_verified, then passed, with counts and no instance name',
                f"{[item['result'] for item in records]}, {last.get('checks_passed')} of {last.get('checks_total')}",
                [item['result'] for item in records] == ['not_verified', 'passed'] and last['checks_passed'] == last['checks_total'] > 0 and restored_project not in (backup_dir / 'restores.jsonl').read_text())
    other_keys = run.work / 'other-provider-keys'
    other_keys.mkdir(mode=0o700)
    (other_keys / 'provider-master.key').write_bytes(secrets.token_bytes(32))
    mismatch = backup_tool(root, 'verify', '--backup', str(backup_dir), '--backup-key', str(run.backup_key), '--key-dir', str(other_keys), '--project', restored_project)
    cases.check('and it fails on the wrong provider key', 'exit 1', mismatch.returncode, mismatch.returncode == 1)
    failed_record = json.loads((backup_dir / 'restores.jsonl').read_text().splitlines()[-1])
    cases.check('a failed verification is recorded as failed', 'failed', failed_record['result'], failed_record['result'] == 'failed')
    source_volumes = run_command(['docker', 'volume', 'ls', '--filter', f'label=com.docker.compose.project={stack.target.project}', '--format', '{{.Name}}'], tool_env()).stdout.split()
    shared = set(source_volumes) & set(result['volumes'])
    gateway_port, db_port = run.app.gateway_port, run.app.db_port
    cases.check('the restore has its own ports and volumes', 'different ports, no shared volume', f"{result['gateway_port']}/{result['db_port']} vs {gateway_port}/{db_port}, {len(shared)} shared", result['gateway_port'] != gateway_port and result['db_port'] != db_port and not shared)
    restored_base = f'http://127.0.0.1:{run.restored_gateway}'
    run.restored_ops = restored_ops = Ops(root, restored_stack, restored_base, run.restored_db, run.logs)
    anon = stack.values['ANON_KEY']
    status_a, run.token_a = password_token(restored_base, anon, EMAIL_A, run.passwords[EMAIL_A])
    status_b, token_b = password_token(restored_base, anon, EMAIL_B, run.passwords[EMAIL_B])
    wrong_login, _ = password_token(restored_base, anon, EMAIL_A, 'not-the-password')
    cases.check('owners sign in on the restore with their own passwords', '200, 200, and a wrong password refused', f'{status_a}, {status_b}, {wrong_login}', status_a == 200 and status_b == 200 and wrong_login in (400, 401))

    def rest(token: str) -> list[Any]:
        code, body = http('GET', f'{restored_base}/rest/v1/runs?select=id,workspace_id', {'apikey': anon, 'Authorization': f'Bearer {token}'}, None)
        rows: list[Any] = json.loads(body) if code == 200 else [{'status': code}]
        return rows

    own, other = rest(run.token_a), rest(token_b)
    cases.check('workspace isolation holds on the restore', 'A sees its runs, B none of them', f'{len(own)}, {len(other)}', len(own) >= 3 and not [row for row in other if row.get('workspace_id') == run.workspace_a])
    restored_ops.env.update({'AUTOBOTS_DATABASE_URL': restored_ops.url})
    expected_sha = hashlib.sha256(FAKE_CREDENTIAL.encode()).hexdigest()
    wrong_provider = run.work / 'wrong-provider.key'
    wrong_provider.write_bytes(secrets.token_bytes(len(run.master_key.read_bytes())))
    wrong_provider.chmod(0o600)
    run_child_check(cases, root, 'restore_check.py', 'verify', run.workspace_a, str(run.key_dir / 'provider-master.key'), str(backup_dir / 'manifest.json'), expected_sha, str(wrong_provider),
                    label='the restore check', env=restored_ops.env, timeout=240, err_dir=root / ERR_DIR, err_name='restore')


def held_restore(run: BackupRun, cases: Cases) -> None:
    """The product worker and API on the restore, still held."""
    root = run.root
    _, restored_ops = run.restored()
    states_before = restored_ops.sql("select string_agg(status || attempts, ',' order by run_id) from app_private.run_jobs;")
    held_worker = restored_ops.spawn('restored-product-worker', [str(root / PYTHON), '-m', 'autobots.operations.worker'])
    beating = wait(lambda: restored_ops.sql("select count(*) from app_private.worker_heartbeats where state = 'running';") == '1', 20)
    time.sleep(4)
    held_worker.send_signal(signal.SIGTERM)
    exited(held_worker, 20)
    states_after = restored_ops.sql("select string_agg(status || attempts, ',' order by run_id) from app_private.run_jobs;")
    routine_log = (run.logs / 'restored-product-worker.log').read_text(errors='replace')
    cases.check('the product worker changes nothing under the hold', 'beats, same jobs, no retention pass', f'{beating}, {states_before == states_after}, retention ran {"retention.applied" in routine_log}', beating and states_before == states_after and 'retention.applied' not in routine_log)
    config_root = run.work / 'restored-config'
    config_root.mkdir(mode=0o700)
    restored_ops.api(run.api_port, config_root)
    wait(lambda: api_call(run.api_port, restored_ops.internal, run.token_a)[0] == 200, 40)
    _code, body = api_call(run.api_port, restored_ops.internal, run.token_a)
    goal = json.dumps({'goal_text': 'Write the report', 'limit_micro_usd': 1000000}).encode()
    admit_code, _ = api_call(run.api_port, restored_ops.internal, run.token_a, 'POST', '/v1/runs', goal, {'Idempotency-Key': secrets.token_hex(8)})
    cases.check('the hold is visible and refuses admission', 'restore_hold, not ready, 503', f"{conditions(body).get('hold')}, {json.loads(body).get('ready')}, {admit_code}", conditions(body).get('hold') == 'restore_hold' and json.loads(body).get('ready') is False and admit_code == 503)


def released_restore(run: BackupRun, cases: Cases) -> None:
    """Released by a person: the restored checkpoint really can continue, with the scripted model."""
    root, interrupted = run.root, run.interrupted
    restored_stack, restored_ops = run.restored()
    released = restored_stack.sql('delete from app_private.installation_holds;')
    reconciled, _reply = api_call(run.api_port, restored_ops.internal, run.token_a, 'POST', f'/v1/runs/{interrupted}/model-calls/reconcile', json.dumps({'charged_micro_usd': 100}).encode(), {'Idempotency-Key': secrets.token_hex(8)})
    cancel = launch([str(root / PYTHON), str(root / 'tests/db/operations_check.py'), 'cancel', run.workspace_a, run.pending], env=restored_ops.env, timeout=60, label='the restored cancel')
    resume = launch([str(root / PYTHON), str(root / 'tests/db/operations_check.py'), 'resume', run.workspace_a, interrupted], env=restored_ops.env, timeout=60, label='the restored resume')
    run.marker.unlink(missing_ok=True)
    worker = restored_ops.fixture_worker('restored-resume-worker', 0, 30, run.marker, 'resume')
    resumed = wait(lambda: restored_ops.sql(f"select status from public.runs where id = '{interrupted}';") == 'succeeded', 60)
    worker.send_signal(signal.SIGTERM)
    exited(worker, 30)
    cases.check('after release, the restored checkpoint continues (scripted model, arranged resume)', 'succeeded', f'release {released.returncode}, reconcile {reconciled}, cancel {cancel.returncode}, resume {resume.returncode}, {resumed}', released.returncode == 0 and reconciled == 200 and cancel.returncode == 0 and resume.returncode == 0 and resumed)


def source_untouched(run: BackupRun, cases: Cases) -> None:
    """Only the declared target changed."""
    ops, stack = run.ops, run.stack
    source_status = ops.sql(f"select status from public.runs where id = '{run.interrupted}';")
    source_counts = durable_counts(ops)
    source_holds = ops.sql('select count(*) from app_private.installation_holds;')
    cases.check('the source is untouched by the restore and what followed', f'paused, {run.counts}, no hold', f'{source_status}, {source_counts}, {source_holds}', source_status == 'paused' and source_counts == run.counts and source_holds == '0')
    outputs = ''.join(result.stdout + result.stderr for result in (run.taken, run.back) if result is not None)
    everything = '\n'.join(path.read_text(errors='replace') for path in run.logs.glob('*.log')) + outputs
    leaked = [name for name, value in (('fake credential', FAKE_CREDENTIAL), ('runtime password', stack.runtime_password), ('jwt secret', stack.values['JWT_SECRET'])) if value in everything]
    cases.check('no tool output or process log holds a secret', 'none', leaked or 'none', not leaked)


SCENARIOS = (source_content, refused_backups, backup_taken, refused_restores, restore, held_restore, released_restore, source_untouched)


def qualify(root: Path) -> int:
    cases = Cases(model_transport=MODEL_TRANSPORT)
    restored_project = f'{PROJECT_PREFIX}{secrets.token_hex(4)}'
    with app_project(root, cases, report=root / REPORT, extra_ports=3) as app:
        api_port, restored_gateway, restored_db = app.ports
        logs = root / '.checks/backup/logs'
        logs.mkdir(parents=True, exist_ok=True)
        for old in logs.glob('*.log'):
            old.unlink()
        work = Path(tempfile.mkdtemp(prefix='autobots-backup-'))
        work.chmod(0o700)
        context = BackupRun(root, app, Ops(root, app.stack, app.base, app.db_port, logs), logs, work, api_port, restored_project,
                            restored_gateway, restored_db)
        try:
            run_scenarios(context, cases, SCENARIOS)
        finally:
            context.ops.stop_all()
            if context.restored_ops is not None:
                context.restored_ops.stop_all()
            shutil.rmtree(work, ignore_errors=True)
    code = finish(root, root / REPORT, 'autobots.backup-qualification/v1', cases, app.started_at,
                  ['H1', 'product acceptance', 'the persistent stack', 'a real model call', 'a real credential', 'protection from losing this Mac'])
    print(f'{"PASS" if code == 0 else "FAIL"}: backup qualification, {round(time.monotonic() - app.started_at)}s, report {REPORT}')
    return code


def main() -> int:
    try:
        return qualify(project_root())
    except Refused as refusal:
        print(f'REFUSED before any change: {refusal}', file=sys.stderr)
        return 1
    except Unavailable as error_:
        print(f'ERROR: {error_}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
