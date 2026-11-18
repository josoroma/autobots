"""qualify_worker_inference.request_shape_problems on requests that break it
(scripts/qualify_worker_inference.py).

Split from test_final_review.py by the script under test (refactor plan R-66, THRN-15).
"""
from __future__ import annotations

import unittest

import harness_support  # noqa: F401 - imported first, so scripts/ is on the path for the import below
import qualify_worker_inference
from harness_support import HarnessTestCase


class RequestShape(HarnessTestCase):
    """The check in `qualify_worker_inference.py`, on requests that break it. Found by US-11.12's review of the harness (docs/engineering/evidence/US-11.12/)."""

    def test_a_plain_request_passes(self) -> None:
        self.assertEqual(qualify_worker_inference.request_shape_problems(['max_tokens', 'messages', 'model', 'provider', 'tools'], None), [])

    def test_an_unadvertised_flag_fails(self) -> None:
        for flag in ('temperature', 'top_p', 'parallel_tool_calls', 'seed'):
            with self.subTest(flag=flag):
                self.assertTrue(qualify_worker_inference.request_shape_problems(['model', flag], None), flag)

    def test_reasoning_off_or_malformed_fails(self) -> None:
        for reasoning in ({'effort': 'none'}, 'high', {'unknown': 1}):
            with self.subTest(reasoning=reasoning):
                self.assertTrue(qualify_worker_inference.request_shape_problems(['model', 'reasoning'], reasoning), reasoning)
        self.assertEqual(qualify_worker_inference.request_shape_problems(['model', 'reasoning'], {'effort': 'high'}), [])


if __name__ == '__main__':
    unittest.main()
