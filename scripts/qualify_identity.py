#!/usr/bin/env python3
"""Real local Auth, membership, PostgREST and Storage on a disposable pinned stack, with nonprivileged identities.

Creates a new project with generated secrets, migrates it, bootstraps two owners through the Auth
admin API, then drives real sign-in, the Python API, the BFF and each exposed service. It removes
only that project. No model is called, and nothing persistent is touched.

Each browser story's state is arranged by one step in ARRANGEMENTS, in order, from the synthetic SQL
fixtures under tests/db/identity. Each step records `arranged: <label>` or raises Unavailable, so no
browser case can pass on a fixture that never existed (refactor plan R-47, SCRP-02, SCRP-09).

Exit codes: 0 passed, 1 a case failed, 2 prerequisite unavailable.
OpenRouter itself is a local fake that logs each request, and it holds no real credential.
Passing establishes neither H1 nor product acceptance.
"""
from __future__ import annotations

import json
import secrets
import shutil
import string
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from app_db import AppStack, app_project, apply_bootstrap, start_app
from disposable_db import (
    Cases,
    Refused,
    Unavailable,
    rows,
    tool_env,
)
from harness_lib import project_root
from qualification.children import (
    Child,
    ChildRun,
    run_arrangement,
    run_child,
    run_child_check,
    service_env,
)
from qualification.net import http
from qualification.owners import bootstrap_owner, password_token
from qualification.report import finish
from qualify_web import BROWSERS, run_problems, start, stop, summarize, wait_until_up
from suites import ARRANGED_PROJECT, IDENTITY_PROJECT, SLICE_PROJECT
from toolchain import child_env, find_tools

REPORT = Path('.checks/identity/qualification.json')
# Read by the recorded evidence scripts under docs/engineering/evidence/ (US-10.2, US-12.4).
STORAGE_SQL = Path('supabase/bootstrap/storage.sql')
BUCKET = 'workspace-artifacts'
PYTHON = Path('services/agent/.venv/bin/python')
# Where a failed child check's stderr is kept (qualification/children.py).
ERR_DIR = Path('.checks/identity')
# The SQL each arrangement sends, with `${name}` placeholders that `fixture` fills in.
IDENTITY_FIXTURES = Path('tests/db/identity')
# Its children drive runs with a scripted model, as its step in qualification/profiles.py says.
MODEL_TRANSPORT = 'mock'
# The checks after the artifact check, in order, against real Storage through the runtime role. Arguments
# name workspace A, workspace B or the service's interpreter (qualification/children.py Child).
IDENTITY_CHILDREN = (
    Child('verification_check.py', 'the verification check', ('{a}',), timeout=240),
    Child('assignment_check.py', 'the assignment check', ('{a}', '{python}'), timeout=240),
    Child('approval_check.py', 'the approval check', ('{a}', '{b}'), timeout=240),
    Child('effect_check.py', 'the effect check', ('{a}', '{b}', '{python}'), timeout=240),
    Child('workflow_run_check.py', 'the workflow run check', ('{a}', '{python}'), timeout=240),
    Child('blocker_check.py', 'the blocker check', ('{a}',), timeout=240),
    Child('major_check.py', 'the major check', ('{a}', '{b}'), timeout=240),
    Child('connector_check.py', 'the connector check', ('{a}',), timeout=240),
    Child('pull_request_check.py', 'the pull request check', ('{a}',), timeout=240),
    Child('wake_check.py', 'the wake check', ('{a}',), timeout=240),
    Child('review_check.py', 'the review check', ('{a}',), timeout=240),
    Child('improvement_check.py', 'the improvement check', ('{a}', '{b}'), timeout=240),
    Child('provider_key_check.py', 'the provider key check', ('{a}',), timeout=240),
    # Last, so no later check's cleanup ends the runs they leave claimed for the browser.
    # The task timing check claims only its own runs and cleans up nothing.
    Child('tool_use_view_check.py', 'the tool-use view check', ('{a}',), timeout=240),
    Child('task_timing_check.py', 'the task timing check', ('{a}',), timeout=240),
    Child('result_stream_check.py', 'the result stream check', ('{a}',), timeout=240),
)
# Owners other steps read, by the email each is bootstrapped with.
OWNER_A, OWNER_B = 'owner-a@example.invalid', 'owner-b@example.invalid'
RUN_LIST_OWNER = 'runs-g@example.invalid'
WORKFLOWS_OWNER = 'flows-l@example.invalid'
OPERATIONS_OWNER = 'ops-n@example.invalid'
# IDs of arranged records that a browser suite, a graph or another fixture names.
RUN_A = '11111111-1111-4111-8111-111111111111'
KEYLESS_RUN = '33333333-3333-4333-8333-333333333333'
COMPOSER_EXPERT = '66666666-6666-4666-8666-000000000002'
HOME_RUNS = tuple(f'77777777-7777-4777-8777-00000000000{index}' for index in range(1, 8))
HOME_APPROVALS = ('77777777-7777-4777-8777-0000000000a1', '77777777-7777-4777-8777-0000000000a2')
ANALYST, WRITER = '88888888-8888-4888-8888-0000000000e1', '88888888-8888-4888-8888-0000000000e2'
BRIEF, PLAIN = '88888888-8888-4888-8888-0000000000f1', '88888888-8888-4888-8888-0000000000f2'
FLOW_RUNS = tuple(f'88888888-8888-4888-8888-00000000000{index}' for index in range(1, 4))
SEARCH_IDS = {'run': '99999999-9999-4999-8999-0000000000d1', 'expert': '99999999-9999-4999-8999-0000000000d2',
              'workflow': '99999999-9999-4999-8999-0000000000d3', 'other_run': '88888888-8888-4888-8888-0000000000d4',
              'other_expert': '88888888-8888-4888-8888-0000000000d5'}
DELAYED_ROUTINE = '44444444-4444-4444-8444-444444444444'
# The arranged project's tests run one at a time, each after its own arrangement (suites.ARRANGED_PROJECT). Each
# is selected by its spec file and its title, so a title that another arranged spec repeats can't select a second
# test (R-58). The spec comes before --project, which would read it as another project's name.
QUALIFICATION_SPEC, SAVED_CHOICE_SPEC, READINESS_SPEC = 'qualification.spec.ts', 'saved-choice.spec.ts', 'readiness.spec.ts'
QUALIFICATION_TITLES = ('after an API restart', 'a route with no record')
# A saved choice naming DeepSeek can't be made through the product now, so each is arranged: its title, the
# saved default and the saved role overrides.
SAVED_CHOICES = (('a saved default naming DeepSeek', 'openrouter_deepseek_flash', {}),
                 ('a saved override on another role', 'openrouter_terra', {'coder': 'openrouter_deepseek_flash'}),
                 ('a saved executor override', 'openrouter_terra', {'executor': 'openrouter_deepseek_flash'}),
                 ('a saved Expert binding', 'openrouter_terra', {}))
READINESS_TITLES = ("names the service that isn't ready", 'all local services ready')


def denied(status: int) -> bool:
    return 400 <= status < 500


@dataclass(frozen=True)
class Owner:
    """An owner bootstrapped with a workspace of its own, and the password it signs in with."""

    email: str
    password: str
    workspace_id: str
    user_id: str


