"""The hook dispatcher as a process: malformed, oversized and unsupported input, its deadline and a missing
library.

Behavioral fixtures for the local hook script, not proof of Claude event delivery (PRD-Development-Harness
DH-05). Split from test_hooks.py by the unit under test (refactor plan R-66, THRN-03).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from harness_support import ROOT, HarnessTestCase, hook


class HookProcess(HarnessTestCase):
    """The documented response, or exit 2 with no echo and no traceback."""

    def test_malformed_payload_fails_closed(self):
        for raw in (b'{bad', b'[]'):
            result = subprocess.run([sys.executable, str(ROOT / '.claude/hooks/dispatch.py')],
                                    input=raw, capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, b'')
            self.assertNotIn(raw[:20], result.stderr)

    def post_edit_payload(self, size: int) -> bytes:
        """A valid PostToolUse object of exactly `size` bytes."""
        payload = {'hook_event_name': 'PostToolUse', 'tool_name': 'Edit',
                   'tool_input': {'file_path': 'SPECS.md'}, 'tool_response': {'originalFile': ''}}
        padding = size - len(json.dumps(payload).encode())
        payload['tool_response']['originalFile'] = 'x' * padding
        raw = json.dumps(payload).encode()
        self.assertEqual(len(raw), size)
        return raw

    def test_input_cap_applies_to_valid_json_at_its_boundary(self):
        limit = 1048576  # A large SPECS.md or PRD edit must fit; see dispatch.py.
        for size, expected in ((300000, 0), (limit, 0), (limit + 1, 2)):
            with self.subTest(size=size):
                result = subprocess.run([sys.executable, str(ROOT / '.claude/hooks/dispatch.py')],
                                        input=self.post_edit_payload(size), capture_output=True, timeout=5)
                self.assertEqual(result.returncode, expected, result.stderr)

    def test_unsupported_event_and_tool_block_without_echo(self):
        for payload in ({'hook_event_name': 'Unknown-SECRET'},
                        {'hook_event_name': 'PreToolUse', 'tool_name': 'SECRET', 'tool_input': {}},
                        {'hook_event_name': 'PreToolUse', 'tool_name': 'Read', 'tool_input': 'SECRET'}):
            with self.subTest(payload=payload):
                result = self.dispatch(json.dumps(payload).encode())
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, b'')
                self.assertNotIn(b'SECRET', result.stderr)
                self.assertNotIn(b'Traceback', result.stderr)

    def test_deadline_blocks_a_stalled_event(self):
        env = {**os.environ, 'AUTOBOTS_HOOK_DEADLINE_SECONDS': '0.3'}
        process = subprocess.Popen([sys.executable, str(ROOT / '.claude/hooks/dispatch.py')], env=env,
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            self.assertEqual(process.wait(timeout=10), 2)  # stdin stays open, so only the deadline ends it.
            self.assertEqual(process.stdout.read(), b'')
            self.assertNotIn(b'Traceback', process.stderr.read())
        finally:
            process.kill()
            process.communicate()

    def test_deadline_override_can_only_shorten(self):
        for value, expected in (('0.5', 0.5), ('60', hook.DEADLINE_SECONDS), ('-1', hook.DEADLINE_SECONDS),
                                ('nope', hook.DEADLINE_SECONDS)):
            with self.subTest(value=value), mock.patch.dict(os.environ, {hook.DEADLINE_OVERRIDE: value}):
                self.assertEqual(hook.deadline_seconds(), expected)

    def test_missing_library_blocks_without_a_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / '.claude/hooks/dispatch.py'
            script.parent.mkdir(parents=True)
            shutil.copy2(ROOT / '.claude/hooks/dispatch.py', script)
            result = self.dispatch(b'{"hook_event_name": "SessionStart"}', script)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, b'')
            self.assertNotIn(b'Traceback', result.stderr)



if __name__ == '__main__':
    unittest.main()
