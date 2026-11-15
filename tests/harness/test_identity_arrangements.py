"""qualify_identity's arrangements, run against a recording stack and a fake subprocess (refactor plan R-47,
SCRP-02).

Each step in ARRANGEMENTS bootstraps its owner, sends its fixture through the role it names and records
`arranged: <label>`, or raises Unavailable, so no later case can pass on a fixture that never existed
(SCRP-09). The one check among them, the concept seed, records its child's cases. Every child the
qualifier starts keeps its arguments, environment, timeout and directory, as R-39 proved for the runner.
"""
from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, ClassVar
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import qualify_identity  # noqa: E402
import qualify_web  # noqa: E402
import suites  # noqa: E402
from qualification import children  # noqa: E402
from qualification.errors import Unavailable  # noqa: E402
from qualification.records import Cases  # noqa: E402

BASE = 'http://127.0.0.1:55402'
DB_PORT = 55401
RUNTIME_URL = f'postgresql://autobots_runtime:runtime-fixture@127.0.0.1:{DB_PORT}/postgres'
SERVICE_KEY = 'service-fixture'
# What each step records, in the order ARRANGEMENTS runs them.
STEP_CASES = (
    ('arrange_member', ['arranged: member C in workspace A']),
    ('arrange_keyless_run', ['arranged: a run in a workspace with no key']),
    ('arrange_reader', ['arranged: the reader as a member of workspace A', 'arranged: the reader outside its own workspace']),
    ('arrange_run_list', ['arranged: 101 runs, three with spend']),
    ('arrange_experts', ['arranged: three Experts, one with three runs',
                         'arranged: an Expert with an older grant, and a published workflow']),
    ('arrange_model_sources', ['arranged: the binding-source run', 'a run admitted with a run role override records its sources']),
    ('arrange_composer', ['arranged: the composer workspace']),
    ('arrange_home', ['arranged: the home workspace']),
    ('arrange_workflows', ['arranged: the workflows workspace']),
    ('arrange_operations', ['arranged: the operations workspace']),
    ('arrange_two_workspace_member', ['arranged: the two-workspace member']),
    ('arrange_search', ['arranged: the search records']),
    ('check_concept_seed', ['the concept seed child case']),
    ('arrange_browser_runs', ['arranged: the browser runs', 'arranged: the browser runs waiting and finished']),
)
# The owners each step bootstraps, in order, after owners A and B.
STEP_OWNERS = ('member-c', 'owner-d', 'reader-f', 'runs-g', 'experts-h', 'models-i', 'composer-j', 'home-k', 'flows-l',
               'ops-n', 'multi-p', 'seed-o', 'owner-e')