@dataclass(frozen=True)
class IdentityRun:
    """The disposable stack one qualification drives, and the owners bootstrapped on it so far, by email."""

    root: Path
    stack: AppStack
    base: str
    db_port: int
    owners: dict[str, Owner] = field(default_factory=dict)

    @property
    def runtime_url(self) -> str:
        return f'postgresql://autobots_runtime:{self.stack.runtime_password}@127.0.0.1:{self.db_port}/postgres'

    @property
    def service_key(self) -> str:
        return self.stack.values['SERVICE_ROLE_KEY']

    @property
    def anon_key(self) -> str:
        return self.stack.values['ANON_KEY']

    def owner(self, email: str) -> Owner:
        """Bootstrap an owner and its workspace through the Auth admin API, with a new password. One that could
        not be bootstrapped raises Unavailable, since no case after it would show anything."""
        password = secrets.token_urlsafe(24)
        printed = bootstrap_owner(self.root, self.base, self.service_key, self.runtime_url, email, password)
        user_id, workspace_id = printed.get('user_id'), printed.get('workspace_id')
        if not (isinstance(user_id, str) and isinstance(workspace_id, str)):
            raise Unavailable(f'owner bootstrap printed no user and workspace for {email}')
        self.owners[email] = Owner(email, password, workspace_id, user_id)
        return self.owners[email]

    def bootstrapped(self, email: str) -> Owner:
        """An owner an earlier step bootstrapped. ARRANGEMENTS orders each step after the owners it reads."""
        if email not in self.owners:
            raise LookupError(f'{email} is bootstrapped by an earlier step, which has not run')
        return self.owners[email]


def sql_literal(value: str) -> str:
    """`value` as one SQL string literal, each quote doubled, as standard_conforming_strings reads it."""
    return "'" + value.replace("'", "''") + "'"


def fixture(root: Path, name: str, **values: str) -> str:
    """The SQL of tests/db/identity/<name>, each `${name}` replaced by its value as one SQL literal. A
    placeholder with no value, a value with no placeholder, or any other `$`, is refused."""
    template = string.Template((root / IDENTITY_FIXTURES / name).read_text())
    if not template.is_valid():
        raise ValueError(f'{name} holds a `$` that is not a `${{name}}` placeholder')
    named = set(template.get_identifiers())
    if named != set(values):
        raise ValueError(f'{name} names {sorted(named)}, given {sorted(values)}')
    return template.substitute({key: sql_literal(value) for key, value in values.items()})


def numbered(prefix: str, values: Sequence[str]) -> dict[str, str]:
    """Fixture parameters `<prefix>_1`, `<prefix>_2` and so on, one for each value."""
    return {f'{prefix}_{index}': value for index, value in enumerate(values, start=1)}


def membership(workspace: str, user: str) -> str:
    return f"insert into public.workspace_members (workspace_id, user_id, role) values ({sql_literal(workspace)}, {sql_literal(user)}, 'member');\n"


def auth_cases(cases: Cases, base: str, anon: str, email: str, password: str) -> None:
    status, _ = http('POST', f'{base}/auth/v1/signup', {'apikey': anon, 'Content-Type': 'application/json'},
                     json.dumps({'email': 'stranger@example.invalid', 'password': secrets.token_hex(16)}).encode())
    cases.check('public signup is refused', 'a 4xx refusal', str(status), denied(status))
    status, _ = password_token(base, anon, email, 'not-the-password')
    cases.check('a wrong password gets no token', 'a 4xx refusal', str(status), denied(status))


def rest_cases(cases: Cases, stack: AppStack, base: str, anon: str, token_a: str, token_b: str, run_a: str) -> None:
    def rest(path: str, token: str | None = None, method: str = 'GET', extra: Mapping[str, str] | None = None, body: bytes | None = None) -> tuple[int, str]:
        headers = {'apikey': anon, **({'Authorization': f'Bearer {token}'} if token else {}), **(extra or {})}
        return http(method, f'{base}/rest/v1/{path}', headers, body)
    status, body = rest(f'runs?select=id&id=eq.{run_a}', token_a)
    cases.check('a member reads its run through PostgREST', 'one row', f'{status} {body[:70]}', status == 200 and run_a in body)
    status, body = rest(f'runs?select=id&id=eq.{run_a}', token_b)
    cases.check('another workspace reads no run through PostgREST', 'no rows', f'{status} {body[:40]}', status == 200 and json.loads(body) == [])
    status, _ = rest('runs?select=id')
    cases.check('anonymous is refused on runs', 'a 4xx refusal', str(status), denied(status))
    status, _ = rest('runs?select=id', f'{token_a[:-4]}AAAA')
    cases.check('a forged token is refused on runs', 'a 4xx refusal', str(status), denied(status))
    status, _ = rest('runs?select=lease_generation', token_a)
    cases.check('lease columns are refused', 'a 4xx refusal', str(status), denied(status))
    status, _ = rest('runs', token_a, 'POST', {'Content-Type': 'application/json'}, b'{"limit_micro_usd": 1}')
    cases.check('a member cannot write runs through PostgREST', 'a 4xx refusal', str(status), denied(status))
    cases.arrange('a canary table in each private schema',
                  stack.migrator('create table app_private.canary (id int);\ncreate table agent_runtime.canary (id int);\n'))
    for schema in ('app_private', 'agent_runtime'):
        status, _ = rest('canary', token_a, extra={'Accept-Profile': schema})
        cases.check(f'{schema} is not an exposed PostgREST schema', 'refused', str(status), denied(status))
    status, _ = rest('canary', token_a)
    cases.check('a private table is absent from the public schema', 'a 4xx refusal', str(status), denied(status))
    status, body = http('GET', f'{base}/rest/v1/', {'apikey': stack.values['SERVICE_ROLE_KEY'], 'Authorization': f"Bearer {stack.values['SERVICE_ROLE_KEY']}"})
    listed = status == 200 and ('canary' in body or 'app_private' in body or 'agent_runtime' in body)
    cases.check('private schemas are absent from the PostgREST description', 'absent', f'{status}, listed {listed}', status == 200 and not listed)
    published = rows(stack, "select count(*) from pg_publication_tables where schemaname in ('app_private', 'agent_runtime');")
    cases.check('private schemas are in no Realtime publication', '0 tables', published, published == '0')
    usage = rows(stack, "select has_schema_privilege('authenticated', 'app_private', 'usage')::text || ',' || has_schema_privilege('anon', 'agent_runtime', 'usage')::text;")
    cases.check('authenticated holds no usage on private schemas', 'false,false', usage, usage == 'false,false')


