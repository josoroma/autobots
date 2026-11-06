#!/usr/bin/env python3
"""Two goals at once on Terra, through the real API and two workers, with local resources sampled.

Kept with the evidence, as a file under `scripts/` would void US-12.3's binding. `--rehearse` uses the fake
transport and spends nothing. `--paid` makes billed OpenRouter calls under the shared ledger, by Decision 0013.
Disposable stack only, removed at the end. Exit 0 stable, 1 failed or not measured, 2 a prerequisite is missing.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import tempfile
import time
from urllib import request

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'scripts'))

from app_db import AppStack, apply_migrations, bootstrap, seed  # noqa: E402
from disposable_db import PROJECT_PREFIX, Target, Unavailable, free_port, other_resources, remove_stack, require_identity, run, tool_env  # noqa: E402
from harness_lib import fingerprint  # noqa: E402
from persistent_install import Refused, reserve_goal  # noqa: E402
from qualify_identity import PYTHON, STORAGE_SQL, bootstrap_owner, password_token  # noqa: E402
from qualify_operations import Ops, api_call, exited, wait  # noqa: E402
from supabase_stack import generated_values, require_images, require_rendered  # noqa: E402

LIMIT_MICRO_USD = 100_000
HELPER = 'tests/db/live_goal_helper.py'
FAKE_HELPER = 'tests/db/product_inference_check.py'
FAKE_WORKER = 'tests/db/product_inference_worker.py'
TERMINAL = {'succeeded', 'failed', 'cancelled'}
TRACING = ('LANGSMITH_TRACING', 'LANGCHAIN_TRACING_V2', 'LANGSMITH_API_KEY', 'LANGSMITH_ENDPOINT')
SECONDS = 600
SAMPLE_SECONDS = 2
GOAL = ('Write a short Markdown report named report.md comparing {a} and {b} for a single-user desktop note-taking app. '
        'Give exactly three trade-offs and a one-sentence recommendation, in under 150 words. Its last line must be exactly: Trade-offs covered: 3')
REQUIRED = [{'name': 'report.md', 'must_contain': ['Trade-offs covered: 3']}]


def rows(ops: Ops, statement: str) -> list[dict]:
    result = ops.stack.runtime(f'select row_to_json(t) from ({statement}) t;')
    return [json.loads(line) for line in result.stdout.splitlines() if line.strip().startswith('{')]


def process_sample(pid: int) -> dict:
    ps = subprocess.run(['ps', '-o', '%cpu=,rss=', '-p', str(pid)], capture_output=True, text=True, check=False).stdout.split()
    tcp = subprocess.run(['lsof', '-nP', '-a', '-p', str(pid), '-iTCP'], capture_output=True, text=True, check=False).stdout
    return {'cpu_percent': float(ps[0]) if ps else None, 'rss_kb': int(ps[1]) if len(ps) > 1 else None,
            'tcp_connections': max(len(tcp.splitlines()) - 1, 0)}


def docker_sample(project: str) -> dict:
    listed = subprocess.run(['docker', 'ps', '--filter', f'label=com.docker.compose.project={project}', '--format', '{{.ID}} {{.Status}}'],
                            capture_output=True, text=True, check=False, timeout=30).stdout.splitlines()
    unhealthy = [line.split(' ', 1)[1] for line in listed if 'unhealthy' in line or 'Restarting' in line]
    ids = [line.split()[0] for line in listed]
    stats = subprocess.run(['docker', 'stats', '--no-stream', '--format', '{{.CPUPerc}} {{.MemUsage}}', *ids],
                           capture_output=True, text=True, check=False, timeout=60).stdout.splitlines() if ids else []
    cpu = sum(float(line.split()[0].rstrip('%')) for line in stats if line)
    unit = {'KiB': 1 / 1024, 'MiB': 1, 'GiB': 1024, 'B': 1 / 1048576}
    memory = 0.0
    for line in stats:
        text = line.split()[1]
        for name, scale in unit.items():
            if text.endswith(name):
                memory += float(text[:-len(name)]) * scale
                break
    return {'containers': len(ids), 'unhealthy': unhealthy, 'cpu_percent': round(cpu, 1), 'memory_mib': round(memory, 1)}


def healthy(url: str) -> bool:
    try:
        with request.urlopen(url, timeout=5) as reply:
            return reply.status < 500
    except OSError:
        return False


def overlap_seconds(calls: list[dict]) -> float:
    """How long calls from different runs were in flight together."""
    total = 0.0
    for index, first in enumerate(calls):
        for second in calls[index + 1:]:
            if first['run_id'] != second['run_id']:
                total += max(0.0, min(first['end'], second['end']) - max(first['start'], second['start']))
    return round(total, 2)


def peaks(samples: list[dict], group: str, field: str) -> float | None:
    values = [item[group][field] for item in samples if item.get(group) and item[group].get(field) is not None]
    return max(values) if values else None


def attempt(root: Path, paid: bool, key_file: Path, ledger_path: Path, out: Path) -> int:
    if paid:
        ledger_a, entry_a = reserve_goal(ledger_path, LIMIT_MICRO_USD)
        try:
            ledger_b, entry_b = reserve_goal(ledger_path, LIMIT_MICRO_USD)
        except Refused:
            ledger_a.settle(entry_a, 0, 'not_started')
            raise
    project = f'{PROJECT_PREFIX}{secrets.token_hex(4)}'
    gateway_port = free_port()
    db_port = free_port([gateway_port])
    api_port = free_port([gateway_port, db_port])
    web_port = free_port([gateway_port, db_port, api_port])
    target = Target(project, db_port, gateway_port)
    stack = AppStack(target, root, root / 'infra/supabase/upstream/docker-compose.yml', values=generated_values(gateway_port, db_port))
    stack.migrator_password, stack.runtime_password = secrets.token_hex(24), secrets.token_hex(24)
    require_identity(target, tool_env())
    if run(['docker', 'info', '--format', '{{.ServerVersion}}'], tool_env(), 30).returncode:
        raise Unavailable('the Docker engine is not reachable')
    require_images(require_rendered(stack))
    logs = out / 'logs'
    logs.mkdir(parents=True, exist_ok=True)
    for old in logs.glob('*.log'):
        old.unlink()
    config_root = Path(tempfile.mkdtemp(prefix='autobots-two-calls-'))
    ops = Ops(root, stack, f'http://127.0.0.1:{gateway_port}', db_port, logs)
    for name in TRACING:
        ops.env.pop(name, None)
    provider_env = {'AUTOBOTS_CONFIG_ROOT': str(config_root), 'NODE_ENV': 'production',
                    'AUTOBOTS_PROVIDER_MASTER_KEY_FILE': str(config_root / 'secrets/master.key')}
    requests_file = logs / 'requests.jsonl'

    def helper(*argv: str, name: str = HELPER, env: dict | None = None) -> str:
        done = subprocess.run([str(root / PYTHON), str(root / name), *argv], env={**ops.env, **provider_env, **(env or {})}, capture_output=True,
                              text=True, errors='replace', timeout=120, check=False)
        if done.returncode:
            raise Unavailable(f'{argv[0]} failed: {done.stderr.strip().splitlines()[-1][:300] if done.stderr.strip() else "no detail"}')
        return done.stdout.strip()

    before_resources = other_resources(project)
    report: dict = {'schema_version': 'autobots.two-call-workload/v1', 'started_at_utc': datetime.now(timezone.utc).isoformat(),
                    'input_fingerprint': fingerprint(root), 'target_class': 'disposable',
                    'model_transport': 'live OpenRouter' if paid else 'fake transport under the real SDK', 'limit_micro_usd_each': LIMIT_MICRO_USD,
                    'samples': [], 'problems': [], 'not_established': ['H1', 'product acceptance', 'a persistent stack', 'responsiveness under load', 'more than this one workload']}
    charged: dict[str, int | None] = {}
    runs: list[str] = []
    finished: dict[str, str] = {}
    if paid:
        report['key_usage_before_usd'] = float(helper('usage', str(key_file)))
    try:
        up = stack.compose('up', '-d', '--wait', '--wait-timeout', '240', timeout=300)
        if up.returncode:
            raise Unavailable(f'the stack did not start: {up.stderr[-300:]}')
        bootstrap(stack, root)
        _, problem = apply_migrations(stack, root / 'supabase/migrations')
        if problem or seed(stack, root).returncode:
            raise Unavailable(f'migrations failed: {problem}')
        if stack.sql((root / STORAGE_SQL).read_text()).returncode:
            raise Unavailable('the storage setup failed')
        email, password = 'owner@example.invalid', secrets.token_urlsafe(24)
        workspace = bootstrap_owner(root, ops.base, stack.values['SERVICE_ROLE_KEY'], ops.url, email, password)['workspace_id']
        token = password_token(ops.base, stack.values['ANON_KEY'], email, password)[1]
        api = ops.api(api_port, config_root, {'AUTOBOTS_SUPABASE_URL': ops.base} if not paid else None)
        wait(lambda: api_call(api_port, ops.internal, token)[0] == 200, 40)
        web = ops.spawn('web', [str(root / 'apps/web/node_modules/.bin/next'), 'start', 'apps/web', '-H', '127.0.0.1', '-p', str(web_port)],
                        {'AUTOBOTS_INTERNAL_TOKEN': ops.internal, 'AUTOBOTS_API_URL': f'http://127.0.0.1:{api_port}', 'AUTOBOTS_ALLOWED_ORIGIN': f'http://127.0.0.1:{web_port}',
                         'NODE_ENV': 'production', 'AUTOBOTS_SUPABASE_URL': ops.base, 'AUTOBOTS_SUPABASE_ANON_KEY': stack.values['ANON_KEY']})
        wait(lambda: healthy(f'http://127.0.0.1:{web_port}/sign-in'), 40)
        if paid:
            helper('save', str(key_file), workspace)
        else:
            helper('save-key', workspace, name=FAKE_HELPER, env={'AUTOBOTS_TEST_KEY': 'arranged-key-one'})

        for label, (first, second) in (('a', ('SQLite', 'PostgreSQL')), ('b', ('Markdown files', 'SQLite'))):
            goal = GOAL.format(a=first, b=second) if paid else f'Write the report [two-{label}]'
            body = {'goal_text': goal, 'limit_micro_usd': LIMIT_MICRO_USD}
            if paid:
                body['required_artifacts'] = REQUIRED
            code, reply = api_call(api_port, ops.internal, token, 'POST', '/v1/runs', json.dumps(body).encode(), {'Idempotency-Key': secrets.token_hex(8)})
            if code != 202:
                raise Unavailable(f'the API refused a goal: {code} {reply[:200]}')
            runs.append(json.loads(reply)['run_id'])
        report['runs'] = runs

        if paid:
            worker_argv = [str(root / PYTHON), str(Path(__file__).with_name('logging_worker.py'))]
            worker_env = {**provider_env, 'AUTOBOTS_WORKER_INFERENCE': 'enabled'}
        else:
            worker_argv = [str(root / PYTHON), FAKE_WORKER]
            worker_env = {**provider_env, 'AUTOBOTS_WORKER_INFERENCE': 'enabled', 'AUTOBOTS_TEST_REQUESTS': str(requests_file), 'AUTOBOTS_TEST_REJECTED_KEY': 'arranged-rejected-key'}
        workers = [ops.spawn(f'worker-{n}', worker_argv, worker_env) for n in (1, 2)]

        started = time.monotonic()
        last: dict[str, str] = {}
        while time.monotonic() - started < SECONDS:
            sample: dict = {'seconds': round(time.monotonic() - started, 1), 'api': process_sample(api.pid), 'ui': process_sample(web.pid),
                            'worker_1': process_sample(workers[0].pid), 'worker_2': process_sample(workers[1].pid), 'docker': docker_sample(project),
                            'api_healthy': api_call(api_port, ops.internal, token)[0] == 200, 'ui_healthy': healthy(f'http://127.0.0.1:{web_port}/sign-in'),
                            'database_connections': int(ops.sql('select count(*) from pg_stat_activity;') or 0),
                            'database_kb': int(ops.sql('select pg_database_size(current_database()) / 1024;') or 0),
                            'disk_used_kb': int(subprocess.run(['df', '-k', str(root)], capture_output=True, text=True, check=False).stdout.splitlines()[-1].split()[2])}
            report['samples'].append(sample)
            if not sample['api_healthy']:
                report['problems'].append(f"the API didn't answer at {sample['seconds']}s")
            if not sample['ui_healthy']:
                report['problems'].append(f"the UI didn't answer at {sample['seconds']}s")
            if sample['docker']['unhealthy']:
                report['problems'].append(f"unhealthy containers at {sample['seconds']}s: {sample['docker']['unhealthy']}")
            statuses = {run_id: ops.sql(f"select status from public.runs where id = '{run_id}';") for run_id in runs}
            for run_id, status in statuses.items():
                if last.get(run_id) != status:
                    print(f"{sample['seconds']}s: {run_id[:8]} {status}", flush=True)
                last[run_id] = status
            for index, worker in enumerate(workers, start=1):
                if worker.poll() is not None:
                    report['problems'].append(f'worker {index} exited with {worker.returncode} during the workload')
            if any(worker.poll() is not None for worker in workers) or (statuses and all(status in TERMINAL or status == 'paused' for status in statuses.values())):
                break
            spent = ops.sql(f"select coalesce(sum(coalesce(charged_micro_usd, reserved_micro_usd)), 0) from app_private.model_invocations where workspace_id = '{workspace}';")
            if spent and int(spent) > 2 * LIMIT_MICRO_USD:
                report['watchdog_fired'] = True
                report['problems'].append('the watchdog stopped the workers on spend')
                for worker in workers:
                    worker.send_signal(signal.SIGKILL)
                break
            time.sleep(SAMPLE_SECONDS)
        report['workload_seconds'] = round(time.monotonic() - started, 1)

        report['calls'] = rows(ops, "select run_id, attempt, role, profile, wire_id, status, failure_class, finish_reason, reserved_micro_usd, charged_micro_usd, "
                                    "extract(epoch from created_at) as start, extract(epoch from coalesce(finished_at, now())) as end "
                                    f"from app_private.model_invocations where workspace_id = '{workspace}' order by created_at")
        report['calls_overlap_seconds'] = overlap_seconds(report['calls'])
        report['worker_of_each_run'] = rows(ops, f"select run_id, lease_owner, generation, status from app_private.run_jobs where run_id in ('{runs[0]}', '{runs[1]}')")
        for run_id in runs:
            finished[run_id] = ops.sql(f"select status from public.runs where id = '{run_id}';")
            code, reply = api_call(api_port, ops.internal, token, 'GET', f'/v1/runs/{run_id}')
            through_api = json.loads(reply).get('status') if code == 200 else f'unread {code}'
            if through_api != finished[run_id]:
                report['problems'].append(f'the API says {through_api} and the database {finished[run_id]}')
            if finished[run_id] not in TERMINAL:
                report['problems'].append(f'a run was left {finished[run_id]}')
            value = ops.sql(f"select coalesce(sum(charged_micro_usd), 0) from app_private.model_invocations where run_id = '{run_id}' or root_run_id = '{run_id}';")
            unsettled = ops.sql(f"select count(*) from app_private.model_invocations where (run_id = '{run_id}' or root_run_id = '{run_id}') and charged_micro_usd is null;")
            charged[run_id] = int(value) if value and unsettled == '0' else None
        report['final_status'] = finished
        report['stop_reasons'] = rows(ops, f"select run_id, stop_reason, model_calls from app_private.run_usage where run_id in ('{runs[0]}', '{runs[1]}')")
        report['uncertain_causes'] = [json.loads(line) for path in logs.glob('worker-*.log') for line in path.read_text(errors='replace').splitlines() if 'diagnosis.uncertain_cause' in line]
        report['charged_micro_usd'] = charged
        report['verifications'] = rows(ops, f"select run_id, passed, unmet from app_private.run_verifications where run_id in ('{runs[0]}', '{runs[1]}') order by created_at")
        written = '\n'.join(path.read_text(errors='replace') for path in logs.glob('*.log'))
        report['step_failures_in_logs'] = written.count('worker.step_failed')
        if report['step_failures_in_logs']:
            report['problems'].append(f"{report['step_failures_in_logs']} worker steps failed")
        for index, worker in enumerate(workers, start=1):
            if worker.poll() is None:
                worker.send_signal(signal.SIGTERM)
                report[f'worker_{index}_exit'] = exited(worker, 60)
        if paid:
            durable, logged = helper('leaks', str(key_file), str(logs)).split()
            report['key_found'] = {'durable_rows': int(durable), 'log_files': int(logged)}
            if int(durable) or int(logged):
                report['problems'].append('the key was found in a durable row or log')
    finally:
        samples = report['samples']
        report['peaks'] = {group: {field: peaks(samples, group, field) for field in ('cpu_percent', 'rss_kb', 'tcp_connections')} for group in ('api', 'ui', 'worker_1', 'worker_2')}
        report['peaks']['docker'] = {field: peaks(samples, 'docker', field) for field in ('cpu_percent', 'memory_mib')}
        report['peaks']['database_connections'] = max((item['database_connections'] for item in samples), default=None)
        if samples:
            report['disk_growth_kb'] = samples[-1]['disk_used_kb'] - samples[0]['disk_used_kb']
            report['database_growth_kb'] = samples[-1]['database_kb'] - samples[0]['database_kb']
        ops.stop_all()
        remove_stack(stack)
        subprocess.run(['rm', '-rf', str(config_root)], check=False)
        label = f'label=com.docker.compose.project={project}'
        left = (run(['docker', 'volume', 'ls', '--filter', label, '--format', '{{.Name}}'], tool_env()).stdout
                + run(['docker', 'ps', '-a', '--filter', label, '--format', '{{.Names}}'], tool_env()).stdout).strip()
        report['left_behind'] = left or 'none'
        report['other_docker_unchanged'] = before_resources == other_resources(project)
        if paid:
            # A run that isn't finished can spend again on resume, so its whole budget stays held.
            for ledger, entry, run_id in ((ledger_a, entry_a, runs[0] if runs else None), (ledger_b, entry_b, runs[1] if len(runs) > 1 else None)):
                if run_id is None:
                    ledger.settle(entry, 0, 'not_started')
                elif finished.get(run_id) in TERMINAL and charged.get(run_id) is not None:
                    ledger.settle(entry, charged[run_id], 'settled')
                else:
                    ledger.settle(entry, None, 'run_not_finished')
            report['shared_ledger_committed_micro_usd'] = ledger_b.committed()
            time.sleep(60)  # OpenRouter's figure can lag, so this checks the ledger and doesn't replace it.
            try:
                report['key_usage_after_usd'] = float(helper('usage', str(key_file)))
            except (Unavailable, ValueError) as error:
                report['key_usage_after_usd'] = f'unread: {type(error).__name__}'
        if not report['problems'] and report.get('calls') is not None:
            overlapped = report.get('calls_overlap_seconds', 0) > 0
            report['verdict'] = 'stable' if overlapped else 'not_measured'
        else:
            report['verdict'] = 'failed'
        name = 'result' if paid else 'rehearsal'
        (out / f'{name}-{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")}.json').write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps({key: report.get(key) for key in ('verdict', 'problems', 'final_status', 'stop_reasons', 'uncertain_causes', 'calls_overlap_seconds', 'charged_micro_usd', 'peaks', 'workload_seconds', 'key_usage_before_usd',
                                                       'key_usage_after_usd', 'shared_ledger_committed_micro_usd', 'key_found', 'left_behind', 'other_docker_unchanged', 'worker_of_each_run', 'step_failures_in_logs', 'disk_growth_kb', 'database_growth_kb')}, indent=1, default=str))
    return 0 if report['verdict'] == 'stable' else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--rehearse', action='store_true', help='a fake transport, and no spending')
    mode.add_argument('--paid', action='store_true', help='billed OpenRouter calls')
    parser.add_argument('--key-file', type=Path, default=Path('.env'))
    parser.add_argument('--ledger', type=Path, default=Path('.checks/decision-0009/ledger.json'))
    arguments = parser.parse_args()
    out = ROOT / '.checks/US-12.4'
    out.mkdir(parents=True, exist_ok=True)
    try:
        return attempt(ROOT, arguments.paid, (ROOT / arguments.key_file).resolve(), ROOT / arguments.ledger, out)
    except Refused as refused:
        print(f'REFUSED: {refused}', file=sys.stderr)
        return 1
    except Unavailable as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
