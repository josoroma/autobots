#!/usr/bin/env python3
"""Exercises the upgrade runbook from a real prior release: its code and migrations, read from git history.

A disposable project takes the prior release's schema and runs its worker, then this revision's migrations
and code take over. The images and pinned packages are the same in both releases, so an image or framework
change is arranged, not observed. Exit 0 passed, 1 a case failed, 2 a prerequisite is missing.

Each scenario is a function of one UpgradeRun, run in the order SCENARIOS states, since later ones use the
state the prior code left (refactor plan R-65, SCRP-05).
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
from dataclasses import dataclass, field
from pathlib import Path

from app_db import (
    BOOTSTRAP_ROW,
    AppRun,
    AppStack,
    app_project,
    apply_bootstrap,
    apply_migrations,
    bootstrap,
    bootstrap_files,
    seed,
)
from disposable_db import Refused, Unavailable
from harness_lib import project_root
from qualification.children import CHECK_PYTHON as PYTHON
from qualification.children import launch, run_child_check
from qualification.ops import Ops, api_call, conditions, exited, wait
from qualification.owners import bootstrap_owner, password_token
from qualification.records import Cases
from qualification.report import finish
from qualification.scenarios import run_scenarios

REPORT = Path('.checks/upgrade/qualification.json')
# Where a failed child check's stderr is kept (qualification/children.py).
ERR_DIR = Path('.checks/upgrade')
# The operations, backup and upgrade qualifiers' fixture workers run a scripted model (qualification/profiles.py).
MODEL_TRANSPORT = 'mock'
# The release delivered before this one, with the worker fixture and every migration up to its own: at least
# PRIOR_MIGRATIONS of them, the last named PRIOR_LAST_MIGRATION (SCRP-19).
PRIOR_REVISION = '8cba043'
PRIOR_MIGRATIONS = 24
PRIOR_LAST_MIGRATION = '20261105000024'
BINDINGS = "select id, policy_snapshot, expert_id, expert_version, session_id from public.runs where id::text = any(%s) order by id"
GOAL = json.dumps({'goal_text': 'Write the report', 'limit_micro_usd': 1000000}).encode()


def extract_prior(root: Path, destination: Path) -> None:
    """Reads git history only. The checkout is untouched."""
    archive = subprocess.run(['git', 'archive', '--format=tar', PRIOR_REVISION, 'services/agent/src', 'supabase/migrations', 'supabase/seeds', 'tests/db'], cwd=root, capture_output=True, timeout=60, check=False)
    if archive.returncode:
        raise Unavailable(f'the prior release {PRIOR_REVISION} is not in this repository')
    with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tar:
        tar.extractall(destination, filter='data')


@dataclass
class UpgradeRun:
    """What the scenarios share: the stack and its processes, the prior release's files and owner, and the runs and
    facts the prior code left for this release to keep."""

    root: Path
    app: AppRun
    ops: Ops
    work: Path
    api_port: int
    email: str = 'owner-a@example.invalid'
    password: str = field(default_factory=lambda: secrets.token_urlsafe(24))
    workspace: str = ''
    token: str = ''
    finished: str = ''
    interrupted: str = ''
    queued: str = ''
    checkpoints: str = ''
    receipts_before: str = ''
    before_hash: str = ''

    @property
    def stack(self) -> AppStack:
        return self.app.stack

    @property
    def prior(self) -> Path:
        return self.work / 'prior'

    # The prior revision's tests/db is flat, as PRIOR_REVISION committed it, so the prior admission and worker keep
    # its paths, and only its own service source is on their path.
    @property
    def prior_env(self) -> dict[str, str]:
        return {'PYTHONPATH': str(self.prior / 'services/agent/src')}

    @property
    def marker(self) -> Path:
        return self.work / 'in-call'

    @property
    def prior_runs(self) -> list[str]:
        return [self.finished, self.interrupted, self.queued]

    def status(self) -> tuple[int, str]:
        return api_call(self.api_port, self.ops.internal, self.token)

    def admit_goal(self) -> tuple[int, str]:
        return api_call(self.api_port, self.ops.internal, self.token, 'POST', '/v1/runs', GOAL, {'Idempotency-Key': secrets.token_hex(8)})

    def prior_admit(self) -> str:
        result = launch([str(self.root / PYTHON), str(self.prior / 'tests/db/operations_check.py'), 'admit', self.workspace], env={**self.ops.env, **self.prior_env}, timeout=60, label='the prior admission')
        lines = result.stdout.strip().splitlines()
        if result.returncode or not lines:
            raise Unavailable(f'the prior release did not admit: exit {result.returncode}: {result.stderr.strip()[-300:]}')
        return lines[-1]

    def prior_worker(self, name: str, hold: float, drain: float, mode: str) -> subprocess.Popen[bytes]:
        return self.ops.spawn(name, [str(self.root / PYTHON), str(self.prior / 'tests/db/operations_worker.py'), self.ops.url, name, str(hold), str(drain), str(self.marker), mode], self.prior_env)


def prior_schema(run: UpgradeRun, cases: Cases) -> None:
    stack, root, prior = run.stack, run.root, run.prior
    started = stack.compose('up', '-d', '--wait', '--wait-timeout', '240', timeout=300)
    if started.returncode:
        raise Unavailable(f'the stack did not start: {started.stderr[-300:]}')
    bootstrap(stack, root)
    applied, problem = apply_migrations(stack, prior / 'supabase/migrations')
    # The prior release's own seeds: this release's can name a profile that schema doesn't have.
    if problem or seed(stack, prior).returncode:
        raise Unavailable(f'prior migrations failed: {problem}')
    # The prior release shipped storage.sql alone, the first bootstrap file.
    _, problem = apply_bootstrap(stack, root, upto=1)
    if problem:
        raise Unavailable(f"the prior release's storage.sql failed: {problem}")
    cases.check('the prior release schema is applied from its own files', f'{PRIOR_REVISION}', f'{applied} migrations', applied >= PRIOR_MIGRATIONS)
    owner = bootstrap_owner(root, run.app.base, stack.values['SERVICE_ROLE_KEY'], run.ops.url, run.email, run.password)
    run.workspace = owner['workspace_id']
    run.token = password_token(run.app.base, stack.values['ANON_KEY'], run.email, run.password)[1]


def prior_state(run: UpgradeRun, cases: Cases) -> None:
    """Real saved state, written by the prior code: finished, paused on an uncertain call, and queued."""
    ops, marker = run.ops, run.marker
    run.finished = run.prior_admit()
    worker = run.prior_worker('prior-finish', 0, 30, 'fresh')
    done = wait(lambda: ops.sql(f"select status from public.runs where id = '{run.finished}';") == 'succeeded', 60)
    worker.send_signal(signal.SIGTERM)
    exited(worker, 30)
    marker.unlink(missing_ok=True)
    run.interrupted = run.prior_admit()
    worker = run.prior_worker('prior-cut', 6, 1, 'fresh')
    wait(marker.exists, 40)
    worker.send_signal(signal.SIGTERM)
    exited(worker, 40)
    worker = run.prior_worker('prior-classify', 0, 30, 'resume')
    paused = wait(lambda: ops.sql(f"select status from public.runs where id = '{run.interrupted}';") == 'paused', 40)
    worker.send_signal(signal.SIGTERM)
    exited(worker, 30)
    run.queued = run.prior_admit()
    run.checkpoints = checkpoints = ops.sql(f"select count(*) from agent_runtime.checkpoints c join public.runs r on r.checkpoint_thread_id = c.thread_id where r.id = '{run.interrupted}';")
    cases.check('the prior code left finished, paused and queued work', 'succeeded, paused, a queued job, checkpoints', f'{done}, {paused}, {checkpoints} checkpoints', done and paused and int(checkpoints or 0) > 0)
    run.receipts_before = ops.sql(f"select count(*) from app_private.tool_receipts where run_id = '{run.interrupted}';")
    binding_probe = f"""