def storage_cases(cases: Cases, base: str, anon: str, service: str, token_a: str, token_b: str, workspace_a: str, workspace_b: str) -> None:
    def storage(method: str, path: str, token: str | None, body: bytes | None = None, kind: str = 'text/plain', key: str = anon) -> tuple[int, str]:
        headers = {'apikey': key, **({'Authorization': f'Bearer {token}'} if token else {}), **({'Content-Type': kind} if body is not None else {})}
        return http(method, f'{base}/storage/v1/{path}', headers, body)
    target = f'{BUCKET}/{workspace_a}/note.txt'
    # Decision 0029 F3: the API writes artifacts with the service key, and a member writes none.
    status, _ = storage('POST', f'object/{target}', service, b'artifact bytes', key=service)
    cases.check('arranged: the service key writes an object to workspace A', '200', str(status), status == 200)
    status, _ = storage('POST', f'object/{BUCKET}/{workspace_a}/mine.txt', token_a, b'x')
    cases.check("a member can't upload to its own workspace", 'a 4xx refusal', str(status), denied(status))
    status, _ = storage('PUT', f'object/{target}', token_a, b'replaced')
    cases.check("a member can't overwrite its workspace's object", 'a 4xx refusal', str(status), denied(status))
    storage('DELETE', f'object/{target}', token_a)
    status, body = storage('GET', f'object/authenticated/{target}', token_a)
    cases.check("a member can't delete or change its workspace's object", 'still readable, unchanged', str(status), status == 200 and body == 'artifact bytes')
    status, body = storage('GET', f'object/authenticated/{target}', token_a)
    cases.check('a member reads its object', '200 and the bytes', f'{status}', status == 200 and body == 'artifact bytes')
    for label, token in (('another workspace', token_b), ('anonymous', None), ('a forged token', f'{token_a[:-4]}AAAA')):
        status, body = storage('GET', f'object/authenticated/{target}', token)
        cases.check(f'{label} cannot read the object', 'a 4xx refusal', str(status), denied(status) and 'artifact bytes' not in body)
    status, _ = storage('POST', f'object/{BUCKET}/{workspace_a}/intruder.txt', token_b, b'x')
    cases.check('another workspace cannot upload there', 'a 4xx refusal', str(status), denied(status))
    status, _ = storage('POST', f'object/{BUCKET}/not-a-uuid/x.txt', token_a, b'x')
    cases.check('an unscoped path is refused', 'a 4xx refusal', str(status), denied(status))
    status, _ = storage('POST', f'object/{BUCKET}/{workspace_b}/x.txt', token_a, b'x')
    cases.check('a member cannot upload to another workspace', 'a 4xx refusal', str(status), denied(status))
    listing = json.dumps({'prefix': workspace_a}).encode()
    status, body = storage('POST', f'object/list/{BUCKET}', token_b, listing, 'application/json')
    cases.check('another workspace lists nothing', 'no objects', f'{status} {body[:40]}', status == 200 and 'note.txt' not in body)
    status, body = storage('POST', f'object/list/{BUCKET}', token_a, listing, 'application/json')
    cases.check('a member lists its object', 'the object', f'{status}', status == 200 and 'note.txt' in body)
    storage('DELETE', f'object/{target}', token_b)
    status, body = storage('GET', f'object/authenticated/{target}', token_a)
    cases.check('another workspace cannot delete the object', 'still readable', str(status), status == 200 and body == 'artifact bytes')
    status, _ = storage('GET', f'object/public/{target}', None)
    cases.check('the bucket has no public read', 'a 4xx refusal', str(status), denied(status))


def storage_child_cases(run: IdentityRun, cases: Cases, token_a: str, token_b: str) -> dict[str, str]:
    """The child checks against real Storage through the runtime role, then the arrangements that read what they
    left: the artifact check, each IDENTITY_CHILDREN check, each schema state, an older approval request and the
    run workspace's fixtures. With no artifact report, nothing after it runs. Returns the variables the browser
    suites read."""
    artifact = artifact_check(run, cases, token_a, token_b)
    if artifact.report is None:
        return {}
    printed = identity_children(run, cases)
    schema_state_cases(run, cases)
    legacy_approval_cases(run, cases, printed.get('AUTOBOTS_TEST_APPROVAL_LEGACY'))
    return {**printed, **arrange_run_workspace(run, cases, artifact), 'AUTOBOTS_TEST_ARTIFACT_RUN': artifact.text('run_id'),
            'AUTOBOTS_TEST_ARTIFACT_ID': artifact.text('artifact_id'), 'AUTOBOTS_TEST_ARTIFACT_TEXT': artifact.text('expected_text'),
            'AUTOBOTS_TEST_ARTIFACT_GONE': artifact.text('gone_id'), 'AUTOBOTS_TEST_ARTIFACT_TAMPERED': artifact.text('tampered_id')}


def artifact_check(run: IdentityRun, cases: Cases, token_a: str, token_b: str) -> ChildRun:
    """Publication and recovery against real Storage, through the runtime role."""
    return run_child_check(cases, run.root, 'artifact_check.py', run.bootstrapped(OWNER_A).workspace_id, run.bootstrapped(OWNER_B).workspace_id,
                           label='the artifact check',
                           env=service_env(run.root, run.runtime_url, AUTOBOTS_STORAGE_BASE=run.base, AUTOBOTS_STORAGE_ANON=run.anon_key,
                                           AUTOBOTS_STORAGE_SERVICE=run.service_key, AUTOBOTS_TOKEN_A=token_a, AUTOBOTS_TOKEN_B=token_b),
                           timeout=240, err_dir=run.root / ERR_DIR)


def identity_children(run: IdentityRun, cases: Cases) -> dict[str, str]:
    """Each IDENTITY_CHILDREN check, in order. Returns the browser variables they printed."""
    values = {'a': run.bootstrapped(OWNER_A).workspace_id, 'b': run.bootstrapped(OWNER_B).workspace_id, 'python': str(run.root / PYTHON)}
    env = service_env(run.root, run.runtime_url, AUTOBOTS_STORAGE_BASE=run.base, AUTOBOTS_STORAGE_SERVICE=run.service_key)
    printed: dict[str, str] = {}
    for child in IDENTITY_CHILDREN:
        printed.update(run_child(cases, run.root, child, values, env=env, err_dir=run.root / ERR_DIR).env('browser_env'))
    return printed


def schema_state_cases(run: IdentityRun, cases: Cases) -> None:
    """US-16.2: each schema state is arranged as the admin, read as the runtime role, then restored."""
    root, stack = run.root, run.stack

    def schema_state(state: str) -> None:
        run_child_check(cases, root, 'schema_release_check.py', state, label=f'the schema check for {state}', env=service_env(root, run.runtime_url),
                        timeout=60, err_dir=root / ERR_DIR, err_name=f'schema_release_check-{state}')

    history = 'autobots_disposable.migrations'
    newest = sorted(path.name for path in (root / 'supabase/migrations').glob('*.sql'))[-1]
    future = '29991231000000_a_later_release.sql'
    schema_state('equal')
    read = stack.sql(f'select sha256 from {history} where name = {sql_literal(newest)};\n')
    held = read.stdout.strip()
    steps = [read, stack.sql(f'delete from {history} where name = {sql_literal(newest)};\n')]
    try:
        schema_state('behind')
    finally:
        steps.append(stack.sql(f'insert into {history} (name, sha256) values ({sql_literal(newest)}, {sql_literal(held)});\n'))
    steps.append(stack.sql(f"insert into {history} (name, sha256) values ({sql_literal(future)}, repeat('0', 64));\n"))
    try:
        schema_state('ahead')
    finally:
        steps.append(stack.sql(f'delete from {history} where name = {sql_literal(future)};\n'))
    steps.append(stack.sql(f'alter table {history} rename to migrations_hidden;\n'))
    try:
        schema_state('no-history')
        steps.append(stack.sql('alter table app_private.plan_task_times rename to plan_task_times_hidden;\n'))
        try:
            schema_state('no-history-missing')
        finally:
            steps.append(stack.sql('alter table app_private.plan_task_times_hidden rename to plan_task_times;\n'))
    finally:
        steps.append(stack.sql(f"alter table {history.split('.')[0]}.migrations_hidden rename to migrations;\n"))
    restored = stack.sql(f"select count(*) from {history} where name ~ '^[0-9]{{14}}_'; select to_regclass('app_private.plan_task_times') is not null;\n").stdout.split()
    migrations = len(list((root / 'supabase/migrations').glob('*.sql')))
    exits = [step.returncode for step in steps]
    cases.arranged('each schema state, then restored', f'every step exit 0, the newest sha256 read, {migrations} rows, the table back',
                   (exits, bool(held), restored), not any(exits) and bool(held) and restored == [str(migrations), 't'])


