"""The case protocol every database check shares, tests/db/fixtures/checklib.py (refactor plan R-38).

The checks themselves need a disposable database, so the db profile runs them. What each one relies
on runs here with the standard library only: a crashing check still prints what it observed, a case
judges the value it shows, and a refusal of the wrong class fails its case (TDBC-03, TDBC-04).
"""
from __future__ import annotations

import ast
import asyncio
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from typing import Any
from unittest import mock
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / 'tests/db/fixtures'
sys.path.insert(0, str(FIXTURES))
import checklib  # noqa: E402

SECRET = 'tvly-fixtureNeverPrinted01'


class Refusal(Exception):
    code = 'budget_exceeded'


class OtherError(Exception):
    code = 'budget_exceeded'


async def raises(error: BaseException) -> None:
    raise error


async def returns(value: object) -> object:
    return value


def printed(text: str) -> Any:
    """The one JSON line a check prints last, which scripts/app_db.py and the qualifiers parse."""
    return json.loads(text.strip().splitlines()[-1])


class FakeCursor:
    def __init__(self, row: tuple[object, ...] | None) -> None:
        self.row = row

    async def fetchone(self) -> tuple[object, ...] | None:
        return self.row


class FakeConnection:
    """Answers each statement with the next arranged row, and keeps what it was asked."""

    def __init__(self, *rows: tuple[object, ...] | None) -> None:
        self.rows = list(rows)
        self.executed: list[tuple[str, tuple[object, ...]]] = []

    async def execute(self, sql: str, values: tuple[object, ...] = ()) -> FakeCursor:
        self.executed.append((sql, tuple(values)))
        return FakeCursor(self.rows.pop(0) if self.rows else None)


