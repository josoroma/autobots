#!/usr/bin/env python3
"""Exercises the backup and restore runbook between two disposable Compose projects.

The source stands in for the persistent stack, which isn't configured on this machine. No model is called
and the credential is an arranged fake. Exit 0 passed, 1 a case failed, 2 a prerequisite is missing.
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
from datetime import UTC, datetime
from pathlib import Path

from app_db import AppStack, apply_migrations, bootstrap, seed
from disposable_db import (
    PROJECT_PREFIX,
    Refused,
    Target,
    Unavailable,
    free_port,
    other_resources,
    remove_stack,
    require_identity,
    run,
    tool_env,
)
from harness_lib import fingerprint, project_root
from local_backup import restored_values
from qualify_identity import PYTHON, STORAGE_SQL, bootstrap_owner, http, password_token
from qualify_operations import Checks, Ops, api_call, conditions, durable_counts, exited, wait
from supabase_stack import generated_values, require_images, require_rendered

REPORT = Path('.checks/backup/qualification.json')
FAKE_CREDENTIAL = 'sk-or-arranged-' + secrets.token_hex(24)


def backup_tool(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(root / PYTHON), str(root / 'scripts/local_backup.py'), *arguments], env={**tool_env(), 'PYTHONDONTWRITEBYTECODE': '1'},
                          cwd=root, capture_output=True, text=True, errors='replace', timeout=500, check=False)


def env_text(stack: AppStack) -> str:
    return ''.join(f'{name}={value}\n' for name, value in stack.values.items())


def qualify(root: Path) -> int:
    project = f'{PROJECT_PREFIX}{secrets.token_hex(4)}'
    restored_project = f'{PROJECT_PREFIX}{secrets.token_hex(4)}'
    gateway_port = free_port()
    db_port = free_port([gateway_port])
    api_port = free_port([gateway_port, db_port])
    restored_gateway = free_port([gateway_port, db_port, api_port])
    restored_db = free_port([gateway_port, db_port, api_port, restored_gateway])
    target = Target(project, db_port, gateway_port)
    stack = AppStack(target, root, root / 'infra/supabase/upstream/docker-compose.yml', values=generated_values(gateway_port, db_port))
    stack.migrator_password, stack.runtime_password = secrets.token_hex(24), secrets.token_hex(24)
    require_identity(target, tool_env())
    if run(['docker', 'info', '--format', '{{.ServerVersion}}'], tool_env(), 30).returncode:
        raise Unavailable('the Docker engine is not reachable')
    (root / REPORT).unlink(missing_ok=True)
    require_images(require_rendered(stack))
    cases = Checks()
    before = other_resources(project)
    started_at = time.monotonic()
    base = f'http://127.0.0.1:{gateway_port}'
    anon = stack.values['ANON_KEY']
    logs = root / '.checks/backup/logs'
    logs.mkdir(parents=True, exist_ok=True)
    for old in logs.glob('*.log'):
        old.unlink()
    work = Path(tempfile.mkdtemp(prefix='autobots-backup-'))
    work.chmod(0o700)
    backup_dir, backup_key, key_dir = work / 'backups/first', work / 'backup-keys/backup.key', work / 'provider-keys'
    master_key = work / 'live/secrets/master.key'
    env_file = work / 'stack.env'
    wrong_key = work / 'wrong.key'
    ops = Ops(root, stack, base, db_port, logs)
    restored_stack = None
    restored_ops = None
    email_a, email_b = 'owner-a@example.invalid', 'owner-b@example.invalid'
    password_a, password_b = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
    try:
        started = stack.compose('up', '-d', '--wait', '--wait-timeout', '240', timeout=300)
        if started.returncode:
            raise Unavailable(f'the stack did not start: {started.stderr[-300:]}')
        bootstrap(stack, root)
        applied, problem = apply_migrations(stack, root / 'supabase/migrations')
        if problem or seed(stack, root).returncode or stack.sql((root / STORAGE_SQL).read_text()).returncode:
            raise Unavailable(f'migrations failed: {problem}')
        owner_a = bootstrap_owner(root, base, stack.values['SERVICE_ROLE_KEY'], ops.url, email_a, password_a)
        bootstrap_owner(root, base, stack.values['SERVICE_ROLE_KEY'], ops.url, email_b, password_b)
        workspace_a = owner_a['workspace_id']

        # Real content, from the real loop: finished, interrupted and pending work, and a credential.
        marker = work / 'in-call'
        finished_run = ops.admit(workspace_a)
        worker = ops.fixture_worker('finish-worker', 0, 30, marker)
        finished = wait(lambda: ops.sql(f"select status from public.runs where id = '{finished_run}';") == 'succeeded', 60)
        worker.send_signal(signal.SIGTERM)
        exited(worker, 30)
        marker.unlink(missing_ok=True)
        interrupted = ops.admit(workspace_a)
        worker = ops.fixture_worker('cut-worker', 6, 1, marker)
        wait(marker.exists, 40)
        worker.send_signal(signal.SIGTERM)
        exited(worker, 40)
        worker = ops.fixture_worker('classify-worker', 0, 30, marker, 'resume')
        paused = wait(lambda: ops.sql(f"select status from public.runs where id = '{interrupted}';") == 'paused', 40)
        worker.send_signal(signal.SIGTERM)
        exited(worker, 30)
        pending = ops.admit(workspace_a)
        master_key.parent.mkdir(parents=True, mode=0o700)
        seeded = subprocess.run([str(root / PYTHON), str(root / 'tests/db/restore_check.py'), 'seed', workspace_a, str(master_key), FAKE_CREDENTIAL], env=ops.env,
                                capture_output=True, text=True, timeout=60, check=False)
        cases.check('the source holds real content (arranged credential)', 'finished, paused, queued, a sealed fake key', f'{finished}, {paused}, seed exit {seeded.returncode}', finished and paused and seeded.returncode == 0)
        env_file.write_text(env_text(stack) + f'AUTOBOTS_MIGRATOR_PASSWORD={stack.migrator_password}\nAUTOBOTS_RUNTIME_PASSWORD={stack.runtime_password}\n')
        env_file.chmod(0o600)
        made = backup_tool(root, 'keygen', '--out', str(backup_key))
        wrong = backup_tool(root, 'keygen', '--out', str(wrong_key))
        cases.check('a backup key is generated, private', '0600', oct(backup_key.stat().st_mode & 0o777), made.returncode == 0 and wrong.returncode == 0 and backup_key.stat().st_mode & 0o777 == 0o600)

        # Refused while anything can still write, and nothing stops.
        worker = ops.spawn('live-worker', [str(root / PYTHON), '-m', 'autobots.operations.worker'])
        wait(lambda: ops.sql("select count(*) from app_private.worker_heartbeats where state = 'running';") == '1', 20)
        take = ('backup', '--project', project, '--env-file', str(env_file), '--out', str(backup_dir), '--backup-key', str(backup_key), '--key-dir', str(key_dir), '--master-key', str(master_key))
        refused = backup_tool(root, *take)
        still = ops.sql('select 1;')
        cases.check('a live worker refuses the backup, and nothing stops', 'exit 1, database up, no backup', f'{refused.returncode}, {still}, {backup_dir.exists()}', refused.returncode == 1 and still == '1' and not backup_dir.exists())
        worker.send_signal(signal.SIGTERM)
        exited(worker, 20)
        inside = backup_tool(root, 'backup', '--project', project, '--env-file', str(env_file), '--out', str(backup_dir), '--backup-key', str(backup_key), '--key-dir', str(backup_dir / 'keys'), '--master-key', str(master_key))
        cases.check('a key directory inside the backup is refused', 'exit 1', inside.returncode, inside.returncode == 1 and not backup_dir.exists())

        counts = durable_counts(ops)
        taken = backup_tool(root, *take)
        if taken.returncode:
            raise Unavailable(f'the backup failed: {taken.stderr[-400:]}')
        manifest = json.loads((backup_dir / 'manifest.json').read_text())
        source_after = wait(lambda: ops.sql('select 1;') == '1', 60)
        cases.check('the source is back after its backup, with the same records', counts, f'{source_after}, {durable_counts(ops)}', source_after and durable_counts(ops) == counts)
        expected_components = {'configuration', 'volume:db-data', 'volume:storage-data'}
        names = set(manifest['components'])
        cases.check('the manifest is versioned and names every component', 'autobots.backup/v1 with database, Storage and configuration', f"{manifest['schema_version']}, {sorted(names)}", manifest['schema_version'] == 'autobots.backup/v1' and expected_components <= names)
        cases.check('the manifest binds versions, migrations and artifact hashes', 'images, compose hashes, migrations, hashes', f"{len(manifest['images'])} images, {len(manifest['compose_files'])} files, {len(manifest['facts']['migrations'])} migrations, {len(manifest['facts']['artifacts'])} artifacts", manifest['images'] and manifest['compose_files'] and len(manifest['facts']['migrations']) == applied and manifest['facts']['artifacts'])
        modes = {path.name: oct(path.stat().st_mode & 0o777) for path in backup_dir.iterdir()}
        cases.check('backup files are private', 'all 0600 in 0700', f'{oct(backup_dir.stat().st_mode & 0o777)}, {sorted(set(modes.values()))}', backup_dir.stat().st_mode & 0o777 == 0o700 and set(modes.values()) == {'0o600'})
        kept_key = key_dir / 'provider-master.key'
        same = kept_key.read_bytes() == master_key.read_bytes()
        cases.check('the provider key is kept apart from the backup', 'outside the directory, 0600, same bytes', f'{oct(kept_key.stat().st_mode & 0o777)}, {same}, inside {kept_key.is_relative_to(backup_dir)}', same and kept_key.stat().st_mode & 0o777 == 0o600 and not kept_key.is_relative_to(backup_dir))
        haystack = b''.join(path.read_bytes() for path in backup_dir.iterdir())
        found = [name for name, value in (('jwt secret', stack.values['JWT_SECRET']), ('postgres password', stack.values['POSTGRES_PASSWORD']), ('runtime password', stack.runtime_password),
                                          ('service key', stack.values['SERVICE_ROLE_KEY']), ('fake credential', FAKE_CREDENTIAL), ('owner email', email_a), ('master key', master_key.read_bytes().hex())) if value.encode() in haystack]
        plain_markers = [marker_ for marker_ in (b'PG_VERSION', b'postgresql.conf') if marker_ in haystack]
        cases.check('nothing in the backup reads in the clear', 'no secret, no database file names', f'{found or "none"}, {plain_markers or "none"}', not found and not plain_markers)

        # A damaged or foreign backup stops before Docker is touched.
        def refused_restore(directory: Path, key: Path, name: str, label: str, marker_text: str = '') -> None:
            result = backup_tool(root, 'restore', '--backup', str(directory), '--backup-key', str(key), '--project', name, '--gateway-port', str(restored_gateway), '--db-port', str(restored_db))
            created = run(['docker', 'volume', 'ls', '--filter', f'label=com.docker.compose.project={name}', '--format', '{{.Name}}'], tool_env()).stdout.split() if name != project else []
            detail = result.stderr.strip()[-80:]
            cases.check(label, 'exit 1, nothing created', f'{result.returncode}, {len(created)} volumes, {detail}', result.returncode == 1 and not created and marker_text in result.stderr)

        refused_restore(backup_dir, backup_key, project, 'a restore onto its own source is refused', 'source')
        refused_restore(backup_dir, backup_key, 'autobots-real', 'a restore outside the disposable namespace is refused')
        refused_restore(backup_dir, wrong_key, restored_project, 'the wrong backup key is refused')
        flipped = work / 'flipped'
        shutil.copytree(backup_dir, flipped)
        victim = flipped / manifest['components']['volume:db-data']['file']
        data = bytearray(victim.read_bytes())
        data[len(data) // 2] ^= 1
        victim.write_bytes(bytes(data))
        refused_restore(flipped, backup_key, restored_project, 'a changed component is refused')
        edited = work / 'edited'
        shutil.copytree(backup_dir, edited)
        (edited / 'manifest.json').write_text((edited / 'manifest.json').read_text().replace('"schema_version"', '"schema_version" ', 1))
        refused_restore(edited, backup_key, restored_project, 'a changed manifest is refused')

        # The real restore, to its own project, ports and volumes.
        back = backup_tool(root, 'restore', '--backup', str(backup_dir), '--backup-key', str(backup_key), '--project', restored_project, '--gateway-port', str(restored_gateway), '--db-port', str(restored_db))
        if back.returncode:
            raise Unavailable(f'the restore failed: {back.stderr[-500:]}')
        result = json.loads(back.stdout.strip().splitlines()[-1])
        held_at = run(['docker', 'exec', f"{restored_project}-db-1", 'psql', '-U', 'supabase_admin', '-d', 'postgres', '-X', '-A', '-t', '-c', "select to_char(created_at at time zone 'utc', 'YYYY-MM-DD\"T\"HH24:MI:SS.US') from app_private.installation_holds;"], tool_env()).stdout.strip()
        rest_started = run(['docker', 'inspect', '-f', '{{.State.StartedAt}}', f'{restored_project}-rest-1'], tool_env()).stdout.strip()[:26]
        cases.check('the hold is written before other services start', 'hold earlier than the REST service', f'{held_at}, {rest_started}', bool(held_at) and bool(rest_started) and held_at < rest_started)
        verified = backup_tool(root, 'verify', '--backup', str(backup_dir), '--backup-key', str(backup_key), '--key-dir', str(key_dir), '--project', restored_project)
        report = json.loads(verified.stdout.strip().splitlines()[-1]) if verified.stdout.strip() else {'cases': []}
        failed = [case['id'] for case in report['cases'] if not case['passed']]
        cases.check("the operator's own verify command passes on the restore", 'exit 0, all facts match', f"exit {verified.returncode}, {len(report['cases'])} facts, failed {failed or 'none'}", verified.returncode == 0 and report['cases'] and not failed)
        records = [json.loads(line) for line in (backup_dir / 'restores.jsonl').read_text().splitlines()]
        last = records[-1] if records else {}
        cases.check('each restore and its verification are recorded where Operations reads them', 'not_verified, then passed, with counts and no instance name',
                    f"{[item['result'] for item in records]}, {last.get('checks_passed')} of {last.get('checks_total')}",
                    [item['result'] for item in records] == ['not_verified', 'passed'] and last['checks_passed'] == last['checks_total'] > 0 and restored_project not in (backup_dir / 'restores.jsonl').read_text())
        other_keys = work / 'other-provider-keys'
        other_keys.mkdir(mode=0o700)
        (other_keys / 'provider-master.key').write_bytes(secrets.token_bytes(32))
        mismatch = backup_tool(root, 'verify', '--backup', str(backup_dir), '--backup-key', str(backup_key), '--key-dir', str(other_keys), '--project', restored_project)
        cases.check('and it fails on the wrong provider key', 'exit 1', mismatch.returncode, mismatch.returncode == 1)
        failed_record = json.loads((backup_dir / 'restores.jsonl').read_text().splitlines()[-1])
        cases.check('a failed verification is recorded as failed', 'failed', failed_record['result'], failed_record['result'] == 'failed')
        source_volumes = run(['docker', 'volume', 'ls', '--filter', f'label=com.docker.compose.project={project}', '--format', '{{.Name}}'], tool_env()).stdout.split()
        shared = set(source_volumes) & set(result['volumes'])
        cases.check('the restore has its own ports and volumes', 'different ports, no shared volume', f"{result['gateway_port']}/{result['db_port']} vs {gateway_port}/{db_port}, {len(shared)} shared", result['gateway_port'] != gateway_port and result['db_port'] != db_port and not shared)
        restored_target = Target(restored_project, restored_db, restored_gateway)
        restored_stack = AppStack(restored_target, root, root / 'infra/supabase/upstream/docker-compose.yml', values=restored_values(stack.values, restored_gateway, restored_db))
        restored_stack.migrator_password, restored_stack.runtime_password = stack.migrator_password, stack.runtime_password
        restored_base = f'http://127.0.0.1:{restored_gateway}'
        restored_ops = Ops(root, restored_stack, restored_base, restored_db, logs)
        status_a, token_a = password_token(restored_base, anon, email_a, password_a)
        status_b, token_b = password_token(restored_base, anon, email_b, password_b)
        wrong_login, _ = password_token(restored_base, anon, email_a, 'not-the-password')
        cases.check('owners sign in on the restore with their own passwords', '200, 200, and a wrong password refused', f'{status_a}, {status_b}, {wrong_login}', status_a == 200 and status_b == 200 and wrong_login in (400, 401))
        def rest(token: str) -> list:
            code, body = http('GET', f'{restored_base}/rest/v1/runs?select=id,workspace_id', {'apikey': anon, 'Authorization': f'Bearer {token}'}, None)
            return json.loads(body) if code == 200 else [{'status': code}]
        own, other = rest(token_a), rest(token_b)
        cases.check('workspace isolation holds on the restore', 'A sees its runs, B none of them', f'{len(own)}, {len(other)}', len(own) >= 3 and not [row for row in other if row.get('workspace_id') == workspace_a])
        restored_ops.env.update({'AUTOBOTS_DATABASE_URL': restored_ops.url})
        expected_sha = hashlib.sha256(FAKE_CREDENTIAL.encode()).hexdigest()
        wrong_provider = work / 'wrong-provider.key'
        wrong_provider.write_bytes(secrets.token_bytes(len(master_key.read_bytes())))
        wrong_provider.chmod(0o600)
        checked = subprocess.run([str(root / PYTHON), str(root / 'tests/db/restore_check.py'), 'verify', workspace_a, str(kept_key), str(backup_dir / 'manifest.json'), expected_sha, str(wrong_provider)], env=restored_ops.env,
                                 capture_output=True, text=True, errors='replace', timeout=240, check=False)
        if checked.returncode:
            (root / '.checks/backup/restore.err').write_text(checked.stderr)
            cases.check('the restore check ran', 'exit 0', f'exit {checked.returncode}: {checked.stderr.strip()[-380:]}', False)
        if checked.stdout.strip():
            for case in json.loads(checked.stdout.strip().splitlines()[-1])['cases']:
                cases.check(case['id'], case['expected'], case['observed'], case['passed'])

        # The product worker and API on the restore, still held.
        states_before = restored_ops.sql("select string_agg(status || attempts, ',' order by run_id) from app_private.run_jobs;")
        held_worker = restored_ops.spawn('restored-product-worker', [str(root / PYTHON), '-m', 'autobots.operations.worker'])
        beating = wait(lambda: restored_ops.sql("select count(*) from app_private.worker_heartbeats where state = 'running';") == '1', 20)
        time.sleep(4)
        held_worker.send_signal(signal.SIGTERM)
        exited(held_worker, 20)
        states_after = restored_ops.sql("select string_agg(status || attempts, ',' order by run_id) from app_private.run_jobs;")
        routine_log = (logs / 'restored-product-worker.log').read_text(errors='replace')
        cases.check('the product worker changes nothing under the hold', 'beats, same jobs, no retention pass', f'{beating}, {states_before == states_after}, retention ran {"retention.applied" in routine_log}', beating and states_before == states_after and 'retention.applied' not in routine_log)
        config_root = work / 'restored-config'
        config_root.mkdir(mode=0o700)
        restored_ops.api(api_port, config_root)
        wait(lambda: api_call(api_port, restored_ops.internal, token_a)[0] == 200, 40)
        _code, body = api_call(api_port, restored_ops.internal, token_a)
        goal = json.dumps({'goal_text': 'Write the report', 'limit_micro_usd': 1000000}).encode()
        admit_code, _ = api_call(api_port, restored_ops.internal, token_a, 'POST', '/v1/runs', goal, {'Idempotency-Key': secrets.token_hex(8)})
        cases.check('the hold is visible and refuses admission', 'restore_hold, not ready, 503', f"{conditions(body).get('hold')}, {json.loads(body).get('ready')}, {admit_code}", conditions(body).get('hold') == 'restore_hold' and json.loads(body).get('ready') is False and admit_code == 503)

        # Released by a person: the restored checkpoint really can continue, with the scripted model.
        released = restored_stack.sql('delete from app_private.installation_holds;')
        reconciled, _reply = api_call(api_port, restored_ops.internal, token_a, 'POST', f'/v1/runs/{interrupted}/model-calls/reconcile', json.dumps({'charged_micro_usd': 100}).encode(), {'Idempotency-Key': secrets.token_hex(8)})
        cancel = subprocess.run([str(root / PYTHON), str(root / 'tests/db/operations_check.py'), 'cancel', workspace_a, pending], env=restored_ops.env, capture_output=True, text=True, timeout=60, check=False)
        resume = subprocess.run([str(root / PYTHON), str(root / 'tests/db/operations_check.py'), 'resume', workspace_a, interrupted], env=restored_ops.env, capture_output=True, text=True, timeout=60, check=False)
        marker.unlink(missing_ok=True)
        worker = restored_ops.fixture_worker('restored-resume-worker', 0, 30, marker, 'resume')
        resumed = wait(lambda: restored_ops.sql(f"select status from public.runs where id = '{interrupted}';") == 'succeeded', 60)
        worker.send_signal(signal.SIGTERM)
        exited(worker, 30)
        cases.check('after release, the restored checkpoint continues (scripted model, arranged resume)', 'succeeded', f'release {released.returncode}, reconcile {reconciled}, cancel {cancel.returncode}, resume {resume.returncode}, {resumed}', released.returncode == 0 and reconciled == 200 and cancel.returncode == 0 and resume.returncode == 0 and resumed)

        # Only the declared target changed.
        source_status = ops.sql(f"select status from public.runs where id = '{interrupted}';")
        source_counts = durable_counts(ops)
        source_holds = ops.sql('select count(*) from app_private.installation_holds;')
        cases.check('the source is untouched by the restore and what followed', f'paused, {counts}, no hold', f'{source_status}, {source_counts}, {source_holds}', source_status == 'paused' and source_counts == counts and source_holds == '0')
        everything = '\n'.join(path.read_text(errors='replace') for path in logs.glob('*.log')) + taken.stdout + taken.stderr + back.stdout + back.stderr
        leaked = [name for name, value in (('fake credential', FAKE_CREDENTIAL), ('runtime password', stack.runtime_password), ('jwt secret', stack.values['JWT_SECRET'])) if value in everything]
        cases.check('no tool output or process log holds a secret', 'none', leaked or 'none', not leaked)
    finally:
        ops.stop_all()
        if restored_ops is not None:
            restored_ops.stop_all()
        for each in (restored_stack, stack):
            if each is not None:
                remove_stack(each)
        shutil.rmtree(work, ignore_errors=True)
    for name in (project, restored_project):
        label = f'label=com.docker.compose.project={name}'
        left = (run(['docker', 'volume', 'ls', '--filter', label, '--format', '{{.Name}}'], tool_env()).stdout
                + run(['docker', 'ps', '-a', '--filter', label, '--format', '{{.Names}}'], tool_env()).stdout).strip()
        cases.check('cleanup removed the owned containers and volumes', 'none left', left or 'none', not left)
    after_resources = other_resources(project)
    cases.check('other Docker resources are untouched', 'same', f'{len(before)} before, {len(after_resources)} after', before == after_resources)
    passed = all(record['status'] == 'passed' for record in cases.records)
    path_report = root / REPORT
    path_report.parent.mkdir(parents=True, exist_ok=True)
    path_report.write_text(json.dumps({'schema_version': 'autobots.backup-qualification/v1', 'completed_at_utc': datetime.now(UTC).isoformat(),
                                       'duration_seconds': round(time.monotonic() - started_at, 1), 'input_fingerprint': fingerprint(root),
                                       'status': 'passed' if passed else 'failed', 'target_class': 'disposable', 'cases': cases.records,
                                       'not_established': ['H1', 'product acceptance', 'the persistent stack', 'a real model call', 'a real credential', 'protection from losing this Mac']}, indent=2))
    print(f'{"PASS" if passed else "FAIL"}: backup qualification, {round(time.monotonic() - started_at)}s, report {REPORT}')
    return 0 if passed else 1


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