def legacy_approval_cases(run: IdentityRun, cases: Cases, legacy: str | None) -> None:
    """US-13.1: an older request, which the approval check names, arranged as the migration finds one, with
    nothing recorded. Only the superuser bypasses the trigger. None of those columns can be filled in later."""
    if not legacy:
        return
    request_id = sql_literal(legacy)
    cleared = run.stack.sql("begin;\nset local session_replication_role = replica;\n"
                            "update public.approval_requests set policy_reason = null, resource_target = null, requested_by = null, requested_by_agent = null, "
                            f"scope_snapshot = null, policy_version = null, policy_rule = null where id = {request_id};\ncommit;\n")
    cases.arrange('an older request with nothing recorded', cleared)
    for column, filled_in in (('requested_by_agent', json.dumps({'kind': 'coordinator'})), ('scope_snapshot', json.dumps({'tools': {}, 'paths': []})),
                              ('policy_version', 'approval-policy/1')):
        filled = run.stack.runtime(f'update public.approval_requests set {column} = {sql_literal(filled_in)} where id = {request_id};\n')
        cases.check(f"an older request's {column} can't be filled in", 'refused as immutable', filled.stderr.strip()[-120:],
                    filled.returncode != 0 and 'immutable' in filled.stderr)


def arrange_run_workspace(run: IdentityRun, cases: Cases, artifact: ChildRun) -> dict[str, str]:
    """Arranged for the run workspace: text a model wrote, a raw framework event, and lost history."""
    loop_run, gap_run = artifact.text('loop_run'), artifact.text('run_id')
    run_id, event = sql_literal(loop_run), sql_literal(json.dumps({'type': 'model.reasoning', 'text': 'PROTECTED-REASONING'}))
    written = run.stack.runtime(
        f"insert into app_private.plan_evidence (run_id, task_id, evidence, summary) values ({run_id}, 'a', '[]', 'used sk-or-leaked-value-here');\n"
        f'update public.runs set event_sequence = event_sequence + 1 where id = {run_id};\n'
        f'insert into public.run_events (run_id, sequence, schema_version, payload, occurred_at) select {run_id}, event_sequence, 1, '
        f'{event}, now() from public.runs where id = {run_id};\n')
    # The gap is arranged as the admin: the runtime role can't delete run events (R-17).
    gap = run.stack.sql(f'delete from public.run_events where run_id = {sql_literal(gap_run)} and sequence < 3;\n') if written.returncode == 0 else written
    cases.arrange('the run workspace fixtures', written, gap)
    return {'AUTOBOTS_TEST_LOOP_RUN': loop_run}


def arrange_member(run: IdentityRun, cases: Cases) -> dict[str, str]:
    """Member C belongs to workspace A without owning it."""
    member = run.owner('member-c@example.invalid')
    cases.arrange('member C in workspace A', run.stack.runtime(membership(run.bootstrapped(OWNER_A).workspace_id, member.user_id)))
    return {'AUTOBOTS_TEST_MEMBER_EMAIL': member.email, 'AUTOBOTS_TEST_MEMBER_PASSWORD': member.password}


def arrange_keyless_run(run: IdentityRun, cases: Cases) -> dict[str, str]:
    """A run in a workspace with no key at all, arranged by SQL since admission would refuse one."""
    owner = run.owner('owner-d@example.invalid')
    cases.arrange('a run in a workspace with no key', run.stack.runtime(
        'insert into public.runs (id, workspace_id, limit_micro_usd, goal_summary) '
        f"values ({sql_literal(KEYLESS_RUN)}, {sql_literal(owner.workspace_id)}, 1, 'Arranged in a workspace with no key');\n"))
    return {'AUTOBOTS_TEST_NO_KEY_RUN': KEYLESS_RUN, 'AUTOBOTS_TEST_NO_KEY_EMAIL': owner.email, 'AUTOBOTS_TEST_NO_KEY_PASSWORD': owner.password}


def arrange_reader(run: IdentityRun, cases: Cases) -> dict[str, str]:
    """US-15.3: a member of workspace A only, who isn't its owner."""
    reader = run.owner('reader-f@example.invalid')
    cases.arrange('the reader as a member of workspace A', run.stack.runtime(membership(run.bootstrapped(OWNER_A).workspace_id, reader.user_id)))
    # As the admin: the runtime role can't delete members (R-17).
    cases.arrange('the reader outside its own workspace', run.stack.sql(
        f'delete from public.workspace_members where workspace_id = {sql_literal(reader.workspace_id)} and user_id = {sql_literal(reader.user_id)};\n'))
    return {'AUTOBOTS_TEST_READER_EMAIL': reader.email, 'AUTOBOTS_TEST_READER_PASSWORD': reader.password}


def arrange_run_list(run: IdentityRun, cases: Cases) -> dict[str, str]:
    """US-15.4: 101 runs, three with spend (tests/db/identity/run_list.sql)."""
    owner = run.owner(RUN_LIST_OWNER)
    cases.arrange('101 runs, three with spend', run.stack.runtime(fixture(run.root, 'run_list.sql', workspace=owner.workspace_id)))
    return {'AUTOBOTS_TEST_RUNS_EMAIL': owner.email, 'AUTOBOTS_TEST_RUNS_PASSWORD': owner.password}


def arrange_experts(run: IdentityRun, cases: Cases) -> dict[str, str]:
    """US-15.6 and US-15.7: three Experts, then an older grant and a published workflow
    (tests/db/identity/experts.sql and older_expert_grant.sql)."""
    owner = run.owner('experts-h@example.invalid')
    ids = {'workspace': owner.workspace_id, 'user': owner.user_id}
    cases.arrange('three Experts, one with three runs', run.stack.runtime(fixture(run.root, 'experts.sql', **ids)))
    cases.arrange('an Expert with an older grant, and a published workflow', run.stack.runtime(fixture(run.root, 'older_expert_grant.sql', **ids)))
    return {'AUTOBOTS_TEST_EXPERTS_EMAIL': owner.email, 'AUTOBOTS_TEST_EXPERTS_PASSWORD': owner.password}


