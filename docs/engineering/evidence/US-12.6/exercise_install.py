#!/usr/bin/env python3
"""The upgrade runbook on the real install, then one goal, by Decision 0013. Kept with the evidence.

Back up, restore to an isolated copy, try the pending migrations there first, apply them to the install, start
it, and run one goal. Each step stops the whole on failure, and a failure on the copy leaves the install's database
unchanged. Prints no value from the install's env files. A file under `scripts/` would void US-12.3's binding.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'services/agent/src'))

from disposable_db import other_resources, tool_env  # noqa: E402
from persistent_install import DEFAULT_DIR, read_record, read_values  # noqa: E402

PROJECT = 'autobots-install'
OUT = ROOT / '.checks/US-12.6'
PY = str(ROOT / 'services/agent/.venv/bin/python')
LIMIT = 250_000
report: dict = {'schema_version': 'autobots.install-at-final-code/v1', 'started_at_utc': datetime.now(timezone.utc).isoformat(), 'steps': []}


def step(name: str, argv: list[str], timeout: int = 600, keep: bool = True) -> str:
    started = time.monotonic()
    done = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, errors='replace', timeout=timeout, check=False,
                          env={**tool_env(), 'PYTHONPATH': str(ROOT / 'services/agent/src'), 'PYTHONDONTWRITEBYTECODE': '1', 'HOME': os.environ['HOME'],
                               'PATH': os.environ['PATH']})
    entry = {'step': name, 'exit': done.returncode, 'seconds': round(time.monotonic() - started, 1)}
    if keep:
        entry['output'] = done.stdout.strip()[-1500:]
    if done.returncode:
        entry['error'] = done.stderr.strip()[-500:]
    report['steps'].append(entry)
    save()
    print(json.dumps({key: value for key, value in entry.items() if key != 'output'}), flush=True)
    if done.returncode:
        raise SystemExit(f'{name} failed, so this stops here')
    return done.stdout


def save() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'report.json').write_text(json.dumps(report, indent=2, default=str))


def installed(*arguments: str) -> list[str]:
    return [PY, 'scripts/persistent_install.py', *arguments]


def facts(directory: Path) -> dict:
    """Read through the install's own database container. Counts and hashes, never content."""
    statement = ("select (select count(*) from auth.users) as users, (select count(*) from public.workspaces) as workspaces, "
                 "(select count(*) from public.runs) as runs, (select count(*) from public.runs where status = 'succeeded') as succeeded, "
                 "(select count(*) from public.artifacts where status = 'published') as artifacts, (select count(*) from agent_runtime.checkpoints) as checkpoints, "
                 "(select count(*) from public.run_events) as events, (select count(*) from app_private.model_invocations) as invocations, "
                 "(select count(*) from autobots_install.migrations) as history")
    compose = ['docker', 'compose', '-p', PROJECT, '--project-directory', str(ROOT / 'infra/supabase/upstream'), '--env-file', str(directory / 'stack.env'),
               '-f', str(ROOT / 'infra/supabase/upstream/docker-compose.yml'), '-f', str(ROOT / 'infra/supabase/compose.overlay.yaml')]
    done = subprocess.run([*compose, 'exec', '-T', 'db', 'psql', '-U', 'postgres', '-d', 'postgres', '-At', '-c', f'select row_to_json(t) from ({statement}) t;'],
                          cwd=ROOT, capture_output=True, text=True, errors='replace', timeout=60, check=False, env={**tool_env(), 'HOME': os.environ['HOME'], 'PATH': os.environ['PATH']})
    if done.returncode:
        return {'unread': done.stderr.strip()[-200:]}
    return json.loads(done.stdout.strip().splitlines()[-1])


def listeners(record) -> dict:
    found = {}
    for name, port in (('gateway', record.gateway_port), ('database', record.db_port), ('api', record.api_port), ('web', record.web_port)):
        done = subprocess.run(['lsof', '-nP', f'-iTCP:{port}', '-sTCP:LISTEN'], capture_output=True, text=True, check=False)
        found[name] = sorted({line.split()[8] for line in done.stdout.splitlines()[1:]})
    return found


