#!/usr/bin/env python3
"""Exercises the upgrade runbook from a real prior release: its code and migrations, read from git history.

A disposable project takes the prior release's schema and runs its worker, then this revision's migrations
and code take over. The images and pinned packages are the same in both releases, so an image or framework
change is arranged, not observed. Exit 0 passed, 1 a case failed, 2 a prerequisite is missing.
"""
from __future__ import annotations

import hashlib
import io
import json
import secrets
import shutil
import signal
import subprocess
import sys
import tarfile
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
from qualification.children import run_child_check
from qualification.records import write_report
from qualify_identity import PYTHON, STORAGE_SQL, bootstrap_owner, password_token
from qualify_operations import MODEL_TRANSPORT, Checks, Ops, api_call, conditions, exited, wait
from supabase_stack import generated_values, require_images, require_rendered

REPORT = Path('.checks/upgrade/qualification.json')
# Where a failed child check's stderr is kept (qualification/children.py).
ERR_DIR = Path('.checks/upgrade')
# The release delivered before this one, with the worker fixture and every migration up to its own.
PRIOR_REVISION = '8cba043'
BINDINGS = "select id, policy_snapshot, expert_id, expert_version, session_id from public.runs where id::text = any(%s) order by id"


def extract_prior(root: Path, destination: Path) -> None:
    """Reads git history only. The checkout is untouched."""
    archive = subprocess.run(['git', 'archive', '--format=tar', PRIOR_REVISION, 'services/agent/src', 'supabase/migrations', 'supabase/seeds', 'tests/db'], cwd=root, capture_output=True, timeout=60, check=False)
    if archive.returncode:
        raise Unavailable(f'the prior release {PRIOR_REVISION} is not in this repository')
    with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tar:
        tar.extractall(destination, filter='data')