import hashlib, json, os, psycopg
with psycopg.connect(os.environ['AUTOBOTS_DATABASE_URL']) as db:
    rows = db.execute({BINDINGS!r}, ({run.prior_runs!r},)).fetchall()
print(hashlib.sha256(json.dumps(rows, default=str, sort_keys=True).encode()).hexdigest())
"""
    hashed = launch([str(run.root / PYTHON), '-c', binding_probe], env=ops.env, timeout=30, label='the binding probe')
    if hashed.returncode:
        raise Unavailable(f'the bindings could not be read: {hashed.stderr[-200:]}')
    run.before_hash = hashed.stdout.strip()


def new_code_on_old_schema(run: UpgradeRun, cases: Cases) -> None:
    """New code on the old schema: everything stops, and it says why."""
    ops = run.ops
    config_root = run.work / 'config'
    config_root.mkdir()
    ops.api(run.api_port, config_root)
    wait(lambda: run.status()[0] == 200, 40)
    code, body = run.status()
    admit_code, _ = run.admit_goal()
    cases.check('new code on the old schema refuses admission', 'schema_behind, 503', f"{conditions(body).get('schema') if code == 200 else code}, {admit_code}", code == 200 and conditions(body).get('schema') == 'schema_behind' and admit_code == 503)
    run.marker.unlink(missing_ok=True)
    early = ops.fixture_worker('new-on-old', 0, 5, run.marker, 'fresh')
    time.sleep(4)
    early.send_signal(signal.SIGTERM)
    exited(early, 20)
    state = ops.sql(f"select status from app_private.run_jobs where run_id = '{run.queued}';")
    cases.check('a new worker on the old schema claims nothing', 'queued', state, state == 'queued')


def forward_paths(run: UpgradeRun, cases: Cases) -> None:
    """A failing migration leaves the schema as it was, and an edited one is refused."""
    root, stack, work = run.root, run.stack, run.work
    broken = work / 'broken'
    shutil.copytree(root / 'supabase/migrations', broken)
    (broken / '20261105999998_arranged_failure.sql').write_text('create table public.arranged_partial (id int);\nselect 1/0;\n')
    for path in sorted(broken.glob('*.sql')):
        if path.name > f'{PRIOR_LAST_MIGRATION}_' and 'arranged' not in path.name:
            path.unlink()
    failed_count, failed = apply_migrations(stack, broken)
    left = run.ops.sql("select to_regclass('public.arranged_partial') is null;")
    cases.check('a failing migration rolls back and is reported (arranged)', 'reported, no partial table, not recorded', f'{failed_count}, {bool(failed)}, absent {left}', failed and failed_count == 0 and left == 't')
    edited = work / 'edited'
    shutil.copytree(root / 'supabase/migrations', edited)
    first = sorted(edited.glob('*.sql'))[0]
    first.write_text(first.read_text() + '\n-- arranged edit\n')
    _, refusal = apply_migrations(stack, edited)
    cases.check('an edited applied migration is refused (arranged)', 'refused', refusal and refusal[-60:], bool(refusal) and 'never edit' in refusal)


def upgrade(run: UpgradeRun, cases: Cases) -> None:
    """The real upgrade, after a workspace and a role chose the model a later release retires."""
    root, stack, ops = run.root, run.stack, run.ops
    cases.arrange('a workspace and a role that chose a retired model',
                  stack.runtime(f"""insert into app_private.model_policies (workspace_id, version, default_profile, role_overrides) values ('{run.workspace}', 7, 'openrouter_astra', '{{"coder": "openrouter_astra", "planner": "openrouter_deepseek_flash"}}') on conflict (workspace_id) do update set default_profile = excluded.default_profile, role_overrides = excluded.role_overrides;"""))
    upgraded, problem = apply_migrations(stack, root / 'supabase/migrations')
    cases.check('this release applies forward over the prior one', 'the new migrations, no error', f'{upgraded}, {problem}', upgraded >= 1 and not problem)
    reseeded = seed(stack, root)
    cases.check("this release's seeds apply over the upgraded schema", 'exit 0', reseeded.returncode, reseeded.returncode == 0)
    newer = [BOOTSTRAP_ROW + path.name for path in bootstrap_files(root)[1:]]
    bootstrapped, problem = apply_bootstrap(stack, root)
    cases.check("this release's bootstrap files apply after the prior storage.sql", ', '.join(newer), f'{bootstrapped}, {problem}',
                bootstrapped == newer and problem is None)
    policy = ops.sql(f"select default_profile || '/' || (role_overrides ->> 'planner') || '/' || coalesce(role_overrides ->> 'coder', 'none') from app_private.model_policies where workspace_id = '{run.workspace}';")
    cases.check('a retired choice returns to the default, and no one moves to a model they did not choose (Decision 0004)', 'deepseek default, planner kept, coder cleared', policy, policy == 'openrouter_deepseek_flash/openrouter_deepseek_flash/none')
    profile_rows = ops.sql("select string_agg(profile_id, ',' order by profile_id) from public.model_profiles;")
    cases.check('the approved profiles are DeepSeek, Sol and Terra (Decision 0019)', 'exactly three', profile_rows, profile_rows == 'openrouter_deepseek_flash,openrouter_sol,openrouter_terra')
    ready = wait(lambda: json.loads(run.status()[1])['ready'] is True, 30)
    cases.check('readiness returns once the schema has caught up', 'ready', ready, ready)
    kept = ops.sql(f"select count(*) from agent_runtime.checkpoints c join public.runs r on r.checkpoint_thread_id = c.thread_id where r.id = '{run.interrupted}';")
    cases.check('saved checkpoints are all still there', run.checkpoints, kept, kept == run.checkpoints)
    checked = run_child_check(cases, root, 'checks/upgrade_check.py', 'upgrade', run.workspace, run.queued, run.interrupted, run.before_hash, label='the upgrade check',
                              env={**ops.env, 'AUTOBOTS_PRIOR_RUNS': json.dumps(run.prior_runs)}, timeout=240, err_dir=root / ERR_DIR, err_name='upgrade')
    # Arranged: this process inherited tracing settings and skipped every entry point, and built real agents.
    tried = 'collector.example.invalid' in checked.stderr or 'LangSmith' in checked.stderr
    cases.check('agent construction turns tracing off, whoever calls it', 'no attempt to reach the arranged collector', tried, not tried)


def prior_checkpoint_continues(run: UpgradeRun, cases: Cases) -> None:
    """A prior checkpoint continuing on this release's code, after a person settled the uncertain call."""
    root, ops, interrupted = run.root, run.ops, run.interrupted
    reconciled, _ = api_call(run.api_port, ops.internal, run.token, 'POST', f'/v1/runs/{interrupted}/model-calls/reconcile', json.dumps({'charged_micro_usd': 100}).encode(), {'Idempotency-Key': secrets.token_hex(8)})
    resume = launch([str(root / PYTHON), str(root / 'tests/db/arrange/run_commands.py'), 'resume', run.workspace, interrupted], env=ops.env, timeout=60, label='the upgraded resume')
    run.marker.unlink(missing_ok=True)
    worker = ops.fixture_worker('upgraded-resume', 0, 30, run.marker, 'resume', 'openrouter_deepseek_flash')
    resumed = wait(lambda: ops.sql(f"select status from public.runs where id = '{interrupted}';") == 'succeeded', 60)
    worker.send_signal(signal.SIGTERM)
    exited(worker, 30)
    added = ops.sql(f"select count(*) from (select tool_id, argument_hash from app_private.tool_receipts where run_id = '{interrupted}' and status = 'succeeded' group by 1, 2 having count(*) > 1) d;")
    cases.check('a checkpoint saved by the prior code continues on this one', 'succeeded, no repeated effect', f'reconcile {reconciled}, resume {resume.returncode}, {resumed}, {run.receipts_before} receipts before, {added} repeated', reconciled == 200 and resume.returncode == 0 and resumed and added == '0')


