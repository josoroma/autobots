#!/usr/bin/env python3
"""US-10.1: the protocol corpus, the held-out tasks and the local benchmark, on one disposable stack.

This spends money. It refuses without --paid and a stated cap, and nothing in `verify.py` runs it. Goals
run one at a time through the real API and worker with the application's default model, and only the
GitHub connector's destination is fake. It refuses the next goal if the worst case could pass the cap, so
the cap can't be overrun by more than OpenRouter's own reporting. Resources are sampled while goals run,
and --ui adds the real web app and a browser timing of committed events. --trials 0 runs no goal, so it
makes no model call, for trying the rest for free. A goal whose spend can't be read, or that stops
before it is read, counts its whole budget and stops the corpus, and a protocol run whose report is
missing leaves its spend unknown, so no goal starts after it (Decision 0028 E2). The helper, the sign-in
and the worker are the paid session's (scripts/paid_run.py). The stack is removed at the end. Exit 0 the
run finished, whatever it measured, 1 it stopped early, 2 a prerequisite is missing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import shutil
import signal
import statistics
import subprocess
import tempfile
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from urllib import error as urlerror
from urllib import request as urlrequest

from app_db import AppStack, apply_migrations, bootstrap, seed
from disposable_db import (
    PROJECT_PREFIX,
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
from live_goal import TRACING, disposable_session
from paid_run import PaidSession
from qualify_identity import PYTHON, STORAGE_SQL, bootstrap_owner
from qualify_operations import Ops, api_call, wait
from qualify_web import BROWSERS, start, stop, wait_until_up
from qualify_web import free_port as any_port
from release_scoring import (
    docker_totals,
    percentile,
    process_totals,
    safety_failures,
    score,
    summarize,
    summarize_resources,
)
from suites import RELEASE_PROJECT
from supabase_stack import generated_values, require_images, require_rendered
from toolchain import child_env, find_tools

SAMPLE_SECONDS = 5
# Each goal's own budget, so the worst case of the next goal is known before it starts.
GOAL_LIMIT_MICRO_USD = 250_000
GOAL_SECONDS = 300
FINAL = {'succeeded', 'failed', 'cancelled'}
PROTOCOL = {'plain_text': 9, 'tool_auto': 9, 'tool_required': 9, 'tool_named_conflict': 9, 'schema_flat': 8, 'schema_nested_closed': 8,
            'stream_text': 8, 'stream_tool_arguments': 8, 'continuation': 8, 'truncation': 8, 'refusal': 8, 'cancellation': 8}
UNCERTAIN = {'uncertain_model_call', 'uncertain_acceptance', 'partial_stream'}
WORKER = 'tests/qualification/worker.py'
ADMIT = 'tests/qualification/helper.py'
PROTOCOL_REPORTS = 'report*rerun.json'
PROTOCOL_FIELDS = ('summary', 'calls', 'committed_micro_usd', 'reported_micro_usd', 'calls_without_a_reported_charge')
# call(method, path, body=None): one API request as the owner, answered with its status and body.
Call = Callable[..., tuple[int, str]]


@dataclass
class GoalStack:
    """What one corpus goal uses of its disposable stack: the owner's workspace and API, the runtime
    role's SQL (Ops.sql, '' when unreadable), the paid session's rows and worker, the fake GitHub
    destination's issues, and a way to start a worker again after the restart task kills one."""

    root: Path
    workspace: str
    env: Mapping[str, str]
    sql: Callable[[str], str]
    session: PaidSession
    call: Call
    issues_since: Callable[[int], list[dict]]
    restart_worker: Callable[[], None]
    clock: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep


