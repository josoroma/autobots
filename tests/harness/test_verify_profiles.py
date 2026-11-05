"""Fixtures for profile results and evidence freshness. They arrange steps; they prove no real toolchain run."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import harness_lib  # noqa: E402
import verify  # noqa: E402
from toolchain import Step, Unavailable  # noqa: E402


def harness_records(_root: Path) -> list[dict]:
    return [{'id': 'project_configuration', 'status': 'passed'},
            {'id': 'backlog_validation', 'status': 'passed', 'exit_code': 0},
            {'id': 'harness_behavior_tests', 'status': 'passed', 'exit_code': 0, 'tests_executed': 1}]


def python_step(root: Path, name: str, code: str, timeout: float = 20.0) -> Step:
    return Step(name, (sys.executable, '-c', code), root, timeout)


class Profiles(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        git = ['git', '-C', str(self.root), '-c', 'user.name=t', '-c', 'user.email=t@invalid', '-c', 'commit.gpgsign=false']
        (self.root / '.gitignore').write_text('.checks/\n')
        (self.root / 'services/agent').mkdir(parents=True)
        (self.root / 'services/agent/code.py').write_text('x = 1\n')
        for arguments in (('init', '-q'), ('add', '-A'), ('commit', '-q', '-m', 'fixture')):
            subprocess.run([*git, *arguments], check=True, capture_output=True)

    def run_steps(self, profile: str, steps: list[Step], left_out: list[dict] | None = None) -> int:
        def plan(_root, _profile, _changed):
            return verify.ToolPlan(steps, {'PATH': os.environ['PATH']}), left_out or []
        with mock.patch('sys.stdout'), mock.patch('sys.stderr'):
            return verify.run_profile(self.root, profile, base_checks=harness_records, plan=plan)

    def report(self, profile: str) -> dict:
        return json.loads((self.root / f'.checks/{profile}/latest.json').read_text())

    def statuses(self, profile: str) -> dict:
        return {check['id']: check['status'] for check in self.report(profile)['checks']}

    def test_results_are_distinct(self):
        self.assertEqual(self.run_steps('full', [python_step(self.root, 'build', 'pass')]), 0)
        self.assertEqual(self.report('full')['status'], 'passed')
        self.assertEqual(self.run_steps('full', [python_step(self.root, 'build', 'raise SystemExit(3)')]), 1)
        self.assertEqual(self.report('full')['status'], 'failed')
        self.assertEqual(self.run_steps('full', [Step('build', ('/nonexistent/tool',), self.root)]), 2)
        self.assertEqual(self.report('full')['status'], 'error')

    def test_timeout_is_an_error_and_not_a_pass(self):
        code = self.run_steps('fast', [python_step(self.root, 'mypy', 'import time; time.sleep(30)', timeout=0.3)])
        self.assertEqual(code, 2)
        self.assertEqual(self.statuses('fast')['mypy'], 'error')

    def test_a_failure_outranks_an_unavailable_step(self):
        steps = [Step('mypy', ('/nonexistent/tool',), self.root),
                 python_step(self.root, 'ruff_check', 'raise SystemExit(1)')]
        self.assertEqual(self.run_steps('fast', steps), 1)

    def test_prerequisite_error_runs_nothing_and_is_recorded(self):
        def plan(_root, _profile, _changed):
            raise Unavailable('uv 0.0.0 is required and was not found; nothing was downloaded or installed')
        with mock.patch('sys.stdout'), mock.patch('sys.stderr'):
            code = verify.run_profile(self.root, 'full', base_checks=harness_records, plan=plan)
        self.assertEqual(code, 2)
        self.assertEqual(self.statuses('full')['non_mutation_guard'], 'error')
        self.assertFalse(harness_lib.report_state(self.root, 'full')[0])

    def test_a_step_that_changes_the_tree_fails_the_guard(self):
        step = python_step(self.root, 'build', "open('services/agent/code.py', 'a').write('y = 2\\n')")
        self.assertEqual(self.run_steps('full', [step]), 1)
        self.assertEqual(self.statuses('full')['non_mutation_guard'], 'failed')
        self.assertFalse(self.report('full')['inputs_unchanged_during_check'])

    def test_children_receive_no_credential(self):
        step = Step('pytest', (sys.executable, '-c', "import os; raise SystemExit('OPENROUTER_API_KEY' in os.environ)"),
                    self.root)
        with mock.patch.dict(os.environ, {'OPENROUTER_API_KEY': 'fixture-not-a-key'}):
            code = self.run_steps('fast', [step])
            self.assertNotIn('OPENROUTER_API_KEY', harness_lib.reduced_env())
        self.assertEqual(code, 0)
        self.assertNotIn('fixture-not-a-key', (self.root / '.checks/fast/latest.json').read_text())

    def test_fast_scope_selection(self):
        step_ids = sorted(verify.PYTHON_STEPS | verify.WEB_STEPS | {'build'})
        both = verify.PYTHON_STEPS | verify.WEB_STEPS
        cases = {('services/agent/a.py',): verify.PYTHON_STEPS,
                 ('apps/web/app/page.tsx',): verify.WEB_STEPS,
                 ('packages/api-client/x.ts',): verify.WEB_STEPS,
                 ('docs/note.md', 'SPECS.md'): frozenset(),
                 ('pnpm-lock.yaml',): both,
                 ('scripts/verify.py',): both,
                 ('contracts/generated/a.json',): both}
        for changed, expected in cases.items():
            with self.subTest(changed=changed):
                self.assertEqual(verify.selected_steps('fast', step_ids, changed), set(expected))
        self.assertEqual(verify.selected_steps('fast', step_ids, None), set(both))
        self.assertEqual(verify.selected_steps('full', step_ids, ['docs/note.md']), set(step_ids))

    def test_fast_records_what_it_left_out_and_needs_no_tools_for_docs(self):
        with mock.patch('verify.find_tools', side_effect=AssertionError('tools were looked up')):
            plan, left_out = verify.tool_plan(self.root, 'fast', ['docs/note.md'])
        self.assertEqual(plan.steps, ())
        self.assertEqual({record['status'] for record in left_out}, {'not_run'})
        self.assertIn('build', {record['id'] for record in left_out})

    def test_real_plan_on_an_unprepared_tree_is_unavailable(self):
        with self.assertRaises(Unavailable):
            verify.tool_plan(self.root, 'full', ['services/agent/code.py'])

    def test_fast_with_left_out_steps_is_current_until_an_input_changes(self):
        left_out = [{'id': 'lint', 'status': 'not_run', 'reason': verify.OUTSIDE_SCOPE}]
        self.assertEqual(self.run_steps('fast', [python_step(self.root, 'mypy', 'pass')], left_out), 0)
        self.assertEqual(self.statuses('fast')['lint'], 'not_run')
        self.assertTrue(harness_lib.report_state(self.root, 'fast')[0])
        (self.root / 'services/agent/untracked.py').write_text('x = 2\n')
        self.assertFalse(harness_lib.report_state(self.root, 'fast')[0])

    def test_full_cannot_leave_a_step_out(self):
        left_out = [{'id': 'lint', 'status': 'not_run', 'reason': verify.OUTSIDE_SCOPE}]
        self.run_steps('full', [python_step(self.root, 'build', 'pass')], left_out)
        self.assertFalse(harness_lib.report_state(self.root, 'full')[0])
        self.run_steps('full', [python_step(self.root, 'build', 'pass')])
        self.assertFalse(harness_lib.report_state(self.root, 'full')[0], 'a full report without fault qualification')
        self.run_steps('full', [python_step(self.root, 'build', 'pass'), python_step(self.root, 'fault_qualification', 'pass')])
        self.assertTrue(harness_lib.report_state(self.root, 'full')[0])

    def test_application_inputs_invalidate_but_environments_do_not(self):
        before = harness_lib.fingerprint(self.root)
        for name in ('.venv/lib/x.py', 'node_modules/x.js', '__pycache__/x.pyc'):
            path = self.root / 'services/agent' / name
            path.parent.mkdir(parents=True)
            path.write_text('x')
        (self.root / 'apps/web').mkdir(parents=True)
        (self.root / 'apps/web/next-env.d.ts').write_text('x')
        self.assertEqual(before, harness_lib.fingerprint(self.root))
        (self.root / 'pnpm-lock.yaml').write_text('x')
        changed = harness_lib.fingerprint(self.root)
        self.assertNotEqual(before, changed)
        (self.root / 'services/agent/code.py').write_text('x = 2\n')
        self.assertNotEqual(changed, harness_lib.fingerprint(self.root))

    def test_stop_needs_fast_or_full_for_application_changes(self):
        with mock.patch('sys.stdout'):
            verify.run_profile(self.root, 'harness', base_checks=harness_records)
        self.assertTrue(harness_lib.evidence_state(self.root)[0], 'a clean tree needs only harness')
        (self.root / 'services/agent/code.py').write_text('x = 2\n')
        with mock.patch('sys.stdout'):
            verify.run_profile(self.root, 'harness', base_checks=harness_records)
        passed, reason = harness_lib.evidence_state(self.root)
        self.assertFalse(passed)
        self.assertIn('fast or full', reason)
        self.assertEqual(self.run_steps('fast', [python_step(self.root, 'mypy', 'pass')]), 0)
        self.assertTrue(harness_lib.evidence_state(self.root)[0])

    def test_held_lock_is_a_prerequisite_error(self):
        (self.root / '.checks').mkdir()
        (self.root / '.checks/verify.lock').write_text('1')
        with mock.patch('sys.stderr'):
            self.assertEqual(verify.run_profile(self.root, 'harness', base_checks=harness_records), 2)


if __name__ == '__main__':
    unittest.main()