def arrange_model_sources(run: IdentityRun, cases: Cases) -> dict[str, str]:
    """US-15.8: a workspace that saves no default and one role override, and a run admitted with a run role
    override, through the admission code (tests/db/model_sources.py)."""
    owner = run.owner('models-i@example.invalid')
    sourced = run_arrangement(cases, run.root, 'model_sources.py', owner.workspace_id, owner.user_id, label='the binding-source run',
                              env=service_env(run.root, run.runtime_url), timeout=120, cwd=run.root)
    recorded = sourced.get('sources')
    sources = recorded if isinstance(recorded, dict) else {}
    cases.check('a run admitted with a run role override records its sources', 'executor run_override, coder workspace_override, researcher builtin_default',
                str({role: sources.get(role) for role in ('executor', 'coder', 'researcher')}),
                (sources.get('executor'), sources.get('coder'), sources.get('researcher')) == ('run_override', 'workspace_override', 'builtin_default'))
    return {'AUTOBOTS_TEST_MODELS_EMAIL': owner.email, 'AUTOBOTS_TEST_MODELS_PASSWORD': owner.password, 'AUTOBOTS_TEST_MODELS_RUN': str(sourced.get('run_id', ''))}


def arrange_composer(run: IdentityRun, cases: Cases) -> dict[str, str]:
    """US-15.9: US$2.10 left of today's cap and one Expert (tests/db/identity/composer.sql). browser_cases
    grants the workspace the installation key."""
    owner = run.owner('composer-j@example.invalid')
    cases.arrange('the composer workspace', run.stack.runtime(
        fixture(run.root, 'composer.sql', workspace=owner.workspace_id, user=owner.user_id, expert=COMPOSER_EXPERT)))
    return {'AUTOBOTS_TEST_COMPOSER_EMAIL': owner.email, 'AUTOBOTS_TEST_COMPOSER_PASSWORD': owner.password,
            'AUTOBOTS_TEST_COMPOSER_WORKSPACE': owner.workspace_id, 'AUTOBOTS_TEST_COMPOSER_EXPERT': COMPOSER_EXPERT}


def arrange_home(run: IdentityRun, cases: Cases) -> dict[str, str]:
    """US-15.10: a Costa Rica workspace whose owner is named Ada, with seven runs (tests/db/identity/home.sql)."""
    owner = run.owner('home-k@example.invalid')
    cases.arrange('the home workspace', run.stack.sql(fixture(run.root, 'home.sql', workspace=owner.workspace_id, user=owner.user_id,
                                                              **numbered('run', HOME_RUNS), **numbered('approval', HOME_APPROVALS))))
    return {'AUTOBOTS_TEST_HOME_EMAIL': owner.email, 'AUTOBOTS_TEST_HOME_PASSWORD': owner.password,
            'AUTOBOTS_TEST_HOME_RUNS': ','.join(HOME_RUNS), 'AUTOBOTS_TEST_HOME_APPROVALS': ','.join(HOME_APPROVALS)}


def brief_graph(write_label: str) -> str:
    """The "Weekly brief" graph: research, then write, then an approval gate."""
    return json.dumps({'ir_version': 2, 'nodes': [
        {'id': 'in', 'block': 'input', 'version': 1, 'config': {'type': 'string'}},
        {'id': 'research', 'block': 'agent', 'version': 1, 'config': {'expert_id': ANALYST}, 'label': 'Find sources'},
        {'id': 'write', 'block': 'agent', 'version': 1, 'config': {'expert_id': WRITER}, 'label': write_label},
        {'id': 'gate', 'block': 'approval', 'version': 1, 'config': {}},
        {'id': 'out', 'block': 'output', 'version': 1, 'config': {}}],
        'links': [{'source': 'in', 'source_port': 'value', 'target': 'research', 'target_port': 'goal'},
                  {'source': 'research', 'source_port': 'result', 'target': 'write', 'target_port': 'goal'},
                  {'source': 'write', 'source_port': 'result', 'target': 'gate', 'target_port': 'value'},
                  {'source': 'gate', 'source_port': 'value', 'target': 'out', 'target_port': 'value'}]})


def plain_graph() -> str:
    """The "Plain totals" graph: the input, upper-cased."""
    return json.dumps({'nodes': [{'id': 'in', 'block': 'input', 'version': 1, 'config': {'type': 'string'}},
                                 {'id': 'up', 'block': 'transform', 'version': 1, 'config': {'operation': 'upper'}},
                                 {'id': 'out', 'block': 'output', 'version': 1, 'config': {}}],
                       'links': [{'source': 'in', 'source_port': 'value', 'target': 'up', 'target_port': 'value'},
                                 {'source': 'up', 'source_port': 'value', 'target': 'out', 'target_port': 'value'}]})


def arrange_workflows(run: IdentityRun, cases: Cases) -> dict[str, str]:
    """US-15.13: a US$10.00 daily cap, two Experts and two workflows, one with a draft and three executions
    (tests/db/identity/workflows.sql)."""
    owner = run.owner(WORKFLOWS_OWNER)
    cases.arrange('the workflows workspace', run.stack.sql(fixture(
        run.root, 'workflows.sql', workspace=owner.workspace_id, user=owner.user_id, analyst=ANALYST, writer=WRITER, brief=BRIEF, plain=PLAIN,
        brief_1=brief_graph('Write the brief'), brief_2=brief_graph('Write the weekly brief'), draft=brief_graph('Draft writer'),
        plain_graph=plain_graph(), **numbered('run', FLOW_RUNS))))
    return {'AUTOBOTS_TEST_FLOWS_EMAIL': owner.email, 'AUTOBOTS_TEST_FLOWS_PASSWORD': owner.password,
            'AUTOBOTS_TEST_FLOWS_BRIEF': BRIEF, 'AUTOBOTS_TEST_FLOWS_PLAIN': PLAIN, 'AUTOBOTS_TEST_FLOWS_RUNS': ','.join(FLOW_RUNS)}


def arrange_operations(run: IdentityRun, cases: Cases) -> dict[str, str]:
    """US-15.18: jobs no worker may take and published artifacts (tests/db/identity/operations.sql)."""
    owner = run.owner(OPERATIONS_OWNER)
    arranged = run.stack.sql(fixture(run.root, 'operations.sql', workspace=owner.workspace_id))
    # US-15.19: its jobs chart reads hours in Costa Rica's time, which has no daylight saving.
    zoned = run.stack.sql(f"update public.workspaces set timezone = 'America/Costa_Rica' where id = {sql_literal(owner.workspace_id)};\n")
    cases.arrange('the operations workspace', arranged, zoned)
    return {'AUTOBOTS_TEST_OPS_EMAIL': owner.email, 'AUTOBOTS_TEST_OPS_PASSWORD': owner.password, 'AUTOBOTS_TEST_OPS_WORKSPACE': owner.workspace_id,
            'AUTOBOTS_TEST_OPS_HELPER': str(run.root / 'tests/db/operations_live.py')}


