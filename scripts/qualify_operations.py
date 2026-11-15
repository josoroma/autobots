#!/usr/bin/env python3
"""Exercises the operations runbook on a new disposable Compose project, standing in for the persistent one.

Named volumes survive `compose stop` here exactly as they would there, and that is all this shows about
the persistent stack, which isn't configured on this machine. No model is called: a scripted fixture
stands in for one. Exit 0 passed, 1 a case failed, 2 a prerequisite is missing.

Each scenario is a function of one OperationsRun, run in the order SCENARIOS states, since later ones use the
runs earlier ones leave (refactor plan R-65, SCRP-05).
"""
from __future__ import annotations

import json
import re
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from urllib import request

from app_db import AppStack, app_project, apply_bootstrap, start_app
from disposable_db import Refused, Unavailable, run, tool_env
from harness_lib import project_root
from qualification.children import CHECK_PYTHON as PYTHON
from qualification.children import launch, run_child_check
from qualification.net import http
from qualification.ops import TRACE_KEY, Ops, api_call, conditions, durable_counts, exited, wait
from qualification.owners import bootstrap_owner, password_token
from qualification.records import Cases
from qualification.report import finish
from qualification.scenarios import run_scenarios

REPORT = Path('.checks/operations/qualification.json')
# Where a failed child check's stderr is kept (qualification/children.py).
ERR_DIR = Path('.checks/operations')
LOG_SECRET = 'sk-or-v1-planted-log-secret'
# The operations, backup and upgrade qualifiers' fixture workers run a scripted model (qualification/profiles.py).
MODEL_TRANSPORT = 'mock'
GOAL = json.dumps({'goal_text': 'Write the report', 'limit_micro_usd': 1000000}).encode()
EMAIL_A, EMAIL_B, EMAIL_C = 'owner-a@example.invalid', 'owner-b@example.invalid', 'member-c@example.invalid'


@dataclass
class OperationsRun:
    """What the scenarios share: the stack and its processes, the owners' workspaces and tokens, and the runs a
    scenario leaves for a later one."""

    root: Path
    stack: AppStack
    ops: Ops
    base: str
    api_port: int
    low_port: int
    config_root: Path
    logs: Path
    workspace_a: str = ''
    workspace_b: str = ''
    user_a: str = ''
    token_a: str = ''
    token_b: str = ''
    token_c: str = ''
    # The API process readiness starts, which the last scenario stops.
    api_process: subprocess.Popen[bytes] | None = None
    # Admitted while no inference worker runs, then finished by `drain`; shutdown and retention use it.
    queued: str = ''
    # Left recoverable by `cut_short_drain`, then resumed by `recovery`.
    cut: str = ''

    @property
    def marker(self) -> Path:
        return self.config_root / 'in-call'

    @property
    def as_a(self) -> dict[str, str]:
        """The member also owns a workspace of their own, so the header names which one is asked about."""
        return {'X-Autobots-Workspace': self.workspace_a}

    def status(self, token: str | None = None, port: int | None = None) -> tuple[int, str]:
        return api_call(port or self.api_port, self.ops.internal, token or self.token_a)

    def admit_goal(self, port: int | None = None) -> tuple[int, str]:
        return api_call(port or self.api_port, self.ops.internal, self.token_a, 'POST', '/v1/runs', GOAL, {'Idempotency-Key': secrets.token_hex(8)})


def infrastructure(run: OperationsRun, cases: Cases) -> None:
    """The order LM-07 states: infrastructure, migrations, contracts, then workers and UI."""
    stack, root = run.stack, run.root
    applied = start_app(stack, root)
    bootstrapped, stored = apply_bootstrap(stack, root)
    cases.check('infrastructure is healthy before migrations and processes', 'exit 0, the bootstrap files applied',
                f'{applied} migrations, bootstrap {bootstrapped}, {stored}', stored is None and bool(bootstrapped))
    passwords = {email: secrets.token_urlsafe(24) for email in (EMAIL_A, EMAIL_B, EMAIL_C)}
    owners = {email: bootstrap_owner(root, run.base, stack.values['SERVICE_ROLE_KEY'], run.ops.url, email, password)
              for email, password in passwords.items()}
    run.workspace_a, run.workspace_b = owners[EMAIL_A]['workspace_id'], owners[EMAIL_B]['workspace_id']
    run.user_a = owners[EMAIL_A]['user_id']
    cases.arrange('member C in workspace A',
                  stack.runtime(f"insert into public.workspace_members (workspace_id, user_id, role) values ('{run.workspace_a}', '{owners[EMAIL_C]['user_id']}', 'member');"))
    anon = stack.values['ANON_KEY']
    run.token_a, run.token_b, run.token_c = (password_token(run.base, anon, email, passwords[email])[1] for email in (EMAIL_A, EMAIL_B, EMAIL_C))


