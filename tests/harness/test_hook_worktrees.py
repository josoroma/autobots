"""A session's root inside a registered worktree, when Git fails or hangs, and Stop per root.

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
import time
import unittest
from pathlib import Path
from unittest import mock

from harness_support import HarnessTestCase, copy_dispatcher, hook, report_state


class HookWorktrees(HarnessTestCase):
    """Only a registered worktree of this checkout, confirmed by Git, becomes a session root."""

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
        script = copy_dispatcher(home)
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
                                         ('two', 'tests/db/sql/h1/seeds/fixtures.sql', 'last passing db report')):
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
            script = copy_dispatcher(home)

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



if __name__ == '__main__':
    unittest.main()
