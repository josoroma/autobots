"""Behavioral fixtures for local hook scripts; not proof of Claude event delivery."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

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

    def dispatch(self, raw: bytes, script: Path | None = None) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(script or ROOT / '.claude/hooks/dispatch.py')], input=raw,
                              capture_output=True, timeout=15)

    def fake_ruff(self, root: Path, body: str) -> Path:
        ruff = root / 'services/agent/.venv/bin/ruff'
        ruff.parent.mkdir(parents=True, exist_ok=True)
        ruff.write_text('#!/bin/sh\n' + body + '\n')
        ruff.chmod(0o755)
        return ruff

    def post_edit(self, root: Path, file_path: object) -> str:
        response = hook.handle(root, {'hook_event_name': 'PostToolUse', 'tool_name': 'Edit',
                                      'tool_input': {'file_path': file_path}})
        return response['hookSpecificOutput']['additionalContext']

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

    def test_missing_interpreter_is_a_configuration_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.claude').mkdir()
            config = json.loads((ROOT / '.claude/autobots.json').read_text())
            config['python_executable'] = '/nonexistent/python3.12'
            (root / '.claude/autobots.json').write_text(json.dumps(config))
            (root / '.claude/settings.json').write_text((ROOT / '.claude/settings.json').read_text())
            self.assertTrue(any('qualified Python' in error for error in config_errors(root)))

    def test_symlink_loop_and_unusable_paths_are_denied(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'loop').symlink_to(root / 'loop')
            for raw in ('loop/file', 'bad\0name', 'x' * 5000, '', None, 7):
                with self.subTest(raw=str(raw)[:20]):
                    self.assertIsNotNone(hook.guard(root, 'Read', {'file_path': raw}))
                    self.assertNotIn('Affected check domains', self.post_edit(root, raw))

    def test_secret_names_are_checked_before_and_after_links(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'plain.txt').write_text('x')
            (root / '.env').symlink_to(root / 'plain.txt')  # The name is secret, the target is not.
            (root / 'real').mkdir()
            (root / 'real/.env.local').write_text('x')
            (root / 'innocent.txt').symlink_to(root / 'real/.env.local')  # The target is secret, the name is not.
            self.assertIsNotNone(hook.guard(root, 'Read', {'file_path': '.env'}))
            self.assertIsNotNone(hook.guard(root, 'Read', {'file_path': 'innocent.txt'}))
            self.assertIsNone(hook.guard(root, 'Read', {'file_path': 'plain.txt'}))

    def test_metacharacter_names_stay_data(self):
        name = 'a b;touch pwned$(touch pwned2)`touch pwned3`\'"é.py'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            agent = root / 'services/agent'
            agent.mkdir(parents=True)
            (agent / name).write_text('x = 1\n')
            record = root / 'argv'
            self.fake_ruff(root, f'for argument in "$@"; do printf "%s\\n" "$argument" >> "{record}"; done')
            self.assertIsNone(hook.guard(root, 'Edit', {'file_path': f'services/agent/{name}'}))
            self.assertIsNone(hook.guard(root, 'Bash', {'command': name}))
            context = self.post_edit(root, f'services/agent/{name}')
            self.assertIn('Affected check domains: python', context)
            self.assertNotIn(name, context)
            self.assertEqual(record.read_text().splitlines()[-2:], ['--', str(agent / name)])
            for marker in ('pwned', 'pwned2', 'pwned3'):
                for place in (root, agent):
                    self.assertFalse((place / marker).exists())

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
                                            ('docs/note.md', 'harness', 'harness')):
                context = self.post_edit(root, path)
                self.assertIn(f'Affected check domains: {expected}.', context)
                self.assertIn(f'--profile {profile}', context)
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

    def test_pending_app_profile_is_not_a_pass(self):
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/verify.py'), '--profile', 'operations'],
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)['status'], 'not_implemented')


if __name__ == '__main__':
    unittest.main()