def readiness(run: OperationsRun, cases: Cases) -> None:
    ops = run.ops
    run.api_process = ops.api(run.api_port, run.config_root)
    up = wait(lambda: run.status()[0] == 200, 40)
    status_code, body = run.status()
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
    leaked = [word for word in ('127.0.0.1', 'postgres', run.stack.runtime_password.lower(), 'service_role', 'langsmith', 'jwt', run.workspace_a) if word in lowered]
    cases.check('the status body has no address, secret or identifier', 'none', leaked or 'none', not leaked)
    code, reply = run.admit_goal()
    cases.check('when ready, admission passes the readiness gate', '409 credentials_required, not 503', f'{code} {reply[:70]}', code == 409)
    code, _ = api_call(run.api_port, ops.internal, run.token_c, extra=run.as_a)
    cases.check('a member cannot read Operations', '403', code, code == 403)
    code, _ = api_call(run.api_port, 'wrong', run.token_a)
    cases.check('the internal token is still required', '401', code, code == 401)


def product_worker(run: OperationsRun, cases: Cases) -> None:
    """The product worker owns no model client, so it can't move a queued job, and says so."""
    ops = run.ops
    run.queued = ops.admit(run.workspace_a)
    product = ops.spawn('product-worker', [str(run.root / PYTHON), '-m', 'autobots.operations.worker'])
    beating = wait(lambda: ops.sql("select count(*) from app_private.worker_heartbeats where state = 'running';") == '1', 20)
    _code, body = run.status()
    cases.check('the product worker starts and beats', 'one running heartbeat', beating, beating)
    cases.check('queued work without an inference worker is visible', 'no_inference_worker', conditions(body).get('worker'), conditions(body).get('worker') == 'no_inference_worker')
    queue_a = json.loads(body)['queue']
    code_b, body_b = run.status(run.token_b)
    queue_b = json.loads(body_b)['queue'] if code_b == 200 else None
    cases.check("counts stay in the caller's workspace", 'A 1 queued, B 0', f'{queue_a}, {queue_b}', queue_a['queued'] == 1 and queue_b is not None and queue_b['queued'] == 0)
    claimed = ops.sql(f"select status from app_private.run_jobs where run_id = '{run.queued}';")
    cases.check('the product worker never claims a job', 'queued', claimed, claimed == 'queued')
    product.send_signal(signal.SIGTERM)
    exit_code = exited(product, 20)
    last = ops.sql("select state from app_private.worker_heartbeats limit 1;")
    cases.check('the product worker stops on SIGTERM and says so', 'exit 0, stopped', f'{exit_code}, {last}', exit_code == 0 and last == 'stopped')


def drain(run: OperationsRun, cases: Cases) -> None:
    """A real goal loop in the product's serve loop, stopped inside a model call."""
    ops = run.ops
    finishing = ops.fixture_worker('drain-worker', 3, 30, run.marker)
    in_call = wait(run.marker.exists, 40)
    finishing.send_signal(signal.SIGTERM)
    draining = wait(lambda: ops.sql("select state from app_private.worker_heartbeats where worker_id = 'drain-worker';") == 'draining', 3)
    exit_code = exited(finishing, 60)
    outcome = ops.sql(f"select status from public.runs where id = '{run.queued}';")
    cases.check('SIGTERM inside a call drains instead of abandoning', 'draining, exit 0, run succeeded', f'in call {in_call}, draining {draining}, exit {exit_code}, {outcome}', in_call and draining and exit_code == 0 and outcome == 'succeeded')
    leases = ops.sql(f"select status || '/' || coalesce(lease_owner, 'none') from app_private.run_jobs where run_id = '{run.queued}';")
    cases.check('a drained job holds no lease', 'done/none', leases, leases == 'done/none')


def cut_short_drain(run: OperationsRun, cases: Cases) -> None:
    """A drain that runs out: the call outlives it, and the job is left for the next worker."""
    ops = run.ops
    run.marker.unlink(missing_ok=True)
    run.cut = ops.admit(run.workspace_a)
    cutting = ops.fixture_worker('cut-worker', 6, 1, run.marker)
    in_call = wait(run.marker.exists, 40)
    cutting.send_signal(signal.SIGTERM)
    exit_code = exited(cutting, 40)
    left = ops.sql(f"select r.status || '/' || j.status from public.runs r join app_private.run_jobs j on j.run_id = r.id where r.id = '{run.cut}';")
    cases.check('a drain past its bound exits and leaves the job recoverable', 'exit 0, running/claimed', f'{in_call}, {exit_code}, {left}', in_call and exit_code == 0 and left == 'running/claimed')
    expired = wait(lambda: conditions(run.status()[1]).get('queue') == 'leases_expired', 30)
    cases.check('the lost lease becomes visible', 'leases_expired', expired, expired)