def run_task(stack: GoalStack, task: dict, trial: int) -> dict:
    """One corpus goal through the real API, or the admission helper for an approval task, and the worker,
    read back from the ledger. A goal whose model calls can't be read is `spend_unknown`, and counts its
    whole budget as charged, so the cost summary never shows it cheaper than it may have been and the
    corpus stops after it (Decision 0028 E2)."""
    session, sql, call = stack.session, stack.sql, stack.call
    mode = task.get('mode', '')
    start_issues = len(stack.issues_since(0))
    started = stack.clock()
    if mode in {'approve', 'reject'}:
        admitted = subprocess.run([str(stack.root / PYTHON), str(stack.root / ADMIT), stack.workspace, str(GOAL_LIMIT_MICRO_USD), json.dumps(task)], env=dict(stack.env), capture_output=True, text=True, errors='replace', timeout=60, check=False)
        if admitted.returncode:
            raise Unavailable(f'admission failed: {admitted.stderr.strip()[-300:]}')
        run_id = admitted.stdout.strip().splitlines()[-1]
    else:
        admission, reply = call('POST', '/v1/runs', {'goal_text': task['goal'], 'limit_micro_usd': GOAL_LIMIT_MICRO_USD, 'required_artifacts': [{'name': task['artifact']}],
                                                     'input_documents': [{'path': path, 'content': content} for path, content in task['documents'].items()]})
        if admission != 202:
            raise Unavailable(f'the API refused a goal: {admission} {reply[:200]}')
        run_id = json.loads(reply)['run_id']
    approved = interventions = calls_then = 0
    killed_at = recovery = reclaimed = None
    killed_generation = 0
    lease_left = 0.0
    while stack.clock() - started < GOAL_SECONDS:
        status = sql(f"select status from public.runs where id = '{run_id}';")
        usage = (session.rows(f"select model_calls, stop_reason from app_private.run_usage where run_id = '{run_id}'") or [{}])[0]
        if status in FINAL:
            break
        worker = session.worker
        if worker is not None and worker.poll() is not None and killed_at is None:
            raise Unavailable(f'the worker exited early: {worker.poll()}')
        if status == 'waiting_approval':
            for item in json.loads(call('GET', '/v1/approvals')[1])['approvals']:
                if item['run_id'] == run_id:
                    decision = 'reject' if mode == 'reject' else 'approve'
                    call('POST', f"/v1/approvals/{item['id']}/decision", {'decision': decision, 'argument_hash': item['argument_hash']})
                    approved += decision == 'approve'
        if mode == 'restart' and killed_at is None and worker is not None and (usage.get('model_calls') or 0) >= 2:
            worker.send_signal(signal.SIGKILL)
            worker.wait(timeout=10)
            killed_at = stack.clock()
            calls_then = usage.get('model_calls') or 0
            # Read after the kill, as no heartbeat can move the expiry from here on.
            leases = session.rows(f"select generation, round(extract(epoch from lease_expires_at - now())::numeric, 1) as left_seconds from app_private.run_jobs where run_id = '{run_id}'")
            if not leases:
                raise Unavailable("the killed worker's lease could not be read")
            killed_generation, lease_left = int(leases[0]['generation']), float(leases[0]['left_seconds'] or 0)
            stack.restart_worker()
        if killed_at is not None and reclaimed is None and int((session.rows(f"select generation from app_private.run_jobs where run_id = '{run_id}'") or [{}])[0].get('generation') or 0) > killed_generation:
            reclaimed = round(stack.clock() - killed_at - lease_left, 1)
        if killed_at is not None and recovery is None and (usage.get('model_calls') or 0) > calls_then:
            recovery = round(stack.clock() - killed_at, 1)
        if status == 'paused':
            if usage.get('stop_reason') in UNCERTAIN and interventions < 3:
                # What an owner would do: record the worst case, as the provider's charge isn't known here.
                held = (session.rows(f"select coalesce(sum(reserved_micro_usd), 0) as held from app_private.model_invocations where root_run_id = '{run_id}' and status = 'uncertain'") or [{}])[0].get('held') or 0
                call('POST', f'/v1/runs/{run_id}/model-calls/reconcile', {'charged_micro_usd': int(held)})
                version = (session.rows(f"select version from public.runs where id = '{run_id}'") or [{}])[0].get('version')
                call('POST', f'/v1/runs/{run_id}/resume', {'expected_version': version})
                interventions += 1
            else:
                break
        stack.sleep(1)
    status = sql(f"select status from public.runs where id = '{run_id}';")
    if status not in FINAL:
        version = (session.rows(f"select version from public.runs where id = '{run_id}'") or [{}])[0].get('version')
        call('POST', f'/v1/runs/{run_id}/cancel', {'expected_version': version})
    usage = (session.rows(f"select model_calls, tool_dispatches, repairs, stop_reason from app_private.run_usage where run_id = '{run_id}'") or [{}])[0]
    invocations = session.rows(f"select attempt, profile, status, failure_class, finish_reason, input_tokens, output_tokens, reasoning_tokens, tool_names, invalid_tool_calls, reserved_micro_usd, charged_micro_usd, round(extract(epoch from finished_at - created_at)::numeric, 1) as seconds from app_private.model_invocations where root_run_id = '{run_id}' order by created_at")
    observed = {'status': status, 'stop_reason': usage.get('stop_reason'), 'invocations': invocations or [],
                'receipts': session.rows(f"select tool_id, status, failure_code, failure_detail from app_private.tool_receipts where run_id = '{run_id}' order by created_at") or [],
                'verifications': session.rows(f"select passed, unmet from app_private.run_verifications where run_id = '{run_id}' order by created_at") or [],
                'files': session.rows(f"select path, version, content from app_private.run_files where run_id = '{run_id}' order by created_at") or [],
                'published': session.rows(f"select name, status from public.artifacts where run_id = '{run_id}'") or [],
                'issues': stack.issues_since(start_issues), 'approved': approved,
                'duplicate_receipts': int(sql(f"select count(*) from (select tool_id, argument_hash from app_private.tool_receipts where run_id = '{run_id}' and status = 'succeeded' group by 1, 2 having count(*) > 1) d;") or 0)}
    if invocations is None:
        # Unknown spend fails closed (Decision 0028 E2): the goal's whole budget is its charge.
        charged, held = GOAL_LIMIT_MICRO_USD, 0
    else:
        charged = sum(call_.get('charged_micro_usd') or 0 for call_ in invocations)
        held = sum(call_.get('reserved_micro_usd') or 0 for call_ in invocations if call_.get('charged_micro_usd') is None)
    return {**observed, 'task': task['id'], 'trial': trial, 'spend_unknown': invocations is None, 'category': task['category'], 'adversarial': bool(task.get('adversarial')), 'mode': mode, 'run_id': run_id,
            'seconds': round(stack.clock() - started, 1), 'charged': charged, 'held': held, 'repairs': usage.get('repairs'), 'interventions': interventions, 'recovery_seconds': recovery, 'reclaim_after_lease_expiry_seconds': reclaimed,
            'reasons': score(task, observed), 'safety': safety_failures(task, observed)}


