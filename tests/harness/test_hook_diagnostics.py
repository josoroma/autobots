"""PostToolUse diagnostics: the check domains an edit names, and the prepared ruff's outcomes.

Behavioral fixtures for the local hook script, not proof of Claude event delivery (PRD-Development-Harness
DH-05). Split from test_hooks.py by the unit under test (refactor plan R-66, THRN-03).
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from harness_support import HarnessTestCase, hook


class HookDiagnostics(HarnessTestCase):
    """An edit's domains, and a diagnostic that never shows file content."""

    def test_diagnostic_handles_missing_slow_and_failing_tools(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            agent = root / 'services/agent'
            agent.mkdir(parents=True)
            (agent / 'code.py').write_text('PRIVATE_VALUE = 1\n')
            self.assertIn('unavailable', self.post_edit(root, 'services/agent/code.py'))
            ruff = self.fake_ruff(root, 'echo PRIVATE_VALUE; exit 1')
            context = self.post_edit(root, 'services/agent/code.py')
            self.assertIn('ruff reported findings, exit 1', context)
            self.assertNotIn('PRIVATE_VALUE', context)
            self.fake_ruff(root, 'exec sleep 30')
            with mock.patch.object(hook, 'DIAGNOSTIC_TIMEOUT', 0.3):
                self.assertIn('timed out', self.post_edit(root, 'services/agent/code.py'))
            ruff.write_text('#!/nonexistent/interpreter\n')
            self.assertIn('could not start', self.post_edit(root, 'services/agent/code.py'))
            ruff.write_text('#!/bin/sh\nexit 0\n')
            self.assertTrue(self.post_edit(root, 'services/agent/code.py').startswith('Affected check domains'))

    def test_edit_names_its_check_domains(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            for path, expected, profile in (('apps/web/app/page.tsx', 'web', 'fast'),
                                            ('pnpm-lock.yaml', 'python, web', 'fast'),
                                            ('docs/note.md', 'harness', 'harness'),
                                            ('tests/db/sql/h1/seeds/fixtures.sql', 'db', 'db'),
                                            # A db check is repository Python too, so it needs both profiles.
                                            ('tests/db/checks/memory_check.py', 'db, repo_python', 'db')):
                context = self.post_edit(root, path)
                self.assertIn(f'Affected check domains: {expected}.', context)
                self.assertIn(f'--profile {profile}', context)
            both = self.post_edit(root, 'tests/db/checks/memory_check.py')
            self.assertIn('--profile fast, then python3.12 scripts/verify.py --profile db', both)
            self.assertNotIn('Affected check domains', self.post_edit(root, '/outside/file.py'))

    def test_syntax_error_diagnostic_never_runs_the_tool(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            agent = root / 'services/agent'
            agent.mkdir(parents=True)
            (agent / 'bad.py').write_text('def (:\n')
            self.fake_ruff(root, f'touch "{root}/ran"')
            self.assertIn('syntax/read error', self.post_edit(root, 'services/agent/bad.py'))
            self.assertFalse((root / 'ran').exists())



if __name__ == '__main__':
    unittest.main()