def readiness_failures(run: OperationsRun, cases: Cases) -> None:
    """Each failure observed through the API a person would use."""
    ops, stack = run.ops, run.stack
    stopped = stack.compose('stop', 'storage', timeout=120)
    down = wait(lambda: conditions(run.status()[1]).get('storage') == 'storage_unreachable', 30)
    _code_status, body = run.status()
    cases.check('Storage down is visible and not ready', 'storage_unreachable, ready false', f"{stopped.returncode}, {down}, {json.loads(body)['ready']}", down and json.loads(body)['ready'] is False)
    jobs = ops.sql('select count(*) from app_private.run_jobs;')
    code, reply = run.admit_goal()
    after = ops.sql('select count(*) from app_private.run_jobs;')
    cases.check('admission stops with Storage down', '503 not_ready, no new job', f'{code}, {jobs} then {after}', code == 503 and 'not_ready' in reply and jobs == after)
    cases.arrange('Storage started again', stack.compose('start', 'storage', timeout=120))
    back = wait(lambda: json.loads(run.status()[1])['ready'] is True, 90)
    cases.check('readiness returns when Storage does', 'ready true', back, back)
    ops.api(run.low_port, run.config_root, {'AUTOBOTS_MIN_FREE_BYTES': str(2**62)})
    wait(lambda: run.status(port=run.low_port)[0] == 200, 40)
    code, body = run.status(port=run.low_port)
    admit_code, _ = run.admit_goal(run.low_port)
    cases.check('low disk stops admission (arranged with an impossible minimum)', 'disk_low, 503', f"{conditions(body).get('disk')}, {admit_code}", conditions(body).get('disk') == 'disk_low' and admit_code == 503)


def shutdown(run: OperationsRun, cases: Cases) -> None:
    """Ordinary shutdown: processes first, then containers. Everything durable has to come back."""
    ops, stack, base = run.ops, run.stack, run.base
    path = f'{run.workspace_a}/{run.queued}/lifecycle/kept.txt'
    content = secrets.token_bytes(64)
    service = stack.values['SERVICE_ROLE_KEY']
    put, _ = http('POST', f'{base}/storage/v1/object/workspace-artifacts/{path}', {'apikey': service, 'Authorization': f'Bearer {service}', 'Content-Type': 'application/octet-stream'}, content)
    counts = durable_counts(ops)
    cases.arrange('a row written just before shutdown',
                  stack.runtime("insert into app_private.retention_log (workspace_id, action) select id, 'lifecycle_marker' from public.workspaces limit 1;"))
    halted = stack.compose('stop', timeout=180)
    volumes = run_volumes(stack)
    cases.check('stopping the stack keeps its volumes', 'exit 0, volumes remain', f'{halted.returncode}, {len(volumes)} volumes', halted.returncode == 0 and len(volumes) > 0)
    code, body = run.status()
    reported = json.loads(body) if code == 200 else {}
    cases.check('with the database down the API still reports it', '200, database_unreachable, installation scope', f"{code}, {reported.get('scope')}, {conditions(body).get('database') if code == 200 else ''}", code == 200 and reported.get('scope') == 'installation' and conditions(body).get('database') == 'database_unreachable')
    code, reply = run.admit_goal()
    cases.check('admission stops with the database down', '503 not_ready', f'{code} {reply[:60]}', code == 503 and 'not_ready' in reply)
    resumed_stack = stack.compose('up', '-d', '--wait', '--wait-timeout', '240', timeout=300)
    restored = durable_counts(ops)
    cases.check('records survive stop and start', counts, f'{resumed_stack.returncode}, {restored}', resumed_stack.returncode == 0 and restored == counts)
    marked = ops.sql("select count(*) from app_private.retention_log where action = 'lifecycle_marker';")
    cases.check('a row written just before shutdown survives it', '1', marked, marked == '1')
    fetch = request.Request(f'{base}/storage/v1/object/workspace-artifacts/{path}', headers={'apikey': service, 'Authorization': f'Bearer {service}'})
    got: list[tuple[int, bytes]] = []

    def read_object() -> bool:
        with request.urlopen(fetch, timeout=10) as reply_:
            got.append((reply_.status, reply_.read()))
        return got[-1][0] == 200

    wait(read_object, 60)
    status, data = got[-1] if got else (-1, b'')
    cases.check('Storage bytes survive stop and start', 'same bytes', f'put {put}, get {status}, same {data == content}', put == 200 and data == content)
    recovered = wait(lambda: json.loads(run.status()[1])['ready'] is True, 90)
    cases.check('the running API reconnects by itself', 'ready true', recovered, recovered)