def arrange_two_workspace_member(run: IdentityRun, cases: Cases) -> dict[str, str]:
    """US-16.3: a member of their own workspace P and of runs-g's G, with a run only in P. The ops-n workspace is
    one they don't belong to (tests/db/identity/two_workspace_member.sql)."""
    member = run.owner('multi-p@example.invalid')
    shared, foreign = run.bootstrapped(RUN_LIST_OWNER).workspace_id, run.bootstrapped(OPERATIONS_OWNER).workspace_id
    cases.arrange('the two-workspace member', run.stack.sql(
        fixture(run.root, 'two_workspace_member.sql', shared=shared, user=member.user_id, workspace=member.workspace_id)))
    return {'AUTOBOTS_TEST_MULTI_EMAIL': member.email, 'AUTOBOTS_TEST_MULTI_PASSWORD': member.password,
            'AUTOBOTS_TEST_MULTI_WORKSPACE_P': member.workspace_id, 'AUTOBOTS_TEST_MULTI_WORKSPACE_G': shared,
            'AUTOBOTS_TEST_FOREIGN_WORKSPACE': foreign}


def arrange_search(run: IdentityRun, cases: Cases) -> dict[str, str]:
    """US-15.22: records named "read" in the ops-n workspace, and in the workflows workspace, which a search from
    ops-n must not return (tests/db/identity/search.sql)."""
    operator, builder = run.bootstrapped(OPERATIONS_OWNER), run.bootstrapped(WORKFLOWS_OWNER)
    cases.arrange('the search records', run.stack.sql(fixture(
        run.root, 'search.sql', workspace=operator.workspace_id, user=operator.user_id, other_workspace=builder.workspace_id,
        other_user=builder.user_id, **SEARCH_IDS)))
    return {'AUTOBOTS_TEST_SEARCH_IDS': json.dumps(SEARCH_IDS)}


def check_concept_seed(run: IdentityRun, cases: Cases) -> dict[str, str]:
    """US-15.25: the concept seed, run twice into a fresh workspace with no GitHub variables. A check, not an
    arrangement, so it records its child's cases and returns nothing for the browser suites."""
    workspace = run.owner('seed-o@example.invalid').workspace_id
    run_child_check(cases, run.root, 'concept_seed_check.py', workspace, label='the concept seed check', env=service_env(run.root, run.runtime_url),
                    timeout=240, cwd=run.root, err_dir=run.root / ERR_DIR)
    return {}


def arrange_browser_runs(run: IdentityRun, cases: Cases) -> dict[str, str]:
    """Runs no screen can reach by itself (tests/db/browser_runs.py): one waiting on an approval in workspace A,
    and one finished in a keyless workspace of its own, as the keyless-run suite asserts that the no-key
    workspace holds exactly one run."""
    keyless = run.owner('owner-e@example.invalid')
    browser_runs = run_arrangement(cases, run.root, 'browser_runs.py', run.bootstrapped(OWNER_A).workspace_id, keyless.workspace_id, label='the browser runs',
                                   env=service_env(run.root, run.runtime_url, AUTOBOTS_STORAGE_BASE=run.base, AUTOBOTS_STORAGE_SERVICE=run.service_key),
                                   timeout=120, cwd=run.root)
    cases.arranged('the browser runs waiting and finished', 'waiting_approval and succeeded', browser_runs.get('states'),
                   browser_runs.get('states') == {'waiting': 'waiting_approval', 'finished': 'succeeded'})
    return {**{name: str(browser_runs.get(key, '')) for name, key in (
        ('AUTOBOTS_TEST_STALE_SESSION', 'stale_session'), ('AUTOBOTS_TEST_STALE_EXPERT', 'stale_expert'),
        ('AUTOBOTS_TEST_WAITING_RUN', 'waiting_run'), ('AUTOBOTS_TEST_FILES_RUN', 'keyless_run'))},
            'AUTOBOTS_TEST_FILES_EMAIL': keyless.email, 'AUTOBOTS_TEST_FILES_PASSWORD': keyless.password}


# One step arranges what the browser suites read, records it and returns their variables.
Arrangement = Callable[[IdentityRun, Cases], dict[str, str]]
# In order: each step runs after the owners it reads (OWNER_A from qualify, RUN_LIST_OWNER, WORKFLOWS_OWNER and
# OPERATIONS_OWNER from the steps that bootstrap them). check_concept_seed is the one check among them: it
# records its child's cases and arranges nothing.
ARRANGEMENTS: tuple[Arrangement, ...] = (
    arrange_member, arrange_keyless_run, arrange_reader, arrange_run_list, arrange_experts, arrange_model_sources,
    arrange_composer, arrange_home, arrange_workflows, arrange_operations, arrange_two_workspace_member, arrange_search,
    check_concept_seed, arrange_browser_runs,
)


def titled_run(playwright: Path, web: Path, spec: str, title: str, timeout: float, browser_env: Mapping[str, str], report: Path) -> int:
    """Run the one test of the arranged project's `spec` with `title`, reporting to `report`. Returns its exit code."""
    report.unlink(missing_ok=True)
    ran = subprocess.run([str(playwright), 'test', spec, '--project', ARRANGED_PROJECT, '-g', title, '--config', 'playwright.config.ts'], cwd=web, capture_output=True, text=True, errors='replace', timeout=timeout, check=False,
                         env={**browser_env, 'AUTOBOTS_WEB_REPORT': str(report)})
    if ran.returncode:
        print(ran.stdout[-1500:], file=sys.stderr)
    return ran.returncode