class CrashingCheck(unittest.TestCase):
    def test_a_crashing_check_still_prints_its_cases(self) -> None:
        async def main(cases: checklib.Cases) -> None:
            cases.check('before the crash', 'seen', 'seen', True)
            raise RuntimeError('arranged crash')

        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaisesRegex(RuntimeError, 'arranged crash'):
            checklib.run_check(main)
        self.assertEqual(printed(out.getvalue()),
                         {'cases': [{'id': 'before the crash', 'expected': 'seen', 'observed': 'seen', 'passed': True}]})

    def test_a_crashing_check_script_exits_non_zero_after_printing(self) -> None:
        """Run as the qualifiers run it: a script in checks/ with fixtures/ on its path (qualification/children.py
        service_env), so no path insert."""
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / 'fixtures').mkdir()
            (Path(folder) / 'checks').mkdir()
            shutil.copy(FIXTURES / 'checklib.py', Path(folder) / 'fixtures')
            script = Path(folder) / 'checks/crash_check.py'
            script.write_text('from checklib import Cases, run_check\n\n\n'
                              'async def main(cases: Cases) -> None:\n'
                              "    cases.check('observed first', 'yes', 'yes', True)\n"
                              "    raise RuntimeError('arranged crash')\n\n\n"
                              'run_check(main)\n')
            result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, timeout=60,
                                    check=False, cwd=folder, env={**os.environ, 'PYTHONPATH': str(Path(folder) / 'fixtures')})
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn('arranged crash', result.stderr)
        self.assertEqual([case['id'] for case in printed(result.stdout)['cases']], ['observed first'])

    def test_a_finished_check_prints_its_extra_fields(self) -> None:
        async def main(cases: checklib.Cases) -> dict[str, object]:
            cases.check('arranged', 'yes', 'yes', True)
            return {'browser_env': {'AUTOBOTS_TEST_RUN': 'r'}}

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            checklib.run_check(main)
        self.assertEqual(printed(out.getvalue())['browser_env'], {'AUTOBOTS_TEST_RUN': 'r'})

    def test_a_case_holding_a_fixture_secret_is_withheld(self) -> None:
        async def main(cases: checklib.Cases) -> None:
            cases.check('a key was shown', 'no key', f'Bearer {SECRET}', False)

        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit):
            checklib.run_check(main, secrets=(SECRET, ''))
        self.assertNotIn(SECRET, out.getvalue())
        self.assertEqual([case['passed'] for case in printed(out.getvalue())['cases']], [False])

    def test_a_crash_whose_error_holds_a_fixture_secret_exits_without_it(self) -> None:
        """The parents copy the end of stderr into evidence, so that traceback is never shown."""
        async def main(cases: checklib.Cases) -> None:
            cases.check('observed before the crash', 'yes', 'yes', True)
            raise RuntimeError(f'the reply held {SECRET}')

        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit) as raised:
            checklib.run_check(main, secrets=(SECRET,))
        self.assertNotIn(SECRET, str(raised.exception.code))
        self.assertTrue(raised.exception.__suppress_context__)
        self.assertEqual([case['id'] for case in printed(out.getvalue())['cases']], ['observed before the crash'])

    def test_a_secret_in_a_scenario_error_is_not_printed(self) -> None:
        async def main(cases: checklib.Cases) -> None:
            with cases.scenario('a scenario whose error names the key'):
                raise RuntimeError(f'the reply held {SECRET}')

        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit):
            checklib.run_check(main, secrets=(SECRET,))
        self.assertNotIn(SECRET, out.getvalue())

    def test_a_failing_first_scenario_stops_the_rest_and_the_cases_still_print(self) -> None:
        ran: list[str] = []

        async def first(cases: checklib.Cases) -> None:
            ran.append('first')
            cases.check('first observed', 'seen', 'seen', True)
            raise LookupError('arranged')

        async def second(cases: checklib.Cases) -> None:
            ran.append('second')
            cases.check('second observed', 'seen', 'seen', True)

        async def third(cases: checklib.Cases) -> None:
            ran.append('third')

        async def main(cases: checklib.Cases) -> None:
            await checklib.run_scenarios(cases, (first, second, third), cases)

        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaisesRegex(LookupError, 'arranged'):
            checklib.run_check(main)
        shown = printed(out.getvalue())['cases']
        self.assertEqual(ran, ['first'])
        self.assertEqual([(case['id'], case['passed']) for case in shown],
                         [('first observed', True), ('first: ran to the end', False),
                          ('second: ran to the end', False), ('third: ran to the end', False)])
        self.assertEqual(shown[1]['observed'], 'LookupError: arranged')
        self.assertEqual(shown[2]['observed'], 'not run, because first raised')

    def test_a_check_whose_first_scenario_fails_exits_non_zero_after_printing(self) -> None:
        """As the qualifiers run it: a script in checks/ with fixtures/ on its path."""
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / 'fixtures').mkdir()
            (Path(folder) / 'checks').mkdir()
            shutil.copy(FIXTURES / 'checklib.py', Path(folder) / 'fixtures')
            script = Path(folder) / 'checks/stops_check.py'
            script.write_text('from checklib import Cases, run_check, run_scenarios\n\n\n'
                              'async def arranges(cases: Cases) -> None:\n'
                              "    cases.check('arranged first', 'yes', 'yes', True)\n"
                              "    raise RuntimeError('arranged crash')\n\n\n"
                              'async def reads_it(cases: Cases) -> None:\n'
                              "    cases.check('read what was arranged', 'yes', 'yes', True)\n\n\n"
                              'async def main(cases: Cases) -> None:\n'
                              '    await run_scenarios(cases, (arranges, reads_it), cases)\n\n\n'
                              'run_check(main, parent_timeout=60)\n')
            result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, timeout=60,
                                    check=False, cwd=folder, env={**os.environ, 'PYTHONPATH': str(Path(folder) / 'fixtures')})
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn('arranged crash', result.stderr)
        self.assertEqual([case['id'] for case in printed(result.stdout)['cases']],
                         ['arranged first', 'arranges: ran to the end', 'reads_it: ran to the end'])

    def test_a_check_past_its_limit_prints_its_cases_and_kills_its_worker(self) -> None:
        """A parent that times out kills its child, which prints nothing, so the check stops itself sooner."""
        held: list[asyncio.subprocess.Process] = []

        async def waits_on_a_worker(cases: checklib.Cases) -> None:
            cases.check('before the worker', 'seen', 'seen', True)
            async with checklib.started_worker(sys.executable, '-c', 'import time; time.sleep(60)') as process:
                held.append(process)
                await process.communicate()

        async def after_it(cases: checklib.Cases) -> None:
            cases.check('after the worker', 'seen', 'seen', True)

        async def main(cases: checklib.Cases) -> None:
            await checklib.run_scenarios(cases, (waits_on_a_worker, after_it), cases)

        out = io.StringIO()
        with (mock.patch.object(checklib, 'STOP_MARGIN', 0.0), contextlib.redirect_stdout(out),
              self.assertRaises(TimeoutError)):
            checklib.run_check(main, parent_timeout=1.0)
        shown = printed(out.getvalue())['cases']
        self.assertEqual([(case['id'], case['passed']) for case in shown],
                         [('before the worker', True), ('waits_on_a_worker: ran to the end', False),
                          ('after_it: ran to the end', False), ('the check finished within its time limit', False)])
        self.assertEqual(shown[1]['observed'], 'CancelledError')
        self.assertEqual(held[0].returncode, checklib.KILLED)

    def test_an_error_raised_inside_the_limit_is_not_called_the_limit(self) -> None:
        async def main(cases: checklib.Cases) -> None:
            raise TimeoutError('a worker wait of its own')

        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaisesRegex(TimeoutError, 'a worker wait of its own'):
            checklib.run_check(main, parent_timeout=60)
        self.assertEqual(printed(out.getvalue())['cases'], [])

    def test_a_scenario_guard_records_its_exception_and_the_next_scenario_runs(self) -> None:
        cases = checklib.Cases()
        with cases.scenario('the first scenario'):
            raise LookupError('arranged')
        with cases.scenario('the second scenario'):
            cases.check('the second scenario ran', 'yes', 'yes', True)
        self.assertEqual([(case['id'], case['passed']) for case in cases.records],
                         [('the first scenario: ran to the end', False), ('the second scenario ran', True)])
        self.assertIn('LookupError: arranged', cases.records[0]['observed'])


