"""toolchain.snapshot, which the non-mutation guard compares before and after each step (scripts/toolchain.py).

Split from test_final_review.py by the script under test (refactor plan R-66, THRN-15).
"""
from __future__ import annotations

import unittest
from unittest import mock

import harness_support  # noqa: F401 - imported first, so scripts/ is on the path for the import below
import toolchain
from harness_support import ROOT, HarnessTestCase


class NonMutationGuard(HarnessTestCase):
    """Found by US-11.12's review of the harness (docs/engineering/evidence/US-11.12/)."""

    def test_the_hooks_delivery_record_isnt_a_change_by_the_run(self) -> None:
        with mock.patch.object(toolchain, 'git_paths', side_effect=[[toolchain.DELIVERY_RECORD, 'scripts/verify.py'], []]), \
             mock.patch.object(toolchain, 'entry_names', return_value=[]), mock.patch.object(toolchain, 'file_hash', return_value='x'):
            found = toolchain.snapshot(ROOT)
        self.assertEqual(list(found['changed']), ['scripts/verify.py'])


if __name__ == '__main__':
    unittest.main()