def main() -> int:
    directory = Path(DEFAULT_DIR)
    record = read_record(directory)
    assert record.project == PROJECT
    before_others = other_resources(PROJECT)
    report['others_before'] = len(before_others) if hasattr(before_others, '__len__') else None
    processes: list[subprocess.Popen] = []
    application = read_values(directory / 'app.env')
    master = Path(application['AUTOBOTS_PROVIDER_MASTER_KEY_FILE'])
    backup_key = next((directory / 'backup-key').iterdir())
    key_dir = directory / 'provider-key-copy'
    restored = f'autobots-disposable-{secrets.token_hex(4)}'
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    backup_dir = directory / 'backups' / stamp
    report['pending_migrations_expected'] = sorted(path.name for path in (ROOT / 'supabase/migrations').glob('*.sql'))[-3:]
    try:
        step('up', installed('up', '--project', PROJECT))
        report['facts_before'] = facts(directory)
        print(json.dumps({'facts_before': report['facts_before']}), flush=True)
        step('backup', [PY, 'scripts/local_backup.py', 'backup', '--project', PROJECT, '--env-file', str(directory / 'stack.env'), '--out', str(backup_dir),
                        '--backup-key', str(backup_key), '--key-dir', str(key_dir), '--master-key', str(master)], 900)
        step('restore to an isolated copy', [PY, 'scripts/local_backup.py', 'restore', '--backup', str(backup_dir), '--backup-key', str(backup_key), '--project', restored], 900)
        try:
            step('verify the copy', [PY, 'scripts/local_backup.py', 'verify', '--backup', str(backup_dir), '--backup-key', str(backup_key), '--key-dir', str(key_dir), '--project', restored], 600)
            step('apply on the restored copy first', installed('apply', '--project', restored, '--restored-copy'), 600)
        finally:
            step('remove the copy', ['python3.12', 'scripts/disposable_db.py', 'cleanup', '--project', restored], 300)
        step('apply on the install', installed('apply', '--project', PROJECT), 600)
        report['facts_after_apply'] = facts(directory)
        print(json.dumps({'facts_after_apply': report['facts_after_apply']}), flush=True)

        env = {**os.environ, **application, 'PYTHONPATH': str(ROOT / 'services/agent/src'), 'PYTHONDONTWRITEBYTECODE': '1'}
        logs = directory / 'logs'
        with (logs / 'api.log').open('a') as api_log, (logs / 'web.log').open('a') as web_log:
            processes.append(subprocess.Popen([PY, '-m', 'uvicorn', '--factory', 'autobots.api.main:create_configured_app', '--host', '127.0.0.1', '--port', str(record.api_port), '--no-access-log'],
                                              cwd=ROOT, env=env, stdout=api_log, stderr=api_log, start_new_session=True))
            processes.append(subprocess.Popen([str(ROOT / 'apps/web/node_modules/.bin/next'), 'start', '-H', '127.0.0.1', '-p', str(record.web_port)],
                                              cwd=ROOT / 'apps/web', env={**env, 'NODE_ENV': 'production', 'PATH': f"{os.environ['HOME']}/.nvm/versions/node/v22.23.2/bin:{os.environ['PATH']}"}, stdout=web_log, stderr=web_log, start_new_session=True))
        time.sleep(8)
        status = json.loads(step('read readiness', ['python3.12', '-P', '.checks/install/status.py'], 120, keep=True).strip().splitlines()[-1])
        report['status_before_goal'] = status
        report['listeners'] = listeners(record)
        print(json.dumps({'status': status, 'listeners': report['listeners']}), flush=True)

        goal = step('one goal on Terra', installed('goal', '--project', PROJECT, '--paid', '--limit-micro-usd', str(LIMIT)), 590, keep=False)
        report['goal'] = json.loads(goal[goal.index('{'):goal.rindex('}') + 1])
        report['facts_after_goal'] = facts(directory)
        print(json.dumps({'facts_after_goal': report['facts_after_goal']}), flush=True)
    finally:
        for process in processes:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
        for process in processes:
            try:
                process.wait(30)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
        after_others = other_resources(PROJECT)
        report['other_docker_unchanged'] = before_others == after_others
        report['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        save()
    print(json.dumps({'other_docker_unchanged': report['other_docker_unchanged']}), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