def blocked_run_refused(run: UpgradeRun, cases: Cases) -> None:
    """Resume is refused through the route while a run is blocked. The key check comes first without a key, so this
    is the same function the route calls, arranged directly."""
    root, stack, ops = run.root, run.stack, run.ops
    blocked_run = ops.admit(run.workspace)
    cases.arrange('a run blocked by a graph state this release does not know',
                  stack.sql(f"update public.runs set execution_contract = '{{\"graph_state\": 99, \"tools\": {{}}}}' where id = '{blocked_run}';"))
    probe = subprocess.run([str(root / PYTHON), '-c', (
            "import asyncio, os, psycopg, sys\n"
            "from uuid import UUID\n"
            "from autobots.application.recovery import execution_block\n"
            "async def main():\n"
            "    async with await psycopg.AsyncConnection.connect(os.environ['AUTOBOTS_DATABASE_URL'], autocommit=True) as db:\n"
            "        print(await execution_block(db, UUID(sys.argv[1])))\n"
            "asyncio.run(main())\n"), blocked_run], env=ops.env, capture_output=True, text=True, timeout=30, check=False)
    cases.check('the resume route has a reason to refuse a blocked run', 'graph state 99', probe.stdout.strip()[:60], 'graph state 99' in probe.stdout)
    cases.arrange("the blocked run's job set aside", stack.runtime(f"update app_private.run_jobs set status = 'done' where run_id = '{blocked_run}';"))


