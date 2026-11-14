"""Fixtures for profile results and evidence freshness. They arrange steps; they prove no real toolchain run."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
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


def passing_full_steps(root: Path) -> list[Step]:
    # The scope tests are judged by unittest's summary, so their fixture prints one.
    summary = "print('Ran 1 test in 0.1s'); print('OK')"
    node = "print('# tests 1'); print('# pass 1')"
    return [python_step(root, name, summary if name == 'toolchain_scope_tests'
                        else node if name in verify.NODE_TEST_STEPS else 'pass')
            for name in sorted(harness_lib.FULL_CHECKS)]


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

    def test_node_reporting_no_tests_fails(self):
        passed = {'id': 'web_unit_tests', 'status': 'passed', 'output': '# tests 0\n# pass 0\n'}
        self.assertEqual(verify.judge_node(passed)['status'], 'failed')
        self.assertEqual(verify.judge_node({**passed, 'output': ''})['status'], 'failed')
        counted = verify.judge_node({**passed, 'output': '# tests 55\n# pass 55\n'})
        self.assertEqual(counted, {'tests_executed': 55})

    def test_fast_scope_selection(self):
        step_ids = sorted(verify.PYTHON_STEPS | verify.WEB_STEPS | {'build'})
        both = verify.PYTHON_STEPS | verify.WEB_STEPS
        cases = {('services/agent/a.py',): verify.PYTHON_STEPS,
                 ('apps/web/app/page.tsx',): verify.WEB_STEPS,
                 ('packages/api-client/x.ts',): verify.WEB_STEPS,
                 ('docs/note.md', 'SPECS.md'): frozenset(),
                 ('pnpm-lock.yaml',): both,
                 ('scripts/verify.py',): both,
                 ('packages/db-types/src/generated.ts',): frozenset(),
                 ('tests/db/seeds/fixtures.sql',): frozenset(),
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
        self.assertFalse(harness_lib.report_state(self.root, 'full')[0], 'a full report without its other steps')
        everything = passing_full_steps(self.root)
        self.run_steps('full', everything[:-1])
        self.assertFalse(harness_lib.report_state(self.root, 'full')[0], f'a full report without {everything[-1].id}')
        self.run_steps('full', everything)
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

    def test_stop_needs_fast_or_full_for_unverified_application_inputs(self):
        with mock.patch('sys.stdout'):
            verify.run_profile(self.root, 'harness', base_checks=harness_records)
        passed, reason = harness_lib.evidence_state(self.root)
        self.assertFalse(passed, 'no application report has ever seen this code')
        self.assertIn('fast or full', reason)
        self.assertEqual(self.run_steps('fast', [python_step(self.root, 'mypy', 'pass')]), 0)
        self.assertTrue(harness_lib.evidence_state(self.root)[0])
        (self.root / 'services/agent/code.py').write_text('x = 2\n')
        with mock.patch('sys.stdout'):
            verify.run_profile(self.root, 'harness', base_checks=harness_records)
        self.assertFalse(harness_lib.evidence_state(self.root)[0], 'harness cannot certify changed application code')
        self.assertEqual(self.run_steps('fast', [python_step(self.root, 'mypy', 'pass')]), 0)
        (self.root / 'docs/engineering').mkdir(parents=True)
        (self.root / 'docs/engineering/note.md').write_text('x')
        self.assertFalse(harness_lib.evidence_state(self.root)[0], 'the note is an unverified input of no report yet')
        with mock.patch('sys.stdout'):
            verify.run_profile(self.root, 'harness', base_checks=harness_records)
        self.assertEqual(harness_lib.scope_paths(self.root), ['docs/engineering/note.md'])
        self.assertTrue(harness_lib.evidence_state(self.root)[0], 'a documentation change needs only harness')

    def test_stop_needs_db_for_database_inputs(self):
        (self.root / 'tests/db').mkdir(parents=True)
        (self.root / 'tests/db/seed.sql').write_text('select 1;')
        self.assertEqual(self.run_steps('fast', []), 0)
        passed, reason = harness_lib.evidence_state(self.root)
        self.assertFalse(passed)
        self.assertIn('db', reason)
        everything = [python_step(self.root, name, 'pass') for name in sorted(harness_lib.DB_CHECKS)]
        self.assertEqual(self.run_steps('db', everything), 0)
        self.assertTrue(harness_lib.evidence_state(self.root)[0])

    def test_operations_plan_is_the_three_qualifiers(self):
        """The plan only: running it starts Docker, which this suite must not do."""
        with mock.patch.dict(os.environ, {'HOME': '/home/fixture', 'OPENROUTER_API_KEY': 'planted'}), \
             mock.patch('verify.find_tools'), mock.patch('verify.missing_prepared_paths', return_value=[]):
            plan, left_out = verify.tool_plan(self.root, 'operations', None)
        self.assertEqual(left_out, [])
        self.assertEqual({step.id: step.argv[1] for step in plan.steps},
                         {'operations_qualification': 'scripts/qualify_operations.py',
                          'backup_qualification': 'scripts/qualify_backup.py',
                          'upgrade_qualification': 'scripts/qualify_upgrade.py'})
        self.assertEqual({step.id for step in plan.steps}, harness_lib.OPERATIONS_CHECKS)
        self.assertEqual(plan.env['HOME'], '/home/fixture')
        self.assertNotIn('OPENROUTER_API_KEY', plan.env)

    def test_db_and_operations_on_an_unprepared_tree_are_unavailable(self):
        for profile in ('db', 'operations'):
            with self.subTest(profile=profile), self.assertRaises(Unavailable):
                verify.tool_plan(self.root, profile, None)

    def test_operations_report_says_it_is_disposable_evidence(self):
        steps = [python_step(self.root, name, 'pass') for name in sorted(harness_lib.OPERATIONS_CHECKS)]
        self.assertEqual(self.run_steps('operations', steps), 0)
        report = self.report('operations')
        self.assertIn('Disposable evidence only, not H1 or product acceptance', report['scope'])
        self.assertLessEqual({'H1', 'product acceptance', 'the persistent stack', 'resource use under load'},
                             set(report['not_tested']))
        classes = {check['class'] for check in report['checks'] if check['id'] in harness_lib.OPERATIONS_CHECKS}
        self.assertEqual(classes, {'disposable'})
        self.assertTrue(harness_lib.report_state(self.root, 'operations')[0])

    def test_operations_needs_every_qualifier(self):
        for missing in sorted(harness_lib.OPERATIONS_CHECKS):
            with self.subTest(missing=missing):
                steps = [python_step(self.root, name, 'pass') for name in sorted(harness_lib.OPERATIONS_CHECKS - {missing})]
                self.assertEqual(self.run_steps('operations', steps), 0)
                self.assertFalse(harness_lib.report_state(self.root, 'operations')[0])

    def test_operations_distinguishes_a_missing_prerequisite_from_a_failure(self):
        passing = [python_step(self.root, name, 'pass') for name in ('operations_qualification', 'backup_qualification')]
        self.assertEqual(self.run_steps('operations', [*passing, python_step(self.root, 'upgrade_qualification', 'raise SystemExit(2)')]), 2)
        self.assertEqual(self.statuses('operations')['upgrade_qualification'], 'error')
        self.assertEqual(self.run_steps('operations', [*passing, python_step(self.root, 'upgrade_qualification', 'raise SystemExit(1)')]), 1)
        self.assertEqual(self.statuses('operations')['upgrade_qualification'], 'failed')

    def test_a_committed_change_is_still_in_scope(self):
        """A clean Git tree proves nothing: scope comes from what a passing report saw."""
        self.assertIsNone(harness_lib.scope_paths(self.root), 'nothing has passed yet, so scope is unknown')
        self.assertEqual(self.run_steps('fast', [python_step(self.root, 'mypy', 'pass')]), 0)
        self.assertEqual(harness_lib.scope_paths(self.root), [])
        (self.root / 'services/agent/code.py').write_text('broken\n')
        git = ['git', '-C', str(self.root), '-c', 'user.name=t', '-c', 'user.email=t@invalid', '-c', 'commit.gpgsign=false']
        subprocess.run([*git, 'commit', '-qam', 'broken'], check=True, capture_output=True)
        self.assertEqual(harness_lib.scope_paths(self.root), ['services/agent/code.py'])
        chosen = verify.selected_steps('fast', sorted(harness_lib.FULL_CHECKS), harness_lib.scope_paths(self.root))
        self.assertEqual(chosen, set(verify.PYTHON_STEPS))

    def test_a_failed_run_does_not_become_the_base_for_scope(self):
        self.assertEqual(self.run_steps('fast', [python_step(self.root, 'mypy', 'pass')]), 0)
        self.assertEqual(self.run_steps('fast', [python_step(self.root, 'mypy', 'raise SystemExit(1)')]), 1)
        self.assertIsNone(harness_lib.scope_paths(self.root))

    def test_skips_and_empty_suites_do_not_pass(self):
        for output, status, executed, skipped in (('Ran 5 tests in 0.1s\n\nOK', None, 5, 0),
                                                  ('Ran 5 tests in 0.1s\n\nOK (skipped=1)', 'failed', 4, 1),
                                                  ('Ran 2 tests in 0.1s\n\nOK (expected failures=2)', 'failed', 0, 2),
                                                  ('Ran 0 tests in 0.0s\n\nOK', 'failed', 0, 0),
                                                  ('no summary', 'failed', 0, 0)):
            with self.subTest(output=output):
                result = verify.judge_unittest({'status': 'passed', 'output': output})
                self.assertEqual((result.get('status'), result['tests_executed'], result['tests_skipped']),
                                 (status, executed, skipped))
        self.assertEqual(verify.judge_pytest({'status': 'passed', 'output': '3 passed, 1 skipped in 1s'})['status'], 'failed')
        self.assertNotIn('status', verify.judge_pytest({'status': 'passed', 'output': '4 passed in 1s'}))

    def test_a_skip_fails_each_wired_step(self):
        skipping = "print('3 passed, 1 skipped in 1s')"
        self.assertEqual(self.run_steps('fast', [python_step(self.root, 'pytest', skipping)]), 1)
        self.assertEqual(self.statuses('fast')['pytest'], 'failed')
        scope = "import sys; print('Ran 2 tests in 0.1s', file=sys.stderr); print('OK (skipped=1)', file=sys.stderr)"
        self.assertEqual(self.run_steps('fast', [python_step(self.root, 'toolchain_scope_tests', scope)]), 1)
        with mock.patch('verify.run_check', side_effect=lambda _root, name, _argv: {
                'id': name, 'status': 'passed', 'exit_code': 0, 'output': 'Ran 3 tests in 0.1s\n\nOK (skipped=1)'}), \
                mock.patch('verify.config_errors', return_value=[]):
            checks = verify.harness_checks(self.root)
        self.assertEqual({check['id']: check['status'] for check in checks}['harness_behavior_tests'], 'failed')

    def test_the_newest_passing_report_is_the_base(self):
        self.run_steps('full', passing_full_steps(self.root))
        (self.root / 'services/agent/code.py').write_text('x = 2\n')
        self.assertEqual(self.run_steps('fast', [python_step(self.root, 'mypy', 'pass')]), 0)
        self.assertEqual(harness_lib.scope_paths(self.root), [], 'the newer fast report is the base')
        report = self.report('full')
        report['completed_at_utc'] = '2999-01-01T00:00:00+00:00'
        (self.root / '.checks/full/latest.json').write_text(json.dumps(report))
        self.assertEqual(harness_lib.scope_paths(self.root), ['services/agent/code.py'], 'now the full report is newer')

    def test_a_report_with_a_skipped_suite_is_not_current(self):
        self.run_steps('fast', [])
        path = self.root / '.checks/fast/latest.json'
        data = json.loads(path.read_text())
        for check in data['checks']:
            if check['id'] == 'harness_behavior_tests':
                check['tests_skipped'] = 1
        path.write_text(json.dumps(data))
        self.assertFalse(harness_lib.report_state(self.root, 'fast')[0])

    def test_steps_carry_their_class_and_transport(self):
        self.assertEqual(verify.classify('pytest'), {'class': 'mock', 'model_transport': 'mock'})
        self.assertEqual(verify.classify('disposable_qualification'), {'class': 'disposable', 'model_transport': 'none'})
        self.assertEqual(verify.classify('lint'), {'class': 'static', 'model_transport': 'none'})

    def test_links_and_example_files_are_inputs(self):
        before = harness_lib.fingerprint(self.root)
        (self.root / 'scripts').mkdir()
        (self.root / 'scripts/link').symlink_to('/nonexistent/target')
        linked = harness_lib.fingerprint(self.root)
        self.assertNotEqual(before, linked)
        (self.root / 'scripts/directory_link').symlink_to(self.root / 'services')
        self.assertNotEqual(linked, harness_lib.fingerprint(self.root), 'a link to an existing directory')
        linked = harness_lib.fingerprint(self.root)
        (self.root / 'scripts/.env.example').write_text('A=\n')
        example = harness_lib.fingerprint(self.root)
        self.assertNotEqual(linked, example)
        (self.root / 'scripts/.env.local').write_text('PRIVATE=1\n')
        self.assertEqual(example, harness_lib.fingerprint(self.root))

    def test_held_lock_is_a_prerequisite_error(self):
        (self.root / '.checks').mkdir()
        (self.root / '.checks/verify.lock').write_text('1')
        with mock.patch('sys.stderr'):
            self.assertEqual(verify.run_profile(self.root, 'harness', base_checks=harness_records), 2)


if __name__ == '__main__':
    unittest.main()
