#!/usr/bin/env python3
"""Three checks US-10.2's read showed a test can settle, by Decision 0013. Kept with the evidence.

A file under `scripts/` or `tests/` would void US-12.3's binding. A fake transport under the real SDK and the product's
worker, so nothing is sent and nothing is spent, on a disposable stack removed at the end.

- PRD 13.1: cancel a run that's really running, with a call in flight, and time the API's answer.
- LC-13: cut the event stream's TCP connection with a reset, repeatedly, during a run, and rebuild from the cursor.
- LC-18: scan what was sent, stored and logged for each secret this stack holds. A canary in the goal and the artifact
  is the control: a scan that can't read a surface fails it. Counts only, so no value reaches a report.

Exit 0 all held, 1 a check failed, 2 a prerequisite is missing.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import secrets
import socket
import struct
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'scripts'))

from app_db import AppStack, apply_migrations, bootstrap, seed  # noqa: E402
from disposable_db import PROJECT_PREFIX, Target, Unavailable, free_port, other_resources, remove_stack, require_identity, run, tool_env  # noqa: E402
from evidence import fingerprints  # noqa: E402
from qualify_identity import PYTHON, STORAGE_SQL, bootstrap_owner, password_token  # noqa: E402
from qualify_operations import Ops, api_call, exited, wait  # noqa: E402
from supabase_stack import generated_values, require_images, require_rendered  # noqa: E402

FAKE_HELPER = 'tests/db/product_inference_check.py'
TERMINAL = {'succeeded', 'failed', 'cancelled'}
TRACING = ('LANGSMITH_TRACING', 'LANGCHAIN_TRACING_V2', 'LANGSMITH_API_KEY', 'LANGSMITH_ENDPOINT')
LIMIT = 100_000
CANCELS = 12
OUT = Path(__file__).with_name('closing-checks.json')


def bodies_of(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def held(ops: Ops, run_id: str) -> str:
    return ops.sql("select coalesce(sum(reserved_micro_usd) filter (where status in ('reserved', 'dispatched', 'uncertain') and reconciled_at is null), 0) "
                   f"from app_private.model_invocations where root_run_id = '{run_id}' or run_id = '{run_id}';")


def start_run(port: int, internal: str, token: str, goal: str) -> str:
    code, reply = api_call(port, internal, token, 'POST', '/v1/runs', json.dumps({'goal_text': goal, 'limit_micro_usd': LIMIT}).encode(),
                           {'Idempotency-Key': secrets.token_hex(8)})
    if code != 202:
        raise Unavailable(f'the API refused a goal: {code} {reply[:200]}')
    return json.loads(reply)['run_id']


def cancel_while_running(ops: Ops, port: int, token: str, bodies: Path) -> dict:
    """Each cancel lands during a call that's in flight, at the first, second or third call of its run."""
    samples, problems = [], []
    for number in range(CANCELS):
        tag = f'cancel-{number}-{secrets.token_hex(3)}'
        run_id = start_run(port, ops.internal, token, f'Write the report [slow] {tag}')
        target = 1 + number % 3
        arrived = wait(lambda: sum(tag in item['body'] for item in bodies_of(bodies)) >= target, 60)
        version = ops.sql(f"select version from public.runs where id = '{run_id}';")
        before = ops.sql(f"select status from public.runs where id = '{run_id}';")
        in_flight = ops.sql(f"select count(*) from app_private.model_invocations where run_id = '{run_id}' and finished_at is null;")
        if not arrived or before != 'running' or in_flight != '1':
            problems.append(f'run {number} was {before}, with {in_flight} calls in flight, before its cancel')
        started = time.perf_counter()
        code, reply = api_call(port, ops.internal, token, 'POST', f'/v1/runs/{run_id}/cancel', json.dumps({'expected_version': int(version)}).encode(),
                               {'Idempotency-Key': secrets.token_hex(8)})
        seconds = time.perf_counter() - started
        acknowledged_at = time.time()
        if code >= 300:
            problems.append(f'run {number}: the cancel answered {code} {reply[:160]}')
        settled = wait(lambda: ops.sql(f"select status from public.runs where id = '{run_id}';") in TERMINAL, 60)
        final = ops.sql(f"select status from public.runs where id = '{run_id}';")
        sent = [item['at'] for item in bodies_of(bodies) if tag in item['body']]
        samples.append({'number': number, 'cancelled_during_call': target, 'answer': code, 'answered_status': json.loads(reply).get('status') if code < 300 else None,
                        'acknowledged_ms': round(seconds * 1000, 1), 'final': final, 'settled': settled,
                        'calls_sent_after_the_answer': sum(at > acknowledged_at for at in sent), 'calls_sent': len(sent),
                        'reserved_after': held(ops, run_id),
                        'stop_reason': ops.sql(f"select stop_reason from app_private.run_usage where run_id = '{run_id}';")})
        if seconds >= 1:
            problems.append(f'run {number}: acknowledged in {seconds:.3f} s')
        # The product's own figure. A call the cancel interrupted may have been charged, so it stays held.
        if samples[-1]['reserved_after'] == '0':
            problems.append(f'run {number}: a call in flight was cancelled, and nothing stayed reserved for it')
        if final != 'cancelled':
            problems.append(f'run {number}: ended {final}')
        if samples[-1]['calls_sent_after_the_answer']:
            problems.append(f'run {number}: a call went out after the cancel was answered')
    times = sorted(item['acknowledged_ms'] for item in samples)
    return {'samples': samples, 'most_ms': times[-1], 'median_ms': times[len(times) // 2], 'problems': problems}


def read_until_cut(port: int, internal: str, token: str, run_id: str, after: int, cut_after: int, seconds: float = 60) -> tuple[list[int], bool]:
    """Reads the stream over a raw socket, then resets the connection with events still to come."""
    connection = socket.create_connection(('127.0.0.1', port), timeout=seconds)
    connection.sendall((f'GET /v1/runs/{run_id}/events/stream?after={after} HTTP/1.1\r\nHost: 127.0.0.1\r\nAccept: text/event-stream\r\n'
                        f'X-Autobots-Internal: {internal}\r\nAuthorization: Bearer {token}\r\nConnection: keep-alive\r\n\r\n').encode())
    buffer, seen, ended = b'', [], False
    deadline = time.monotonic() + seconds
    try:
        while time.monotonic() < deadline and len(seen) < cut_after and not ended:
            part = connection.recv(65536)
            if not part:
                break
            buffer += part
            while b'\n\n' in buffer:
                frame, buffer = buffer.split(b'\n\n', 1)
                for line in frame.splitlines():
                    if line.startswith(b'id: '):
                        seen.append(int(line[4:]))
                    if line.strip() == b'event: end':
                        ended = True
    finally:
        # Linger zero sends a reset, so the server sees a cut and not a close.
        connection.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0))
        connection.close()
    return seen, ended


