"""What report freshness covers: the input manifest, its fingerprint and report_state (scripts/harness_lib.py).

Split from test_hooks.py and test_final_review.py by the unit under test (refactor plan R-66, THRN-03, THRN-15).
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from harness_support import (
    ROOT,
    HarnessTestCase,
    fingerprint,
    harness_lib,
    input_manifest,
    report_state,
)


class Inputs(HarnessTestCase):
    """A changed input makes a report stale, and only inputs count."""

    def test_untracked_change_invalidates_result(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'scripts').mkdir()
            (root / 'scripts/code.py').write_text('x = 1\n')
            out = root / '.checks/harness'
            out.mkdir(parents=True)
            (out / 'latest.json').write_text(json.dumps(self.valid_report(root)))
            self.assertTrue(report_state(root)[0])
            (root / 'scripts/untracked.py').write_text('x = 2\n')
            self.assertFalse(report_state(root)[0])

    def test_incomplete_template_empty_and_failed_reports_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            out = root / '.checks/harness'
            out.mkdir(parents=True)
            records = [{'profile': 'harness', 'status': 'passed',
                        'input_fingerprint': fingerprint(root)}]
            for field, value in [('template', True), ('checks', []),
                                 ('inputs_unchanged_during_check', False)]:
                data = self.valid_report(root)
                data[field] = value
                records.append(data)
            data = self.valid_report(root)
            data['checks'][-1]['tests_executed'] = 0
            records.append(data)
            data = self.valid_report(root)
            data['checks'][-1]['status'] = 'skipped'
            records.append(data)
            for data in records:
                with self.subTest(data=data):
                    (out / 'latest.json').write_text(json.dumps(data))
                    self.assertFalse(report_state(root)[0])

    def test_reports_and_secrets_are_not_fingerprinted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            start = fingerprint(root)
            (root / '.env').write_text('PRIVATE=do-not-copy\n')
            (root / '.checks').mkdir()
            (root / '.checks/log').write_text('result')
            self.assertEqual(start, fingerprint(root))

    def test_mapped_document_outside_default_paths_is_fingerprinted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.claude').mkdir()
            (root / 'planning').mkdir()
            doc = root / 'planning/backlog.md'
            doc.write_text('# First\n')
            (root / '.claude/autobots.json').write_text(json.dumps({'documents': {'specs': 'planning/backlog.md'}}))
            before = fingerprint(root)
            doc.write_text('# Changed\n')
            self.assertNotEqual(before, fingerprint(root))

    def test_ohmyorch_runtime_state_is_not_a_verification_input(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = root / '.claude/ohmyorch'
            (state / 'runtime/session').mkdir(parents=True)
            (state / 'backups').mkdir()
            (state / 'project.json').write_text('{}')
            before = fingerprint(root)
            (state / 'runtime/delivery.owner.json').write_text('{"updatedAt": 1}')
            (state / 'runtime/session/loop.state').write_text('1')
            (state / 'backups/op.bak').write_text('x')
            (state / 'approvals.local.json').write_text('{}')
            self.assertEqual(before, fingerprint(root))
            # Reviewed configuration still counts.
            (state / 'project.json').write_text('{"changed": true}')
            self.assertNotEqual(before, fingerprint(root))

    def test_a_worktree_is_not_an_input_of_the_checkout_containing_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_files(root, ('.claude/rules/real.md',))
            before = fingerprint(root)
            # A copy of real inputs, and the tool state a bootstrap leaves there.
            worktree = '.claude/worktrees/other/'
            self.write_files(root, tuple(worktree + name for name in
                                         ('scripts/harness_lib.py', '.claude/rules/real.md', 'SPECS.md', '.uv/cache/x')))
            self.assertEqual(before, fingerprint(root))
            (root / worktree / 'SPECS.md').write_text('changed')
            self.assertEqual(before, fingerprint(root))
            self.assertEqual(sorted(input_manifest(root)), ['.claude/rules/real.md'])
            # A real `.claude` input still counts.
            (root / '.claude/rules/real.md').write_text('changed')
            self.assertNotEqual(before, fingerprint(root))

    def test_a_worktree_is_excluded_by_its_place_and_not_by_its_name(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            near_misses = ('.claude/worktrees-notes/x.md', '.claude/rules/worktrees/x.md', 'scripts/worktrees/x.py')
            self.write_files(root, near_misses)
            self.assertEqual(sorted(input_manifest(root)), sorted(near_misses))

    def test_worktree_contents_are_never_walked_and_a_link_there_is_not_an_input(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            self.write_files(root, ('.claude/rules/real.md', '.claude/worktrees/other/scripts/x.py'))
            walked, walk = [], os.walk

            def spy(top, *args, **kwargs):
                for entry in walk(top, *args, **kwargs):
                    walked.append(Path(entry[0]))
                    yield entry

            with mock.patch('os.walk', spy):
                input_manifest(root)
            self.assertIn(root / '.claude/rules', walked)
            self.assertFalse([path for path in walked if path.is_relative_to(root / '.claude/worktrees')])
            shutil.rmtree(root / '.claude/worktrees')
            (root / '.claude/worktrees').symlink_to(root / '.claude/rules', target_is_directory=True)
            self.assertEqual(sorted(input_manifest(root)), ['.claude/rules/real.md'])

    def test_tool_written_directories_are_not_inputs_at_any_depth(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_files(root, ('services/agent/code.py',))
            before = fingerprint(root)
            self.write_files(root, ('services/agent/.uv/cache/x', 'apps/web/.cache/pnpm/x',
                                    'packages/client/.pnpm-store/x', '.claude/.corepack/x'))
            self.assertEqual(before, fingerprint(root))
            # Only the exact names: a similar name is still source.
            self.write_files(root, ('services/agent/cache/x.py',))
            self.assertNotEqual(before, fingerprint(root))



class Fingerprint(HarnessTestCase):
    """Found by US-11.12's review of the harness (docs/engineering/evidence/US-11.12/). Moved from test_final_review.py (THRN-15)."""

    def test_what_checks_read_is_in_the_manifest(self) -> None:
        manifest = harness_lib.input_manifest(ROOT)
        self.assertIn('docs/design/luma.css', manifest)
        self.assertIn('tests/qualification/tasks.json', manifest)


if __name__ == '__main__':
    unittest.main()