class JudgedOnce(unittest.TestCase):
    def test_a_check_evaluates_its_value_once(self) -> None:
        calls: list[int] = []
        judged: list[object] = []

        def claim() -> str:
            calls.append(len(calls) + 1)
            return f'claim {len(calls)}'

        def one_claim(value: str) -> bool:
            judged.append(value)
            return value == 'claim 1'

        cases = checklib.Cases()
        shown = cases.check('one claim', 'claim 1', claim(), one_claim)
        self.assertEqual((calls, judged, shown), ([1], ['claim 1'], 'claim 1'))
        self.assertEqual(cases.records, [{'id': 'one claim', 'expected': 'claim 1', 'observed': 'claim 1', 'passed': True}])

    def test_the_predicate_judges_the_same_object_that_is_shown(self) -> None:
        cases = checklib.Cases()
        value = ['first']
        seen: list[object] = []

        def never(observed: list[str]) -> bool:
            seen.append(observed)
            return False

        cases.check('the same list', "['first']", value, never)
        self.assertIs(seen[0], value)
        self.assertFalse(cases.records[0]['passed'])

    def test_a_long_observation_is_shortened_but_judged_whole(self) -> None:
        cases = checklib.Cases()
        cases.check('long', 'ends in z', 'a' * 5000 + 'z', lambda observed: observed.endswith('z'))
        self.assertTrue(cases.records[0]['passed'])
        self.assertLessEqual(len(cases.records[0]['observed']), checklib.OBSERVED_LIMIT)


