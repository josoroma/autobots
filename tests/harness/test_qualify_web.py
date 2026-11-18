"""qualify_web.run_problems: what makes a browser run fail its qualification (scripts/qualify_web.py).

Split from test_final_review.py by the script under test (refactor plan R-66, THRN-15).
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import harness_support  # noqa: F401 - imported first, so scripts/ is on the path for the import below
import qualify_web
from harness_support import HarnessTestCase


def report(path: Path, specs: list[dict], errors: list[str] | None = None) -> Path:
    path.write_text(json.dumps({'suites': [{'file': 'x', 'specs': specs}], 'errors': errors or [], 'stats': {}}))
    return path


class BrowserRuns(HarnessTestCase):
    """Found by US-11.12's review of the harness (docs/engineering/evidence/US-11.12/)."""

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'report.json'
        self.one = [{'title': 't', 'tests': [{'results': [{'status': 'passed'}]}]}]

    def test_a_clean_run_has_no_problem(self) -> None:
        self.assertEqual(qualify_web.run_problems(report(self.path, self.one), 0), [])

    def test_a_non_zero_exit_counts_though_every_case_passed(self) -> None:
        self.assertIn('exit 1', qualify_web.run_problems(report(self.path, self.one), 1))

    def test_a_run_of_no_tests_isnt_a_pass(self) -> None:
        self.assertIn('no tests ran', qualify_web.run_problems(report(self.path, []), 0))

    def test_an_error_outside_any_test_counts(self) -> None:
        self.assertIn('errors outside any test', qualify_web.run_problems(report(self.path, self.one, ['load error']), 0))

    def test_no_report_counts(self) -> None:
        self.assertIn('no report', qualify_web.run_problems(self.path, 0))


if __name__ == '__main__':
    unittest.main()