# The role each arranging statement runs as: the runtime role where it may write, the admin where it may not.
STEP_ROLES = (
    ('runtime', 'insert into public.workspace_members'), ('runtime', 'insert into public.runs'),
    ('runtime', 'insert into public.workspace_members'), ('sql', 'delete from public.workspace_members'),
    ('runtime', 'insert into public.runs'), ('runtime', 'insert into public.experts'), ('runtime', 'insert into public.experts'),
    ('runtime', 'insert into public.runs'), ('sql', 'update public.workspaces'), ('sql', 'insert into app_private.model_spend_limits'),
    ('sql', 'insert into public.runs'), ('sql', 'update public.workspaces'), ('sql', 'insert into public.workspace_members'),
    ('sql', 'insert into public.runs'),
)
BROWSER_VARIABLES = sorted((
    'AUTOBOTS_TEST_MEMBER_EMAIL', 'AUTOBOTS_TEST_MEMBER_PASSWORD',
    'AUTOBOTS_TEST_NO_KEY_RUN', 'AUTOBOTS_TEST_NO_KEY_EMAIL', 'AUTOBOTS_TEST_NO_KEY_PASSWORD',
    'AUTOBOTS_TEST_READER_EMAIL', 'AUTOBOTS_TEST_READER_PASSWORD', 'AUTOBOTS_TEST_RUNS_EMAIL', 'AUTOBOTS_TEST_RUNS_PASSWORD',
    'AUTOBOTS_TEST_EXPERTS_EMAIL', 'AUTOBOTS_TEST_EXPERTS_PASSWORD',
    'AUTOBOTS_TEST_MODELS_EMAIL', 'AUTOBOTS_TEST_MODELS_PASSWORD', 'AUTOBOTS_TEST_MODELS_RUN',
    'AUTOBOTS_TEST_COMPOSER_EMAIL', 'AUTOBOTS_TEST_COMPOSER_PASSWORD', 'AUTOBOTS_TEST_COMPOSER_WORKSPACE', 'AUTOBOTS_TEST_COMPOSER_EXPERT',
    'AUTOBOTS_TEST_HOME_EMAIL', 'AUTOBOTS_TEST_HOME_PASSWORD', 'AUTOBOTS_TEST_HOME_RUNS', 'AUTOBOTS_TEST_HOME_APPROVALS',
    'AUTOBOTS_TEST_FLOWS_EMAIL', 'AUTOBOTS_TEST_FLOWS_PASSWORD', 'AUTOBOTS_TEST_FLOWS_BRIEF', 'AUTOBOTS_TEST_FLOWS_PLAIN',
    'AUTOBOTS_TEST_FLOWS_RUNS', 'AUTOBOTS_TEST_OPS_EMAIL', 'AUTOBOTS_TEST_OPS_PASSWORD', 'AUTOBOTS_TEST_OPS_WORKSPACE',
    'AUTOBOTS_TEST_OPS_HELPER', 'AUTOBOTS_TEST_MULTI_EMAIL', 'AUTOBOTS_TEST_MULTI_PASSWORD', 'AUTOBOTS_TEST_MULTI_WORKSPACE_P',
    'AUTOBOTS_TEST_MULTI_WORKSPACE_G', 'AUTOBOTS_TEST_FOREIGN_WORKSPACE', 'AUTOBOTS_TEST_SEARCH_IDS',
    'AUTOBOTS_TEST_STALE_SESSION', 'AUTOBOTS_TEST_STALE_EXPERT', 'AUTOBOTS_TEST_WAITING_RUN', 'AUTOBOTS_TEST_FILES_RUN',
    'AUTOBOTS_TEST_FILES_EMAIL', 'AUTOBOTS_TEST_FILES_PASSWORD'))


class RecordingStack:
    """Records each statement with the role it runs as, and fails the ones `failing` matches."""

    runtime_password = 'runtime-fixture'
    values: ClassVar[dict[str, str]] = {'SERVICE_ROLE_KEY': SERVICE_KEY, 'ANON_KEY': 'anon-fixture', 'JWT_SECRET': 'jwt-fixture'}

    def __init__(self, failing: str | None = None) -> None:
        self.statements: list[tuple[str, str]] = []
        self.failing = failing

    def answer(self, role: str, statement: str) -> subprocess.CompletedProcess[str]:
        self.statements.append((role, statement))
        failed = self.failing is not None and self.failing in statement
        return subprocess.CompletedProcess([], 3 if failed else 0, '', 'ERROR: arranged failure' if failed else '')

    def sql(self, statement: str) -> subprocess.CompletedProcess[str]:
        return self.answer('sql', statement)

    def runtime(self, statement: str) -> subprocess.CompletedProcess[str]:
        return self.answer('runtime', statement)

    def migrator(self, statement: str) -> subprocess.CompletedProcess[str]:
        return self.answer('migrator', statement)