def run_volumes(stack: AppStack) -> list[str]:
    return run(['docker', 'volume', 'ls', '--filter', f'label=com.docker.compose.project={stack.target.project}', '--format', '{{.Name}}'], tool_env()).stdout.split()


def recovery(run: OperationsRun, cases: Cases) -> None:
    """The job the bound cut short resumes from its checkpoint, with nothing repeated."""
    ops, root, cut = run.ops, run.root, run.cut
    receipts_before = ops.sql(f"select count(*) from app_private.tool_receipts where run_id = '{cut}';")
    run.marker.unlink(missing_ok=True)
    resuming = ops.fixture_worker('resume-worker', 0, 30, run.marker, 'resume')
    paused = wait(lambda: ops.sql(f"select status from public.runs where id = '{cut}';") == 'paused', 40)
    uncertain = ops.sql(f"select count(*) from app_private.model_invocations where run_id = '{cut}' and status = 'uncertain';")
    cases.check('a call cut off by shutdown waits for a person, not a blind retry', 'paused, 1 uncertain', f'{paused}, {uncertain}', paused and uncertain == '1')
    code, reply = api_call(run.api_port, ops.internal, run.token_a, 'POST', f'/v1/runs/{cut}/model-calls/reconcile', json.dumps({'charged_micro_usd': 100}).encode(), {'Idempotency-Key': secrets.token_hex(8)})
    cases.check('the owner reconciles it through the API', '200, one call', f'{code} {reply[:60]}', code == 200 and '"reconciled_calls":1' in reply)
    # Arranged: the route also requires a usable key, and none exists here, so this is the command it calls.
    resumed = launch([str(root / PYTHON), str(root / 'tests/db/operations_check.py'), 'resume', run.workspace_a, cut], env=ops.env, timeout=60, label='the arranged resume')
    finished = wait(lambda: ops.sql(f"select status from public.runs where id = '{cut}';") == 'succeeded', 60)
    resuming.send_signal(signal.SIGTERM)
    exit_code = exited(resuming, 30)
    duplicates = ops.sql(f"select count(*) from (select tool_id, argument_hash from app_private.tool_receipts where run_id = '{cut}' and status = 'succeeded' group by 1, 2 having count(*) > 1) d;")
    state = ops.sql(f"select r.status || '/' || j.status || '/' || j.attempts || '/' || coalesce((select payload::text from public.run_events e where e.run_id = r.id order by sequence desc limit 1), '') from public.runs r join app_private.run_jobs j on j.run_id = r.id where r.id = '{cut}';")
    cases.check('the interrupted job resumes after the restart', 'succeeded, exit 0, no repeated effect', f'resume exit {resumed.returncode}, {finished}, {exit_code}, {receipts_before} before, {duplicates} repeated, {state[:220]}', finished and exit_code == 0 and duplicates == '0')


def retention(run: OperationsRun, cases: Cases) -> None:
    """Retention, on the real run `drain` finished."""
    ops, root = run.ops, run.root
    run_child_check(cases, root, 'operations_check.py', 'retention', run.workspace_a, run.workspace_b, run.queued, label='the retention check',
                    env=ops.env, timeout=240, err_dir=root / ERR_DIR, err_name='retention')
    code, _ = api_call(run.api_port, ops.internal, run.token_b, 'PUT', '/v1/operations/retention', json.dumps({'run_days': 30, 'receipt_days': 7}).encode())
    cases.check('a key window shorter than run content is refused', '422', code, code == 422)
    code, _reply = api_call(run.api_port, ops.internal, run.token_b, 'PUT', '/v1/operations/retention', json.dumps({'run_days': 30, 'receipt_days': 30}).encode())
    applied_code, applied_body = api_call(run.api_port, ops.internal, run.token_b, 'POST', '/v1/operations/retention/apply')
    cases.check('an owner sets and applies retention through the API', '200, 200', f'{code}, {applied_code} {applied_body[:80]}', code == 200 and applied_code == 200)
    code, _ = api_call(run.api_port, ops.internal, run.token_c, 'POST', '/v1/operations/retention/apply', extra=run.as_a)
    cases.check('a member cannot apply retention', '403', code, code == 403)
    denied = run.stack.as_role('authenticated', run.user_a, f"select app_private.purge_run_content('{run.workspace_a}', '{run.queued}', now())")
    cases.check('a signed-in role cannot call the purge function', 'permission denied', 'permission denied' if 'permission denied' in denied.stderr else f'exit {denied.returncode}', denied.returncode != 0 and 'permission denied' in denied.stderr)
    # The product worker's own pass, for the workspace that declared a window above.
    product = ops.spawn('product-worker-2', [str(root / PYTHON), '-m', 'autobots.operations.worker'])
    passed_retention = wait(lambda: 'retention.applied' in (run.logs / 'product-worker-2.log').read_text(errors='replace'), 30)
    product.send_signal(signal.SIGTERM)
    cases.check('the worker applies declared retention on its own pass', 'retention.applied, exit 0', f'{passed_retention}, {exited(product, 20)}', passed_retention and product.returncode == 0)


