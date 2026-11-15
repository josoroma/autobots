#!/usr/bin/env python3
"""One real goal through the product's API and worker, on a disposable stack, with a real paid model.

This spends money. It refuses without --paid, and nothing in `verify.py` runs it. The run's own budget
is the limit under test, so the paid session's watchdog (scripts/paid_run.py) also stops the worker if
what's committed ever passes it, can't be read for three polls in a row (Decision 0028 E2) or a poll
fails. The stack, its copy of the key and its master key are removed at the end. Exit 0 the run
succeeded with its spend known and the key found nowhere, 1 it didn't, 2 a prerequisite is missing.
"""
from __future__ import annotations

import argparse
import json
import secrets
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

from app_db import AppStack, apply_bootstrap, apply_migrations, bootstrap, seed
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
from paid_run import ACTIVE, PaidSession, goal_exit_code
from qualify_identity import bootstrap_owner
from qualify_operations import Ops, api_call, wait
from supabase_stack import generated_values, require_images, require_rendered

# The user's go-ahead: "Yes, try one goal", at US$0.25.
AUTHORIZED_MICRO_USD = 250_000
OUT = Path('.checks/live-goal')
SECONDS = 1000
TRACING = ('LANGSMITH_TRACING', 'LANGCHAIN_TRACING_V2', 'LANGSMITH_API_KEY', 'LANGSMITH_ENDPOINT')
GOAL = ('Write a short Markdown report named report.md comparing SQLite and PostgreSQL for a single-user desktop '
        'note-taking app. Give exactly three trade-offs and a one-sentence recommendation, in under 150 words. '
        'Its last line must be exactly: Trade-offs covered: 3')
REQUIRED = [{'name': 'report.md', 'must_contain': ['Trade-offs covered: 3']}]


def disposable_session(root: Path, ops: Ops, provider_env: dict[str, str]) -> PaidSession:
    """A disposable stack's paid session. The helper gets the provider settings, and the worker starts
    through Ops, so Ops stops it with everything else it started."""
    return PaidSession(root, ops.stack, {**ops.env, **provider_env}, lambda argv, extra: ops.spawn('worker', argv, {**provider_env, **extra}))


