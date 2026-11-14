"""The one runner every qualifier uses for its tests/db child checks (refactor plan R-39, SCRP-01).

Each fake child here is a real process: the runner starts `services/agent/.venv/bin/python` under a
temporary root, which links to this interpreter, so what it records is what a qualifier records. A
child that could not run, crashed, printed partial output, printed after its report or printed no
report adds exactly one failed case of the runner's own and never raises (PRD-Development-Harness
DH-09.2). Cases a failed child printed before it stopped are kept (TDBC-04).
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from typing import Any, ClassVar
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import app_db  # noqa: E402
import qualify_identity  # noqa: E402
from qualification import children  # noqa: E402
from qualification.errors import Unavailable  # noqa: E402
from qualification.records import Cases  # noqa: E402

REPORT = {'cases': [{'id': 'first', 'expected': 'one', 'observed': 'one', 'passed': True},
                    {'id': 'second', 'expected': 'two', 'observed': 'three', 'passed': False}],
          'browser_env': {'AUTOBOTS_TEST_RUN': 'run-1'}, 'run_id': 'run-1'}


class FakeRoot:
    """A repository root whose service interpreter is this one and whose tests/db holds fake children."""

    def __init__(self, folder: str) -> None:
        self.path = Path(folder)
        python = self.path / children.CHECK_PYTHON
        python.parent.mkdir(parents=True)
        python.symlink_to(sys.executable)
        (self.path / children.CHECKS).mkdir(parents=True)
        self.err_dir = self.path / '.checks/fake'

    def child(self, name: str, body: str) -> str:
        (self.path / children.CHECKS / name).write_text(textwrap.dedent(body))
        return name


def printing(report: object, *, after: str = '', code: int = 0) -> str:
    """A child that prints a report line, then optionally more, then exits with `code`."""
    return (f'import json, sys\nprint("starting")\nprint(json.dumps({report!r}))\n'
            + (f'print({after!r})\n' if after else '')
            + f'sys.stderr.write("the end of stderr")\nraise SystemExit({code})\n')


class Quiet(unittest.TestCase):
    """Cases prints a line for each case it records, which these tests read from the records instead."""

    def setUp(self) -> None:
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))


class ChildOutcomes(Quiet):
    def setUp(self) -> None:
        super().setUp()
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = FakeRoot(self.folder.name)

    def run_child(self, script: str, *args: str, timeout: float = 30, **options: Any) -> tuple[Cases, children.ChildRun]:
        cases = Cases()
        env = children.service_env(self.root.path, 'postgresql://runtime@127.0.0.1:55401/postgres')
        ran = children.run_child_check(cases, self.root.path, script, *args, label='the fake check', env=env,
                                       timeout=timeout, err_dir=self.root.err_dir, **options)
        return cases, ran

    def outcomes(self, cases: Cases) -> list[tuple[str, str]]:
        return [(record['id'], record['status']) for record in cases.records]

    def test_a_report_replays_its_cases_and_keeps_its_fields(self) -> None:
        cases, ran = self.run_child(self.root.child('good_check.py', printing(REPORT)))
        self.assertEqual(self.outcomes(cases), [('first', 'passed'), ('second', 'failed')])
        self.assertEqual(cases.records[1]['observed'], 'three')
        self.assertTrue(ran.completed)
        self.assertEqual((ran.text('run_id'), ran.env('browser_env')), ('run-1', {'AUTOBOTS_TEST_RUN': 'run-1'}))
        self.assertEqual((ran.text('absent'), ran.env('absent')), ('', {}))
        self.assertFalse(self.root.err_dir.exists())

    def test_a_non_zero_exit_with_no_output_fails_one_case(self) -> None:
        cases, ran = self.run_child(self.root.child('dies_check.py', 'import sys\nsys.stderr.write("Traceback: boom")\nraise SystemExit(3)\n'))
        self.assertEqual(self.outcomes(cases), [('the fake check ran', 'failed')])
        self.assertIn('exit 3', cases.records[0]['observed'])
        self.assertIn('Traceback: boom', cases.records[0]['observed'])
        self.assertFalse(ran.completed)
        self.assertEqual((ran.returncode, ran.report), (3, None))

    def test_a_crash_after_its_report_fails_one_case_and_keeps_what_it_printed(self) -> None:
        cases, _ = self.run_child(self.root.child('crash_check.py', printing(REPORT, code=1)))
        self.assertEqual(self.outcomes(cases), [('the fake check ran', 'failed'), ('first', 'passed'), ('second', 'failed')])

    def test_partial_output_fails_one_case(self) -> None:
        truncated = 'print(\'{"cases": [{"id": "first", "expec\')\n'
        for code, failed in ((0, 'the fake check printed its cases'), (1, 'the fake check ran')):
            with self.subTest(code=code):
                cases, ran = self.run_child(self.root.child(f'partial_{code}_check.py', truncated + f'raise SystemExit({code})\n'))
                self.assertEqual(self.outcomes(cases), [(failed, 'failed')])
                self.assertIsNone(ran.report)

    def test_a_late_warning_after_the_report_fails_one_case(self) -> None:
        cases, ran = self.run_child(self.root.child('late_check.py', printing(REPORT, after='DeprecationWarning: late')))
        self.assertEqual(self.outcomes(cases), [('the fake check printed its cases', 'failed')])
        self.assertEqual(cases.records[0]['observed'], 'a last line that is not one')
        self.assertFalse(ran.completed)

    def test_a_missing_report_fails_one_case(self) -> None:
        for name, body, observed in (('silent_check.py', 'pass\n', 'no output'),
                                     ('chatty_check.py', 'print("done, no report")\n', 'a last line that is not one'),
                                     ('list_check.py', 'print("[1, 2]")\n', 'a last line that is not one')):
            with self.subTest(name):
                cases, _ = self.run_child(self.root.child(name, body))
                self.assertEqual(self.outcomes(cases), [('the fake check printed its cases', 'failed')])
                self.assertEqual(cases.records[0]['observed'], observed)

    def test_a_malformed_case_fails_one_case(self) -> None:
        for name, case in (('truthy_check.py', {'id': 'x', 'expected': 'y', 'observed': 'z', 'passed': 'yes'}),
                           ('short_check.py', {'id': 'x', 'expected': 'y', 'passed': True}),
                           ('nameless_check.py', {'id': 1, 'expected': 'y', 'observed': 'z', 'passed': True})):
            with self.subTest(name):
                cases, ran = self.run_child(self.root.child(name, printing({'cases': [case]})))
                self.assertEqual(self.outcomes(cases), [('the fake check printed its cases', 'failed')])
                self.assertIsNone(ran.report)

    def test_a_child_that_could_not_start_fails_one_case(self) -> None:
        (self.root.path / children.CHECK_PYTHON).unlink()
        cases, ran = self.run_child('any_check.py')
        self.assertEqual(self.outcomes(cases), [('the fake check ran', 'failed')])
        self.assertIn('could not start', cases.records[0]['observed'])
        self.assertIsNone(ran.returncode)

    def test_a_child_that_outlives_its_timeout_fails_one_case(self) -> None:
        script = self.root.child('slow_check.py', 'import time\nprint("started", flush=True)\ntime.sleep(30)\n')
        cases, ran = self.run_child(script, timeout=0.5)
        self.assertEqual(self.outcomes(cases), [('the fake check ran', 'failed')])
        self.assertIn('timed out after 0.5 seconds', cases.records[0]['observed'])
        self.assertIsNone(ran.returncode)

    def test_a_failed_child_keeps_its_stderr_and_a_passing_one_removes_it(self) -> None:
        script = self.root.child('flaky_check.py', printing(REPORT, code=1))
        self.run_child(script)
        kept = self.root.err_dir / 'flaky_check.err'
        self.assertEqual(kept.read_text(), 'the end of stderr')
        self.root.child('flaky_check.py', printing(REPORT))
        self.run_child(script)
        self.assertFalse(kept.exists())
        self.run_child(self.root.child('named_check.py', printing(REPORT, code=1)), err_name='named')
        self.assertTrue((self.root.err_dir / 'named.err').is_file())

    def test_an_answered_child_reads_the_reply_to_its_first_line(self) -> None:
        script = self.root.child('asks_check.py', '''
            import json, sys
            print(json.dumps({"stage": "needs_grant"}), flush=True)
            reply = sys.stdin.readline()
            print(json.dumps({"cases": [{"id": "the reply", "expected": "a newline", "observed": repr(reply), "passed": reply == "\\n"}]}))
            ''')
        asked: list[str] = []

        def answer(line: str) -> str:
            asked.append(line)
            return '\n'

        cases, ran = self.run_child(script, answer=answer)
        self.assertEqual(asked, ['{"stage": "needs_grant"}\n'])
        self.assertEqual(self.outcomes(cases), [('the reply', 'passed')])
        self.assertTrue(ran.completed)


class Launches(Quiet):
    """Each child starts with exactly the arguments, environment, timeout and directory it is given."""

    def recorded(self, call: Any) -> list[dict[str, Any]]:
        launches: list[dict[str, Any]] = []

        def fake_run(argv: list[str], **options: Any) -> subprocess.CompletedProcess[str]:
            launches.append({'argv': argv, **options})
            return subprocess.CompletedProcess(argv, 0, json.dumps({'cases': []}) + '\n', '')

        with mock.patch.object(children.subprocess, 'run', fake_run):
            call()
        return launches

    def test_the_runner_passes_its_launch_through_unchanged(self) -> None:
        root = Path('/repo')
        env = {'ONLY': 'this'}
        launches = self.recorded(lambda: children.run_child_check(Cases(), root, 'some_check.py', 'a', 'b', label='some check',
                                                                  env=env, timeout=42, cwd=root / 'elsewhere', err_dir=None))
        self.assertEqual(launches, [{'argv': ['/repo/services/agent/.venv/bin/python', '/repo/tests/db/some_check.py', 'a', 'b'],
                                     'env': env, 'capture_output': True, 'text': True, 'errors': 'replace',
                                     'timeout': 42, 'check': False, 'cwd': root / 'elsewhere'}])

    def test_the_service_environment_holds_no_inherited_credential(self) -> None:
        with mock.patch.dict(os.environ, {'OPENROUTER_API_KEY': 'fixture-not-a-key', 'HOME': '/home/fixture'}):
            env = children.service_env(Path('/repo'), 'postgresql://u@127.0.0.1:55401/postgres', AUTOBOTS_EXTRA='x')
        self.assertNotIn('OPENROUTER_API_KEY', env)
        self.assertEqual({key: env[key] for key in ('AUTOBOTS_DATABASE_URL', 'AUTOBOTS_EXTRA', 'PYTHONPATH', 'PYTHONDONTWRITEBYTECODE', 'HOME')},
                         {'AUTOBOTS_DATABASE_URL': 'postgresql://u@127.0.0.1:55401/postgres', 'AUTOBOTS_EXTRA': 'x',
                          'PYTHONPATH': '/repo/services/agent/src', 'PYTHONDONTWRITEBYTECODE': '1', 'HOME': '/home/fixture'})

    def test_a_child_formats_its_argument_templates(self) -> None:
        child = children.Child('loop_check.py', 'the loop check', ('{workspace}', 'literal', '{python}'), timeout=240, from_root=True)
        root = Path('/repo')
        launches = self.recorded(lambda: children.run_child(Cases(), root, child, {'workspace': 'w-1', 'python': '/py'}, env={}, err_dir=None))
        self.assertEqual((launches[0]['argv'][2:], launches[0]['timeout'], launches[0]['cwd']), (['w-1', 'literal', '/py'], 240, root))


class FakeStack:
    """Answers every statement with exit 0, so the qualifier code runs without a database."""

    runtime_password = 'runtime-fixture'
    values: ClassVar[dict[str, str]] = {'SERVICE_ROLE_KEY': 'service-fixture'}

    def __getattr__(self, name: str) -> Any:
        return lambda *args, **kwargs: subprocess.CompletedProcess(args, 0, '', '')


class QualifiersSurviveBadChildren(Quiet):
    def test_app_db_records_a_child_whose_last_line_is_not_its_report_and_carries_on(self) -> None:
        cases = Cases()

        def warned(argv: list[str], **_options: Any) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(argv, 0, json.dumps({'cases': []}) + '\nwarning: printed late\n', '')

        with tempfile.TemporaryDirectory() as folder, mock.patch.object(children.subprocess, 'run', warned):
            app_db.tool_cases(FakeStack(), cases, Path(folder), 55401)  # type: ignore[arg-type]
        printed = [record['id'] for record in cases.records if record['id'].endswith('printed its cases')]
        self.assertEqual(printed, ['the tool gateway check printed its cases'])

    def test_every_child_table_names_a_real_check(self) -> None:
        for child in (*app_db.TOOL_CHILDREN, *qualify_identity.IDENTITY_CHILDREN):
            with self.subTest(child.script):
                self.assertTrue((ROOT / children.CHECKS / child.script).is_file())
        labels = [child.label for child in (*app_db.TOOL_CHILDREN, *qualify_identity.IDENTITY_CHILDREN)]
        self.assertEqual(len(labels), len(set(labels)))


class Arrangements(Quiet):
    def test_an_arrangement_is_recorded_whether_or_not_it_held(self) -> None:
        cases = Cases()
        held = cases.arrange('the canary tables', subprocess.CompletedProcess([], 0, '', ''))
        failed = cases.arrange('the grant', subprocess.CompletedProcess([], 0, '', ''),
                               subprocess.CompletedProcess([], 3, '', 'ERROR: relation missing'))
        self.assertEqual((held, failed), (True, False))
        self.assertEqual([(record['id'], record['status']) for record in cases.records],
                         [('arranged: the canary tables', 'passed'), ('arranged: the grant', 'failed')])
        self.assertIn('exit 3: ERROR: relation missing', cases.records[1]['observed'])

    def test_a_required_arrangement_that_failed_raises_unavailable(self) -> None:
        cases = Cases()
        with self.assertRaisesRegex(Unavailable, 'the stack could not be arranged: exit 1'):
            cases.arrange('the stack', subprocess.CompletedProcess([], 1, '', 'no'), required=True)
        self.assertEqual(cases.records, [])

    def test_a_condition_is_arranged_the_same_way(self) -> None:
        cases = Cases()
        self.assertFalse(cases.arranged('the browser runs', 'waiting and finished', "{'waiting': 'queued'}", False))
        self.assertEqual(cases.records[0]['id'], 'arranged: the browser runs')

    def test_an_arrangement_child_returns_its_output_or_raises_unavailable(self) -> None:
        cases = Cases()
        outputs = iter([(0, '{"run_id": "r"}\n'), (0, 'not json\n'), (2, '')])

        def fake_run(argv: list[str], **_options: Any) -> subprocess.CompletedProcess[str]:
            code, stdout = next(outputs)
            return subprocess.CompletedProcess(argv, code, stdout, 'stderr tail')

        with mock.patch.object(children.subprocess, 'run', fake_run):
            self.assertEqual(children.run_arrangement(cases, Path('/repo'), 'model_sources.py', label='the binding-source run',
                                                      env={}, timeout=120), {'run_id': 'r'})
            for _ in range(2):
                with self.assertRaisesRegex(Unavailable, 'the binding-source run could not be arranged'):
                    children.run_arrangement(cases, Path('/repo'), 'model_sources.py', label='the binding-source run', env={}, timeout=120)
        self.assertEqual([(record['id'], record['status']) for record in cases.records], [('arranged: the binding-source run', 'passed')])


if __name__ == '__main__':
    unittest.main()