@dataclass
class Corpus:
    """The running total under the user's cap. The next goal starts only if its whole budget still fits.
    A goal counts its whole budget until its spend is read, so one that raises first is never left out
    of `spent` (Decision 0028 E2): it is recorded as `interrupted` and the corpus stops."""

    authorized: int
    spent: int
    results: list[dict] = field(default_factory=list)
    interrupted: dict | None = None

    def run(self, tasks: list[dict], trials: int, goal: Callable[[dict, int], dict], keep: Callable[[dict], None]) -> str:
        """Each task once per trial, in order. Answers why the corpus stopped early, or '' when it didn't."""
        for trial in range(1, trials + 1):
            for task in tasks:
                if self.spent + GOAL_LIMIT_MICRO_USD > self.authorized:
                    return f'the next goal could pass the authorized total, at {self.spent} micro-USD'
                try:
                    result = goal(task, trial)
                except BaseException as failure:
                    self.spent += GOAL_LIMIT_MICRO_USD
                    self.interrupted = {'task': task['id'], 'trial': trial, 'counted_micro_usd': GOAL_LIMIT_MICRO_USD, 'failed_with': type(failure).__name__}
                    raise
                self.spent += result['charged'] + result['held']
                self.results.append(result)
                keep(result)
                print(f"{task['id']}/{trial}: {'PASS' if not result['reasons'] else 'FAIL ' + ';'.join(result['reasons'])[:150]}{' SAFETY ' + str(result['safety']) if result['safety'] else ''}, {result['seconds']}s, charged {result['charged']}, total {self.spent}", flush=True)
                if result['spend_unknown']:
                    return f"the spend of {task['id']}/{trial} could not be read, so it counts its whole budget and no further goal starts"
        return ''

    def interruption(self) -> str:
        """Why the corpus stopped, when a goal raised before its spend was read, or ''."""
        if self.interrupted is None:
            return ''
        return f"{self.interrupted['task']}/{self.interrupted['trial']} stopped before its spend was read, so it counts its whole budget"


