"""Behavioral fixtures for local hook scripts; not proof of Claude event delivery."""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from harness_lib import config_errors, fingerprint, input_manifest, reduced_env, report_state  # noqa: E402 - imported after the scripts path is added

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
            for name in ('.env', '.env.local', 'provider-master.key', '.ENV', '.Env.Local', 'stack.env', 'app.env', 'owner.env',
                         'master.key', 'Master.Key', 'backup.key'):
                response = hook.handle(root, {'hook_event_name': 'PreToolUse',
                                             'tool_name': 'Read', 'tool_input': {'file_path': name}})
                self.assertEqual(response['hookSpecificOutput']['permissionDecision'], 'deny')
            self.assertEqual(hook.guard(root, 'Read', {'file_path': '.env.example'}), None)
            # The real install's whole folder, by any tool this guard sees.
            self.assertIsNotNone(hook.guard(root, 'Read', {'file_path': str(Path.home() / '.local/share/autobots-install/record.json')}))
            for command in ('cat ~/.local/share/autobots-install/backup-key/x', 'cat backup.key', 'cat master.key',
                            'sed -n p backup.key', 'awk 1 master.key', 'xargs cat master.key',
                            'head other/autobots-install/app.env'):
                self.assertIsNotNone(hook.guard(root, 'Bash', {'command': command}), command)
            self.assertIsNone(hook.guard(root, 'Bash', {'command': 'docker ps --filter name=autobots-install'}))
            # Naming a key isn't reading it.
            self.assertIsNone(hook.guard(root, 'Bash', {'command': 'grep -n master.key scripts/local_backup.py'}))
            self.assertIsNone(hook.guard(root, 'Bash', {'command': 'git log -S backup.key'}))

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
            for command in ('cat .env.local', 'cat .env;', 'CAT .ENV', 'cat ".env"', 'cat "$HOME/.env"', 'docker volume rm autobots_db-data',
                            'docker-compose down -v', 'docker compose down --volumes'):
                self.assertIsNotNone(hook.guard(root, 'Bash', {'command': command}), command)
            self.assertIsNone(hook.guard(root, 'Bash', {'command': 'cat .env.example'}))

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

    def write_files(self, root: Path, names: tuple[str, ...]) -> None:
        for name in names:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(name)

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
                                            ('docs/note.md', 'harness', 'harness'),
                                            ('tests/db/seeds/fixtures.sql', 'db', 'db'),
                                            # A db check is repository Python too, so it needs both profiles.
                                            ('tests/db/memory_check.py', 'db, repo_python', 'db')):
                context = self.post_edit(root, path)
                self.assertIn(f'Affected check domains: {expected}.', context)
                self.assertIn(f'--profile {profile}', context)
            both = self.post_edit(root, 'tests/db/memory_check.py')
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

    def git(self, directory: Path, *arguments: str) -> None:
        subprocess.run(['git', '-C', str(directory), '-c', 'user.name=fixture', '-c', 'user.email=fixture@example.invalid',
                        *arguments], env=reduced_env(), stdin=subprocess.DEVNULL, capture_output=True, timeout=15, check=True)

    def checkout_with_worktrees(self, parent: Path) -> Path:
        """A real repository with worktrees `one` and `two`, the way a session's worktree is laid out."""
        home = parent / 'home'
        home.mkdir()
        self.git(home, 'init', '--quiet')
        self.git(home, 'commit', '--quiet', '--allow-empty', '-m', 'fixture')
        for name in ('one', 'two'):
            self.git(home, 'worktree', 'add', '--quiet', '-b', name, f'.claude/worktrees/{name}')
        return home

    def edit_denied(self, root: Path, path: Path) -> bool:
        return hook.guard(root, 'Edit', {'file_path': str(path)}) is not None

    def test_a_registered_worktree_is_the_root_of_a_session_inside_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary).resolve()
            home = self.checkout_with_worktrees(parent)
            one = home / '.claude/worktrees/one'
            (one / 'services/agent').mkdir(parents=True)
            for cwd in (one, one / 'services/agent', one / 'not/created/yet', str(one) + '/services/../services'):
                with self.subTest(cwd=str(cwd)):
                    self.assertEqual(hook.session_root(home, str(cwd)), one)
            self.assertFalse(self.edit_denied(one, one / 'SPECS.md'))
            self.assertTrue(self.edit_denied(one, home / 'SPECS.md'))
            self.assertTrue(self.edit_denied(one, home / '.claude/worktrees/two/SPECS.md'))

    def test_the_innermost_registered_worktree_holds_the_session(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = self.checkout_with_worktrees(Path(temporary).resolve())
            one = home / '.claude/worktrees/one'
            self.git(one, 'worktree', 'add', '--quiet', '-b', 'nested', '.claude/worktrees/nested')
            nested = one / '.claude/worktrees/nested'
            self.assertEqual(hook.session_root(home, str(nested)), nested)
            self.assertEqual(hook.session_root(home, str(one)), one)

    def test_a_forged_cwd_never_chooses_a_root_outside_the_home_checkout(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary).resolve()
            home = self.checkout_with_worktrees(parent)
            worktrees = home / '.claude/worktrees'
            outside = parent / 'outside'
            outside.mkdir()
            # A real worktree of this repository, registered somewhere the guard should not move to.
            self.git(home, 'worktree', 'add', '--quiet', '-b', 'elsewhere', str(parent / 'elsewhere'))
            # A look-alike under the right place, claiming a real administrative directory.
            (worktrees / 'fake').mkdir()
            (worktrees / 'fake/.git').write_text((worktrees / 'one/.git').read_text())
            # A registered worktree swapped for a link to a directory holding its `.git` file.
            shutil.copy2(worktrees / 'two/.git', outside / '.git')
            shutil.rmtree(worktrees / 'two')
            (worktrees / 'two').symlink_to(outside, target_is_directory=True)
            # A worktree whose directory is gone, which Git reports as prunable.
            self.git(home, 'worktree', 'add', '--quiet', '-b', 'gone', '.claude/worktrees/gone')
            shutil.rmtree(worktrees / 'gone')
            # The same, but locked, which Git does not report as prunable.
            self.git(home, 'worktree', 'add', '--quiet', '-b', 'locked', '.claude/worktrees/locked')
            self.git(home, 'worktree', 'lock', '.claude/worktrees/locked')
            shutil.rmtree(worktrees / 'locked')
            forged = [str(parent), str(outside), '/', str(parent / 'elsewhere'), str(worktrees), str(worktrees / 'fake'),
                      str(worktrees / 'two'), str(worktrees / 'two/sub'), str(worktrees / 'gone'), str(worktrees / 'locked'),
                      str(home / '.CLAUDE/worktrees/one'),
                      str(worktrees / 'one/../../..'), '.', '', None, 7, ['x'], 'bad\0name', 'x' * 5000]
            for cwd in forged:
                with self.subTest(cwd=str(cwd)[:60]):
                    root = hook.session_root(home, cwd)
                    self.assertEqual(root, home)
                    self.assertTrue(self.edit_denied(root, outside / 'file.txt'))
                    self.assertTrue(self.edit_denied(root, parent / 'elsewhere/file.txt'))

    def test_a_registered_path_wider_than_the_worktree_directory_is_never_chosen(self):
        # Git's list comes from files a shell can rewrite, so the list alone cannot widen the root either.
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary).resolve()
            home = parent / 'home'
            cwd = home / '.claude/worktrees/one'
            cwd.mkdir(parents=True)
            for listed in (Path('/'), parent, home.parent, home / '.claude', home / '.claude/worktrees'):
                with self.subTest(listed=str(listed)), mock.patch.object(hook, 'registered_worktrees', return_value=[listed]):
                    self.assertEqual(hook.session_root(home, str(cwd)), home)

    def test_a_cwd_cannot_name_another_repository(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary).resolve()
            home = self.checkout_with_worktrees(parent)
            other = parent / 'other'
            other.mkdir()
            self.git(other, 'init', '--quiet')
            self.git(other, 'commit', '--quiet', '--allow-empty', '-m', 'other')
            # Registered, in the right place, but with another repository.
            self.git(other, 'worktree', 'add', '--quiet', '-b', 'stray', str(home / '.claude/worktrees/stray'))
            self.assertEqual(hook.session_root(home, str(home / '.claude/worktrees/stray')), home)

    def test_git_environment_cannot_redirect_the_registered_list(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary).resolve()
            home = self.checkout_with_worktrees(parent)
            one = home / '.claude/worktrees/one'
            with mock.patch.dict(os.environ, {'GIT_DIR': str(parent / 'absent'), 'GIT_WORK_TREE': str(parent)}):
                self.assertEqual(hook.session_root(home, str(one)), one)

    def test_a_path_with_a_newline_survives_the_registered_list(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = self.checkout_with_worktrees(Path(temporary).resolve())
            self.git(home, 'worktree', 'add', '--quiet', '-b', 'newline', '.claude/worktrees/new\nline')
            worktree = home / '.claude/worktrees/new\nline'
            self.assertEqual(hook.session_root(home, str(worktree)), worktree)

    def dispatch_with_git(self, parent: Path, body: str, payload: dict,
                          deadline: str | None = None) -> tuple[subprocess.CompletedProcess, float]:
        """An event from a worktree, through the real main(), with this `git` first on PATH."""
        home = parent / 'home'
        script = home / '.claude/hooks/dispatch.py'
        script.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / '.claude/hooks/dispatch.py', script)
        (home / 'scripts').mkdir(exist_ok=True)
        shutil.copy2(ROOT / 'scripts/harness_lib.py', home / 'scripts/harness_lib.py')
        fake = parent / 'bin/git'
        fake.parent.mkdir(exist_ok=True)
        fake.write_text('#!/bin/sh\n' + body + '\n')
        fake.chmod(0o755)
        env = {**os.environ, 'PATH': f"{fake.parent}{os.pathsep}{os.environ['PATH']}"}
        if deadline:
            env['AUTOBOTS_HOOK_DEADLINE_SECONDS'] = deadline
        raw = json.dumps({'cwd': str(home / '.claude/worktrees/one'), **payload}).encode()
        start = time.monotonic()
        result = subprocess.run([sys.executable, str(script)], input=raw, env=env, capture_output=True, timeout=15)
        return result, time.monotonic() - start

    EDIT_EVENT = {'hook_event_name': 'PreToolUse', 'tool_name': 'Edit', 'tool_input': {'file_path': '/outside/SPECS.md'}}  # noqa: RUF012 - a constant the tests only read

    def test_when_git_cannot_answer_no_event_loops_or_passes(self):
        for body in ('exit 128', 'echo PRIVATE_VALUE >&2; exit 1'):
            with self.subTest(body=body), tempfile.TemporaryDirectory() as temporary:
                parent = Path(temporary).resolve()
                inside = str(parent / 'home/.claude/worktrees/one/SPECS.md')
                edit = {**self.EDIT_EVENT, 'tool_input': {'file_path': inside}}
                post = {'hook_event_name': 'PostToolUse', 'tool_name': 'Edit', 'tool_input': {'file_path': inside}}
                outputs = []
                for payload in (edit, post, {'hook_event_name': 'Stop', 'stop_hook_active': False},
                                {'hook_event_name': 'Stop', 'stop_hook_active': True}):
                    result, _ = self.dispatch_with_git(parent, body, payload)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertNotIn(b'PRIVATE_VALUE', result.stdout + result.stderr)
                    outputs.append(json.loads(result.stdout))
                denied, diagnostic, stop, repeat = outputs
                # An edit inside what would be the worktree is still refused, because Git never confirmed it.
                self.assertEqual(denied['hookSpecificOutput']['permissionDecision'], 'deny')
                self.assertIn('Git could not say', denied['hookSpecificOutput']['permissionDecisionReason'])
                self.assertIn('Git could not say', diagnostic['hookSpecificOutput']['additionalContext'])
                self.assertNotIn('Affected check domains', diagnostic['hookSpecificOutput']['additionalContext'])
                self.assertEqual(stop['decision'], 'block')
                self.assertIn('Git could not say', stop['reason'])
                self.assertNotIn('decision', repeat)

    def test_events_that_judge_no_checkout_never_ask_git(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary).resolve()
            marker = parent / 'git-ran'
            body = f'touch "{marker}"; exit 1'
            for payload in ({'hook_event_name': 'SessionStart'}, {'hook_event_name': 'SubagentStop'},
                            {'hook_event_name': 'PreToolUse', 'tool_name': 'Bash', 'tool_input': {'command': 'git status'}},
                            {'hook_event_name': 'PreToolUse', 'tool_name': 'Read', 'tool_input': {'file_path': '/outside/x'}}):
                with self.subTest(payload=payload):
                    result, _ = self.dispatch_with_git(parent, body, payload)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertNotIn('permissionDecision', result.stdout.decode())
                    self.assertFalse(marker.exists())
            self.dispatch_with_git(parent, body, self.EDIT_EVENT)
            self.assertTrue(marker.exists())  # The same fixture does reach Git when an edit needs it.

    def test_a_slow_git_is_stopped_by_its_own_timeout(self):
        with tempfile.TemporaryDirectory() as temporary:
            result, elapsed = self.dispatch_with_git(Path(temporary).resolve(), 'exec sleep 30', self.EDIT_EVENT)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['hookSpecificOutput']['permissionDecision'], 'deny')
            self.assertGreaterEqual(elapsed, hook.GIT_TIMEOUT)
            self.assertLess(elapsed, hook.DEADLINE_SECONDS - 2)  # Well before the dispatcher's deadline.

    def test_the_dispatcher_deadline_still_blocks_during_the_git_call(self):
        with tempfile.TemporaryDirectory() as temporary:
            result, _ = self.dispatch_with_git(Path(temporary).resolve(), 'exec sleep 30', self.EDIT_EVENT, deadline='1')
            # Git's own timeout answers with a denial and exit 0, so exit 2 means the deadline ended it.
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, b'')
            self.assertEqual(result.stderr.decode().strip(), hook.FAILURE)

    def test_a_directory_that_is_no_repository_cannot_answer(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary).resolve()
            self.git(parent, 'init', '--quiet')  # Git must not answer from an enclosing repository.
            home = parent / 'home'
            home.mkdir()
            self.assertIsNone(hook.session_root(home, str(home / '.claude/worktrees/one')))

    def test_a_session_outside_the_worktree_directory_runs_no_git(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary).resolve()
            with mock.patch.object(hook.subprocess, 'run') as run:
                for cwd in (str(home), str(home / 'scripts'), '/', None):
                    self.assertEqual(hook.session_root(home, cwd), home)
            run.assert_not_called()

    def test_stop_reads_the_reports_of_the_session_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = self.checkout_with_worktrees(Path(temporary).resolve())
            one, two = home / '.claude/worktrees/one', home / '.claude/worktrees/two'
            for checkout in (home, one):
                (checkout / '.checks/harness').mkdir(parents=True)
                (checkout / '.checks/harness/latest.json').write_text(json.dumps(self.valid_report(checkout)))
            stop = {'hook_event_name': 'Stop', 'stop_hook_active': False}
            self.assertEqual(hook.handle(hook.session_root(home, str(one)), stop), {})
            # The home checkout's current report does not satisfy a worktree with none of its own.
            self.assertEqual(hook.handle(hook.session_root(home, str(two)), stop)['decision'], 'block')
            self.assertNotIn('decision', hook.handle(hook.session_root(home, str(two)), {**stop, 'stop_hook_active': True}))
            # Nor the other way around.
            (home / '.checks/harness/latest.json').unlink()
            self.assertEqual(hook.handle(hook.session_root(home, str(home)), stop)['decision'], 'block')
            self.assertEqual(hook.handle(hook.session_root(home, str(one)), stop), {})

    def test_a_new_worktree_with_real_inputs_needs_more_than_a_harness_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = self.checkout_with_worktrees(Path(temporary).resolve())
            stop = {'hook_event_name': 'Stop', 'stop_hook_active': False}
            for name, source, wanted in (('one', 'package.json', 'fast or full'),
                                         ('two', 'tests/db/seeds/fixtures.sql', 'last passing db report')):
                with self.subTest(source=source):
                    worktree = home / '.claude/worktrees' / name
                    self.write_files(worktree, (source,))
                    (worktree / '.checks/harness').mkdir(parents=True)
                    (worktree / '.checks/harness/latest.json').write_text(json.dumps(self.valid_report(worktree)))
                    self.assertTrue(report_state(worktree, 'harness')[0])
                    response = hook.handle(worktree, stop)
                    self.assertEqual(response['decision'], 'block')
                    self.assertIn(wanted, response['reason'])
                    self.assertNotIn('decision', hook.handle(worktree, {**stop, 'stop_hook_active': True}))

    def test_the_dispatcher_applies_the_session_root_to_each_event(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary).resolve()
            home = self.checkout_with_worktrees(parent)
            one = home / '.claude/worktrees/one'
            script = home / '.claude/hooks/dispatch.py'
            script.parent.mkdir(parents=True)
            shutil.copy2(ROOT / '.claude/hooks/dispatch.py', script)
            (home / 'scripts').mkdir()
            shutil.copy2(ROOT / 'scripts/harness_lib.py', home / 'scripts/harness_lib.py')

            def respond(event: str, cwd: Path, file_path: Path) -> dict:
                result = self.dispatch(json.dumps({'hook_event_name': event, 'cwd': str(cwd), 'tool_name': 'Edit',
                                                   'tool_input': {'file_path': str(file_path)}}).encode(), script)
                self.assertEqual(result.returncode, 0, result.stderr)
                return json.loads(result.stdout)['hookSpecificOutput'] if event == 'PostToolUse' or result.stdout != b'{}\n' else {}

            sibling, main_file = home / '.claude/worktrees/two/SPECS.md', home / 'SPECS.md'
            self.assertEqual(respond('PreToolUse', one, one / 'SPECS.md'), {})
            for target in (sibling, main_file):
                self.assertEqual(respond('PreToolUse', one, target)['permissionDecision'], 'deny')
            # A session in the home checkout keeps the behavior it has always had.
            self.assertEqual(respond('PreToolUse', home, main_file), {})
            self.assertEqual(respond('PreToolUse', parent / 'forged', parent / 'forged/file')['permissionDecision'], 'deny')
            # The path is classified from the worktree, not as a file under `.claude/worktrees`.
            context = respond('PostToolUse', one, one / 'scripts/harness_lib.py')['additionalContext']
            self.assertIn('Affected check domains: db, python, repo_python, web.', context)
            self.assertIn('--profile fast', context)
            (one / '.checks/harness').mkdir(parents=True)
            (one / '.checks/harness/latest.json').write_text(json.dumps(self.valid_report(one)))
            for cwd, blocked in ((one, False), (home / '.claude/worktrees/two', True)):
                result = self.dispatch(json.dumps({'hook_event_name': 'Stop', 'cwd': str(cwd)}).encode(), script)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual('decision' in json.loads(result.stdout), blocked)

    def test_unknown_profile_is_not_a_pass(self):
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/verify.py'), '--profile', 'nonexistent'],
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, '')


if __name__ == '__main__':
    unittest.main()