def printed_by(argv: list[str]) -> str:
    """What each child the arrangements start prints: an owner, an arrangement's JSON or a check's cases."""
    if 'autobots.operations.bootstrap_owner' in argv:
        email = argv[argv.index('--email') + 1].split('@')[0]
        return json.dumps({'user_id': f'user-{email}', 'workspace_id': f'ws-{email}'})
    script = Path(argv[1]).name
    if script == 'model_sources.py':
        return json.dumps({'sources': {'executor': 'run_override', 'coder': 'workspace_override', 'researcher': 'builtin_default'},
                           'run_id': 'models-run'})
    if script == 'browser_runs.py':
        return json.dumps({'states': {'waiting': 'waiting_approval', 'finished': 'succeeded'}, 'stale_session': 'session-1',
                           'stale_expert': 'expert-1', 'waiting_run': 'waiting-1', 'keyless_run': 'keyless-1'})
    if script == 'concept_seed_check.py':
        return json.dumps({'cases': [{'id': 'the concept seed child case', 'expected': 'x', 'observed': 'x', 'passed': True}]})
    if script == 'artifact_check.py':
        return json.dumps({'cases': [{'id': 'artifact case', 'expected': 'x', 'observed': 'x', 'passed': True}],
                           'loop_run': 'loop-run', 'run_id': 'artifact-run', 'artifact_id': 'artifact-id', 'expected_text': 'text',
                           'gone_id': 'gone', 'tampered_id': 'tampered'})
    legacy = {'AUTOBOTS_TEST_APPROVAL_LEGACY': 'legacy-approval'} if script == 'approval_check.py' else {}
    return json.dumps({'cases': [{'id': f'{script} {" ".join(argv[2:])}', 'expected': 'x', 'observed': 'x', 'passed': True}],
                       'browser_env': {f'AUTOBOTS_TEST_FROM_{Path(script).stem.upper()}': script, **legacy}})


class Arranged(unittest.TestCase):
    """A disposable root whose tests/ and supabase/ are this repository's, so fixtures and migrations are real
    and anything the qualifier keeps under .checks stays in the temporary folder."""

    def setUp(self) -> None:
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))
        folder = self.enterContext(tempfile.TemporaryDirectory())
        self.root = Path(folder)
        for name in ('tests', 'supabase'):
            (self.root / name).symlink_to(ROOT / name)
        self.launches: list[dict[str, Any]] = []
        self.fail_launch: Callable[[list[str]], subprocess.CompletedProcess[str] | None] = lambda argv: None
        passwords = iter(f'password-{number}' for number in range(1, 100))
        self.enterContext(mock.patch.object(qualify_identity.secrets, 'token_urlsafe', lambda _size: next(passwords)))
        self.enterContext(mock.patch.object(children.subprocess, 'run', self.fake_run))

    def fake_run(self, argv: list[str], **options: Any) -> subprocess.CompletedProcess[str]:
        self.launches.append({'argv': list(argv), **options})
        # The owner bootstrap prints one JSON object and nothing else; a check may print progress first.
        progress = '' if 'autobots.operations.bootstrap_owner' in argv else 'progress\n'
        return self.fail_launch(argv) or subprocess.CompletedProcess(argv, 0, f'{progress}{printed_by(argv)}\n', '')

    def identity(self, stack: RecordingStack | None = None) -> Any:
        run = qualify_identity.IdentityRun(self.root, stack or RecordingStack(), BASE, DB_PORT)  # type: ignore[arg-type]  # a recording stand-in
        run.owner(qualify_identity.OWNER_A)
        run.owner(qualify_identity.OWNER_B)
        return run

    def arrange_all(self, run: Any, cases: Cases) -> tuple[dict[str, str], list[tuple[str, list[str]]]]:
        fixtures: dict[str, str] = {}
        recorded: list[tuple[str, list[str]]] = []
        for arrange in qualify_identity.ARRANGEMENTS:
            before = len(cases.records)
            fixtures |= arrange(run, cases)
            recorded.append((arrange.__name__, [record['id'] for record in cases.records[before:]]))
        return fixtures, recorded