def unqualified_adapter(run: UpgradeRun, cases: Cases) -> None:
    """An unqualified adapter (arranged): as if a framework release changed under the same schema."""
    root, stack, ops = run.root, run.stack, run.ops
    migrator_url = ops.url.replace(f'autobots_runtime:{stack.runtime_password}', f'autobots_migrator:{stack.migrator_password}')
    run_child_check(cases, root, 'checks/upgrade_check.py', 'adapter', migrator_url, ops.url, label='the adapter check', env=ops.env, timeout=120,
                    err_dir=root / ERR_DIR, err_name='adapter')
    saved = stack.sql('create table public.arranged_adapter_rows as select * from agent_runtime.adapter_qualifications;\ndelete from agent_runtime.adapter_qualifications;\n')
    cases.arrange('an unqualified adapter', saved)
    pending = ops.admit(run.workspace)
    _code, body = run.status()
    admit_code, _ = run.admit_goal()
    run.marker.unlink(missing_ok=True)
    early = ops.fixture_worker('unqualified', 0, 5, run.marker, 'fresh')
    time.sleep(4)
    early.send_signal(signal.SIGTERM)
    exited(early, 20)
    state = ops.sql(f"select status from app_private.run_jobs where run_id = '{pending}';")
    cases.check('an unqualified adapter stops continuation until qualified (arranged)', 'adapter_unqualified, 503, job still queued', f"{saved.returncode}, {conditions(body).get('adapter')}, {admit_code}, {state}", saved.returncode == 0 and conditions(body).get('adapter') == 'adapter_unqualified' and admit_code == 503 and state == 'queued')
    cases.arrange('the adapter qualification restored',
                  stack.sql('insert into agent_runtime.adapter_qualifications select * from public.arranged_adapter_rows;\ndrop table public.arranged_adapter_rows;\n'))
    back = wait(lambda: json.loads(run.status()[1])['ready'] is True, 15)
    cases.check('recording the qualification restores readiness', 'ready', back, back)


