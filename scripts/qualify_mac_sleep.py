#!/usr/bin/env python3
"""Observe one real Mac sleep during a run, on a disposable stack with a scripted model. US-11.10.

`start` runs this detached, since the session that starts it sleeps too. It arranges the stack and a run,
writes `ready_to_sleep` in .checks/mac-sleep/state.json, and waits for a person to sleep this Mac, following
docs/engineering/runbooks/mac-sleep.md. Nothing here sleeps the Mac or sends SIGSTOP. A sleep is only counted
when the wall clock runs ahead of the monotonic clock, and macOS's own power log is recorded beside that.

It removes only its own `autobots-disposable-*` project. Exit codes: 0 observed, 1 a failure was observed or no
sleep happened, 2 prerequisite unavailable. Passing establishes neither H1 nor product acceptance.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import secrets
import signal
import subprocess
import sys
import tempfile
import time

from app_db import AppStack, apply_migrations, bootstrap, seed
from disposable_db import PROJECT_PREFIX, Target, Unavailable, free_port, other_resources, remove_stack, require_identity, run, tool_env
from harness_lib import project_root
from qualify_identity import PYTHON, STORAGE_SQL, bootstrap_owner, password_token
from qualify_operations import Ops, api_call, wait
from supabase_stack import generated_values, require_images, require_rendered

OUT = Path('.checks/mac-sleep')
DRIVER = 'tests/db/sleep_inference_worker.py'
HELPER = 'tests/db/product_inference_check.py'
KEY = 'sk-or-arranged-sleep-key'
GOAL = 'Write the report [sleep-proof]'
# Long enough to notice a sleep, and short enough that a lid closed for a moment isn't called one.
SLEEP_GAP_SECONDS = 20.0
WAIT_FOR_SLEEP_SECONDS = 2400
AFTER_WAKE_SECONDS = 600
SETTLED_PAUSE_SECONDS = 60
TERMINAL = {'succeeded', 'failed', 'cancelled'}
SNAPSHOT = ("select row_to_json(t) from (select r.status, r.version, "
            "(select stop_reason from app_private.run_usage u where u.run_id = r.id) as stop_reason, "
            "(select count(*) from app_private.model_invocations i where i.root_run_id = r.id) as calls, "
            "(select coalesce(sum(i.reserved_micro_usd) filter (where i.status in ('reserved', 'dispatched', 'uncertain') and i.reconciled_at is null), 0) from app_private.model_invocations i where i.root_run_id = r.id) as reserved, "
            "(select coalesce(sum(i.charged_micro_usd), 0) from app_private.model_invocations i where i.root_run_id = r.id) as charged, "
            "(select count(*) from app_private.model_invocations i where i.root_run_id = r.id and i.status = 'uncertain' and i.reconciled_at is null) as uncertain, "
            "(select count(*) from app_private.tool_receipts x where x.run_id = r.id) as receipts, "
            "(select count(*) from app_private.tool_receipts x where x.run_id = r.id and x.status = 'unknown') as unknown_receipts, "
            "(select count(*) from app_private.run_files f where f.run_id = r.id and f.path like 'outputs/%%') as saved_versions, "
            "(select count(distinct f.path) from app_private.run_files f where f.run_id = r.id and f.path like 'outputs/%%') as saved_paths, "
            "(select count(*) from public.artifacts a where a.run_id = r.id and a.status = 'published') as published, "
            "(select j.status from app_private.run_jobs j where j.run_id = r.id) as job, "
            "(select j.attempts from app_private.run_jobs j where j.run_id = r.id) as attempts, "
            "(select r.lease_generation) as generation from public.runs r where r.id = '{run}') t;")


class Run:
    def __init__(self, root: Path) -> None:
        self.root, self.out = root, root / OUT
        self.out.mkdir(parents=True, exist_ok=True)
        self.report: dict = {'schema_version': 'autobots.mac-sleep/v1', 'started_at_utc': datetime.now(timezone.utc).isoformat(), 'target_class': 'disposable',
                             'model_transport': 'scripted, over a fake HTTP transport', 'used_sigstop': False, 'timeline': [],
                             'not_established': ['H1', 'product acceptance', 'a real provider across sleep', 'a persistent stack across sleep', 'Docker Desktop restarting']}

    def state(self, phase: str, **extra: object) -> None:
        (self.out / 'state.json').write_text(json.dumps({'phase': phase, 'at': datetime.now(timezone.utc).isoformat(), **extra}) + '\n')
        print(f'{phase} {extra}', flush=True)

    def finish(self, verdict: str) -> None:
        self.report['verdict'] = verdict
        self.report['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        (self.out / 'report.json').write_text(json.dumps(self.report, indent=2, default=str) + '\n')
        self.state('done', verdict=verdict)


def power_log(since: str) -> list[str]:
    """macOS's own record, so a sleep isn't only this script's inference."""
    listed = subprocess.run(['pmset', '-g', 'log'], capture_output=True, text=True, errors='replace', timeout=120, check=False).stdout.splitlines()
    wanted = re.compile(r'^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d [-+]\d{4} (Sleep|Wake|DarkWake)\s')
    return [line.strip()[:170] for line in listed if line[:19] >= since and wanted.match(line)]