class Registry(Arranged):
    def test_each_step_records_its_cases_in_order(self) -> None:
        cases = Cases()
        _, recorded = self.arrange_all(self.identity(), cases)
        self.assertEqual(recorded, [(name, ids) for name, ids in STEP_CASES])
        self.assertEqual(cases.status, 'passed')

    def test_every_arrangement_records_an_arranged_case(self) -> None:
        _, recorded = self.arrange_all(self.identity(), Cases())
        for name, ids in recorded:
            with self.subTest(name):
                self.assertTrue(name.startswith(('arrange_', 'check_')))
                if name.startswith('arrange_'):
                    self.assertTrue(any(case_id.startswith('arranged: ') for case_id in ids), ids)

    def test_the_steps_return_the_variables_the_browser_suites_read(self) -> None:
        run = self.identity()
        fixtures, _ = self.arrange_all(run, Cases())
        self.assertEqual(sorted(fixtures), BROWSER_VARIABLES)
        self.assertEqual({name: fixtures[name] for name in ('AUTOBOTS_TEST_MEMBER_EMAIL', 'AUTOBOTS_TEST_MEMBER_PASSWORD',
                                                           'AUTOBOTS_TEST_NO_KEY_RUN', 'AUTOBOTS_TEST_COMPOSER_WORKSPACE',
                                                           'AUTOBOTS_TEST_COMPOSER_EXPERT', 'AUTOBOTS_TEST_MULTI_WORKSPACE_G',
                                                           'AUTOBOTS_TEST_FOREIGN_WORKSPACE', 'AUTOBOTS_TEST_MODELS_RUN',
                                                           'AUTOBOTS_TEST_FILES_RUN', 'AUTOBOTS_TEST_OPS_HELPER')},
                         {'AUTOBOTS_TEST_MEMBER_EMAIL': 'member-c@example.invalid', 'AUTOBOTS_TEST_MEMBER_PASSWORD': 'password-3',
                          'AUTOBOTS_TEST_NO_KEY_RUN': '33333333-3333-4333-8333-333333333333',
                          'AUTOBOTS_TEST_COMPOSER_WORKSPACE': 'ws-composer-j',
                          'AUTOBOTS_TEST_COMPOSER_EXPERT': '66666666-6666-4666-8666-000000000002',
                          'AUTOBOTS_TEST_MULTI_WORKSPACE_G': 'ws-runs-g', 'AUTOBOTS_TEST_FOREIGN_WORKSPACE': 'ws-ops-n',
                          'AUTOBOTS_TEST_MODELS_RUN': 'models-run', 'AUTOBOTS_TEST_FILES_RUN': 'keyless-1',
                          'AUTOBOTS_TEST_OPS_HELPER': str(self.root / 'tests/db/operations_live.py')})
        self.assertEqual(fixtures['AUTOBOTS_TEST_HOME_RUNS'].split(','), [f'77777777-7777-4777-8777-00000000000{index}' for index in range(1, 8)])
        self.assertEqual(fixtures['AUTOBOTS_TEST_HOME_APPROVALS'], '77777777-7777-4777-8777-0000000000a1,77777777-7777-4777-8777-0000000000a2')
        self.assertEqual(fixtures['AUTOBOTS_TEST_FLOWS_RUNS'].split(','), [f'88888888-8888-4888-8888-00000000000{index}' for index in range(1, 4)])
        self.assertEqual(json.loads(fixtures['AUTOBOTS_TEST_SEARCH_IDS']),
                         {'run': '99999999-9999-4999-8999-0000000000d1', 'expert': '99999999-9999-4999-8999-0000000000d2',
                          'workflow': '99999999-9999-4999-8999-0000000000d3', 'other_run': '88888888-8888-4888-8888-0000000000d4',
                          'other_expert': '88888888-8888-4888-8888-0000000000d5'})

    def test_each_statement_runs_as_the_role_its_fixture_needs(self) -> None:
        stack = RecordingStack()
        run = self.identity(stack)
        self.arrange_all(run, Cases())
        self.assertEqual(len(stack.statements), len(STEP_ROLES))
        for (role, statement), (expected_role, opening) in zip(stack.statements, STEP_ROLES, strict=True):
            with self.subTest(opening):
                body = '\n'.join(line for line in statement.splitlines() if not line.startswith('--')).lstrip()
                self.assertEqual(role, expected_role)
                self.assertTrue(body.startswith(opening), body[:80])
                self.assertNotIn('$', statement)

    def test_every_identity_fixture_file_is_rendered_by_a_step(self) -> None:
        rendered: list[str] = []
        real = qualify_identity.fixture

        def spy(root: Path, name: str, **values: str) -> str:
            rendered.append(name)
            return real(root, name, **values)

        with mock.patch.object(qualify_identity, 'fixture', spy):
            self.arrange_all(self.identity(), Cases())
        files = sorted(path.name for path in (ROOT / qualify_identity.IDENTITY_FIXTURES).glob('*.sql'))
        self.assertEqual(sorted(rendered), files)
        self.assertEqual(len(rendered), len(set(rendered)))

    def test_each_owner_is_bootstrapped_with_exactly_its_launch(self) -> None:
        self.arrange_all(self.identity(), Cases())
        bootstraps = [launch for launch in self.launches if 'autobots.operations.bootstrap_owner' in launch['argv']]
        emails = [f'{name}@example.invalid' for name in ('owner-a', 'owner-b', *STEP_OWNERS)]
        self.assertEqual(len(bootstraps), len(emails))
        for number, (launch, email) in enumerate(zip(bootstraps, emails, strict=True), start=1):
            with self.subTest(email):
                self.assertEqual(launch, {
                    'argv': [str(self.root / 'services/agent/.venv/bin/python'), '-m', 'autobots.operations.bootstrap_owner',
                             '--email', email, '--workspace-name', email],
                    'env': {**children.tool_env(), 'PYTHONPATH': str(self.root / 'services/agent/src'), 'PYTHONDONTWRITEBYTECODE': '1',
                            'AUTOBOTS_SUPABASE_URL': BASE, 'AUTOBOTS_SERVICE_ROLE_KEY': SERVICE_KEY,
                            'AUTOBOTS_OWNER_PASSWORD': f'password-{number}', 'AUTOBOTS_DATABASE_URL': RUNTIME_URL},
                    'capture_output': True, 'text': True, 'timeout': 60, 'check': False})

    def test_each_helper_and_check_keeps_its_launch(self) -> None:
        self.arrange_all(self.identity(), Cases())
        python, checks = str(self.root / 'services/agent/.venv/bin/python'), self.root / 'tests/db'
        service = children.service_env(self.root, RUNTIME_URL)
        helpers = [launch for launch in self.launches if 'autobots.operations.bootstrap_owner' not in launch['argv']]
        common = {'capture_output': True, 'text': True, 'errors': 'replace', 'check': False, 'cwd': self.root}
        self.assertEqual(helpers, [
            {'argv': [python, str(checks / 'model_sources.py'), 'ws-models-i', 'user-models-i'], 'env': service, 'timeout': 120, **common},
            {'argv': [python, str(checks / 'concept_seed_check.py'), 'ws-seed-o'], 'env': service, 'timeout': 240, **common},
            {'argv': [python, str(checks / 'browser_runs.py'), 'ws-owner-a', 'ws-owner-e'],
             'env': children.service_env(self.root, RUNTIME_URL, AUTOBOTS_STORAGE_BASE=BASE, AUTOBOTS_STORAGE_SERVICE=SERVICE_KEY),
             'timeout': 120, **common}])