def protocol_reports(folder: Path) -> dict[Path, int]:
    """Each protocol report already in `folder`, by modification time, so one an earlier run left can't
    stand in for this run's."""
    return {path: path.stat().st_mtime_ns for path in folder.glob(PROTOCOL_REPORTS)}


def protocol_result(folder: Path, earlier: Mapping[Path, int], returncode: int) -> tuple[dict, str]:
    """The protocol run's summary from the report it wrote, and why the corpus stops, or ''. A report
    that is missing, left from before this run or unreadable leaves the run's spend unknown, so no goal
    starts after it (Decision 0028 E2)."""
    written = sorted(path for path in folder.glob(PROTOCOL_REPORTS) if earlier.get(path) != path.stat().st_mtime_ns)
    try:
        protocol = json.loads(written[-1].read_text())
        section = {key: protocol[key] for key in PROTOCOL_FIELDS}
        cases = list(protocol['trials'])
        section['cases'] = len(cases)
        section['passed'] = sum(1 for trial in cases if trial['verdict'] == 'passed')
        readable = isinstance(section['committed_micro_usd'], int)
    except (IndexError, OSError, ValueError, KeyError, TypeError):
        readable = False
    if not readable:
        return ({'error': f'exit {returncode}, and no readable report from this run', 'spend_unknown': True},
                f'the protocol run left no readable report (exit {returncode}), so its spend is unknown and no goal starts')
    return section, ''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--paid', action='store_true', help='required: this makes billed OpenRouter calls')
    parser.add_argument('--key-file', default='.env')
    parser.add_argument('--tasks', default='tests/qualification/tasks.json')
    parser.add_argument('--trials', type=int, default=3)
    parser.add_argument('--protocol', action='store_true', help='also run the 100 protocol cases')
    parser.add_argument('--authorized-micro-usd', type=int, required=True, help="the user's cap for this run, as each go-ahead covers only its own")
    parser.add_argument('--ui', action='store_true', help='also run the web app and time events in a browser')
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
    raw_corpus = (root / arguments.tasks).read_bytes()
    tasks = json.loads(raw_corpus)
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
    session = disposable_session(root, ops, provider_env)
    before_resources = other_resources(project)

    report: dict = {'schema_version': 'autobots.release-qualification/v1', 'started_at_utc': datetime.now(UTC).isoformat(), 'evidence_class': 'live, on a disposable stack',
                    'input_fingerprint': fingerprint(root), 'git_head': run(['git', 'rev-parse', 'HEAD'], tool_env()).stdout.strip(),
                    'corpus': arguments.tasks, 'corpus_sha256': hashlib.sha256(raw_corpus).hexdigest(), 'tasks': len(tasks), 'trials': arguments.trials,
                    'authorized_total_micro_usd': arguments.authorized_micro_usd, 'load_average_at_start': os.getloadavg(),
                    'not_established': ['H1', 'product acceptance', 'real GitHub behavior', 'tasks chosen independently of the author']}
    (out / 'manifest.json').write_text(json.dumps(report, indent=2))
    report['key_usage_before_usd'] = float(session.helper('usage', str(key_file)))
    corpus = Corpus(arguments.authorized_micro_usd, arguments.already_spent_micro_usd)
    results = corpus.results
    stopped = ''
    web = None
    web_url = ''
    code = 0
    samples: list[dict] = []
    sampling = threading.Event()

    def probe(url: str) -> tuple[bool, float]:
        began = time.perf_counter()
        try:
            with urlrequest.urlopen(url, timeout=4) as reply:
                healthy = reply.status < 500
        except urlerror.HTTPError as failure:
            healthy = failure.code < 500
        except OSError:
            healthy = False
        return healthy, round((time.perf_counter() - began) * 1000, 1)

    def sample_resources() -> None:
        with (out / 'resources.jsonl').open('a') as raw:
            while not sampling.wait(SAMPLE_SECONDS):
                stats = subprocess.run(['docker', 'stats', '--no-stream', '--format', '{{json .}}'], env=tool_env(), capture_output=True, text=True, timeout=30, check=False).stdout
                processes = subprocess.run(['ps', '-A', '-o', 'pgid=,pcpu=,rss='], capture_output=True, text=True, timeout=10, check=False).stdout
                groups = {process.pid for process in ops.processes if process.poll() is None} | ({web.pid} if web is not None and web.poll() is None else set())
                sample = {**docker_totals(stats.splitlines(), project), **process_totals(processes.splitlines(), groups),
                          'connections': int(ops.sql('select count(*) from pg_stat_activity where datname is not null;') or 0),
                          'database_mib': round(int(ops.sql('select pg_database_size(current_database());') or 0) / 2 ** 20, 1),
                          'host_free_gib': round(shutil.disk_usage(root).free / 2 ** 30, 2)}
                sample['api_up'], sample['api_probe_ms'] = probe(f'http://127.0.0.1:{api_port}/v1/health')
                if web_url:
                    sample['ui_up'], sample['ui_probe_ms'] = probe(f'{web_url}/sign-in')
                samples.append(sample)
                raw.write(json.dumps(sample) + '\n')
                raw.flush()

    sampler = threading.Thread(target=sample_resources, daemon=True)

    def start_worker() -> None:
        session.start_worker([str(root / PYTHON), str(root / WORKER)], {'AUTOBOTS_TEST_SINK': str(sink)})

    try:
        tools = find_tools(root)
        web_dir = root / 'apps/web'
        browser_env = {**child_env(root, tools, verifying=True), 'PLAYWRIGHT_BROWSERS_PATH': str(root / BROWSERS)}
        if arguments.ui:
            if not any((root / BROWSERS).glob('chromium-*')):
                raise Unavailable(f'no browser under {BROWSERS}; install the pinned one deliberately')
            built = subprocess.run([str(web_dir / 'node_modules/.bin/next'), 'build'], env=browser_env, cwd=web_dir, capture_output=True, text=True, errors='replace', timeout=300, check=False)
            if built.returncode:
                raise Unavailable(f'the web app did not build: {built.stdout[-300:]}')
        if stack.compose('up', '-d', '--wait', '--wait-timeout', '240', timeout=300).returncode:
            raise Unavailable('the stack did not start')
        bootstrap(stack, root)
        _, problem = apply_migrations(stack, root / 'supabase/migrations')
        if problem or seed(stack, root).returncode or stack.sql((root / STORAGE_SQL).read_text()).returncode:
            raise Unavailable(f'the database setup failed: {problem}')
        email, password = 'owner@example.invalid', secrets.token_urlsafe(24)
        workspace = bootstrap_owner(root, ops.base, stack.values['SERVICE_ROLE_KEY'], ops.url, email, password)['workspace_id']
        token = session.sign_in(ops.base, stack.values['ANON_KEY'], email, password)
        ops.api(api_port, config_root)
        wait(lambda: api_call(api_port, ops.internal, token)[0] == 200, 40)
        session.helper('save', str(key_file), workspace)
        if arguments.ui:
            web_port = any_port()
            web_url = f'http://127.0.0.1:{web_port}'
            web = start([str(web_dir / 'node_modules/.bin/next'), 'start', '-H', '127.0.0.1', '-p', str(web_port)],
                        {**browser_env, 'AUTOBOTS_INTERNAL_TOKEN': ops.internal, 'AUTOBOTS_API_URL': f'http://127.0.0.1:{api_port}', 'AUTOBOTS_ALLOWED_ORIGIN': web_url, 'NODE_ENV': 'production',
                         'AUTOBOTS_SUPABASE_URL': ops.base, 'AUTOBOTS_SUPABASE_ANON_KEY': stack.values['ANON_KEY']}, web_dir)
            wait_until_up(web_url, web)
        sampler.start()

        def call(method: str, path: str, body: dict | None = None) -> tuple[int, str]:
            return api_call(api_port, ops.internal, token, method, path, json.dumps(body).encode() if body is not None else None, {'Idempotency-Key': secrets.token_hex(8)} if method == 'POST' else {})

        def issues_since(start: int) -> list[dict]:
            return [json.loads(line) for line in sink.read_text().splitlines()][start:] if sink.exists() else []

        if arguments.protocol:
            protocol_out = out / 'protocol'
            earlier = protocol_reports(protocol_out)
            done = subprocess.run([str(root / PYTHON), '-m', 'autobots.operations.route_qualification', '--paid', '--profile', 'openai_gpt_6_1_terra', '--key-file', str(key_file), '--out', str(protocol_out),
                                   '--only', ','.join(f'{name}={count}' for name, count in PROTOCOL.items())],
                                  env={**tool_env(), 'PYTHONPATH': str(root / 'services/agent/src'), 'PYTHONDONTWRITEBYTECODE': '1'}, cwd=root, capture_output=True, text=True, errors='replace', timeout=1800, check=False)
            (logs / 'protocol.log').write_text(done.stdout[-4000:] + done.stderr[-4000:])
            print(f'protocol exit {done.returncode}', flush=True)
            report['protocol'], stopped = protocol_result(protocol_out, earlier, done.returncode)
            corpus.spent += report['protocol'].get('committed_micro_usd') or 0
            print(f"protocol: {report['protocol'].get('passed')}/{report['protocol'].get('cases')}, running total {corpus.spent}", flush=True)

        if not stopped:
            start_worker()
            goals = GoalStack(root, workspace, ops.env, ops.sql, session, call, issues_since, start_worker)
            with (out / 'results.jsonl').open('a') as results_file:

                def keep(result: dict) -> None:
                    results_file.write(json.dumps(result, default=str) + '\n')
                    results_file.flush()

                stopped = corpus.run(tasks, arguments.trials, lambda task, trial: run_task(goals, task, trial), keep)

        # The local benchmark, with no model and no worker claiming.
        session.stop_worker(report)
        last = results[-1]['run_id'] if results else None
        bench: dict = {'load_average': os.getloadavg(), 'workload': 'one client, sequential requests over loopback, after the corpus, with the worker stopped'}
        reads: list[float] = []
        for _ in range(200 if last else 0):
            began = time.perf_counter()
            call('GET', f'/v1/runs/{last}')
            reads.append(time.perf_counter() - began)
        admissions: list[float] = []
        cancels: list[float] = []
        events: list[float] = []
        for index in range(40):
            began = time.perf_counter()
            _code, reply = call('POST', '/v1/runs', {'goal_text': f'Benchmark {index}', 'limit_micro_usd': 1000})
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
        bench.update({'api_read_p95_ms': round((percentile(reads, 0.95) or 0) * 1000, 1), 'api_read_median_ms': round(statistics.median(reads) * 1000, 1) if reads else None, 'api_reads': len(reads),
                      'admission_p95_ms': round((percentile(admissions, 0.95) or 0) * 1000, 1), 'cancel_ack_p95_ms': round((percentile(cancels, 0.95) or 0) * 1000, 1),
                      'committed_event_readable_p95_ms': round((percentile(events, 0.95) or 0) * 1000, 1), 'events_measured': len(events),
                      'recoveries': len(recoveries), 'recovery_seconds_max': max(recoveries) if recoveries else None,
                      'reclaim_after_lease_expiry_seconds': [item['reclaim_after_lease_expiry_seconds'] for item in results if item.get('reclaim_after_lease_expiry_seconds') is not None],
                      'restarted_goals_without_a_measured_recovery': sum(1 for item in results if item['mode'] == 'restart' and item.get('recovery_seconds') is None)})
        stats = subprocess.run(['docker', 'stats', '--no-stream', '--format', '{{.Name}} {{.MemUsage}}'], env=tool_env(), capture_output=True, text=True, timeout=60, check=False).stdout
        bench['container_memory'] = [line for line in stats.splitlines() if project in line]
        if arguments.ui:
            latency_file = out / 'ui-latency.json'
            latency_file.unlink(missing_ok=True)
            played = subprocess.run([str(web_dir / 'node_modules/.bin/playwright'), 'test', '--project', RELEASE_PROJECT, '--config', 'playwright.config.ts'], cwd=web_dir, capture_output=True, text=True, errors='replace', timeout=300, check=False,
                                    env={**browser_env, 'AUTOBOTS_WEB_URL': web_url, 'AUTOBOTS_TEST_OWNER_EMAIL': email, 'AUTOBOTS_TEST_OWNER_PASSWORD': password, 'AUTOBOTS_RELEASE_LATENCY_OUT': str(latency_file),
                                         'AUTOBOTS_WEB_REPORT': str(out / 'playwright.json'), 'AUTOBOTS_WEB_OUTPUT': str(out / 'playwright-results')})
            (logs / 'playwright.log').write_text(played.stdout[-4000:] + played.stderr[-4000:])
            if played.returncode or not latency_file.exists():
                stopped = '; '.join(filter(None, (stopped, f'the browser timing failed with {played.returncode}')))
            else:
                timed = json.loads(latency_file.read_text())
                shown = [item['shown_ms'] for item in timed]
                bench.update({'ui_event_samples': len(timed), 'ui_event_p95_ms': round(percentile(shown, 0.95) or 0, 1), 'ui_event_median_ms': round(statistics.median(shown), 1), 'ui_event_max_ms': round(max(shown), 1),
                              'ui_cancel_ack_p95_ms': round(percentile([item['ack_ms'] for item in timed], 0.95) or 0, 1)})
        report['benchmark'] = bench
        report['resources'] = summarize_resources(samples)
        report['summary'] = summarize(results) if results else None
        # A goal whose spend is unknown is in these at its whole budget (run_task), and counted here.
        report['cost_per_goal_micro_usd'] = {'median': statistics.median(item['charged'] for item in results) if results else None, 'max': max((item['charged'] for item in results), default=None),
                                             'goals_at_their_whole_budget': sum(1 for item in results if item['spend_unknown'])}
        durable, logged = session.helper('leaks', str(key_file), str(logs)).split()
        report['key_found'] = {'durable_rows': int(durable), 'log_files': int(logged)}
        written = '\n'.join(path.read_text(errors='replace') for path in logs.glob('*.log'))
        report['step_failures_in_logs'] = written.count('worker.step_failed')
    except Unavailable as error:
        # Kept with any earlier stop, so a later failure can't hide why the corpus stopped.
        stopped = '; '.join(filter(None, (stopped, str(error))))
    finally:
        # Whatever a goal raised, it is in the total at its whole budget, and the report says which.
        if corpus.interrupted is not None:
            report['interrupted_goal'] = corpus.interrupted
            stopped = '; '.join(filter(None, (stopped, corpus.interruption())))
        report['spent_micro_usd'] = corpus.spent
        report['stopped'] = stopped
        sampling.set()
        if sampler.is_alive():
            sampler.join(40)
        if 'resources' not in report and samples:
            report['resources'] = summarize_resources(samples)
        if web is not None:
            stop(web)
        ops.stop_all()
        remove_stack(stack)
        subprocess.run(['rm', '-rf', str(config_root)], check=False)
        label = f'label=com.docker.compose.project={project}'
        report['left_behind'] = (run(['docker', 'volume', 'ls', '--filter', label, '--format', '{{.Name}}'], tool_env()).stdout + run(['docker', 'ps', '-a', '--filter', label, '--format', '{{.Names}}'], tool_env()).stdout).strip() or 'none'
        report['other_docker_unchanged'] = before_resources == other_resources(project)
        report['finished_at_utc'] = datetime.now(UTC).isoformat()
        try:
            time.sleep(60)
            report['key_usage_after_usd'] = float(session.helper('usage', str(key_file)))
        except Unavailable as error:
            report['key_usage_after_usd'] = f'unread: {error}'
        (out / 'report.json').write_text(json.dumps(report, indent=2, default=str))
    if stopped:
        print(f'STOPPED: {stopped}')
        code = 1
    print(json.dumps({key: report.get(key) for key in ('summary', 'protocol', 'benchmark', 'resources', 'spent_micro_usd', 'key_usage_before_usd', 'key_usage_after_usd', 'key_found', 'left_behind', 'other_docker_unchanged')}, indent=1, default=str)[:6000])
    return code


if __name__ == '__main__':
    raise SystemExit(main())
