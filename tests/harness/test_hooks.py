"""Behavioral fixtures for local hook scripts; not proof of Claude event delivery."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from harness_lib import config_errors, fingerprint, input_manifest, report_state

spec = importlib.util.spec_from_file_location('autobots_hook', ROOT / '.claude/hooks/dispatch.py')
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


class HookTests(unittest.TestCase):
    def valid_report(self, root):
        return {'schema_version': 'autobots.harness-result/v1', 'template': False,
                'profile': 'harness', 'status': 'passed', 'inputs_unchanged_during_check': True,
                'input_fingerprint': fingerprint(root), 'input_manifest': input_manifest(root),
                'checks': [{'id': 'project_configuration', 'status': 'passed'},
                           {'id': 'backlog_validation', 'status': 'passed', 'exit_code': 0},
                           {'id': 'harness_behavior_tests', 'status': 'passed',
                            'exit_code': 0, 'tests_executed': 1}]}

    def test_secret_files_rejected_without_echo(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('.env', '.env.local', 'provider-master.key'):
                response = hook.handle(root, {'hook_event_name': 'PreToolUse',
                                             'tool_name': 'Read', 'tool_input': {'file_path': name}})
                self.assertEqual(response['hookSpecificOutput']['permissionDecision'], 'deny')
            self.assertEqual(hook.guard(root, 'Read', {'file_path': '.env.example'}), None)

    def test_symlink_edit_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root = Path(directory)
            (root / 'escape').symlink_to(outside, target_is_directory=True)
            self.assertIsNotNone(hook.guard(root, 'Edit', {'file_path': 'escape/file.txt'}))

    def test_guard_does_not_execute_command_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            marker = root / 'unexpected'
            hook.guard(root, 'Bash', {'command': f'touch "{marker}"'})
            self.assertFalse(marker.exists())
            self.assertIsNotNone(hook.guard(root, 'Bash', {'command': 'supabase db reset'}))
            self.assertIsNotNone(hook.guard(root, 'Bash', {'command': 'docker compose down -v'}))
            self.assertIsNone(hook.guard(root, 'Bash', {'command': 'python3 scripts/specs.py validate'}))

    def test_stop_blocks_once_and_never_claims_live_proof(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            response = hook.handle(root, {'hook_event_name': 'Stop', 'stop_hook_active': False})
            self.assertEqual(response['decision'], 'block')
            retry = hook.handle(root, {'hook_event_name': 'Stop', 'stop_hook_active': True})
            self.assertNotIn('decision', retry)

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

    def test_empty_hook_groups_are_not_an_enabled_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.claude').mkdir()
            config = json.loads((ROOT / '.claude/autobots.json').read_text())
            config['documents'] = {key: 'source.md' for key in config['documents']}
            (root / 'source.md').write_text('# Source\n')
            (root / '.claude/autobots.json').write_text(json.dumps(config))
            settings = json.loads((ROOT / '.claude/settings.json').read_text())
            settings['hooks'] = {key: [] for key in settings['hooks']}
            (root / '.claude/settings.json').write_text(json.dumps(settings))
            errors = config_errors(root)
            self.assertEqual(sum('nonempty hook group' in error for error in errors), 5)

    def test_disabled_and_async_hook_configuration_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.claude').mkdir()
            config = json.loads((ROOT / '.claude/autobots.json').read_text())
            config['documents'] = {key: 'source.md' for key in config['documents']}
            (root / 'source.md').write_text('# Source\n')
            (root / '.claude/autobots.json').write_text(json.dumps(config))
            settings = json.loads((ROOT / '.claude/settings.json').read_text())
            settings['disableAllHooks'] = True
            (root / '.claude/settings.json').write_text(json.dumps(settings))
            self.assertTrue(any('only the reviewed hooks' in error for error in config_errors(root)))
            settings.pop('disableAllHooks')
            settings['hooks']['PreToolUse'][0]['hooks'][0]['async'] = True
            (root / '.claude/settings.json').write_text(json.dumps(settings))
            self.assertTrue(any('asynchronous enforcement' in error for error in config_errors(root)))

    def test_malformed_and_oversized_payload_fail_closed(self):
        for raw in (b'{bad', b'[]', b'x' * 65537):
            result = subprocess.run([sys.executable, str(ROOT / '.claude/hooks/dispatch.py')],
                                    input=raw, capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, b'')
            self.assertNotIn(raw[:20], result.stderr)

    def test_pending_app_profile_is_not_a_pass(self):
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/verify.py'), '--profile', 'db'],
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)['status'], 'not_implemented')


if __name__ == '__main__':
    unittest.main()