class Failures(Arranged):
    def test_a_failed_statement_fails_its_arrangement_and_the_steps_carry_on(self) -> None:
        cases = Cases()
        _, recorded = self.arrange_all(self.identity(RecordingStack(failing='Market watcher')), cases)
        failed = [record['id'] for record in cases.records if record['status'] == 'failed']
        self.assertEqual(failed, ['arranged: three Experts, one with three runs'])
        self.assertEqual([name for name, _ in recorded], [name for name, _ in STEP_CASES])
        self.assertIn('exit 3: ERROR: arranged failure', cases.records[5]['observed'])

    def test_an_owner_that_could_not_be_bootstrapped_raises_unavailable(self) -> None:
        for code, stdout, reason in ((1, '', 'owner bootstrap failed'), (0, 'not json', 'printed no JSON'),
                                     (0, json.dumps({'user_id': 'u'}), 'no user and workspace')):
            with self.subTest(reason):
                self.fail_launch = lambda argv, code=code, stdout=stdout: subprocess.CompletedProcess(argv, code, stdout, 'boom')
                with self.assertRaisesRegex(Unavailable, reason):
                    qualify_identity.IdentityRun(self.root, RecordingStack(), BASE, DB_PORT).owner('x@example.invalid')  # type: ignore[arg-type]  # a recording stand-in

    def test_a_step_out_of_order_names_the_owner_it_needs(self) -> None:
        run = self.identity()
        with self.assertRaisesRegex(LookupError, 'ops-n@example.invalid'):
            qualify_identity.arrange_search(run, Cases())


