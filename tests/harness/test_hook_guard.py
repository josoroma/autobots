"""The PreToolUse guard's path and command policy, and Stop's single block.

Behavioral fixtures for the local hook script, not proof of Claude event delivery (PRD-Development-Harness
DH-05). Split from test_hooks.py by the unit under test (refactor plan R-66, THRN-03).
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from harness_support import HarnessTestCase, hook


class HookGuard(HarnessTestCase):
    """What the guard refuses, and that it refuses without running or repeating what it was given."""

    def test_secret_files_rejected_without_echo(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('.env', '.env.local', 'provider-master.key', '.ENV', '.Env.Local', 'stack.env', 'app.env', 'owner.env',
                         'master.key', 'Master.Key', 'backup.key'):
                with self.subTest(name=name):
                    response = hook.handle(root, {'hook_event_name': 'PreToolUse',
                                                 'tool_name': 'Read', 'tool_input': {'file_path': name}})
                    self.assertEqual(response['hookSpecificOutput']['permissionDecision'], 'deny')
                    # Without echo: the reason never names the file (THRN-06).
                    self.assertNotIn(name.casefold(), response['hookSpecificOutput']['permissionDecisionReason'].casefold())
            self.assertEqual(hook.guard(root, 'Read', {'file_path': '.env.example'}), None)
            # The real install's whole folder, by any tool this guard sees.
            self.assertIsNotNone(hook.guard(root, 'Read', {'file_path': str(Path.home() / '.local/share/autobots-install/record.json')}))
            for command in ('cat ~/.local/share/autobots-install/backup-key/x', 'cat backup.key', 'cat master.key',
                            'sed -n p backup.key', 'awk 1 master.key', 'xargs cat master.key',
                            'head other/autobots-install/app.env'):
                with self.subTest(command=command):
                    reason = hook.guard(root, 'Bash', {'command': command})
                    self.assertIsNotNone(reason, command)
                    self.assertNotIn(command, reason or '')
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

    def test_guard_denies_destructive_and_secret_reading_commands(self):
        """Split from the non-execution test, whose name it didn't match (THRN-06)."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for command in ('supabase db reset', 'docker compose down -v', 'cat .env.local', 'cat .env;', 'CAT .ENV', 'cat ".env"',
                            'cat "$HOME/.env"', 'docker volume rm autobots_db-data', 'docker-compose down -v',
                            'docker compose down --volumes'):
                with self.subTest(command=command):
                    self.assertIsNotNone(hook.guard(root, 'Bash', {'command': command}), command)
            for command in ('python3 scripts/specs.py validate', 'cat .env.example'):
                with self.subTest(command=command):
                    self.assertIsNone(hook.guard(root, 'Bash', {'command': command}))

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

    def test_stop_blocks_once_and_never_claims_live_proof(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            response = hook.handle(root, {'hook_event_name': 'Stop', 'stop_hook_active': False})
            self.assertEqual(response['decision'], 'block')
            # Never claims live proof: its reason says it certifies nothing (THRN-06).
            self.assertIn('This hook does not certify application completion.', response['reason'])
            retry = hook.handle(root, {'hook_event_name': 'Stop', 'stop_hook_active': True})
            self.assertNotIn('decision', retry)



if __name__ == '__main__':
    unittest.main()