def assess(report: dict, requests: list[dict]) -> list[str]:
    """LC-31 and LM-A07, in the story's own terms. Each entry is a failure."""
    failures = []
    started = [line['step'] for line in requests if line.get('event') == 'call_started']
    repeated = sorted({step for step in started if started.count(step) > 1})
    report['steps_sent_more_than_once'] = repeated
    if repeated:
        failures.append('blind_redispatch')
    after = report.get('after_settled') or {}
    if after.get('saved_versions') != after.get('saved_paths') or (after.get('published') or 0) > 1:
        failures.append('duplicate_effect')
    if report.get('api_status_at_end') != after.get('status'):
        failures.append('false_status')
    if after.get('status') not in TERMINAL and not after.get('stop_reason'):
        failures.append('stranded_run')
    if after.get('stop_reason') == 'active_time_limit':
        failures.append('sleep_counted_as_work')
    return failures


def observe(root: Path) -> int:
    run_state = Run(root)
    project = f'{PROJECT_PREFIX}{secrets.token_hex(4)}'
    gateway_port = free_port()
    db_port = free_port([gateway_port])
    api_port = free_port([gateway_port, db_port])
    target = Target(project, db_port, gateway_port)
    stack = AppStack(target, root, root / 'infra/supabase/upstream/docker-compose.yml', values=generated_values(gateway_port, db_port))
    stack.migrator_password, stack.runtime_password = secrets.token_hex(24), secrets.token_hex(24)
    require_identity(target, tool_env())
    require_images(require_rendered(stack))
    logs = run_state.out / 'logs'
    logs.mkdir(parents=True, exist_ok=True)
    for old in logs.glob('*.log'):
        old.unlink()
    config_root = Path(tempfile.mkdtemp(prefix='autobots-sleep-'))
    requests_file = config_root / 'requests.jsonl'
    ops = Ops(root, stack, f'http://127.0.0.1:{gateway_port}', db_port, logs)
    for name in ('LANGSMITH_TRACING', 'LANGCHAIN_TRACING_V2', 'LANGSMITH_API_KEY', 'LANGSMITH_ENDPOINT'):
        ops.env.pop(name, None)
    provider_env = {'AUTOBOTS_CONFIG_ROOT': str(config_root), 'NODE_ENV': 'production', 'AUTOBOTS_PROVIDER_MASTER_KEY_FILE': str(config_root / 'secrets/master.key')}
    before_resources = other_resources(project)
    run_state.state('arranging', project=project)
    code = 1
    try:
        started = stack.compose('up', '-d', '--wait', '--wait-timeout', '240', timeout=300)
        if started.returncode:
            raise Unavailable(f'the stack did not start: {started.stderr[-300:]}')
        bootstrap(stack, root)
        _, problem = apply_migrations(stack, root / 'supabase/migrations')
        if problem or seed(stack, root).returncode or stack.sql((root / STORAGE_SQL).read_text()).returncode:
            raise Unavailable(f'the schema could not be set up: {problem}')
        email, password = 'owner@example.invalid', secrets.token_urlsafe(24)
        workspace = bootstrap_owner(root, ops.base, stack.values['SERVICE_ROLE_KEY'], ops.url, email, password)['workspace_id']
        ops.api(api_port, config_root)
        token = password_token(ops.base, stack.values['ANON_KEY'], email, password)[1]
        wait(lambda: api_call(api_port, ops.internal, token)[0] == 200, 40)
        saved = subprocess.run([str(root / PYTHON), str(root / HELPER), 'save-key', workspace], env={**ops.env, **provider_env, 'AUTOBOTS_TEST_KEY': KEY}, capture_output=True, text=True, errors='replace', timeout=90, check=False)
        if saved.returncode:
            raise Unavailable(f'the arranged key could not be saved: {saved.stderr[-200:]}')
        body = json.dumps({'goal_text': GOAL, 'limit_micro_usd': 1_000_000, 'required_artifacts': [{'name': 'report.md', 'must_contain': ['Total: 42']}]}).encode()
        status, reply = api_call(api_port, ops.internal, token, 'POST', '/v1/runs', body, {'Idempotency-Key': secrets.token_hex(8)})
        if status != 202:
            raise Unavailable(f'the API refused the goal: {status} {reply[:200]}')
        run_id = json.loads(reply)['run_id']
        run_state.report['run_id'] = run_id
        worker = ops.spawn('sleep-worker', [str(root / PYTHON), str(root / DRIVER)],
                           {**provider_env, 'AUTOBOTS_WORKER_INFERENCE': 'enabled', 'AUTOBOTS_TEST_REQUESTS': str(requests_file), 'AUTOBOTS_TEST_REJECTED_KEY': 'sk-or-none'})

        def snapshot() -> dict:
            result = stack.runtime(SNAPSHOT.format(run=run_id).replace('%%', '%'))
            lines = [line for line in result.stdout.splitlines() if line.strip().startswith('{')]
            return json.loads(lines[0]) if result.returncode == 0 and lines else {'unreadable': result.stderr[-160:]}

        def api_status() -> str:
            try:
                status_code, text = api_call(api_port, ops.internal, token, 'GET', f'/v1/runs/{run_id}')
            except OSError as failure:
                return f'unreachable: {type(failure).__name__}'
            return json.loads(text).get('status', '') if status_code == 200 else f'http {status_code}'

        def note(label: str) -> dict:
            current = snapshot()
            run_state.report['timeline'].append({'label': label, 'at': datetime.now(timezone.utc).isoformat(), 'api': api_status(), **current})
            return current

        if not wait(lambda: snapshot().get('status') == 'running', 60):
            raise Unavailable(f'the run never started: {snapshot()}')
        note('running, before any sleep')
        since = datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S')
        run_state.state('ready_to_sleep', run_id=run_id, deadline_seconds=WAIT_FOR_SLEEP_SECONDS)

        # A monotonic clock stops while a Mac sleeps, and the wall clock doesn't. That's the detector.
        begun = time.monotonic()
        last_wall, last_mono = time.time(), time.monotonic()
        last_seen: dict = {}
        gap = 0.0
        while time.monotonic() - begun < WAIT_FOR_SLEEP_SECONDS:
            time.sleep(2)
            wall, mono = time.time(), time.monotonic()
            gap = (wall - last_wall) - (mono - last_mono)
            last_wall, last_mono = wall, mono
            if gap > SLEEP_GAP_SECONDS:
                break
            gap = 0.0
            last_seen = snapshot()
            if last_seen.get('status') in TERMINAL:
                break
        if gap == 0.0:
            run_state.report['before_sleep'] = last_seen
            run_state.report['slept'] = False
            run_state.finish('no_sleep_during_the_run')
            return 1
        woke_at = datetime.now(timezone.utc).isoformat()
        run_state.report.update({'slept': True, 'sleep_seconds_by_clocks': round(gap, 1), 'woke_at_utc': woke_at, 'before_sleep': last_seen})
        run_state.state('observing_after_wake', sleep_seconds=round(gap, 1))
        note('first read after waking')

        # What a real install would do: nothing but what its own worker does, until it settles.
        woke = time.monotonic()
        last_status, paused_since = '', None
        reconciled = False
        total_gap = gap
        last_wall, last_mono = time.time(), time.monotonic()
        while time.monotonic() - woke < AFTER_WAKE_SECONDS:
            time.sleep(3)
            # A Mac can drop back to sleep from a dark wake, and this keeps counting.
            wall, mono = time.time(), time.monotonic()
            again = (wall - last_wall) - (mono - last_mono)
            last_wall, last_mono = wall, mono
            if again > SLEEP_GAP_SECONDS:
                total_gap += again
                run_state.report['sleep_seconds_by_clocks'] = round(total_gap, 1)
                note(f'slept again for {round(again)} seconds')
            current = snapshot()
            if current.get('status') != last_status:
                note(f"status became {current.get('status')}")
                last_status = current.get('status', '')
            if current.get('status') in TERMINAL:
                break
            if worker.poll() is not None:
                run_state.report['worker_exited_after_wake'] = worker.returncode
                break
            if current.get('status') == 'paused':
                paused_since = paused_since or time.monotonic()
                if time.monotonic() - paused_since > SETTLED_PAUSE_SECONDS:
                    run_state.report['paused_after_wake'] = current
                    if reconciled:
                        break
                    # The runbook's steps for a person, once: record the charge, then resume.
                    reconciled = True
                    if current.get('uncertain'):
                        reply_code, _ = api_call(api_port, ops.internal, token, 'POST', f'/v1/runs/{run_id}/model-calls/reconcile', json.dumps({'charged_micro_usd': 100}).encode(), {'Idempotency-Key': secrets.token_hex(8)})
                        run_state.report['reconciled'] = reply_code
                    version = snapshot().get('version')
                    reply_code, text = api_call(api_port, ops.internal, token, 'POST', f'/v1/runs/{run_id}/resume', json.dumps({'expected_version': version}).encode(), {'Idempotency-Key': secrets.token_hex(8)})
                    run_state.report['resume_after_wake'] = {'status': reply_code, 'body': text[:200]}
                    paused_since = None
            else:
                paused_since = None
        settled = note('settled, or out of time')
        run_state.report['after_settled'] = settled
        run_state.report['api_status_at_end'] = api_status()
        run_state.report['verification'] = ops.sql(f"select passed::text || ' ' || unmet::text from app_private.run_verifications where run_id = '{run_id}' order by created_at desc limit 1;")
        run_state.report['invocations'] = [json.loads(line) for line in stack.runtime(f"select row_to_json(t) from (select attempt, status, failure_class, reserved_micro_usd, charged_micro_usd, reconciled_at is not null as reconciled from app_private.model_invocations where root_run_id = '{run_id}' order by created_at) t;").stdout.splitlines() if line.strip().startswith('{')]
        requests = [json.loads(line) for line in requests_file.read_text().splitlines()]
        run_state.report['requests'] = requests
        run_state.report['calls_across_the_sleep'] = [line for line in requests if line.get('event') == 'call_replied' and line['wall'] - line['started_wall'] > 60]
        run_state.report['refused_hosts'] = [line for line in requests if 'refused_host' in line]
        written = '\n'.join(path.read_text(errors='replace') for path in logs.glob('*.log'))
        run_state.report['log_events'] = {name: written.count(name) for name in ('worker.woke', 'worker.step_failed', 'worker.drain_cut_short', 'lease_lost', 'Traceback')}
        worker.send_signal(signal.SIGTERM)
        run_state.report['power_log'] = power_log(since)
        run_state.report['failures'] = assess(run_state.report, requests)
        code = 1 if run_state.report['failures'] else 0
    finally:
        ops.stop_all()
        remove_stack(stack)
        subprocess.run(['rm', '-rf', str(config_root)], check=False)
    label = f'label=com.docker.compose.project={project}'
    left = (run(['docker', 'volume', 'ls', '--filter', label, '--format', '{{.Name}}'], tool_env()).stdout + run(['docker', 'ps', '-a', '--filter', label, '--format', '{{.Names}}'], tool_env()).stdout).strip()
    run_state.report['left_behind'] = left or 'none'
    run_state.report['other_docker_unchanged'] = before_resources == other_resources(project)
    run_state.finish('failure_observed' if code else 'no_failure_observed')
    return code


def main(argv: list[str]) -> int:
    root = project_root()
    if argv == ['start']:
        out = root / OUT
        out.mkdir(parents=True, exist_ok=True)
        for name in ('state.json', 'report.json'):
            (out / name).unlink(missing_ok=True)
        with (out / 'run.log').open('w') as handle:
            process = subprocess.Popen([sys.executable, __file__, 'observe'], cwd=root, stdin=subprocess.DEVNULL, stdout=handle, stderr=handle, start_new_session=True)
        print(json.dumps({'status': 'started', 'pid': process.pid, 'state': str(OUT / 'state.json')}))
        return 0
    if argv == ['observe']:
        try:
            return observe(root)
        except Unavailable as problem:
            Run(root).finish(f'unavailable: {problem}')
            return 2
    print('usage: qualify_mac_sleep.py start', file=sys.stderr)
    return 2


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