class Refusals(unittest.TestCase):
    def outcomes(self, *attempts: tuple[str, str | None, Any]) -> dict[str, bool]:
        cases = checklib.Cases()
        for name, code, attempt in attempts:
            asyncio.run(cases.refused(name, code, attempt, Refusal))
        return {case['id']: case['passed'] for case in cases.records}

    def test_a_refusal_of_the_wrong_class_fails_the_case(self) -> None:
        self.assertEqual(self.outcomes(('the named refusal', 'budget_exceeded', raises(Refusal())),
                                       ('another class with the same code', 'budget_exceeded', raises(OtherError('x'))),
                                       ('the class alone', None, raises(Refusal()))),
                         {'the named refusal': True, 'another class with the same code': False, 'the class alone': True})

    def test_a_refusal_with_another_code_or_none_fails_the_case(self) -> None:
        wrong = Refusal()
        wrong.code = 'no_inference_slot'
        self.assertEqual(self.outcomes(('another code', 'budget_exceeded', raises(wrong)),
                                       ('accepted', 'budget_exceeded', returns('admitted'))),
                         {'another code': False, 'accepted': False})

    def test_the_failed_case_names_what_happened(self) -> None:
        cases = checklib.Cases()
        asyncio.run(cases.refused('wrong class', 'budget_exceeded', raises(OtherError('arranged')), Refusal))
        asyncio.run(cases.refused('accepted', 'budget_exceeded', returns('admitted'), Refusal))
        self.assertEqual([case['observed'] for case in cases.records], ['OtherError: arranged', 'accepted: admitted'])
        self.assertEqual(cases.records[0]['expected'], 'Refusal budget_exceeded')

    def test_a_cancellation_is_never_taken_for_a_refusal(self) -> None:
        cases = checklib.Cases()
        with self.assertRaises(asyncio.CancelledError):
            asyncio.run(cases.refused('cancelled', None, raises(asyncio.CancelledError()), Refusal))
        self.assertEqual(cases.records, [])


class Arrangements(unittest.TestCase):
    def test_a_missing_row_names_its_sql(self) -> None:
        db = checklib.Db(FakeConnection(None), checklib.Cases(), uuid4(), uuid4())
        with self.assertRaises(checklib.NoRow) as raised:
            asyncio.run(db.value('select status from public.runs where id = %s', uuid4()))
        self.assertEqual(raised.exception.sql, 'select status from public.runs where id = %s')

    def test_isolation_ends_only_what_claim_next_could_take(self) -> None:
        connection = FakeConnection()
        run = uuid4()
        asyncio.run(checklib.Db(connection, checklib.Cases(), uuid4(), uuid4()).quiesce(keep=run))
        (sql, values), = connection.executed
        self.assertIn("status = 'queued'", sql)
        self.assertIn("status = 'claimed' and lease_expires_at <= clock_timestamp()", sql)
        self.assertNotIn("<> 'done'", sql)
        self.assertEqual(values, (run,))

    def test_an_isolated_claim_of_another_run_fails_its_case(self) -> None:
        under_test, other = uuid4(), uuid4()
        for claimed, passed in ((under_test, True), (other, False)):
            with self.subTest(passed=passed):
                leases = types.ModuleType('autobots.application.worker_leases')

                async def claim_next(connection: object, *, worker_id: str, lease_seconds: float,
                                     run: object = claimed) -> object:
                    return types.SimpleNamespace(run_id=run, generation=1)

                leases.claim_next = claim_next  # type: ignore[attr-defined]
                modules = {'autobots': types.ModuleType('autobots'),
                           'autobots.application': types.ModuleType('autobots.application'),
                           'autobots.application.worker_leases': leases}
                cases = checklib.Cases()
                db = checklib.Db(FakeConnection(), cases, uuid4(), uuid4())
                with mock.patch.dict(sys.modules, modules), contextlib.suppress(checklib.NoClaim):
                    asyncio.run(db.isolated_claim(under_test, worker_id='isolated'))
                self.assertEqual([case['passed'] for case in cases.records], [passed])
                self.assertEqual(cases.records[0]['expected'], str(under_test))

    def test_one_pool_lends_its_one_connection(self) -> None:
        connection = object()

        async def lent() -> object:
            async with checklib.OnePool(connection).connection() as held:
                return held

        self.assertIs(asyncio.run(lent()), connection)

    def test_a_killed_worker_records_its_exit(self) -> None:
        dies = [sys.executable, '-c', "import os, signal; print('started', flush=True); os.kill(os.getpid(), signal.SIGKILL)"]
        lives = [sys.executable, '-c', "print('started')"]
        cases = checklib.Cases()
        out = asyncio.run(checklib.killed_worker(cases, 'the worker was killed', dies))
        asyncio.run(checklib.killed_worker(cases, 'a worker that lives fails', lives))
        self.assertEqual(out.strip(), 'started')
        self.assertEqual([(case['expected'], case['passed']) for case in cases.records], [('exit -9', True), ('exit -9', False)])

    def test_a_worker_past_its_limit_is_killed_and_the_wait_raises(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            pid_file = Path(folder) / 'pid'
            sleeps = [sys.executable, '-c', f'import os, time; open({str(pid_file)!r}, "w").write(str(os.getpid())); time.sleep(60)']
            with self.assertRaises(TimeoutError):
                asyncio.run(checklib.run_worker(*sleeps, limit_seconds=2))
            pid = int(pid_file.read_text())
        # Reaped, so the process no longer exists.
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)

    def test_a_worker_run_to_its_end_gives_its_exit_and_output(self) -> None:
        code, out, err = asyncio.run(checklib.run_worker(sys.executable, '-c', "import sys; print('out'); sys.exit(3)"))
        self.assertEqual((code, out.strip(), err), (3, b'out', b''))


