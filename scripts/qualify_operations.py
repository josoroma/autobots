#!/usr/bin/env python3
"""Exercises the operations runbook on a new disposable Compose project, standing in for the persistent one.

Named volumes survive `compose stop` here exactly as they would there, and that is all this shows about
the persistent stack, which isn't configured on this machine. No model is called: a scripted fixture
stands in for one. Exit 0 passed, 1 a case failed, 2 a prerequisite is missing.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import signal
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import IO
from urllib import error, request

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
from qualification.children import run_child_check, service_env
from qualification.records import Cases, write_report
from qualify_identity import PYTHON, STORAGE_SQL, bootstrap_owner, http, password_token
from supabase_stack import generated_values, require_images, require_rendered

REPORT = Path('.checks/operations/qualification.json')
# Where a failed child check's stderr is kept (qualification/children.py).
ERR_DIR = Path('.checks/operations')
LOG_SECRET = 'sk-or-v1-planted-log-secret'
TRACE_KEY = 'lsv2-planted-trace-key'
# The operations, backup and upgrade qualifiers' fixture workers run a scripted model (verify.STEP_CLASSES).
MODEL_TRANSPORT = 'mock'
# Cases.check shows any observed value as text and reads `passed` for its truth.
Checks = Cases


class Ops:
    """The API and worker processes of one run of this script, each logging to its own local file."""

    def __init__(self, root: Path, stack: AppStack, base: str, db_port: int, logs: Path) -> None:
        self.root, self.stack, self.base, self.logs = root, stack, base, logs
        self.url = f'postgresql://autobots_runtime:{stack.runtime_password}@127.0.0.1:{db_port}/postgres'
        self.internal = secrets.token_hex(24)
        self.processes: list[subprocess.Popen] = []
        self.handles: list[IO[str]] = []
        self.env = service_env(root, self.url, AUTOBOTS_SUPABASE_URL=base, AUTOBOTS_SERVICE_ROLE_KEY=stack.values['SERVICE_ROLE_KEY'],
                               AUTOBOTS_STORAGE_BASE=base, AUTOBOTS_STORAGE_SERVICE=stack.values['SERVICE_ROLE_KEY'], AUTOBOTS_MIN_FREE_BYTES='1',
                               # Arranged: what a host might have exported. The bootstrap has to turn it off.
                               LANGSMITH_TRACING='true', LANGCHAIN_TRACING_V2='true', LANGSMITH_API_KEY=TRACE_KEY,
                               LANGSMITH_ENDPOINT='https://collector.example.invalid')

    def spawn(self, name: str, argv: list[str], extra: dict[str, str] | None = None) -> subprocess.Popen:
        handle = (self.logs / f'{name}.log').open('a')
        self.handles.append(handle)
        process = subprocess.Popen(argv, env={**self.env, **(extra or {})}, cwd=self.root, stdin=subprocess.DEVNULL,
                                   stdout=handle, stderr=handle, start_new_session=True)
        self.processes.append(process)
        return process

    def api(self, port: int, config_root: Path, extra: dict[str, str] | None = None) -> subprocess.Popen:
        api_env = {'AUTOBOTS_INTERNAL_TOKEN': self.internal, 'AUTOBOTS_JWT_SECRET': self.stack.values['JWT_SECRET'],
                   'AUTOBOTS_CONFIG_ROOT': str(config_root), 'NODE_ENV': 'production',
                   'AUTOBOTS_PROVIDER_MASTER_KEY_FILE': str(config_root / 'secrets/master.key'), **(extra or {})}
        return self.spawn(f'api-{port}', [str(self.root / PYTHON), '-m', 'uvicorn', '--factory', 'autobots.api.main:create_configured_app',
                                          '--host', '127.0.0.1', '--port', str(port), '--no-access-log'], api_env)

    def fixture_worker(self, name: str, hold: float, drain: float, marker: Path, mode: str = 'fresh', profile: str | None = None) -> subprocess.Popen:
        return self.spawn(name, [str(self.root / PYTHON), str(self.root / 'tests/db/operations_worker.py'), self.url, name, str(hold), str(drain), str(marker), mode],
                          {'AUTOBOTS_TEST_ROUTE_PROFILE': profile} if profile else None)

    def sql(self, statement: str) -> str:
        result = self.stack.runtime(statement)
        return result.stdout.strip().splitlines()[0] if result.returncode == 0 and result.stdout.strip() else ''

    def admit(self, workspace: str) -> str:
        result = subprocess.run([str(self.root / PYTHON), str(self.root / 'tests/db/operations_check.py'), 'admit', workspace], env=self.env,
                                capture_output=True, text=True, timeout=60, check=False)
        lines = result.stdout.strip().splitlines()
        if result.returncode or not lines:
            raise Unavailable(f'the fixture job was not admitted: exit {result.returncode}: {result.stderr.strip()[-300:]}')
        return lines[-1]

    def stop_all(self) -> None:
        for process in self.processes:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(10)
        for handle in self.handles:
            handle.close()


def api_call(port: int, internal: str, token: str, method: str = 'GET', path: str = '/v1/operations/local-status',
             body: bytes | None = None, extra: dict[str, str] | None = None) -> tuple[int, str]:
    headers = {'X-Autobots-Internal': internal, 'Authorization': f'Bearer {token}', 'Content-Type': 'application/json', **(extra or {})}
    try:
        with request.urlopen(request.Request(f'http://127.0.0.1:{port}{path}', data=body, method=method, headers=headers), timeout=20) as reply:
            return reply.status, reply.read().decode(errors='replace')
    except error.HTTPError as failure:
        return failure.code, failure.read().decode(errors='replace')


def conditions(body: str) -> dict[str, str]:
    return {item['name']: item['code'] for item in json.loads(body)['conditions']}


def wait(check, seconds: float) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            if check():
                return True
        except (OSError, ValueError, KeyError):
            pass
        time.sleep(0.5)
    return False


def exited(process: subprocess.Popen, seconds: float) -> int | None:
    try:
        return process.wait(seconds)
    except subprocess.TimeoutExpired:
        return None


def durable_counts(ops: Ops) -> str:
    return ops.sql("select (select count(*) from public.runs) || '/' || (select count(*) from public.run_events) || '/' || "
                   "(select count(*) from app_private.tool_receipts) || '/' || (select count(*) from agent_runtime.checkpoints) || '/' || "
                   "(select count(*) from app_private.idempotency_receipts);")


def qualify(root: Path) -> int:
    project = f'{PROJECT_PREFIX}{secrets.token_hex(4)}'
    gateway_port = free_port()
    db_port = free_port([gateway_port])
    api_port = free_port([gateway_port, db_port])
    low_port = free_port([gateway_port, db_port, api_port])
    target = Target(project, db_port, gateway_port)
    stack = AppStack(target, root, root / 'infra/supabase/upstream/docker-compose.yml', values=generated_values(gateway_port, db_port))
    stack.migrator_password, stack.runtime_password = secrets.token_hex(24), secrets.token_hex(24)
    require_identity(target, tool_env())
    if run(['docker', 'info', '--format', '{{.ServerVersion}}'], tool_env(), 30).returncode:
        raise Unavailable('the Docker engine is not reachable')
    (root / REPORT).unlink(missing_ok=True)
    rendered = require_rendered(stack)
    require_images(rendered)
    cases = Checks(model_transport=MODEL_TRANSPORT)
    before = other_resources(project)
    started_at = time.monotonic()
    base = f'http://127.0.0.1:{gateway_port}'
    anon = stack.values['ANON_KEY']
    logs = root / '.checks/operations/logs'
    logs.mkdir(parents=True, exist_ok=True)
    for old in logs.glob('*.log'):
        old.unlink()
    config_root = Path(tempfile.mkdtemp(prefix='autobots-ops-'))
    ops = Ops(root, stack, base, db_port, logs)
    email_a, email_b, email_c = 'owner-a@example.invalid', 'owner-b@example.invalid', 'member-c@example.invalid'
    password_a, password_b, password_c = secrets.token_urlsafe(24), secrets.token_urlsafe(24), secrets.token_urlsafe(24)
    goal = json.dumps({'goal_text': 'Write the report', 'limit_micro_usd': 1000000}).encode()
    try:
        # The order LM-07 states: infrastructure, migrations, contracts, then workers and UI.
        started = stack.compose('up', '-d', '--wait', '--wait-timeout', '240', timeout=300)
        if started.returncode:
            raise Unavailable(f'the stack did not start: {started.stderr[-300:]}')
        bootstrap(stack, root)
        applied, problem = apply_migrations(stack, root / 'supabase/migrations')
        if problem or seed(stack, root).returncode:
            raise Unavailable(f'migrations failed: {problem}')
        stored = stack.sql((root / STORAGE_SQL).read_text())
        cases.check('infrastructure is healthy before migrations and processes', 'exit 0', f'{applied} migrations, storage exit {stored.returncode}', stored.returncode == 0)
        owner_a = bootstrap_owner(root, base, stack.values['SERVICE_ROLE_KEY'], ops.url, email_a, password_a)
        owner_b = bootstrap_owner(root, base, stack.values['SERVICE_ROLE_KEY'], ops.url, email_b, password_b)
        owner_c = bootstrap_owner(root, base, stack.values['SERVICE_ROLE_KEY'], ops.url, email_c, password_c)
        workspace_a, workspace_b = owner_a['workspace_id'], owner_b['workspace_id']
        cases.arrange('member C in workspace A',
                      stack.runtime(f"insert into public.workspace_members (workspace_id, user_id, role) values ('{workspace_a}', '{owner_c['user_id']}', 'member');"))
        token_a = password_token(base, anon, email_a, password_a)[1]
        token_b = password_token(base, anon, email_b, password_b)[1]
        token_c = password_token(base, anon, email_c, password_c)[1]
        # The member also owns a workspace of their own, so the header names which one is asked about.
        as_a = {'X-Autobots-Workspace': workspace_a}

        ops.api(api_port, config_root)
        up = wait(lambda: api_call(api_port, ops.internal, token_a)[0] == 200, 40)
        status_code, body = api_call(api_port, ops.internal, token_a)
        cases.check('readiness is reported once processes are up', '200 and ready', f'{status_code}, {up}', status_code == 200 and json.loads(body)['ready'] is True)
        cases.check('no worker reads as visibly absent', 'worker_absent', conditions(body).get('worker'), conditions(body).get('worker') == 'worker_absent')
        cases.check('inherited tracing settings are turned off at bootstrap', 'disabled', json.loads(body)['remote_tracing'], json.loads(body)['remote_tracing'] == 'disabled')
        # The declared checkpoint adapter (Decision 0022 D5) names its package, langgraph-checkpoint-postgres.
        # It must be exactly that package and a release, checked on its own; only then is that one value set
        # aside, so 'postgres' anywhere else, such as in an address, still fails (Decision 0027 D10).
        adapter = str(json.loads(body).get('values', {}).get('checkpoint_adapter', ''))
        expected = re.fullmatch(r'langgraph-checkpoint-postgres \d+\.\d+\.\d+', adapter) is not None
        cases.check('the status names the checkpoint adapter package and its release', 'langgraph-checkpoint-postgres x.y.z',
                    adapter, expected)
        lowered = body.lower().replace(f'"{adapter.lower()}"', '""') if expected else body.lower()
        leaked = [word for word in ('127.0.0.1', 'postgres', stack.runtime_password.lower(), 'service_role', 'langsmith', 'jwt', workspace_a) if word in lowered]
        cases.check('the status body has no address, secret or identifier', 'none', leaked or 'none', not leaked)
        code, reply = api_call(api_port, ops.internal, token_a, 'POST', '/v1/runs', goal, {'Idempotency-Key': secrets.token_hex(8)})
        cases.check('when ready, admission passes the readiness gate', '409 credentials_required, not 503', f'{code} {reply[:70]}', code == 409)
        code, _ = api_call(api_port, ops.internal, token_c, extra=as_a)
        cases.check('a member cannot read Operations', '403', code, code == 403)
        code, _ = api_call(api_port, 'wrong', token_a)
        cases.check('the internal token is still required', '401', code, code == 401)

        # The product worker: it owns no model client, so it can't move a queued job and says so.
        marker = config_root / 'in-call'
        queued = ops.admit(workspace_a)
        product = ops.spawn('product-worker', [str(root / PYTHON), '-m', 'autobots.operations.worker'])
        beating = wait(lambda: ops.sql("select count(*) from app_private.worker_heartbeats where state = 'running';") == '1', 20)
        code, body = api_call(api_port, ops.internal, token_a)
        cases.check('the product worker starts and beats', 'one running heartbeat', beating, beating)
        cases.check('queued work without an inference worker is visible', 'no_inference_worker', conditions(body).get('worker'), conditions(body).get('worker') == 'no_inference_worker')
        queue_a = json.loads(body)['queue']
        code_b, body_b = api_call(api_port, ops.internal, token_b)
        queue_b = json.loads(body_b)['queue'] if code_b == 200 else None
        cases.check("counts stay in the caller's workspace", 'A 1 queued, B 0', f'{queue_a}, {queue_b}', queue_a['queued'] == 1 and queue_b is not None and queue_b['queued'] == 0)
        claimed = ops.sql(f"select status from app_private.run_jobs where run_id = '{queued}';")
        cases.check('the product worker never claims a job', 'queued', claimed, claimed == 'queued')
        product.send_signal(signal.SIGTERM)
        exit_code = exited(product, 20)
        last = ops.sql("select state from app_private.worker_heartbeats limit 1;")
        cases.check('the product worker stops on SIGTERM and says so', 'exit 0, stopped', f'{exit_code}, {last}', exit_code == 0 and last == 'stopped')

        # Drain: a real goal loop in the product's serve loop, stopped inside a model call.
        finishing = ops.fixture_worker('drain-worker', 3, 30, marker)
        in_call = wait(marker.exists, 40)
        finishing.send_signal(signal.SIGTERM)
        draining = wait(lambda: ops.sql("select state from app_private.worker_heartbeats where worker_id = 'drain-worker';") == 'draining', 3)
        exit_code = exited(finishing, 60)
        outcome = ops.sql(f"select status from public.runs where id = '{queued}';")
        cases.check('SIGTERM inside a call drains instead of abandoning', 'draining, exit 0, run succeeded', f'in call {in_call}, draining {draining}, exit {exit_code}, {outcome}', in_call and draining and exit_code == 0 and outcome == 'succeeded')
        leases = ops.sql(f"select status || '/' || coalesce(lease_owner, 'none') from app_private.run_jobs where run_id = '{queued}';")
        cases.check('a drained job holds no lease', 'done/none', leases, leases == 'done/none')
        real_run = queued

        # A drain that runs out: the call outlives it, and the job is left for the next worker.
        marker.unlink(missing_ok=True)
        cut = ops.admit(workspace_a)
        cutting = ops.fixture_worker('cut-worker', 6, 1, marker)
        in_call = wait(marker.exists, 40)
        cutting.send_signal(signal.SIGTERM)
        exit_code = exited(cutting, 40)
        left = ops.sql(f"select r.status || '/' || j.status from public.runs r join app_private.run_jobs j on j.run_id = r.id where r.id = '{cut}';")
        cases.check('a drain past its bound exits and leaves the job recoverable', 'exit 0, running/claimed', f'{in_call}, {exit_code}, {left}', in_call and exit_code == 0 and left == 'running/claimed')
        expired = wait(lambda: conditions(api_call(api_port, ops.internal, token_a)[1]).get('queue') == 'leases_expired', 30)
        cases.check('the lost lease becomes visible', 'leases_expired', expired, expired)

        # Readiness failures, each observed through the API a person would use.
        stopped = stack.compose('stop', 'storage', timeout=120)
        down = wait(lambda: conditions(api_call(api_port, ops.internal, token_a)[1]).get('storage') == 'storage_unreachable', 30)
        _code_status, body = api_call(api_port, ops.internal, token_a)
        cases.check('Storage down is visible and not ready', 'storage_unreachable, ready false', f"{stopped.returncode}, {down}, {json.loads(body)['ready']}", down and json.loads(body)['ready'] is False)
        jobs = ops.sql('select count(*) from app_private.run_jobs;')
        code, reply = api_call(api_port, ops.internal, token_a, 'POST', '/v1/runs', goal, {'Idempotency-Key': secrets.token_hex(8)})
        after = ops.sql('select count(*) from app_private.run_jobs;')
        cases.check('admission stops with Storage down', '503 not_ready, no new job', f'{code}, {jobs} then {after}', code == 503 and 'not_ready' in reply and jobs == after)
        cases.arrange('Storage started again', stack.compose('start', 'storage', timeout=120))
        back = wait(lambda: json.loads(api_call(api_port, ops.internal, token_a)[1])['ready'] is True, 90)
        cases.check('readiness returns when Storage does', 'ready true', back, back)
        ops.api(low_port, config_root, {'AUTOBOTS_MIN_FREE_BYTES': str(2**62)})
        wait(lambda: api_call(low_port, ops.internal, token_a)[0] == 200, 40)
        code, body = api_call(low_port, ops.internal, token_a)
        admit_code, _ = api_call(low_port, ops.internal, token_a, 'POST', '/v1/runs', goal, {'Idempotency-Key': secrets.token_hex(8)})
        cases.check('low disk stops admission (arranged with an impossible minimum)', 'disk_low, 503', f"{conditions(body).get('disk')}, {admit_code}", conditions(body).get('disk') == 'disk_low' and admit_code == 503)

        # Ordinary shutdown: processes first, then containers. Everything durable has to come back.
        path = f'{workspace_a}/{real_run}/lifecycle/kept.txt'
        content = secrets.token_bytes(64)
        put, _ = http('POST', f'{base}/storage/v1/object/workspace-artifacts/{path}', {'apikey': stack.values['SERVICE_ROLE_KEY'], 'Authorization': f"Bearer {stack.values['SERVICE_ROLE_KEY']}", 'Content-Type': 'application/octet-stream'}, content)
        counts = durable_counts(ops)
        cases.arrange('a row written just before shutdown',
                      stack.runtime("insert into app_private.retention_log (workspace_id, action) select id, 'lifecycle_marker' from public.workspaces limit 1;"))
        halted = stack.compose('stop', timeout=180)
        volumes = run(['docker', 'volume', 'ls', '--filter', f'label=com.docker.compose.project={project}', '--format', '{{.Name}}'], tool_env()).stdout.split()
        cases.check('stopping the stack keeps its volumes', 'exit 0, volumes remain', f'{halted.returncode}, {len(volumes)} volumes', halted.returncode == 0 and len(volumes) > 0)
        code, body = api_call(api_port, ops.internal, token_a)
        reported = json.loads(body) if code == 200 else {}
        cases.check('with the database down the API still reports it', '200, database_unreachable, installation scope', f"{code}, {reported.get('scope')}, {conditions(body).get('database') if code == 200 else ''}", code == 200 and reported.get('scope') == 'installation' and conditions(body).get('database') == 'database_unreachable')
        code, reply = api_call(api_port, ops.internal, token_a, 'POST', '/v1/runs', goal, {'Idempotency-Key': secrets.token_hex(8)})
        cases.check('admission stops with the database down', '503 not_ready', f'{code} {reply[:60]}', code == 503 and 'not_ready' in reply)
        resumed_stack = stack.compose('up', '-d', '--wait', '--wait-timeout', '240', timeout=300)
        restored = durable_counts(ops)
        cases.check('records survive stop and start', counts, f'{resumed_stack.returncode}, {restored}', resumed_stack.returncode == 0 and restored == counts)
        marked = ops.sql("select count(*) from app_private.retention_log where action = 'lifecycle_marker';")
        cases.check('a row written just before shutdown survives it', '1', marked, marked == '1')
        got, data = -1, b''
        fetch = request.Request(f'{base}/storage/v1/object/workspace-artifacts/{path}', headers={'apikey': stack.values['SERVICE_ROLE_KEY'], 'Authorization': f"Bearer {stack.values['SERVICE_ROLE_KEY']}"})
        def read_object() -> bool:
            nonlocal got, data
            with request.urlopen(fetch, timeout=10) as reply_:
                got, data = reply_.status, reply_.read()
            return got == 200
        wait(read_object, 60)
        cases.check('Storage bytes survive stop and start', 'same bytes', f'put {put}, get {got}, same {data == content}', put == 200 and data == content)
        recovered = wait(lambda: json.loads(api_call(api_port, ops.internal, token_a)[1])['ready'] is True, 90)
        cases.check('the running API reconnects by itself', 'ready true', recovered, recovered)

        # Recovery: the job the bound cut short resumes from its checkpoint, with nothing repeated.
        receipts_before = ops.sql(f"select count(*) from app_private.tool_receipts where run_id = '{cut}';")
        marker.unlink(missing_ok=True)
        resuming = ops.fixture_worker('resume-worker', 0, 30, marker, 'resume')
        paused = wait(lambda: ops.sql(f"select status from public.runs where id = '{cut}';") == 'paused', 40)
        uncertain = ops.sql(f"select count(*) from app_private.model_invocations where run_id = '{cut}' and status = 'uncertain';")
        cases.check('a call cut off by shutdown waits for a person, not a blind retry', 'paused, 1 uncertain', f'{paused}, {uncertain}', paused and uncertain == '1')
        code, reply = api_call(api_port, ops.internal, token_a, 'POST', f'/v1/runs/{cut}/model-calls/reconcile', json.dumps({'charged_micro_usd': 100}).encode(), {'Idempotency-Key': secrets.token_hex(8)})
        cases.check('the owner reconciles it through the API', '200, one call', f'{code} {reply[:60]}', code == 200 and '"reconciled_calls":1' in reply)
        # Arranged: the route also requires a usable key, and none exists here, so this is the command it calls.
        resumed = subprocess.run([str(root / PYTHON), str(root / 'tests/db/operations_check.py'), 'resume', workspace_a, cut], env=ops.env, capture_output=True, text=True, timeout=60, check=False)
        finished = wait(lambda: ops.sql(f"select status from public.runs where id = '{cut}';") == 'succeeded', 60)
        resuming.send_signal(signal.SIGTERM)
        exit_code = exited(resuming, 30)
        duplicates = ops.sql(f"select count(*) from (select tool_id, argument_hash from app_private.tool_receipts where run_id = '{cut}' and status = 'succeeded' group by 1, 2 having count(*) > 1) d;")
        state = ops.sql(f"select r.status || '/' || j.status || '/' || j.attempts || '/' || coalesce((select payload::text from public.run_events e where e.run_id = r.id order by sequence desc limit 1), '') from public.runs r join app_private.run_jobs j on j.run_id = r.id where r.id = '{cut}';")
        cases.check('the interrupted job resumes after the restart', 'succeeded, exit 0, no repeated effect', f'resume exit {resumed.returncode}, {finished}, {exit_code}, {receipts_before} before, {duplicates} repeated, {state[:220]}', finished and exit_code == 0 and duplicates == '0')

        # Retention, on the real run finished above.
        run_child_check(cases, root, 'operations_check.py', 'retention', workspace_a, workspace_b, real_run, label='the retention check',
                        env=ops.env, timeout=240, err_dir=root / ERR_DIR, err_name='retention')
        code, _ = api_call(api_port, ops.internal, token_b, 'PUT', '/v1/operations/retention', json.dumps({'run_days': 30, 'receipt_days': 7}).encode())
        cases.check('a key window shorter than run content is refused', '422', code, code == 422)
        code, reply = api_call(api_port, ops.internal, token_b, 'PUT', '/v1/operations/retention', json.dumps({'run_days': 30, 'receipt_days': 30}).encode())
        applied_code, applied_body = api_call(api_port, ops.internal, token_b, 'POST', '/v1/operations/retention/apply')
        cases.check('an owner sets and applies retention through the API', '200, 200', f'{code}, {applied_code} {applied_body[:80]}', code == 200 and applied_code == 200)
        code, _ = api_call(api_port, ops.internal, token_c, 'POST', '/v1/operations/retention/apply', extra=as_a)
        cases.check('a member cannot apply retention', '403', code, code == 403)
        denied = stack.as_role('authenticated', owner_a['user_id'], f"select app_private.purge_run_content('{workspace_a}', '{real_run}', now())")
        cases.check('a signed-in role cannot call the purge function', 'permission denied', 'permission denied' if 'permission denied' in denied.stderr else f'exit {denied.returncode}', denied.returncode != 0 and 'permission denied' in denied.stderr)
        # The product worker's own pass, for the workspace that declared a window above.
        product = ops.spawn('product-worker-2', [str(root / PYTHON), '-m', 'autobots.operations.worker'])
        passed_retention = wait(lambda: 'retention.applied' in (logs / 'product-worker-2.log').read_text(errors='replace'), 30)
        product.send_signal(signal.SIGTERM)
        cases.check('the worker applies declared retention on its own pass', 'retention.applied, exit 0', f'{passed_retention}, {exited(product, 20)}', passed_retention and product.returncode == 0)

        # Graceful API stop, then what every process wrote.
        api_process = ops.processes[0]
        api_process.send_signal(signal.SIGTERM)
        api_exit = exited(api_process, 20)
        api_log = (logs / f'api-{api_port}.log').read_text(errors='replace')
        # uvicorn re-raises the signal once it has shut down, so its status is -15 after a clean stop.
        cases.check('the API stops cleanly on SIGTERM', 'shutdown complete', api_exit, api_exit in (0, -signal.SIGTERM) and 'Application shutdown complete' in api_log)
        written = {path_.name: path_.read_text(errors='replace') for path_ in logs.glob('*.log')}
        everything = '\n'.join(written.values())
        planted = [name for name, value in (('log secret', LOG_SECRET), ('trace key', TRACE_KEY), ('runtime password', stack.runtime_password),
                                            ('service key', stack.values['SERVICE_ROLE_KEY']), ('jwt secret', stack.values['JWT_SECRET']), ('internal token', ops.internal)) if value in everything]
        cases.check('no process log holds a secret, with one planted through the logger', 'none, and the planted line was written', f"{planted or 'none'}, {'[redacted]' in everything}", not planted and '[redacted]' in everything)
        worker_lines = [line for line in written.get('drain-worker.log', '').splitlines() if line.startswith('{')]
        events = [json.loads(line).get('event') for line in worker_lines]
        cases.check('worker logs are structured and name the lifecycle', 'started, draining, stopped', events, 'worker.started' in events and 'worker.draining' in events and 'worker.stopped' in events)
        cut_events = [json.loads(line).get('event') for line in written.get('cut-worker.log', '').splitlines() if line.startswith('{')]
        cases.check('a cut-short drain is logged', 'worker.drain_cut_short', cut_events, 'worker.drain_cut_short' in cut_events)
        config = stack.compose('config', timeout=60).stdout.lower()
        collectors = [word for word in ('langsmith', 'otel-collector', 'otlp', 'datadog', 'sentry') if word in config]
        cases.check('the merged Compose names no remote trace collector', 'none', collectors or 'none', not collectors)
    finally:
        ops.stop_all()
        remove_stack(stack)
        subprocess.run(['rm', '-rf', str(config_root)], check=False)
    label = f'label=com.docker.compose.project={project}'
    left = (run(['docker', 'volume', 'ls', '--filter', label, '--format', '{{.Name}}'], tool_env()).stdout
            + run(['docker', 'ps', '-a', '--filter', label, '--format', '{{.Names}}'], tool_env()).stdout).strip()
    cases.check('cleanup removed the owned containers and volumes', 'none left', left or 'none', not left)
    after_resources = other_resources(project)
    cases.check('other Docker resources are untouched', 'same', f'{len(before)} before, {len(after_resources)} after', before == after_resources)
    passed = cases.status == 'passed'
    write_report(root / REPORT, {'schema_version': 'autobots.operations-qualification/v1', 'completed_at_utc': datetime.now(UTC).isoformat(),
                                 'duration_seconds': round(time.monotonic() - started_at, 1), 'input_fingerprint': fingerprint(root),
                                 'status': cases.status, 'target_class': 'disposable', 'project': project, 'cases': cases.records,
                                 'not_established': ['H1', 'product acceptance', 'the persistent stack', 'a real model call', 'Mac sleep', 'resource use under load']})
    print(f'{"PASS" if passed else "FAIL"}: operations qualification, {round(time.monotonic() - started_at)}s, report {REPORT}')
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