def qualify(root: Path) -> int:
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
    (root / REPORT).unlink(missing_ok=True)
    require_images(require_rendered(stack))
    cases = Checks(model_transport=MODEL_TRANSPORT)
    before = other_resources(project)
    started_at = time.monotonic()
    base = f'http://127.0.0.1:{gateway_port}'
    logs = root / '.checks/upgrade/logs'
    logs.mkdir(parents=True, exist_ok=True)
    for old in logs.glob('*.log'):
        old.unlink()
    work = Path(tempfile.mkdtemp(prefix='autobots-upgrade-'))
    prior = work / 'prior'
    extract_prior(root, prior)
    ops = Ops(root, stack, base, db_port, logs)
    prior_env = {'PYTHONPATH': str(prior / 'services/agent/src')}
    email, password = 'owner-a@example.invalid', secrets.token_urlsafe(24)
    goal = json.dumps({'goal_text': 'Write the report', 'limit_micro_usd': 1000000}).encode()
    try:
        started = stack.compose('up', '-d', '--wait', '--wait-timeout', '240', timeout=300)
        if started.returncode:
            raise Unavailable(f'the stack did not start: {started.stderr[-300:]}')
        bootstrap(stack, root)
        applied, problem = apply_migrations(stack, prior / 'supabase/migrations')
        # The prior release's own seeds: this release's can name a profile that schema doesn't have.
        if problem or seed(stack, prior).returncode or stack.sql((root / STORAGE_SQL).read_text()).returncode:
            raise Unavailable(f'prior migrations failed: {problem}')
        cases.check('the prior release schema is applied from its own files', f'{PRIOR_REVISION}', f'{applied} migrations', applied >= 24)
        owner = bootstrap_owner(root, base, stack.values['SERVICE_ROLE_KEY'], ops.url, email, password)
        workspace = owner['workspace_id']
        token = password_token(base, stack.values['ANON_KEY'], email, password)[1]

        def prior_admit() -> str:
            result = subprocess.run([str(root / PYTHON), str(prior / 'tests/db/operations_check.py'), 'admit', workspace], env={**ops.env, **prior_env}, capture_output=True, text=True, timeout=60, check=False)
            lines = result.stdout.strip().splitlines()
            if result.returncode or not lines:
                raise Unavailable(f'the prior release did not admit: exit {result.returncode}: {result.stderr.strip()[-300:]}')
            return lines[-1]

        def prior_worker(name: str, hold: float, drain: float, mode: str) -> subprocess.Popen:
            return ops.spawn(name, [str(root / PYTHON), str(prior / 'tests/db/operations_worker.py'), ops.url, name, str(hold), str(drain), str(marker), mode], prior_env)

        # Real saved state, written by the prior code: finished, paused on an uncertain call, and queued.
        marker = work / 'in-call'
        finished = prior_admit()
        worker = prior_worker('prior-finish', 0, 30, 'fresh')
        done = wait(lambda: ops.sql(f"select status from public.runs where id = '{finished}';") == 'succeeded', 60)
        worker.send_signal(signal.SIGTERM)
        exited(worker, 30)
        marker.unlink(missing_ok=True)
        interrupted = prior_admit()
        worker = prior_worker('prior-cut', 6, 1, 'fresh')
        wait(marker.exists, 40)
        worker.send_signal(signal.SIGTERM)
        exited(worker, 40)
        worker = prior_worker('prior-classify', 0, 30, 'resume')
        paused = wait(lambda: ops.sql(f"select status from public.runs where id = '{interrupted}';") == 'paused', 40)
        worker.send_signal(signal.SIGTERM)
        exited(worker, 30)
        queued = prior_admit()
        checkpoints = ops.sql(f"select count(*) from agent_runtime.checkpoints c join public.runs r on r.checkpoint_thread_id = c.thread_id where r.id = '{interrupted}';")
        cases.check('the prior code left finished, paused and queued work', 'succeeded, paused, a queued job, checkpoints', f'{done}, {paused}, {checkpoints} checkpoints', done and paused and int(checkpoints or 0) > 0)
        prior_runs = [finished, interrupted, queued]
        receipts_before = ops.sql(f"select count(*) from app_private.tool_receipts where run_id = '{interrupted}';")
        binding_probe = f"""
import hashlib, json, os, psycopg
with psycopg.connect(os.environ['AUTOBOTS_DATABASE_URL']) as db:
    rows = db.execute({BINDINGS!r}, ({prior_runs!r},)).fetchall()
print(hashlib.sha256(json.dumps(rows, default=str, sort_keys=True).encode()).hexdigest())
"""
        hashed = subprocess.run([str(root / PYTHON), '-c', binding_probe], env=ops.env, capture_output=True, text=True, timeout=30, check=False)
        if hashed.returncode:
            raise Unavailable(f'the bindings could not be read: {hashed.stderr[-200:]}')
        before_hash = hashed.stdout.strip()

        # New code on the old schema: everything stops, and it says why.
        config_root = work / 'config'
        config_root.mkdir()
        ops.api(api_port, config_root)
        wait(lambda: api_call(api_port, ops.internal, token)[0] == 200, 40)
        code, body = api_call(api_port, ops.internal, token)
        admit_code, _ = api_call(api_port, ops.internal, token, 'POST', '/v1/runs', goal, {'Idempotency-Key': secrets.token_hex(8)})
        cases.check('new code on the old schema refuses admission', 'schema_behind, 503', f"{conditions(body).get('schema') if code == 200 else code}, {admit_code}", code == 200 and conditions(body).get('schema') == 'schema_behind' and admit_code == 503)
        marker.unlink(missing_ok=True)
        early = ops.fixture_worker('new-on-old', 0, 5, marker, 'fresh')
        time.sleep(4)
        early.send_signal(signal.SIGTERM)
        exited(early, 20)
        state = ops.sql(f"select status from app_private.run_jobs where run_id = '{queued}';")
        cases.check('a new worker on the old schema claims nothing', 'queued', state, state == 'queued')

        # The forward paths: a failing migration leaves the schema as it was, and an edited one is refused.
        broken = work / 'broken'
        shutil.copytree(root / 'supabase/migrations', broken)
        (broken / '20261105999998_arranged_failure.sql').write_text('create table public.arranged_partial (id int);\nselect 1/0;\n')
        for path in sorted(broken.glob('*.sql')):
            if path.name > '20261105000024_' and 'arranged' not in path.name:
                path.unlink()
        failed_count, failed = apply_migrations(stack, broken)
        left = ops.sql("select to_regclass('public.arranged_partial') is null;")
        cases.check('a failing migration rolls back and is reported (arranged)', 'reported, no partial table, not recorded', f'{failed_count}, {bool(failed)}, absent {left}', failed and failed_count == 0 and left == 't')
        edited = work / 'edited'
        shutil.copytree(root / 'supabase/migrations', edited)
        first = sorted(edited.glob('*.sql'))[0]
        first.write_text(first.read_text() + '\n-- arranged edit\n')
        _, refusal = apply_migrations(stack, edited)
        cases.check('an edited applied migration is refused (arranged)', 'refused', refusal and refusal[-60:], bool(refusal) and 'never edit' in refusal)

        # A workspace and a role that chose the model a later release retires.
        cases.arrange('a workspace and a role that chose a retired model',
                      stack.runtime(f"""insert into app_private.model_policies (workspace_id, version, default_profile, role_overrides) values ('{workspace}', 7, 'openrouter_astra', '{{"coder": "openrouter_astra", "planner": "openrouter_deepseek_flash"}}') on conflict (workspace_id) do update set default_profile = excluded.default_profile, role_overrides = excluded.role_overrides;"""))

        # The real upgrade.
        upgraded, problem = apply_migrations(stack, root / 'supabase/migrations')
        cases.check('this release applies forward over the prior one', 'the new migrations, no error', f'{upgraded}, {problem}', upgraded >= 1 and not problem)
        reseeded = seed(stack, root)
        cases.check("this release's seeds apply over the upgraded schema", 'exit 0', reseeded.returncode, reseeded.returncode == 0)
        policy = ops.sql(f"select default_profile || '/' || (role_overrides ->> 'planner') || '/' || coalesce(role_overrides ->> 'coder', 'none') from app_private.model_policies where workspace_id = '{workspace}';")
        cases.check('a retired choice returns to the default, and no one moves to a model they did not choose (Decision 0004)', 'deepseek default, planner kept, coder cleared', policy, policy == 'openrouter_deepseek_flash/openrouter_deepseek_flash/none')
        profile_rows = ops.sql("select string_agg(profile_id, ',' order by profile_id) from public.model_profiles;")
        cases.check('the approved profiles are DeepSeek, Sol and Terra (Decision 0019)', 'exactly three', profile_rows, profile_rows == 'openrouter_deepseek_flash,openrouter_sol,openrouter_terra')
        ready = wait(lambda: json.loads(api_call(api_port, ops.internal, token)[1])['ready'] is True, 30)
        cases.check('readiness returns once the schema has caught up', 'ready', ready, ready)
        kept = ops.sql(f"select count(*) from agent_runtime.checkpoints c join public.runs r on r.checkpoint_thread_id = c.thread_id where r.id = '{interrupted}';")
        cases.check('saved checkpoints are all still there', checkpoints, kept, kept == checkpoints)

        checked = run_child_check(cases, root, 'upgrade_check.py', 'upgrade', workspace, queued, interrupted, before_hash, label='the upgrade check',
                                  env={**ops.env, 'AUTOBOTS_PRIOR_RUNS': json.dumps(prior_runs)}, timeout=240, err_dir=root / ERR_DIR, err_name='upgrade')
        # Arranged: this process inherited tracing settings and skipped every entry point, and built real agents.
        tried = 'collector.example.invalid' in checked.stderr or 'LangSmith' in checked.stderr
        cases.check('agent construction turns tracing off, whoever calls it', 'no attempt to reach the arranged collector', tried, not tried)

        # A prior checkpoint continuing on this release's code, after a person settled the uncertain call.
        reconciled, _ = api_call(api_port, ops.internal, token, 'POST', f'/v1/runs/{interrupted}/model-calls/reconcile', json.dumps({'charged_micro_usd': 100}).encode(), {'Idempotency-Key': secrets.token_hex(8)})
        resume = subprocess.run([str(root / PYTHON), str(root / 'tests/db/operations_check.py'), 'resume', workspace, interrupted], env=ops.env, capture_output=True, text=True, timeout=60, check=False)
        marker.unlink(missing_ok=True)
        worker = ops.fixture_worker('upgraded-resume', 0, 30, marker, 'resume', 'openrouter_deepseek_flash')
        resumed = wait(lambda: ops.sql(f"select status from public.runs where id = '{interrupted}';") == 'succeeded', 60)
        worker.send_signal(signal.SIGTERM)
        exited(worker, 30)
        added = ops.sql(f"select count(*) from (select tool_id, argument_hash from app_private.tool_receipts where run_id = '{interrupted}' and status = 'succeeded' group by 1, 2 having count(*) > 1) d;")
        cases.check('a checkpoint saved by the prior code continues on this one', 'succeeded, no repeated effect', f'reconcile {reconciled}, resume {resume.returncode}, {resumed}, {receipts_before} receipts before, {added} repeated', reconciled == 200 and resume.returncode == 0 and resumed and added == '0')

        # Resume is refused through the route while a run is blocked. The key check comes first without a key,
        # so this is the same function the route calls, arranged directly.
        blocked_run = ops.admit(workspace)
        cases.arrange('a run blocked by a graph state this release does not know',
                      stack.sql(f"update public.runs set execution_contract = '{{\"graph_state\": 99, \"tools\": {{}}}}' where id = '{blocked_run}';"))
        probe = subprocess.run([str(root / PYTHON), '-c', (
            "import asyncio, os, psycopg, sys\n"
            "from uuid import UUID\n"
            "from autobots.application.goal_loop import execution_block\n"
            "async def main():\n"
            "    async with await psycopg.AsyncConnection.connect(os.environ['AUTOBOTS_DATABASE_URL'], autocommit=True) as db:\n"
            "        print(await execution_block(db, UUID(sys.argv[1])))\n"
            "asyncio.run(main())\n"), blocked_run], env=ops.env, capture_output=True, text=True, timeout=30, check=False)
        cases.check('the resume route has a reason to refuse a blocked run', 'graph state 99', probe.stdout.strip()[:60], 'graph state 99' in probe.stdout)
        cases.arrange("the blocked run's job set aside", stack.runtime(f"update app_private.run_jobs set status = 'done' where run_id = '{blocked_run}';"))

        # An unqualified adapter (arranged): as if a framework release changed under the same schema.
        migrator_url = ops.url.replace(f'autobots_runtime:{stack.runtime_password}', f'autobots_migrator:{stack.migrator_password}')
        run_child_check(cases, root, 'upgrade_check.py', 'adapter', migrator_url, ops.url, label='the adapter check', env=ops.env, timeout=120,
                        err_dir=root / ERR_DIR, err_name='adapter')
        saved = stack.sql('create table public.arranged_adapter_rows as select * from agent_runtime.adapter_qualifications;\ndelete from agent_runtime.adapter_qualifications;\n')
        cases.arrange('an unqualified adapter', saved)
        pending = ops.admit(workspace)
        code, body = api_call(api_port, ops.internal, token)
        admit_code, _ = api_call(api_port, ops.internal, token, 'POST', '/v1/runs', goal, {'Idempotency-Key': secrets.token_hex(8)})
        marker.unlink(missing_ok=True)
        early = ops.fixture_worker('unqualified', 0, 5, marker, 'fresh')
        time.sleep(4)
        early.send_signal(signal.SIGTERM)
        exited(early, 20)
        state = ops.sql(f"select status from app_private.run_jobs where run_id = '{pending}';")
        cases.check('an unqualified adapter stops continuation until qualified (arranged)', 'adapter_unqualified, 503, job still queued', f"{saved.returncode}, {conditions(body).get('adapter')}, {admit_code}, {state}", saved.returncode == 0 and conditions(body).get('adapter') == 'adapter_unqualified' and admit_code == 503 and state == 'queued')
        cases.arrange('the adapter qualification restored',
                      stack.sql('insert into agent_runtime.adapter_qualifications select * from public.arranged_adapter_rows;\ndrop table public.arranged_adapter_rows;\n'))
        back = wait(lambda: json.loads(api_call(api_port, ops.internal, token)[1])['ready'] is True, 15)
        cases.check('recording the qualification restores readiness', 'ready', back, back)
    finally:
        ops.stop_all()
        remove_stack(stack)
        shutil.rmtree(work, ignore_errors=True)
    label = f'label=com.docker.compose.project={project}'
    left_over = (run(['docker', 'volume', 'ls', '--filter', label, '--format', '{{.Name}}'], tool_env()).stdout
                 + run(['docker', 'ps', '-a', '--filter', label, '--format', '{{.Names}}'], tool_env()).stdout).strip()
    cases.check('cleanup removed the owned containers and volumes', 'none left', left_over or 'none', not left_over)
    after_resources = other_resources(project)
    cases.check('other Docker resources are untouched', 'same', f'{len(before)} before, {len(after_resources)} after', before == after_resources)
    passed = cases.status == 'passed'
    write_report(root / REPORT, {'schema_version': 'autobots.upgrade-qualification/v1', 'completed_at_utc': datetime.now(UTC).isoformat(),
                                 'duration_seconds': round(time.monotonic() - started_at, 1), 'input_fingerprint': fingerprint(root), 'prior_revision': PRIOR_REVISION,
                                 'digest': hashlib.sha256(json.dumps(cases.records).encode()).hexdigest(),
                                 'status': cases.status, 'target_class': 'disposable', 'cases': cases.records,
                                 'not_established': ['H1', 'product acceptance', 'the persistent stack', 'a real model call', 'a real image or framework version change']})
    print(f'{"PASS" if passed else "FAIL"}: upgrade qualification, {round(time.monotonic() - started_at)}s, report {REPORT}')
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