def cut_streams(ops: Ops, port: int, token: str, canary: str) -> dict:
    run_id = start_run(port, ops.internal, token, f'Write the report [paced] {canary}')
    delivered: list[int] = []
    cuts, ended = 0, False
    while not ended and cuts < 200:
        seen, ended = read_until_cut(port, ops.internal, token, run_id, delivered[-1] if delivered else 0, 1)
        delivered += seen
        if not ended:
            cuts += 1
            # Long enough for the next call to finish, so events commit while nothing is connected.
            time.sleep(1.5)
    wait(lambda: ops.sql(f"select status from public.runs where id = '{run_id}';") in TERMINAL, 60)
    stored = [int(item) for item in ops.sql(f"select string_agg(sequence::text, ',' order by sequence) from public.run_events where run_id = '{run_id}';").split(',')]
    code, reply = api_call(port, ops.internal, token, 'GET', f'/v1/runs/{run_id}')
    view = json.loads(reply) if code == 200 else {}
    final = ops.sql(f"select status from public.runs where id = '{run_id}';")
    problems = []
    if delivered != stored:
        problems.append(f'delivered {len(delivered)} events against {len(stored)} stored, or out of order')
    if len(set(delivered)) != len(delivered):
        problems.append('an event was delivered twice')
    if cuts < 3:
        problems.append(f'only {cuts} cuts landed before the end, so this says little')
    if final != 'succeeded' or view.get('status') != final:
        problems.append(f"the run ended {final}, and the API says {view.get('status')}")
    return {'run_id': run_id, 'cuts_with_events_still_to_come': cuts, 'events_delivered': len(delivered), 'events_stored': len(stored), 'in_order_no_gap_no_duplicate': delivered == stored,
            'final': final, 'problems': problems}


def counted(blob: bytes, values: dict[str, bytes]) -> dict[str, int]:
    """Each value as text, and as hex, as `pg_dump` prints a blob."""
    return {name: blob.count(value) + blob.lower().count(value.hex().encode()) for name, value in values.items()}