def browser_cases(run: IdentityRun, cases: Cases, fixtures: Mapping[str, str]) -> None:
    """Build the web app, start the API fixture and the BFF, and run the browser suites with the arranged
    `fixtures`: the main project, each arranged test after its own arrangement, then the slice with a worker."""
    root, stack = run.root, run.stack
    owner_a, owner_b = run.bootstrapped(OWNER_A), run.bootstrapped(OWNER_B)
    tools = find_tools(root)
    web = root / 'apps/web'
    next_bin, playwright = web / 'node_modules/.bin/next', web / 'node_modules/.bin/playwright'
    browsers = root / BROWSERS
    if not any(browsers.glob('chromium-*')):
        raise Unavailable(f'no browser under {BROWSERS}; install the pinned one deliberately')
    env = {**child_env(root, tools, verifying=True), 'PLAYWRIGHT_BROWSERS_PATH': str(browsers)}
    built = subprocess.run([str(next_bin), 'build'], env=env, cwd=web, capture_output=True, text=True, errors='replace', timeout=300, check=False)
    cases.check('the web app builds', 'exit 0', f'exit {built.returncode}', built.returncode == 0)
    if built.returncode:
        print(built.stdout[-1200:], file=sys.stderr)
        return
    from qualify_web import free_port as any_port
    internal = secrets.token_hex(32)
    api_port, web_port = any_port(), any_port()
    config_root = Path(tempfile.mkdtemp(prefix='autobots-config-'))
    # The arranged installation key. Only workspace B is granted it, so A exercises the app store.
    (config_root / '.env.local').write_text('OPENROUTER_API_KEY=sk-or-valid-arranged-installation\n')
    # US-14.17: a Jina key in the configuration root's lowest-priority .env, and no Tavily key anywhere.
    (config_root / '.env').write_text('JINA_API_KEY=jina_fixtureConfigRoot0001')
    cases.arrange("workspace B's installation key grant",
                  stack.sql(f'insert into app_private.installation_credential_grants values ({sql_literal(owner_b.workspace_id)});\n'))
    if fixtures.get('AUTOBOTS_TEST_COMPOSER_WORKSPACE'):
        cases.arrange("the composer workspace's installation key grant",
                      stack.sql(f"insert into app_private.installation_credential_grants values ({sql_literal(fixtures['AUTOBOTS_TEST_COMPOSER_WORKSPACE'])});\n"))
    out = root / '.checks/identity'
    upstream_log = out / 'upstream.log'
    upstream_log.parent.mkdir(parents=True, exist_ok=True)
    upstream_log.write_text('')
    catalog_down = config_root / 'catalog-down'
    backups = config_root / 'backups'
    backups.mkdir(parents=True, exist_ok=True)
    # Arranged: a delayed occurrence, on a routine that's off so no worker evaluates it.
    routine, config, workspace_a_sql = sql_literal(DELAYED_ROUTINE), sql_literal(json.dumps({})), sql_literal(owner_a.workspace_id)
    arranged = stack.sql(f"insert into public.routines (id, workspace_id, name, enabled, evaluated_until) values ({routine}, {workspace_a_sql}, 'Arranged nightly report', false, now());\n"
                         f"insert into public.routine_versions (routine_id, version, config, created_by) values ({routine}, 1, {config}, {workspace_a_sql});\n"
                         f"insert into public.routine_occurrences (routine_id, occurrence_time, routine_version, status, reason) values ({routine}, '2026-11-05T03:00:00Z', 1, 'missed', 'host_away');\n")
    cases.arrange('the delayed occurrence', arranged)
    api_url, web_url = f'http://127.0.0.1:{api_port}', f'http://127.0.0.1:{web_port}'
    api_env = {**tool_env(), 'PYTHONPATH': str(root / 'services/agent/src'), 'PYTHONDONTWRITEBYTECODE': '1', 'AUTOBOTS_INTERNAL_TOKEN': internal,
               'AUTOBOTS_JWT_SECRET': stack.values['JWT_SECRET'], 'AUTOBOTS_DATABASE_URL': run.runtime_url,
               'AUTOBOTS_SUPABASE_URL': run.base, 'AUTOBOTS_SERVICE_ROLE_KEY': run.service_key, 'AUTOBOTS_STREAM_SECONDS': '4',
               'AUTOBOTS_CONFIG_ROOT': str(config_root), 'AUTOBOTS_PROVIDER_MASTER_KEY_FILE': str(config_root / 'secrets/master.key'),
               'AUTOBOTS_TEST_UPSTREAM_LOG': str(upstream_log), 'AUTOBOTS_TEST_CATALOG_DOWN': str(catalog_down), 'AUTOBOTS_BACKUP_DIR': str(backups), 'NODE_ENV': 'production'}
    web_env = {**env, 'AUTOBOTS_INTERNAL_TOKEN': internal, 'AUTOBOTS_API_URL': api_url, 'AUTOBOTS_ALLOWED_ORIGIN': web_url, 'NODE_ENV': 'production',
               'AUTOBOTS_SUPABASE_URL': run.base, 'AUTOBOTS_SUPABASE_ANON_KEY': run.anon_key}
    screenshots = out / 'screenshots'
    screenshots.mkdir(parents=True, exist_ok=True)
    report = out / 'playwright.json'
    report.unlink(missing_ok=True)
    processes = []
    try:
        processes.append(start([str(root / PYTHON), str(root / 'tests/web/fixture_upstream_api.py'), str(api_port)], api_env, root))
        processes.append(start([str(next_bin), 'start', '-H', '127.0.0.1', '-p', str(web_port)], web_env, web))
        wait_until_up(f'{api_url}/v1/health', processes[0])
        wait_until_up(web_url, processes[1])
        browser_env = {**env, **fixtures, 'AUTOBOTS_WEB_URL': web_url, 'AUTOBOTS_TEST_OWNER_EMAIL': owner_a.email, 'AUTOBOTS_TEST_OWNER_PASSWORD': owner_a.password,
                       'AUTOBOTS_TEST_WORKSPACE_A': owner_a.workspace_id, 'AUTOBOTS_TEST_WORKSPACE_B': owner_b.workspace_id,
                       'AUTOBOTS_TEST_OWNER_B_EMAIL': owner_b.email, 'AUTOBOTS_TEST_OWNER_B_PASSWORD': owner_b.password,
                       'AUTOBOTS_TEST_CONFIG_DOTENV': str(config_root / '.env'),
                       'AUTOBOTS_TEST_UPSTREAM_LOG': str(upstream_log), 'AUTOBOTS_TEST_CATALOG_DOWN': str(catalog_down), 'AUTOBOTS_TEST_BACKUP_DIR': str(backups),
                       'AUTOBOTS_TEST_SERVICE_KEY': run.service_key, 'AUTOBOTS_WEB_REPORT': str(report),
                       'AUTOBOTS_WEB_OUTPUT': str(out / 'results'), 'AUTOBOTS_WEB_SCREENSHOTS': str(screenshots),
                       'AUTOBOTS_TEST_VISUAL_DIR': str(out / 'visual')}
        result = subprocess.run([str(playwright), 'test', '--project', IDENTITY_PROJECT, '--config', 'playwright.config.ts'], cwd=web, capture_output=True, text=True, errors='replace', timeout=660, check=False,
                                env=browser_env)
        # A real restart, then Settings reads the stored records. Then one is removed, under the same key.
        stop(processes[0])
        processes[0] = start([str(root / PYTHON), str(root / 'tests/web/fixture_upstream_api.py'), str(api_port)], api_env, root)
        wait_until_up(f'{api_url}/v1/health', processes[0])
        qualification_reports: list[Path] = []
        qualification_codes: list[int] = []

        def titled(spec: str, title: str, timeout: float, report_path: Path) -> None:
            qualification_reports.append(report_path)
            qualification_codes.append(titled_run(playwright, web, spec, title, timeout, browser_env, report_path))

        for index, title in enumerate(QUALIFICATION_TITLES, start=1):
            if title == 'a route with no record':
                cases.arrange('a route with no record', stack.sql("create table public.arranged_route_rows as select * from agent_runtime.route_qualifications;\n"
                                                                  "delete from agent_runtime.route_qualifications where profile = 'openrouter_terra';\n"))
            titled(QUALIFICATION_SPEC, title, 120, out / f'playwright-qualification-{index}.json')
        cases.arrange('the route records restored', stack.sql("delete from agent_runtime.route_qualifications;\n"
                                                              "insert into agent_runtime.route_qualifications select * from public.arranged_route_rows;\n"
                                                              "drop table public.arranged_route_rows;\n"))
        for index, (title, profile, overrides) in enumerate(SAVED_CHOICES, start=1):
            cases.arrange(f'the saved choice: {title}', stack.runtime(
                f'update app_private.model_policies set version = version + 1, default_profile = {sql_literal(profile)}, '
                f'role_overrides = {sql_literal(json.dumps(overrides))} where workspace_id = {workspace_a_sql};\n'))
            titled(SAVED_CHOICE_SPEC, title, 120, out / f'playwright-saved-choice-{index}.json')
        # US-15.3: readiness as a member. First with no worker heartbeat, then with an arranged one
        # dated ahead, so it stays fresh for the whole run, and removed afterwards.
        for index, title in enumerate(READINESS_TITLES, start=1):
            if index == 2:
                cases.arrange('a worker heartbeat that stays fresh for the readiness run',
                              stack.runtime("insert into app_private.worker_heartbeats (worker_id, state, claims_inference, beat_at) "
                                            "values ('arranged-readiness', 'running', true, clock_timestamp() + interval '15 minutes');\n"))
            titled(READINESS_SPEC, title, 180, out / f'playwright-readiness-{index}.json')
        # As the admin: the runtime role holds DELETE on workflow drafts only (R-17).
        cleared = stack.sql("delete from app_private.worker_heartbeats where worker_id = 'arranged-readiness'; "
                            "select count(*) from app_private.worker_heartbeats where worker_id = 'arranged-readiness';\n")
        cases.arranged('the readiness heartbeat removed before the slice', 'exit 0, 0 rows',
                       f'exit {cleared.returncode}, {cleared.stdout.strip()} rows', cleared.returncode == 0 and cleared.stdout.strip() == '0')
        # The slice runs last, with a worker, so nothing above sees its jobs claimed.
        cases.arrange('no job left for the slice worker but its own',
                      stack.runtime("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null where status <> 'done';\n"))
        # The settings suite changed the workspace default, and the fixture worker's route is the original.
        cases.arrange("the slice's original model route",
                      stack.runtime("update app_private.model_policies set default_profile = 'openrouter_terra', role_overrides = '{}';\n"))
        slice_report = out / 'playwright-slice.json'
        slice_report.unlink(missing_ok=True)
        worker_env = {**tool_env(), 'PYTHONPATH': str(root / 'services/agent/src'), 'PYTHONDONTWRITEBYTECODE': '1', 'AUTOBOTS_DATABASE_URL': run.runtime_url,
                      'AUTOBOTS_STORAGE_BASE': run.base, 'AUTOBOTS_STORAGE_SERVICE': run.service_key,
                      'AUTOBOTS_TEST_DIED_MARKER': str(config_root / 'worker-died')}
        processes.append(start([str(root / PYTHON), str(root / 'tests/web/fixture_worker.py')], worker_env, root))
        slice_result = subprocess.run([str(playwright), 'test', '--project', SLICE_PROJECT, '--config', 'playwright.config.ts'], cwd=web, capture_output=True, text=True, errors='replace', timeout=900, check=False,
                                      env={**browser_env, 'AUTOBOTS_WEB_REPORT': str(slice_report)})
        if slice_result.returncode:
            print(slice_result.stdout[-2500:], file=sys.stderr)
    finally:
        for process in processes:
            stop(process)
    if not report.exists():
        print(result.stdout[-1500:], result.stderr[-800:], file=sys.stderr)
        raise Unavailable('the browser suite produced no report')
    if result.returncode:
        print(result.stdout[-2500:], file=sys.stderr)
    found, _ = summarize(report)
    if slice_report.exists():
        found.extend(summarize(slice_report)[0])
    else:
        cases.check('the slice suite produced a report', 'a report', 'none', False)
    for report_path in qualification_reports:
        if report_path.exists():
            found.extend(summarize(report_path)[0])
        else:
            cases.check('the qualification suite produced a report', 'a report', 'none', False)
    for case in found:
        cases.check(f"browser: {case['id']}", 'passed', case['status'], case['status'] == 'passed')
    runs = [('main suite', report, result.returncode), ('slice suite', slice_report, slice_result.returncode),
            *((f'qualification suite {index + 1}', path, code) for index, (path, code) in enumerate(zip(qualification_reports, qualification_codes, strict=False)))]
    for label, path, code in runs:
        problems = run_problems(path, code)
        cases.check(f'the {label} ran to a clean exit', 'exit 0, with tests', ', '.join(problems) or 'exit 0', not problems)
    calls = sorted(set(upstream_log.read_text().splitlines()))
    cases.check('only key metadata and the catalog reached the fake upstream', 'GET /key and GET /models only', ', '.join(calls),
                calls == ['GET /api/v1/key', 'GET /api/v1/models'])
    row = rows(stack, f"select count(*) filter (where position('sk-or'::bytea in ciphertext) > 0) from app_private.provider_credentials where workspace_id = {workspace_a_sql};")
    versions = rows(stack, f'select count(*) from app_private.provider_credentials where workspace_id = {workspace_a_sql};')
    cases.check('stored rows hold no plaintext key', '0 of the rows', f'{row} of {versions}', row == '0' and versions != '0')
    shutil.rmtree(config_root, ignore_errors=True)


