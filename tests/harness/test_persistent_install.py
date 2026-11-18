"""persistent_install's refusals before a paid goal (scripts/persistent_install.py).

Split from test_final_review.py by the script under test (refactor plan R-66, THRN-15).
"""
from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import harness_support  # noqa: F401 - imported first, so scripts/ is on the path for the import below
import persistent_install
from harness_support import ROOT, HarnessTestCase


class PaidWorkerGuard(HarnessTestCase):
    """Found by US-11.12's review of the harness (docs/engineering/evidence/US-11.12/)."""

    def test_other_queued_work_refuses_a_paid_goal(self) -> None:
        persistent_install.refuse_other_work('0')
        with self.assertRaisesRegex(persistent_install.Refused, '3 other queued'):
            persistent_install.refuse_other_work('3')

    def test_an_unreadable_answer_refuses_too_and_says_so(self) -> None:
        with self.assertRaisesRegex(persistent_install.Refused, 'Could not read'):
            persistent_install.refuse_other_work('')

    def test_every_failed_check_stays_listed(self) -> None:
        report: dict = {}
        persistent_install.note_failed(report, 'first')
        persistent_install.note_failed(report, 'second')
        self.assertEqual(report['after_run_check_failed'], 'first; second')

    def test_a_paid_goal_really_asks(self) -> None:
        """`goal` itself, on a fake install whose database reports 3 queued jobs: it refuses before the key,
        the owner's sign-in, an admission or a worker, and releases its reservation (SCRP-03)."""
        settled: list[tuple[int | None, str]] = []

        class Ledger:
            def settle(self, entry: dict, reported: int | None, state: str) -> None:
                settled.append((reported, state))
                entry['state'] = state

            def committed(self) -> int:
                return 0

        class Install:
            def runtime(self, statements: str) -> subprocess.CompletedProcess[str]:
                queued = 'app_private.run_jobs' in statements
                return subprocess.CompletedProcess([], 0 if queued else 1, '3\n' if queued else '', '')

        record = persistent_install.Record('autobots-install', 'install-id', 1, 2, 3, 4, Path(tempfile.gettempdir()))
        entry = {'label': 'install-goal', 'worst_case': 1000, 'reported': None, 'state': 'reserved', 'at': 'now'}
        nothing_sent = AssertionError('nothing may be sent')
        with mock.patch.object(persistent_install, 'reserve_goal', return_value=(Ledger(), entry)), \
             mock.patch.object(persistent_install, 'install_stack', return_value=Install()), \
             mock.patch.object(persistent_install, 'require_install'), \
             mock.patch.object(persistent_install, 'read_values', return_value={}), \
             mock.patch('subprocess.run', side_effect=nothing_sent) as helper, \
             mock.patch('subprocess.Popen', side_effect=nothing_sent) as worker, \
             mock.patch('urllib.request.urlopen', side_effect=nothing_sent) as request:
            with self.assertRaisesRegex(persistent_install.Refused, '3 other queued'):
                persistent_install.goal(ROOT, record, 'autobots-install', Path('key'), 1000, Path('ledger.json'), 'a goal', [])
        self.assertEqual((helper.called, worker.called, request.called), (False, False, False))
        self.assertEqual(settled, [(0, 'not_started')])


if __name__ == '__main__':
    unittest.main()