class Fixtures(unittest.TestCase):
    def test_a_value_is_quoted_as_one_sql_literal(self) -> None:
        self.assertEqual(qualify_identity.sql_literal("it's"), "'it''s'")
        self.assertEqual(qualify_identity.sql_literal('{"tools": []}'), '\'{"tools": []}\'')

    def test_a_fixture_takes_exactly_its_parameters(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / qualify_identity.IDENTITY_FIXTURES).mkdir(parents=True)
            (root / qualify_identity.IDENTITY_FIXTURES / 'one.sql').write_text(
                "-- Synthetic.\ninsert into t values (${workspace}, '{\"a\": 1}');\n")
            self.assertEqual(qualify_identity.fixture(root, 'one.sql', workspace="w'1"),
                             "-- Synthetic.\ninsert into t values ('w''1', '{\"a\": 1}');\n")
            for values in ({}, {'workspace': 'w', 'extra': 'x'}):
                with self.subTest(values), self.assertRaisesRegex(ValueError, 'one.sql'):
                    qualify_identity.fixture(root, 'one.sql', **values)

    def test_each_identity_fixture_says_it_is_synthetic_and_disposable(self) -> None:
        for path in sorted((ROOT / qualify_identity.IDENTITY_FIXTURES).glob('*.sql')):
            with self.subTest(path.name):
                opening = path.read_text().splitlines()[0]
                self.assertTrue(opening.startswith('-- '), opening)
                self.assertIn('disposable', path.read_text().split('\n\n')[0])


class StorageChildren(Arranged):
    def test_the_storage_children_keep_their_launches_and_arrangements(self) -> None:
        stack = RecordingStack()
        run = self.identity(stack)
        self.launches.clear()
        cases = Cases()
        fixtures = qualify_identity.storage_child_cases(run, cases, 'token-a', 'token-b')
        python, checks = str(self.root / 'services/agent/.venv/bin/python'), self.root / 'tests/db'
        storage = children.service_env(self.root, RUNTIME_URL, AUTOBOTS_STORAGE_BASE=BASE, AUTOBOTS_STORAGE_SERVICE=SERVICE_KEY)
        common = {'capture_output': True, 'text': True, 'errors': 'replace', 'check': False, 'cwd': None}
        values = {'a': 'ws-owner-a', 'b': 'ws-owner-b', 'python': python}
        expected = [{'argv': [python, str(checks / 'artifact_check.py'), 'ws-owner-a', 'ws-owner-b'],
                     'env': children.service_env(self.root, RUNTIME_URL, AUTOBOTS_STORAGE_BASE=BASE, AUTOBOTS_STORAGE_ANON='anon-fixture',
                                                 AUTOBOTS_STORAGE_SERVICE=SERVICE_KEY, AUTOBOTS_TOKEN_A='token-a', AUTOBOTS_TOKEN_B='token-b'),
                     'timeout': 240, **common}]
        expected += [{'argv': [python, str(checks / child.script), *(argument.format_map(values) for argument in child.args)],
                      'env': storage, 'timeout': 240, **common} for child in qualify_identity.IDENTITY_CHILDREN]
        expected += [{'argv': [python, str(checks / 'schema_release_check.py'), state], 'env': children.service_env(self.root, RUNTIME_URL),
                      'timeout': 60, **common} for state in ('equal', 'behind', 'ahead', 'no-history', 'no-history-missing')]
        self.assertEqual(self.launches, expected)
        self.assertEqual(len(qualify_identity.IDENTITY_CHILDREN), 16)
        arranged = [record['id'] for record in cases.records if record['id'].startswith('arranged: ')]
        self.assertEqual(arranged, ['arranged: each schema state, then restored', 'arranged: an older request with nothing recorded',
                                    'arranged: the run workspace fixtures'])
        self.assertEqual({name: fixtures[name] for name in ('AUTOBOTS_TEST_APPROVAL_LEGACY', 'AUTOBOTS_TEST_LOOP_RUN',
                                                           'AUTOBOTS_TEST_ARTIFACT_RUN', 'AUTOBOTS_TEST_ARTIFACT_TAMPERED')},
                         {'AUTOBOTS_TEST_APPROVAL_LEGACY': 'legacy-approval', 'AUTOBOTS_TEST_LOOP_RUN': 'loop-run',
                          'AUTOBOTS_TEST_ARTIFACT_RUN': 'artifact-run', 'AUTOBOTS_TEST_ARTIFACT_TAMPERED': 'tampered'})
        event = next(statement for _, statement in stack.statements if 'public.run_events' in statement and 'insert' in statement)
        self.assertIn(""", 1, '{"type": "model.reasoning", "text": "PROTECTED-REASONING"}', now()""", event)

    def test_no_child_runs_after_an_artifact_check_with_no_report(self) -> None:
        run = self.identity()
        self.launches.clear()
        self.fail_launch = lambda argv: subprocess.CompletedProcess(argv, 1, '', 'boom')
        self.assertEqual(qualify_identity.storage_child_cases(run, Cases(), 'token-a', 'token-b'), {})
        self.assertEqual(len(self.launches), 1)


