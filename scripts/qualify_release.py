#!/usr/bin/env python3
"""US-10.1: the protocol corpus, the held-out tasks and the local benchmark, on one disposable stack.

This spends money. It refuses without --paid, and nothing in `verify.py` runs it. Goals run one at a time
through the real API and worker with the application's default model, and only the GitHub connector's
destination is fake. It refuses the next goal if the worst case could pass the authorized total, so the
total can't be overrun by more than OpenRouter's own reporting. The stack is removed at the end. Exit 0
the run finished, whatever it measured, 1 it stopped early, 2 a prerequisite is missing.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import signal
import statistics
import subprocess
import tempfile
import time

from app_db import AppStack, apply_migrations, bootstrap, seed
from disposable_db import PROJECT_PREFIX, Target, Unavailable, free_port, other_resources, remove_stack, require_identity, run, tool_env
from harness_lib import fingerprint, project_root
from live_goal import HELPER, TRACING, rows
from qualify_identity import PYTHON, STORAGE_SQL, bootstrap_owner, password_token
from qualify_operations import Ops, api_call, exited, wait
from release_scoring import percentile, safety_failures, score, summarize
from supabase_stack import generated_values, require_images, require_rendered

# The user's go-ahead: "Full run, up to US$5".
AUTHORIZED_TOTAL_MICRO_USD = 5_000_000
# Each goal's own budget, so the worst case of the next goal is known before it starts.
GOAL_LIMIT_MICRO_USD = 250_000
GOAL_SECONDS = 300
FINAL = {'succeeded', 'failed', 'cancelled'}
PROTOCOL = {'plain_text': 9, 'tool_auto': 9, 'tool_required': 9, 'tool_named_conflict': 9, 'schema_flat': 8, 'schema_nested_closed': 8,
            'stream_text': 8, 'stream_tool_arguments': 8, 'continuation': 8, 'truncation': 8, 'refusal': 8, 'cancellation': 8}
UNCERTAIN = {'uncertain_model_call', 'uncertain_acceptance', 'partial_stream'}
WORKER = 'tests/qualification/worker.py'
ADMIT = 'tests/qualification/helper.py'


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--paid', action='store_true', help='required: this makes billed OpenRouter calls')
    parser.add_argument('--key-file', default='.env')
    parser.add_argument('--tasks', default='tests/qualification/tasks.json')
    parser.add_argument('--trials', type=int, default=3)
    parser.add_argument('--protocol', action='store_true', help='also run the 100 protocol cases')
    parser.add_argument('--out', default='.checks/release')
    parser.add_argument('--already-spent-micro-usd', type=int, default=0, help='spend under the same authorization, from earlier runs')
    arguments = parser.parse_args()
    if not arguments.paid:
        print('REFUSED: this makes billed calls, and needs --paid')
        return 2
    root = project_root()
    try:
        return attempt(root, arguments, (root / arguments.key_file).resolve())
    except Unavailable as error:
        print(f'ERROR: {error}')
        return 2


def attempt(root: Path, arguments: argparse.Namespace, key_file: Path) -> int:
    out = root / arguments.out
    logs = out / 'logs'
    logs.mkdir(parents=True, exist_ok=True)
    corpus = (root / arguments.tasks).read_bytes()
    tasks = json.loads(corpus)
    project = f'{PROJECT_PREFIX}{secrets.token_hex(4)}'
    gateway_port = free_port()
    db_port = free_port([gateway_port])
    api_port = free_port([gateway_port, db_port])
    target = Target(project, db_port, gateway_port)
    stack = AppStack(target, root, root / 'infra/supabase/upstream/docker-compose.yml', values=generated_values(gateway_port, db_port))
    stack.migrator_password, stack.runtime_password = secrets.token_hex(24), secrets.token_hex(24)
    require_identity(target, tool_env())
    require_images(require_rendered(stack))
    config_root = Path(tempfile.mkdtemp(prefix='autobots-release-'))
    ops = Ops(root, stack, f'http://127.0.0.1:{gateway_port}', db_port, logs)
    for name in TRACING:
        ops.env.pop(name, None)
    provider_env = {'AUTOBOTS_CONFIG_ROOT': str(config_root), 'NODE_ENV': 'production', 'AUTOBOTS_PROVIDER_MASTER_KEY_FILE': str(config_root / 'secrets/master.key')}
    sink = config_root / 'github-issues.jsonl'
    before_resources = other_resources(project)

    def helper(*argv: str) -> str:
        done = subprocess.run([str(root / PYTHON), str(root / HELPER), *argv], env={**ops.env, **provider_env}, capture_output=True, text=True, errors='replace', timeout=120, check=False)
        if done.returncode:
            raise Unavailable(f'{argv[0]} failed: {done.stderr.strip().splitlines()[-1][:300] if done.stderr.strip() else "no detail"}')
        return done.stdout.strip()

    report: dict = {'schema_version': 'autobots.release-qualification/v1', 'started_at_utc': datetime.now(timezone.utc).isoformat(), 'evidence_class': 'live, on a disposable stack',
                    'input_fingerprint': fingerprint(root), 'git_head': run(['git', 'rev-parse', 'HEAD'], tool_env()).stdout.strip(),
                    'corpus': arguments.tasks, 'corpus_sha256': hashlib.sha256(corpus).hexdigest(), 'tasks': len(tasks), 'trials': arguments.trials,
                    'authorized_total_micro_usd': AUTHORIZED_TOTAL_MICRO_USD, 'load_average_at_start': os.getloadavg(),
                    'not_established': ['H1', 'product acceptance', 'real GitHub behavior', 'tasks chosen independently of the author']}
    (out / 'manifest.json').write_text(json.dumps(report, indent=2))
    report['key_usage_before_usd'] = float(helper('usage', str(key_file)))
    spent = arguments.already_spent_micro_usd
    results: list[dict] = []
    stopped = ''
    worker = None
    code = 0

    def start_worker() -> subprocess.Popen:
        return ops.spawn('worker', [str(root / PYTHON), str(root / WORKER)], {**provider_env, 'AUTOBOTS_WORKER_INFERENCE': 'enabled', 'AUTOBOTS_TEST_SINK': str(sink)})

    try:
        if stack.compose('up', '-d', '--wait', '--wait-timeout', '240', timeout=300).returncode:
            raise Unavailable('the stack did not start')
        bootstrap(stack, root)
        _, problem = apply_migrations(stack, root / 'supabase/migrations')
        if problem or seed(stack, root).returncode or stack.sql((root / STORAGE_SQL).read_text()).returncode:
            raise Unavailable(f'the database setup failed: {problem}')
        email, password = 'owner@example.invalid', secrets.token_urlsafe(24)
        workspace = bootstrap_owner(root, ops.base, stack.values['SERVICE_ROLE_KEY'], ops.url, email, password)['workspace_id']
        token = password_token(ops.base, stack.values['ANON_KEY'], email, password)[1]
        ops.api(api_port, config_root)
        wait(lambda: api_call(api_port, ops.internal, token)[0] == 200, 40)
        helper('save', str(key_file), workspace)

        def call(method: str, path: str, body: dict | None = None) -> tuple[int, str]:
            return api_call(api_port, ops.internal, token, method, path, json.dumps(body).encode() if body is not None else None, {'Idempotency-Key': secrets.token_hex(8)} if method == 'POST' else {})

        def issues_since(start: int) -> list[dict]:
            return [json.loads(line) for line in sink.read_text().splitlines()][start:] if sink.exists() else []

        def run_task(task: dict, trial: int) -> dict:
            nonlocal worker
            mode = task.get('mode', '')
            start_issues = len(issues_since(0))
            started = time.monotonic()
            if mode in {'approve', 'reject'}:
                admitted = subprocess.run([str(root / PYTHON), str(root / ADMIT), workspace, str(GOAL_LIMIT_MICRO_USD), json.dumps(task)], env=ops.env, capture_output=True, text=True, errors='replace', timeout=60, check=False)
                if admitted.returncode:
                    raise Unavailable(f'admission failed: {admitted.stderr.strip()[-300:]}')
                run_id = admitted.stdout.strip().splitlines()[-1]
            else:
                code_, reply = call('POST', '/v1/runs', {'goal_text': task['goal'], 'limit_micro_usd': GOAL_LIMIT_MICRO_USD, 'required_artifacts': [{'name': task['artifact']}],
                                                         'input_documents': [{'path': path, 'content': content} for path, content in task['documents'].items()]})
                if code_ != 202:
                    raise Unavailable(f'the API refused a goal: {code_} {reply[:200]}')
                run_id = json.loads(reply)['run_id']
            approved = interventions = 0
            killed_at = recovery = None
            while time.monotonic() - started < GOAL_SECONDS:
                status = ops.sql(f"select status from public.runs where id = '{run_id}';")
                usage = (rows(ops, f"select model_calls, stop_reason from app_private.run_usage where run_id = '{run_id}'") or [{}])[0]
                if status in FINAL:
                    break
                if worker is not None and worker.poll() is not None and killed_at is None:
                    raise Unavailable(f'the worker exited early: {worker.returncode}')
                if status == 'waiting_approval':
                    for item in json.loads(call('GET', '/v1/approvals')[1])['approvals']:
                        if item['run_id'] == run_id:
                            decision = 'reject' if mode == 'reject' else 'approve'
                            call('POST', f"/v1/approvals/{item['id']}/decision", {'decision': decision, 'argument_hash': item['argument_hash']})
                            approved += decision == 'approve'
                if mode == 'restart' and killed_at is None and (usage.get('model_calls') or 0) >= 2:
                    worker.send_signal(signal.SIGKILL)
                    worker.wait(timeout=10)
                    killed_at = time.monotonic()
                    calls_then = usage.get('model_calls') or 0
                    worker = start_worker()
                if killed_at is not None and recovery is None and (usage.get('model_calls') or 0) > calls_then:
                    recovery = round(time.monotonic() - killed_at, 1)
                if status == 'paused':
                    if usage.get('stop_reason') in UNCERTAIN and interventions < 3:
                        # What an owner would do: record the worst case, as the provider's charge isn't known here.
                        held = (rows(ops, f"select coalesce(sum(reserved_micro_usd), 0) as held from app_private.model_invocations where root_run_id = '{run_id}' and status = 'uncertain'") or [{}])[0].get('held') or 0
                        call('POST', f'/v1/runs/{run_id}/model-calls/reconcile', {'charged_micro_usd': int(held)})
                        version = (rows(ops, f"select version from public.runs where id = '{run_id}'") or [{}])[0].get('version')
                        call('POST', f'/v1/runs/{run_id}/resume', {'expected_version': version})
                        interventions += 1
                    else:
                        break
                time.sleep(1)
            status = ops.sql(f"select status from public.runs where id = '{run_id}';")
            if status not in FINAL:
                version = (rows(ops, f"select version from public.runs where id = '{run_id}'") or [{}])[0].get('version')
                call('POST', f'/v1/runs/{run_id}/cancel', {'expected_version': version})
            usage = (rows(ops, f"select model_calls, tool_dispatches, repairs, stop_reason from app_private.run_usage where run_id = '{run_id}'") or [{}])[0]
            invocations = rows(ops, f"select attempt, profile, status, failure_class, finish_reason, input_tokens, output_tokens, reasoning_tokens, tool_names, invalid_tool_calls, reserved_micro_usd, charged_micro_usd, round(extract(epoch from finished_at - created_at)::numeric, 1) as seconds from app_private.model_invocations where root_run_id = '{run_id}' order by created_at")
            observed = {'status': status, 'stop_reason': usage.get('stop_reason'), 'invocations': invocations,
                        'receipts': rows(ops, f"select tool_id, status, failure_code, failure_detail from app_private.tool_receipts where run_id = '{run_id}' order by created_at"),
                        'verifications': rows(ops, f"select passed, unmet from app_private.run_verifications where run_id = '{run_id}' order by created_at"),
                        'files': rows(ops, f"select path, version, content from app_private.run_files where run_id = '{run_id}' order by created_at"),
                        'published': rows(ops, f"select name, status from public.artifacts where run_id = '{run_id}'"),
                        'issues': issues_since(start_issues), 'approved': approved,
                        'duplicate_receipts': int(ops.sql(f"select count(*) from (select tool_id, argument_hash from app_private.tool_receipts where run_id = '{run_id}' and status = 'succeeded' group by 1, 2 having count(*) > 1) d;") or 0)}
            charged = sum(call_.get('charged_micro_usd') or 0 for call_ in invocations)
            held = sum(call_.get('reserved_micro_usd') or 0 for call_ in invocations if call_.get('charged_micro_usd') is None)
            return {**observed, 'task': task['id'], 'trial': trial, 'category': task['category'], 'adversarial': bool(task.get('adversarial')), 'mode': mode, 'run_id': run_id,
                    'seconds': round(time.monotonic() - started, 1), 'charged': charged, 'held': held, 'repairs': usage.get('repairs'), 'interventions': interventions, 'recovery_seconds': recovery,
                    'reasons': score(task, observed), 'safety': safety_failures(task, observed)}

        if arguments.protocol:
            protocol_out = out / 'protocol'
            done = subprocess.run([str(root / PYTHON), '-m', 'autobots.operations.route_qualification', '--paid', '--profile', 'openai_gpt_6_1_terra', '--key-file', str(key_file), '--out', str(protocol_out),
                                   '--only', ','.join(f'{name}={count}' for name, count in PROTOCOL.items())],
                                  env={**tool_env(), 'PYTHONPATH': str(root / 'services/agent/src'), 'PYTHONDONTWRITEBYTECODE': '1'}, cwd=root, capture_output=True, text=True, errors='replace', timeout=1800, check=False)
            (logs / 'protocol.log').write_text(done.stdout[-4000:] + done.stderr[-4000:])
            print(f'protocol exit {done.returncode}', flush=True)
            found = sorted(protocol_out.glob('report*rerun.json'))
            if found:
                protocol = json.loads(found[-1].read_text())
                report['protocol'] = {key: protocol[key] for key in ('summary', 'calls', 'committed_micro_usd', 'reported_micro_usd', 'calls_without_a_reported_charge')}
                spent += protocol['committed_micro_usd']
                cases = [trial for trial in protocol['trials']]
                report['protocol']['cases'] = len(cases)
                report['protocol']['passed'] = sum(1 for trial in cases if trial['verdict'] == 'passed')
            else:
                report['protocol'] = {'error': f'exit {done.returncode}, no report'}
            print(f"protocol: {report['protocol'].get('passed')}/{report['protocol'].get('cases')}, running total {spent}", flush=True)

        worker = start_worker()
        results_file = (out / 'results.jsonl').open('a')
        for trial in range(1, arguments.trials + 1):
            for task in tasks:
                if spent + GOAL_LIMIT_MICRO_USD > AUTHORIZED_TOTAL_MICRO_USD:
                    stopped = f'the next goal could pass the authorized total, at {spent} micro-USD'
                    break
                result = run_task(task, trial)
                spent += result['charged'] + result['held']
                results.append(result)
                results_file.write(json.dumps(result, default=str) + '\n')
                results_file.flush()
                print(f"{task['id']}/{trial}: {'PASS' if not result['reasons'] else 'FAIL ' + ';'.join(result['reasons'])[:150]}{' SAFETY ' + str(result['safety']) if result['safety'] else ''}, {result['seconds']}s, charged {result['charged']}, total {spent}", flush=True)
            if stopped:
                break
        results_file.close()

        # The local benchmark, with no model and no worker claiming.
        if worker.poll() is None:
            worker.send_signal(signal.SIGTERM)
            report['worker_exit'] = exited(worker, 60)
        last = results[-1]['run_id'] if results else None
        bench: dict = {'load_average': os.getloadavg(), 'workload': 'one client, sequential requests over loopback, after the corpus, with the worker stopped'}
        reads: list[float] = []
        for _ in range(200):
            began = time.perf_counter()
            call('GET', f'/v1/runs/{last}')
            reads.append(time.perf_counter() - began)
        admissions: list[float] = []
        cancels: list[float] = []
        events: list[float] = []
        for index in range(40):
            began = time.perf_counter()
            code_, reply = call('POST', '/v1/runs', {'goal_text': f'Benchmark {index}', 'limit_micro_usd': 1000})
            admissions.append(time.perf_counter() - began)
            run_id = json.loads(reply)['run_id']
            version = json.loads(call('GET', f'/v1/runs/{run_id}')[1]).get('version', 1)
            began = time.perf_counter()
            cancel_code = call('POST', f'/v1/runs/{run_id}/cancel', {'expected_version': version})[0]
            cancels.append(time.perf_counter() - began)
            count = len(json.loads(call('GET', f'/v1/runs/{run_id}/events')[1]).get('events', []))
            if cancel_code < 300 and count >= 2:
                events.append(time.perf_counter() - began)
        recoveries = [item['recovery_seconds'] for item in results if item.get('recovery_seconds') is not None]
        bench.update({'api_read_p95_ms': round((percentile(reads, 0.95) or 0) * 1000, 1), 'api_read_median_ms': round(statistics.median(reads) * 1000, 1), 'api_reads': len(reads),
                      'admission_p95_ms': round((percentile(admissions, 0.95) or 0) * 1000, 1), 'cancel_ack_p95_ms': round((percentile(cancels, 0.95) or 0) * 1000, 1),
                      'committed_event_readable_p95_ms': round((percentile(events, 0.95) or 0) * 1000, 1), 'events_measured': len(events),
                      'recoveries': len(recoveries), 'recovery_seconds_max': max(recoveries) if recoveries else None,
                      'restarted_goals_without_a_measured_recovery': sum(1 for item in results if item['mode'] == 'restart' and item.get('recovery_seconds') is None)})
        stats = subprocess.run(['docker', 'stats', '--no-stream', '--format', '{{.Name}} {{.MemUsage}}'], env=tool_env(), capture_output=True, text=True, timeout=60, check=False).stdout
        bench['container_memory'] = [line for line in stats.splitlines() if project in line]
        report['benchmark'] = bench
        report['summary'] = summarize(results)
        report['cost_per_goal_micro_usd'] = {'median': statistics.median(item['charged'] for item in results) if results else None, 'max': max((item['charged'] for item in results), default=None)}
        durable, logged = helper('leaks', str(key_file), str(logs)).split()
        report['key_found'] = {'durable_rows': int(durable), 'log_files': int(logged)}
        written = '\n'.join(path.read_text(errors='replace') for path in logs.glob('*.log'))
        report['step_failures_in_logs'] = written.count('worker.step_failed')
    except Unavailable as error:
        stopped = str(error)
    finally:
        report['spent_micro_usd'] = spent
        report['stopped'] = stopped
        ops.stop_all()
        remove_stack(stack)
        subprocess.run(['rm', '-rf', str(config_root)], check=False)
        label = f'label=com.docker.compose.project={project}'
        report['left_behind'] = (run(['docker', 'volume', 'ls', '--filter', label, '--format', '{{.Name}}'], tool_env()).stdout + run(['docker', 'ps', '-a', '--filter', label, '--format', '{{.Names}}'], tool_env()).stdout).strip() or 'none'
        report['other_docker_unchanged'] = before_resources == other_resources(project)
        report['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        try:
            time.sleep(60)
            report['key_usage_after_usd'] = float(helper('usage', str(key_file)))
        except Unavailable as error:
            report['key_usage_after_usd'] = f'unread: {error}'
        (out / 'report.json').write_text(json.dumps(report, indent=2, default=str))
    if stopped:
        print(f'STOPPED: {stopped}')
        code = 1
    print(json.dumps({key: report.get(key) for key in ('summary', 'protocol', 'benchmark', 'spent_micro_usd', 'key_usage_before_usd', 'key_usage_after_usd', 'key_found', 'left_behind', 'other_docker_unchanged')}, indent=1, default=str)[:6000])
    return code


if __name__ == '__main__':
    raise SystemExit(main())