def attempt(root: Path, key_file: Path, limit: int, profile: str | None = None) -> int:
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
    out = root / OUT
    logs = out / 'logs'
    logs.mkdir(parents=True, exist_ok=True)
    for old in logs.glob('*.log'):
        old.unlink()
    config_root = Path(tempfile.mkdtemp(prefix='autobots-live-goal-'))
    ops = Ops(root, stack, f'http://127.0.0.1:{gateway_port}', db_port, logs)
    # Ops arranges an inherited tracing setting to test the guard. Real content gets no such test.
    for name in TRACING:
        ops.env.pop(name, None)
    provider_env = {'AUTOBOTS_CONFIG_ROOT': str(config_root), 'NODE_ENV': 'production',
                    'AUTOBOTS_PROVIDER_MASTER_KEY_FILE': str(config_root / 'secrets/master.key')}
    session = disposable_session(root, ops, provider_env)
    before_resources = other_resources(project)
    report: dict = {'schema_version': 'autobots.live-goal/v1', 'started_at_utc': datetime.now(UTC).isoformat(),
                    'input_fingerprint': fingerprint(root), 'target_class': 'disposable', 'model_transport': 'live OpenRouter',
                    'limit_micro_usd': limit, 'goal': GOAL, 'required_artifacts': REQUIRED, 'timeline': [], 'watchdog_fired': False,
                    'not_established': ['H1', 'product acceptance', 'US-3.4', 'task quality beyond this one goal', 'the persistent stack']}
    report['key_usage_before_usd'] = float(session.helper('usage', str(key_file)))
    run_id = ''
    started = time.monotonic()
    try:
        up = stack.compose('up', '-d', '--wait', '--wait-timeout', '240', timeout=300)
        if up.returncode:
            raise Unavailable(f'the stack did not start: {up.stderr[-300:]}')
        bootstrap(stack, root)
        _, problem = apply_migrations(stack, root / 'supabase/migrations')
        if problem or seed(stack, root).returncode:
            raise Unavailable(f'migrations failed: {problem}')
        if apply_bootstrap(stack, root)[1]:
            raise Unavailable('the storage setup failed')
        email, password = 'owner@example.invalid', secrets.token_urlsafe(24)
        workspace = bootstrap_owner(root, ops.base, stack.values['SERVICE_ROLE_KEY'], ops.url, email, password)['workspace_id']
        token = session.sign_in(ops.base, stack.values['ANON_KEY'], email, password)
        ops.api(api_port, config_root)
        wait(lambda: api_call(api_port, ops.internal, token)[0] == 200, 40)
        session.helper('save', str(key_file), workspace)
        report['key_check'] = session.rows(f"select auth_status from app_private.provider_settings where workspace_id = '{workspace}'")

        if profile:
            code, reply = api_call(api_port, ops.internal, token, 'PUT', '/v1/settings/model-policy',
                                   json.dumps({'expected_version': 0, 'default_profile': profile, 'role_overrides': {}}).encode())
            report['policy_put'] = code
            if code != 200:
                raise Unavailable(f'the policy was refused: {code} {reply[:200]}')

        body = json.dumps({'goal_text': GOAL, 'limit_micro_usd': limit, 'required_artifacts': REQUIRED}).encode()
        code, reply = api_call(api_port, ops.internal, token, 'POST', '/v1/runs', body, {'Idempotency-Key': secrets.token_hex(8)})
        report['admission'] = code
        if code != 202:
            raise Unavailable(f'the API refused the goal: {code} {reply[:200]}')
        run_id = json.loads(reply)['run_id']
        report['run_id'] = run_id

        status = f"select status from public.runs where id = '{run_id}';"
        spend = f"select coalesce(sum(coalesce(charged_micro_usd, reserved_micro_usd)), 0) from app_private.model_invocations where root_run_id = '{run_id}';"
        session.start_worker()
        goal_started = time.monotonic()
        watched = session.watch(lambda: {'status': session.sql(status) or ''}, lambda current: bool(current['status']) and current['status'] not in ACTIVE,
                                limit, spend, SECONDS)
        report['goal_seconds'] = round(time.monotonic() - goal_started, 1)
        watched.record(report)
        # Stopped before anything is read, since it can still dispatch while it drains.
        session.stop_worker(report)
        session.spend_after(watched, spend, report)

        # Everything below reads the same stack, so a failure in one can't hide the others.
        # Spend comes from the ledger below, as the API's does. The runs table's own column isn't maintained.
        report['run'] = session.rows(f"select status, limit_micro_usd from public.runs where id = '{run_id}'")
        report['usage'] = session.rows(f"select * from app_private.run_usage where run_id = '{run_id}'")
        report['invocations'] = session.rows(f"select attempt, profile, wire_id, status, failure_class, finish_reason, input_tokens, output_tokens, reasoning_tokens, "
                                             f"tool_names, invalid_tool_calls, reserved_micro_usd, charged_micro_usd, upstream_provider, "
                                             f"round(extract(epoch from finished_at - created_at)::numeric, 1) as seconds, char_length(accumulated_output) as partial_chars "
                                             f"from app_private.model_invocations where root_run_id = '{run_id}' order by created_at")
        report['receipts'] = session.rows(f"select tool_id, status, failure_code, failure_detail, created_at from app_private.tool_receipts where run_id = '{run_id}' order by created_at")
        report['verifications'] = session.rows(f"select passed, unmet, created_at from app_private.run_verifications where run_id = '{run_id}' order by created_at")
        report['files'] = session.rows(f"select path, version, char_length(content) as chars, sha256, content from app_private.run_files where run_id = '{run_id}' order by created_at")
        report['events'] = session.rows(f"select sequence, occurred_at, payload from public.run_events where run_id = '{run_id}' order by sequence")
        report['published'] = session.rows(f"select name, status, sha256, size_bytes from public.artifacts where run_id = '{run_id}' order by created_at")
        report['workspace_spend'] = session.rows(f"select coalesce(sum(charged_micro_usd), 0) as charged, count(*) as calls from app_private.model_invocations where workspace_id = '{workspace}'")
        written = '\n'.join(path.read_text(errors='replace') for path in logs.glob('*.log'))
        report['step_failures_in_logs'] = written.count('worker.step_failed')
        durable, logged = session.helper('leaks', str(key_file), str(logs)).split()
        report['key_found'] = {'durable_rows': int(durable), 'log_files': int(logged)}
    finally:
        ops.stop_all()
        remove_stack(stack)
        subprocess.run(['rm', '-rf', str(config_root)], check=False)
        report['total_seconds'] = round(time.monotonic() - started, 1)
        label = f'label=com.docker.compose.project={project}'
        left = (run(['docker', 'volume', 'ls', '--filter', label, '--format', '{{.Name}}'], tool_env()).stdout
                + run(['docker', 'ps', '-a', '--filter', label, '--format', '{{.Names}}'], tool_env()).stdout).strip()
        report['left_behind'] = left or 'none'
        report['other_docker_unchanged'] = before_resources == other_resources(project)
        try:
            # OpenRouter's figure can lag, so this is a check and the ledger above isn't replaced by it.
            time.sleep(60)
            report['key_usage_after_usd'] = float(session.helper('usage', str(key_file)))
        except Unavailable as error:
            report['key_usage_after_usd'] = f'unread: {error}'
        out.mkdir(parents=True, exist_ok=True)
        (out / f'result-{datetime.now(UTC).strftime("%Y%m%dT%H%M%S")}.json').write_text(json.dumps(report, indent=2, default=str))
    final = (report.get('run') or [{}])[0].get('status')
    print(json.dumps({key: report.get(key) for key in ('run_id', 'goal_seconds', 'timeline', 'watchdog_fired', 'key_usage_before_usd', 'key_usage_after_usd', 'key_found', 'left_behind', 'other_docker_unchanged')}, indent=2))
    print(f'FINAL: {final}')
    return goal_exit_code(report, achieved=final == 'succeeded')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--paid', action='store_true', help='required: this makes billed OpenRouter calls')
    parser.add_argument('--key-file', default='.env')
    parser.add_argument('--limit-micro-usd', type=int, default=AUTHORIZED_MICRO_USD)
    parser.add_argument('--profile', choices=('openrouter_terra',), help="the workspace's default model; the application's default if omitted. DeepSeek isn't offered, by Decision 0013")
    arguments = parser.parse_args()
    if not arguments.paid:
        print('REFUSED: this makes billed calls, and needs --paid', file=sys.stderr)
        return 2
    if not 0 < arguments.limit_micro_usd <= AUTHORIZED_MICRO_USD:
        print(f'REFUSED: the authorized limit is {AUTHORIZED_MICRO_USD} micro-USD', file=sys.stderr)
        return 2
    root = project_root()
    try:
        return attempt(root, (root / arguments.key_file).resolve(), arguments.limit_micro_usd, arguments.profile)
    except Unavailable as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