def qualify(root: Path) -> int:
    cases = Cases(model_transport=MODEL_TRANSPORT)
    with app_project(root, cases, report=root / REPORT) as app:
        stack = app.stack
        run = IdentityRun(root, stack, app.base, app.db_port)
        applied = start_app(stack, root)
        bootstrapped, stored = apply_bootstrap(stack, root)
        cases.check('the bootstrap files apply, storage.sql first', 'each with its history row', f'{applied} migrations, {bootstrapped}, {stored}',
                    stored is None and bootstrapped[:1] == ['bootstrap/storage.sql'])
        if stored:
            print(stored[-500:], file=sys.stderr)
        owner_a, owner_b = run.owner(OWNER_A), run.owner(OWNER_B)
        cases.check('owners are bootstrapped through the Auth admin API', 'two users', f'{bool(owner_a.user_id)}, {bool(owner_b.user_id)}',
                    (owner_a.user_id, owner_a.workspace_id) != (owner_b.user_id, owner_b.workspace_id))
        auth_cases(cases, run.base, run.anon_key, owner_a.email, owner_a.password)
        status_a, token_a = password_token(run.base, run.anon_key, owner_a.email, owner_a.password)
        status_b, token_b = password_token(run.base, run.anon_key, owner_b.email, owner_b.password)
        cases.check('owners sign in with a local password', '200 each', f'{status_a}, {status_b}', status_a == status_b == 200)
        cases.arrange("workspace A's run", stack.runtime(
            f'insert into public.runs (id, workspace_id, limit_micro_usd) values ({sql_literal(RUN_A)}, {sql_literal(owner_a.workspace_id)}, 1);\n'))
        rest_cases(cases, stack, run.base, run.anon_key, token_a, token_b, RUN_A)
        storage_cases(cases, run.base, run.anon_key, run.service_key, token_a, token_b, owner_a.workspace_id, owner_b.workspace_id)
        fixtures = storage_child_cases(run, cases, token_a, token_b)
        for arrange in ARRANGEMENTS:
            fixtures |= arrange(run, cases)
        browser_cases(run, cases, fixtures)
    return finish(root, root / REPORT, 'autobots.identity-qualification/v1', cases, app.started_at,
                  ['H1', 'product acceptance', 'the persistent stack', 'a running Realtime service'], project=stack.target.project)


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
