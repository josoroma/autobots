"""The forward arrangement (tests/harness/forward_arrangement.py): a reproducible fixture copy under .checks.

Split from test_assistant_assets.py by the unit under test (refactor plan R-66, THRN-04).
"""
from __future__ import annotations

import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from harness_support import (
    ROOT,
    HarnessTestCase,
    load_script,
    run_cli,
    sha256,
    specs_cli,
    story_body,
)

arrangement = load_script('autobots_forward_arrangement', ROOT / 'tests/harness/forward_arrangement.py')
RETAINED_FIXTURE = ROOT / 'docs/engineering/evidence/HARNESS-ADAPT-001/forward-fixture'


class ArrangementTests(HarnessTestCase):
    def setUp(self) -> None:
        checks = ROOT / '.checks'
        checks.mkdir(exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=checks, prefix='arrangement-test-')
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)

    def test_arranged_copy(self):
        copy = arrangement.arrange(self.base / 'nested/run')
        arguments = ('--project-root', str(copy), '--path', 'SPECS.md')
        self.assertEqual(specs_cli('validate', *arguments).returncode, 0)
        before = sha256(copy / 'SPECS.md')
        self.assertEqual(specs_cli('render', *arguments).returncode, 0)
        self.assertEqual(sha256(copy / 'SPECS.md'), before)
        text = (copy / 'SPECS.md').read_text()
        self.assertEqual(re.findall(r'(?m)^\| \[(SP-\d+)\]\([^)]+\) \| (US-[\d.]+) \|$', text),
                         [('SP-901', 'US-1.1'), ('SP-902', 'US-1.3')])
        self.assertNotIn('No `AGENTS.md` file exists', text)
        self.assertIn('CONTRACT.md#sp-901-missing-key-draft-preservation', story_body(text, 'US-1.1'))
        self.assertIn('CONTRACT.md#sp-902-retry-visibility', story_body(text, 'US-1.3'))
        self.assertIn('Status: READY', story_body(text, 'US-1.1'))
        self.assertIn('Status: IN PROGRESS\nChange: `openspec/changes/fixture-us-1-2/`\n', story_body(text, 'US-1.2'))
        self.assertIn('Status: NEEDS CLARIFICATION', story_body(text, 'US-1.3'))
        self.assertIn('Dependencies:\n- US-1.2\n', story_body(text, 'US-1.3'))
        self.assertIn('Status: BLOCKED', story_body(text, 'US-1.4'))
        self.assertIn('US_1_2 -.-> US_1_3', text)
        self.assertIn('When the composer draft changes', (copy / 'PRD.md').read_text())
        self.assertEqual(len(re.findall(r'(?m)^## SP-', (copy / 'CONTRACT.md').read_text())), 2)
        self.assertEqual(len((copy / 'AGENTS.md').read_text().splitlines()), 1)
        self.assertTrue((copy / '.claude/autobots.json').is_file())

    def test_arrangement_is_reproducible(self):
        first = arrangement.arrange(self.base / 'first')
        second = arrangement.arrange(self.base / 'second')
        names = sorted(path.relative_to(first) for path in first.rglob('*') if path.is_file())
        self.assertEqual(names, sorted(path.relative_to(second) for path in second.rglob('*') if path.is_file()))
        for name in names:
            self.assertEqual(sha256(first / name), sha256(second / name), name)

    def test_refuses_an_existing_destination(self):
        destination = self.base / 'exists'
        destination.mkdir()
        (destination / 'kept').write_text('kept')
        with self.assertRaisesRegex(ValueError, 'already exists'):
            arrangement.arrange(destination)
        self.assertEqual((destination / 'kept').read_text(), 'kept')

    def test_refuses_a_destination_outside_checks(self):
        with tempfile.TemporaryDirectory() as outside:
            with self.assertRaisesRegex(ValueError, 'must lie under'):
                arrangement.arrange(Path(outside) / 'run')
            self.assertFalse((Path(outside) / 'run').exists())
        with self.assertRaisesRegex(ValueError, 'must lie under'):
            arrangement.arrange(ROOT / '.checks')

    def test_command_line_refusal_exits_nonzero(self):
        destination = self.base / 'exists'
        destination.mkdir()
        result = run_cli([sys.executable, str(ROOT / 'tests/harness/forward_arrangement.py'), str(destination)], text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('already exists', result.stderr)

    def test_missing_anchor_fails_and_leaves_no_destination(self):
        fixture = self.base / 'fixture'
        shutil.copytree(RETAINED_FIXTURE, fixture)
        specs_file = fixture / 'SPECS.md'
        specs_file.write_text(specs_file.read_text().replace('### US-1.2: Store application records locally\n\nStatus: READY',
                                                             '### US-1.2: Store application records locally\n\nStatus: BLOCKED'))
        destination = self.base / 'run'
        with self.assertRaisesRegex(ValueError, 'anchor'):
            arrangement.arrange(destination, fixture=fixture)
        self.assertFalse(destination.exists())
        self.assertEqual([path.name for path in self.base.iterdir() if path.name.startswith('.arranging-')], [])


if __name__ == '__main__':
    unittest.main()
