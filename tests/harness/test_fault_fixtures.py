"""The fault set stays complete, and the outcome rule cannot be satisfied by a wrong failure."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import qualify_faults  # noqa: E402

STATE = ROOT / 'tests/faults/state'


class FaultSet(unittest.TestCase):
    def test_each_required_kind_has_a_good_and_a_bad_case(self):
        cases = qualify_faults.cases(ROOT)
        for kind in qualify_faults.KINDS:
            with self.subTest(kind=kind):
                markers = [case.marker for case in cases if case.kind == kind]
                self.assertIn(None, markers)
                self.assertTrue(any(marker for marker in markers))
        self.assertEqual(len({case.id for case in cases}), len(cases))

    def test_each_fixture_a_case_names_exists(self):
        for case in qualify_faults.cases(ROOT):
            for argument in case.argv:
                if argument.startswith(str(qualify_faults.FAULTS)) or argument.endswith('expected.json'):
                    with self.subTest(case=case.id):
                        self.assertTrue((ROOT / case.cwd / argument).exists(), argument)

    def test_a_real_transport_fault_runs_with_a_key_present(self):
        case = next(case for case in qualify_faults.cases(ROOT) if case.id == 'model_real_bad')
        self.assertTrue(case.with_arranged_key)
        self.assertEqual(case.marker, 'SocketBlockedError')
        self.assertIn('not-a-real', qualify_faults.ARRANGED_KEY)

    def test_outcome_rule(self):
        good = qualify_faults.Case('g', 'state', None, ())
        bad = qualify_faults.Case('b', 'state', 'MARKER', ())
        cases = [(good, {'exit_code': 0, 'status': 'passed', 'output': ''}, None),
                 (good, {'exit_code': 1, 'status': 'failed', 'output': ''}, 'a good fixture failed'),
                 (good, {'exit_code': 0, 'status': 'passed', 'output': '1 skipped in 0.1s'}, 'skipped its test'),
                 (bad, {'exit_code': 1, 'status': 'failed', 'output': 'x MARKER'}, None),
                 (bad, {'exit_code': 0, 'status': 'passed', 'output': 'MARKER'}, 'a bad fixture passed'),
                 (bad, {'exit_code': 1, 'status': 'failed', 'output': 'crash'}, 'without the expected marker'),
                 (bad, {'exit_code': None, 'status': 'error', 'output': 'MARKER'}, 'did not run')]
        for case, record, expected in cases:
            with self.subTest(case=case.id, record=record):
                problem = qualify_faults.outcome(case, record)
                if expected is None:
                    self.assertIsNone(problem)
                else:
                    self.assertIn(expected, problem)


class StateChecker(unittest.TestCase):
    """The state fixtures need only the standard library, so the harness profile runs them too."""

    def run_fixture(self, name: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(STATE / 'check.py'), str(STATE / name)],
                              capture_output=True, text=True, timeout=10)

    def test_good_fixtures_hold(self):
        for name in ('good.json', 'good_cancel.json'):
            with self.subTest(name=name):
                self.assertEqual(self.run_fixture(name).returncode, 0)

    def test_bad_fixtures_fail_for_their_reason(self):
        for name, marker in (('bad_terminal_resume.json', 'INVALID TRANSITION'),
                             ('bad_skipped_verification.json', 'INVALID TRANSITION'),
                             ('bad_reducer.json', 'REDUCER'), ('bad_private_event.json', 'PRIVATE DATA')):
            with self.subTest(name=name):
                result = self.run_fixture(name)
                self.assertEqual(result.returncode, 1)
                self.assertIn(marker, result.stdout)

    def test_every_canonical_state_is_known_to_the_checker(self):
        states = {'queued', 'running', 'waiting_input', 'waiting_approval', 'paused', 'verifying', 'cancelling',
                  'succeeded', 'failed', 'cancelled'}
        source = (STATE / 'check.py').read_text()
        for state in states:
            self.assertIn(f'"{state}"', source)
        self.assertEqual(json.loads((STATE / 'good.json').read_text())['states'][-1], 'succeeded')


if __name__ == '__main__':
    unittest.main()