SCENARIOS = (prior_schema, prior_state, new_code_on_old_schema, forward_paths, upgrade, prior_checkpoint_continues, blocked_run_refused,
             unqualified_adapter)


def qualify(root: Path) -> int:
    cases = Cases(model_transport=MODEL_TRANSPORT)
    work = Path(tempfile.mkdtemp(prefix='autobots-upgrade-'))
    try:
        # Read before any stack exists, so a missing prior release leaves nothing to remove, and no earlier report.
        (root / REPORT).unlink(missing_ok=True)
        extract_prior(root, work / 'prior')
        with app_project(root, cases, report=root / REPORT, extra_ports=1) as app:
            logs = root / '.checks/upgrade/logs'
            logs.mkdir(parents=True, exist_ok=True)
            for old in logs.glob('*.log'):
                old.unlink()
            ops = Ops(root, app.stack, app.base, app.db_port, logs)
            try:
                run_scenarios(UpgradeRun(root, app, ops, work, app.ports[0]), cases, SCENARIOS)
            finally:
                ops.stop_all()
    finally:
        shutil.rmtree(work, ignore_errors=True)
    code = finish(root, root / REPORT, 'autobots.upgrade-qualification/v1', cases, app.started_at,
                  ['H1', 'product acceptance', 'the persistent stack', 'a real model call', 'a real image or framework version change'],
                  prior_revision=PRIOR_REVISION, digest=hashlib.sha256(json.dumps(cases.records).encode()).hexdigest())
    print(f'{"PASS" if code == 0 else "FAIL"}: upgrade qualification, {round(time.monotonic() - app.started_at)}s, report {REPORT}')
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