def scan(ops: Ops, stack: AppStack, project: str, logs: Path, bodies: Path, values: dict[str, bytes], canary: bytes) -> dict:
    sent = bodies_of(bodies)
    container = run(['docker', 'ps', '--filter', f'label=com.docker.compose.project={project}', '--filter', 'label=com.docker.compose.service=db', '--format', '{{.ID}}'], tool_env()).stdout.strip()
    objects = run(['docker', 'ps', '--filter', f'label=com.docker.compose.project={project}', '--filter', 'label=com.docker.compose.service=storage', '--format', '{{.ID}}'], tool_env()).stdout.strip()
    dump = subprocess.run(['docker', 'exec', container, 'pg_dump', '-U', 'postgres', '-d', 'postgres', '--data-only', '-n', 'public', '-n', 'app_private', '-n', 'agent_runtime'],
                          capture_output=True, timeout=180, check=False, env=tool_env())
    tar = subprocess.run(['docker', 'exec', objects, 'tar', '-cf', '-', '/var/lib/storage'], capture_output=True, timeout=180, check=False, env=tool_env())
    events = subprocess.run(['docker', 'exec', container, 'psql', '-U', 'postgres', '-d', 'postgres', '-At', '-c', 'select payload::text from public.run_events'],
                            capture_output=True, timeout=120, check=False, env=tool_env())
    surfaces = {'prompts_sent': '\n'.join(item['body'] for item in sent).encode(),
                'request_headers_without_authorization': json.dumps([item['headers'] for item in sent]).encode(),
                'events': events.stdout, 'application_rows': dump.stdout, 'stored_objects': tar.stdout,
                'logs': b'\n'.join(path.read_bytes() for path in logs.glob('*.log') if path.is_file())}
    found = {name: counted(blob, values) for name, blob in surfaces.items()}
    sizes = {name: len(blob) for name, blob in surfaces.items()}
    control = {name: blob.count(canary) + blob.lower().count(canary.hex().encode()) for name, blob in surfaces.items()}
    problems = []
    for name, each in found.items():
        for secret, count in each.items():
            if count:
                problems.append(f'{secret} found {count} times in {name}')
    # Where the canary goes by design. A surface missing it here couldn't have shown a secret either.
    for name in ('prompts_sent', 'application_rows', 'stored_objects'):
        if not control[name]:
            problems.append(f"the canary wasn't found in {name}, so the scan of it shows nothing")
    # The canary doesn't reach events by design, so this shows the surface was really read.
    report_events = surfaces['events'].count(b'report.md')
    if not report_events:
        problems.append("no event names the artifact, so the scan of events shows nothing")
    if dump.returncode or tar.returncode or events.returncode:
        problems.append(f'a read failed: {dump.returncode} {tar.returncode} {events.returncode}')
    return {'requests_read': len(sent), 'surface_bytes': sizes, 'secrets_checked': sorted(values), 'found': found, 'canary_found': control, 'events_naming_the_artifact': report_events, 'problems': problems}