def process_logs(run: OperationsRun, cases: Cases) -> None:
    """Graceful API stop, then what every process wrote."""
    api_process = run.api_process
    if api_process is None:
        raise RuntimeError('readiness started no API')
    api_process.send_signal(signal.SIGTERM)
    api_exit = exited(api_process, 20)
    api_log = (run.logs / f'api-{run.api_port}.log').read_text(errors='replace')
    # uvicorn re-raises the signal once it has shut down, so its status is -15 after a clean stop.
    cases.check('the API stops cleanly on SIGTERM', 'shutdown complete', api_exit, api_exit in (0, -signal.SIGTERM) and 'Application shutdown complete' in api_log)
    written = {path_.name: path_.read_text(errors='replace') for path_ in run.logs.glob('*.log')}
    everything = '\n'.join(written.values())
    stack = run.stack
    planted = [name for name, value in (('log secret', LOG_SECRET), ('trace key', TRACE_KEY), ('runtime password', stack.runtime_password),
                                        ('service key', stack.values['SERVICE_ROLE_KEY']), ('jwt secret', stack.values['JWT_SECRET']), ('internal token', run.ops.internal)) if value in everything]
    cases.check('no process log holds a secret, with one planted through the logger', 'none, and the planted line was written', f"{planted or 'none'}, {'[redacted]' in everything}", not planted and '[redacted]' in everything)
    worker_lines = [line for line in written.get('drain-worker.log', '').splitlines() if line.startswith('{')]
    events = [json.loads(line).get('event') for line in worker_lines]
    cases.check('worker logs are structured and name the lifecycle', 'started, draining, stopped', events, 'worker.started' in events and 'worker.draining' in events and 'worker.stopped' in events)
    cut_events = [json.loads(line).get('event') for line in written.get('cut-worker.log', '').splitlines() if line.startswith('{')]
    cases.check('a cut-short drain is logged', 'worker.drain_cut_short', cut_events, 'worker.drain_cut_short' in cut_events)
    config = stack.compose('config', timeout=60).stdout.lower()
    collectors = [word for word in ('langsmith', 'otel-collector', 'otlp', 'datadog', 'sentry') if word in config]
    cases.check('the merged Compose names no remote trace collector', 'none', collectors or 'none', not collectors)


SCENARIOS = (infrastructure, readiness, product_worker, drain, cut_short_drain, readiness_failures, shutdown, recovery, retention,
             process_logs)


def qualify(root: Path) -> int:
    cases = Cases(model_transport=MODEL_TRANSPORT)
    with app_project(root, cases, report=root / REPORT, extra_ports=2) as app:
        api_port, low_port = app.ports
        logs = root / '.checks/operations/logs'
        logs.mkdir(parents=True, exist_ok=True)
        for old in logs.glob('*.log'):
            old.unlink()
        config_root = Path(tempfile.mkdtemp(prefix='autobots-ops-'))
        ops = Ops(root, app.stack, app.base, app.db_port, logs)
        try:
            run_scenarios(OperationsRun(root, app.stack, ops, app.base, api_port, low_port, config_root, logs), cases, SCENARIOS)
        finally:
            ops.stop_all()
            shutil.rmtree(config_root, ignore_errors=True)
    code = finish(root, root / REPORT, 'autobots.operations-qualification/v1', cases, app.started_at,
                  ['H1', 'product acceptance', 'the persistent stack', 'a real model call', 'Mac sleep', 'resource use under load'],
                  project=app.stack.target.project)
    print(f'{"PASS" if code == 0 else "FAIL"}: operations qualification, {round(time.monotonic() - app.started_at)}s, report {REPORT}')
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