class ScenarioCheckLimits(unittest.TestCase):
    """Each check that runs SCENARIOS stops STOP_MARGIN seconds before the timeout its parent's Child entry gives it,
    so its cases print before the parent would kill it (checklib.run_check)."""

    @staticmethod
    def call_name(node: ast.Call) -> str | None:
        return node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, 'attr', None)

    def parent_timeouts(self) -> dict[str, list[float]]:
        children = ast.parse((ROOT / 'scripts/qualification/children.py').read_text())
        default = next(node.value.value for node in ast.walk(children) if isinstance(node, ast.AnnAssign)
                       and isinstance(node.target, ast.Name) and node.target.id == 'timeout' and isinstance(node.value, ast.Constant))
        found: dict[str, list[float]] = {}
        for path in sorted((ROOT / 'scripts').rglob('*.py')):
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.Call) and self.call_name(node) == 'Child' and node.args \
                        and isinstance(node.args[0], ast.Constant) and str(node.args[0].value).startswith('checks/'):
                    given = next((keyword.value.value for keyword in node.keywords if keyword.arg == 'timeout'
                                  and isinstance(keyword.value, ast.Constant)), default)
                    found.setdefault(node.args[0].value.removeprefix('checks/'), []).append(given)
        return found

    def test_each_scenario_check_stops_before_its_parent_would_kill_it(self) -> None:
        parents = self.parent_timeouts()
        scenario_checks = 0
        for path in sorted((ROOT / 'tests/db/checks').glob('*.py')):
            tree = ast.parse(path.read_text())
            declared = [keyword.value.value for node in ast.walk(tree) if isinstance(node, ast.Call)
                        and self.call_name(node) == 'run_check' for keyword in node.keywords
                        if keyword.arg == 'parent_timeout' and isinstance(keyword.value, ast.Constant)]
            has_scenarios = any(isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'SCENARIOS'
                                                                     for target in node.targets) for node in tree.body)
            if not (declared or has_scenarios):
                continue
            scenario_checks += has_scenarios
            with self.subTest(path.name):
                self.assertIn(path.name, parents, 'no parent runs it')
                self.assertEqual(declared, [min(parents[path.name])])
                self.assertGreater(declared[0], checklib.STOP_MARGIN)
        self.assertGreaterEqual(scenario_checks, 8)


if __name__ == '__main__':
    unittest.main()