def main() -> int:
    root = ROOT
    project = f'{PROJECT_PREFIX}{secrets.token_hex(4)}'
    gateway_port = free_port()
    db_port = free_port([gateway_port])
    api_port = free_port([gateway_port, db_port])
    target = Target(project, db_port, gateway_port)
    stack = AppStack(target, root, root / 'infra/supabase/upstream/docker-compose.yml', values=generated_values(gateway_port, db_port))
    stack.migrator_password, stack.runtime_password = secrets.token_hex(24), secrets.token_hex(24)
    require_identity(target, tool_env())
    if run(['docker', 'info', '--format', '{{.ServerVersion}}'], tool_env(), 30).returncode:
        raise Unavailable('the Docker engine is not reachable')
    require_images(require_rendered(stack))
    scratch = Path(tempfile.mkdtemp(prefix='autobots-closing-'))
    logs = scratch / 'logs'
    logs.mkdir()
    config_root = scratch / 'config'
    bodies = scratch / 'bodies.jsonl'
    ops = Ops(root, stack, f'http://127.0.0.1:{gateway_port}', db_port, logs)
    for name in TRACING:
        ops.env.pop(name, None)
    provider_env = {'AUTOBOTS_CONFIG_ROOT': str(config_root), 'NODE_ENV': 'production', 'AUTOBOTS_PROVIDER_MASTER_KEY_FILE': str(config_root / 'secrets/master.key')}
    key = f'arranged-{secrets.token_hex(16)}'
    canary = f'arranged-canary-{secrets.token_hex(8)}'
    before = other_resources(project)
    report: dict = {'schema_version': 'autobots.us-10-2-closing-checks/v1', 'started_at_utc': datetime.now(timezone.utc).isoformat(), 'source_fingerprint': fingerprints(root)['source_manifest_sha256'],
                    'target_class': 'disposable', 'model_transport': 'fake transport under the real SDK', 'spending': 'none',
                    'not_established': ['H1', 'product acceptance', 'a real provider', 'a persistent stack', 'a cut between the browser and the web app']}
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
        ops.api(api_port, config_root, {'AUTOBOTS_SUPABASE_URL': ops.base})
        wait(lambda: api_call(api_port, ops.internal, token)[0] == 200, 40)
        saved = subprocess.run([str(root / PYTHON), str(root / FAKE_HELPER), 'save-key', workspace], env={**ops.env, **provider_env, 'AUTOBOTS_TEST_KEY': key},
                               capture_output=True, text=True, errors='replace', timeout=120, check=False)
        if saved.returncode:
            raise Unavailable('the key could not be saved')
        worker = ops.spawn('worker', [str(root / PYTHON), str(Path(__file__).with_name('scripted_worker.py'))],
                           {**provider_env, 'AUTOBOTS_WORKER_INFERENCE': 'enabled', 'AUTOBOTS_TEST_REQUESTS': str(scratch / 'requests.jsonl'),
                            'AUTOBOTS_TEST_REJECTED_KEY': 'arranged-rejected', 'AUTOBOTS_TEST_BODIES': str(bodies), 'AUTOBOTS_TEST_CANARY': canary})

        report['stream_cut'] = cut_streams(ops, api_port, token, canary)
        print(json.dumps({'stream_cut': report['stream_cut']}, default=str), flush=True)
        report['cancel_while_running'] = cancel_while_running(ops, api_port, token, bodies)
        print(json.dumps({key_: report['cancel_while_running'][key_] for key_ in ('median_ms', 'most_ms', 'problems')}), flush=True)
        report['worker_exit'] = exited(worker, 60) if worker.send_signal(15) is None else None

        values = {'provider_key': key.encode(), 'master_key': (config_root / 'secrets/master.key').read_bytes().strip(), 'internal_token': ops.internal.encode(),
                  'migrator_password': stack.migrator_password.encode(), 'runtime_password': stack.runtime_password.encode()}
        for name in ('SERVICE_ROLE_KEY', 'JWT_SECRET', 'POSTGRES_PASSWORD', 'DASHBOARD_PASSWORD'):
            if stack.values.get(name):
                values[name.lower()] = stack.values[name].encode()
        report['secret_scan'] = scan(ops, stack, project, logs, bodies, values, canary.encode())
        print(json.dumps({item: report['secret_scan'][item] for item in ('requests_read', 'surface_bytes', 'canary_found', 'events_naming_the_artifact', 'problems')}), flush=True)
    finally:
        ops.stop_all()
        remove_stack(stack)
        subprocess.run(['rm', '-rf', str(scratch)], check=False)
        label = f'label=com.docker.compose.project={project}'
        left = (run(['docker', 'volume', 'ls', '--filter', label, '--format', '{{.Name}}'], tool_env()).stdout
                + run(['docker', 'ps', '-a', '--filter', label, '--format', '{{.Names}}'], tool_env()).stdout).strip()
        report['left_behind'] = left or 'none'
        report['other_docker_unchanged'] = before == other_resources(project)
        report['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        problems = [item for part in ('stream_cut', 'cancel_while_running', 'secret_scan') for item in report.get(part, {'problems': [f'{part} did not run']})['problems']]
        if report['left_behind'] != 'none' or not report['other_docker_unchanged']:
            problems.append('resources were left behind or changed')
        report['problems'] = problems
        report['verdict'] = 'held' if not problems else 'failed'
        OUT.write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps({'verdict': report['verdict'], 'problems': report['problems'], 'left_behind': report['left_behind'], 'other_docker_unchanged': report['other_docker_unchanged']}, indent=1))
    return 0 if report['verdict'] == 'held' else 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Unavailable as error:
        print(f'ERROR: {error}', file=sys.stderr)
        raise SystemExit(2) from None