class BrowserLaunches(Arranged):
    """The build, the services and every Playwright run keep their arguments, directory, timeout and report."""

    @contextlib.contextmanager
    def browser_fakes(self) -> Iterator[list[dict[str, Any]]]:
        started: list[dict[str, Any]] = []
        (self.root / qualify_web.BROWSERS / 'chromium-1').mkdir(parents=True)
        ports = iter(range(56001, 56010))

        def start(argv: list[str], env: dict[str, str], cwd: Path) -> str:
            started.append({'argv': list(argv), 'env': dict(env), 'cwd': cwd})
            return f'process-{len(started)}'

        def report(argv: list[str], **options: Any) -> subprocess.CompletedProcess[str]:
            if argv[0].endswith('playwright'):
                Path(options['env']['AUTOBOTS_WEB_REPORT']).write_text('{}')
            return self.fake_run(argv, **options)

        with contextlib.ExitStack() as patches:
            for name, value in (('find_tools', lambda root: 'tools'), ('child_env', lambda root, tools, verifying: {'CHILD': str(verifying)}),
                                ('start', start), ('stop', lambda process: None), ('wait_until_up', lambda url, process: None),
                                ('summarize', lambda path: ([{'id': Path(path).name, 'status': 'passed'}], {})),
                                ('run_problems', lambda path, code: []), ('rows', lambda stack, statement: '1')):
                patches.enter_context(mock.patch.object(qualify_identity, name, value))
            patches.enter_context(mock.patch.object(qualify_web, 'free_port', lambda: next(ports)))
            patches.enter_context(mock.patch.object(qualify_identity.secrets, 'token_hex', lambda size: f'hex-{size}'))
            patches.enter_context(mock.patch.object(qualify_identity.tempfile, 'mkdtemp', lambda prefix: str(self.root / 'config')))
            patches.enter_context(mock.patch.object(children.subprocess, 'run', report))
            (self.root / 'config').mkdir()
            yield started

    def test_each_browser_run_keeps_its_launch(self) -> None:
        run = self.identity()
        fixtures = {'AUTOBOTS_TEST_MEMBER_EMAIL': 'member-c@example.invalid', 'AUTOBOTS_TEST_MEMBER_PASSWORD': 'password-member',
                    'AUTOBOTS_TEST_COMPOSER_WORKSPACE': 'ws-composer-j'}
        self.launches.clear()
        with self.browser_fakes() as started:
            qualify_identity.browser_cases(run, Cases(), fixtures)
        web, checks = self.root / 'apps/web', self.root / '.checks/identity'
        playwright = str(web / 'node_modules/.bin/playwright')
        config = ['--config', 'playwright.config.ts']
        # The arranged project's tests, each selected by its spec file and its title (R-58).
        arranged = ['--project', 'arranged', '-g']
        expected = [([str(web / 'node_modules/.bin/next'), 'build'], 300, None),
                    ([playwright, 'test', '--project', 'main', *config], 660, 'playwright.json'),
                    ([playwright, 'test', 'qualification.spec.ts', *arranged, 'after an API restart', *config], 120,
                     'playwright-qualification-1.json'),
                    ([playwright, 'test', 'qualification.spec.ts', *arranged, 'a route with no record', *config], 120,
                     'playwright-qualification-2.json'),
                    *(([playwright, 'test', 'saved-choice.spec.ts', *arranged, title, *config], 120, f'playwright-saved-choice-{index}.json')
                      for index, title in enumerate(('a saved default naming DeepSeek', 'a saved override on another role',
                                                     'a saved executor override', 'a saved Expert binding'), start=1)),
                    ([playwright, 'test', 'readiness.spec.ts', *arranged, "names the service that isn't ready", *config], 180,
                     'playwright-readiness-1.json'),
                    ([playwright, 'test', 'readiness.spec.ts', *arranged, 'all local services ready', *config], 180,
                     'playwright-readiness-2.json'),
                    ([playwright, 'test', '--project', 'slice', *config], 900, 'playwright-slice.json')]
        observed = [(launch['argv'], launch['timeout'], Path(launch['env']['AUTOBOTS_WEB_REPORT']).name if 'AUTOBOTS_WEB_REPORT' in launch['env'] else None)
                    for launch in self.launches]
        self.assertEqual(observed, expected)
        for launch in self.launches:
            self.assertEqual((launch['cwd'], launch['capture_output'], launch['text'], launch['errors'], launch['check']),
                             (web, True, True, 'replace', False))
        browser_env = self.launches[1]['env']
        self.assertEqual({name: browser_env[name] for name in (
            'AUTOBOTS_TEST_OWNER_EMAIL', 'AUTOBOTS_TEST_OWNER_PASSWORD', 'AUTOBOTS_TEST_WORKSPACE_A', 'AUTOBOTS_TEST_WORKSPACE_B',
            'AUTOBOTS_TEST_OWNER_B_EMAIL', 'AUTOBOTS_TEST_OWNER_B_PASSWORD', 'AUTOBOTS_TEST_MEMBER_EMAIL', 'AUTOBOTS_TEST_MEMBER_PASSWORD',
            'AUTOBOTS_TEST_COMPOSER_WORKSPACE', 'AUTOBOTS_WEB_REPORT', 'AUTOBOTS_TEST_SERVICE_KEY', 'CHILD')},
            {'AUTOBOTS_TEST_OWNER_EMAIL': 'owner-a@example.invalid', 'AUTOBOTS_TEST_OWNER_PASSWORD': 'password-1',
             'AUTOBOTS_TEST_WORKSPACE_A': 'ws-owner-a', 'AUTOBOTS_TEST_WORKSPACE_B': 'ws-owner-b',
             'AUTOBOTS_TEST_OWNER_B_EMAIL': 'owner-b@example.invalid', 'AUTOBOTS_TEST_OWNER_B_PASSWORD': 'password-2',
             'AUTOBOTS_TEST_MEMBER_EMAIL': 'member-c@example.invalid', 'AUTOBOTS_TEST_MEMBER_PASSWORD': 'password-member',
             'AUTOBOTS_TEST_COMPOSER_WORKSPACE': 'ws-composer-j', 'AUTOBOTS_WEB_REPORT': str(checks / 'playwright.json'),
             'AUTOBOTS_TEST_SERVICE_KEY': SERVICE_KEY, 'CHILD': 'True'})
        python = str(self.root / 'services/agent/.venv/bin/python')
        self.assertEqual([(item['argv'], item['cwd']) for item in started],
                         [([python, str(self.root / 'tests/web/fixture_upstream_api.py'), '56001'], self.root),
                          ([str(web / 'node_modules/.bin/next'), 'start', '-H', '127.0.0.1', '-p', '56002'], web),
                          ([python, str(self.root / 'tests/web/fixture_upstream_api.py'), '56001'], self.root),
                          ([python, str(self.root / 'tests/web/fixture_worker.py')], self.root)])


class ArrangedSpecs(unittest.TestCase):
    def test_the_spec_files_named_are_the_arranged_projects(self) -> None:
        # Each arranged test is selected by its spec file and title (R-58), so the files must be the project's.
        projects = json.loads((ROOT / suites.BROWSER_PROJECTS).read_text())
        named = (qualify_identity.QUALIFICATION_SPEC, qualify_identity.SAVED_CHOICE_SPEC, qualify_identity.READINESS_SPEC)
        self.assertEqual(sorted(named), sorted(projects[suites.ARRANGED_PROJECT]))


if __name__ == '__main__':
    unittest.main()
