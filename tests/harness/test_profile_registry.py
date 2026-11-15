"""Each profile is described once, in qualification/profiles.py, and the verifier, report_state and evidence.py read it
there (refactor plan R-65, SCRP-12). No step runs here: plans are built and reports are arranged."""
from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import evidence  # noqa: E402
import harness_lib  # noqa: E402
import toolchain  # noqa: E402
import verify  # noqa: E402
from qualification import profiles  # noqa: E402

TOOLS = toolchain.Tools(node_dir='/fixture/node/bin', python='/fixture/python3.12', uv='/fixture/uv', corepack='/fixture/node/bin/corepack',
                        pins=toolchain.Pins(node='22.0.0', python='3.12.0', uv='0.1.0', pnpm='10.0.0'))


class Registry(unittest.TestCase):
    def test_the_profiles_are_the_ones_the_configuration_declares_in_its_order(self) -> None:
        declared = json.loads((ROOT / '.claude/autobots.json').read_text())['verification']['implemented_profiles']
        self.assertEqual(list(profiles.PROFILES), declared)
        self.assertEqual(verify.IMPLEMENTED_PROFILES, tuple(declared))

    def test_each_step_id_is_registered_once(self) -> None:
        ids = [step.id for step in (*profiles.HARNESS_STEPS, profiles.GUARD, *profiles.APPLICATION_STEPS,
                                    *profiles.PROFILES['db'].steps, *profiles.PROFILES['operations'].steps)]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(profiles.STEPS), set(ids))

    def test_no_other_script_lists_a_profiles_steps(self) -> None:
        """A qualifier added in one place and missed in another changed what 'passed' meant (SCRP-12)."""
        for step in (*profiles.PROFILES['db'].steps, *profiles.PROFILES['operations'].steps):
            named = sorted(path.relative_to(ROOT).as_posix() for path in (ROOT / 'scripts').rglob('*.py') if f"'{step.id}'" in path.read_text())
            with self.subTest(step.id):
                self.assertEqual(named, ['scripts/qualification/profiles.py'])

    def test_every_qualifier_a_profile_runs_exists_and_reports_its_own_prerequisites(self) -> None:
        for name in ('db', 'operations'):
            for step in profiles.PROFILES[name].steps:
                with self.subTest(step.id):
                    self.assertTrue((ROOT / str(step.script)).is_file())
                    self.assertTrue(step.self_reporting)
                    self.assertEqual(step.klass, 'disposable')


class VerifierReadsIt(unittest.TestCase):
    def test_the_docker_profiles_plan_exactly_the_registered_qualifiers(self) -> None:
        for name in ('db', 'operations'):
            with self.subTest(name), mock.patch('verify.find_tools'), mock.patch('verify.missing_prepared_paths', return_value=[]):
                plan, left_out = verify.tool_plan(ROOT, name, None)
            self.assertEqual(left_out, [])
            self.assertEqual([(step.id, step.argv, step.cwd, step.timeout) for step in plan.steps],
                             [(step.id, (sys.executable, *(step.argv or ())[1:]), ROOT, step.timeout) for step in profiles.PROFILES[name].steps])

    def test_full_plans_every_registered_step_in_its_order_with_its_deadline(self) -> None:
        with mock.patch('verify.find_tools', return_value=TOOLS), mock.patch('verify.missing_prepared_paths', return_value=[]):
            plan, left_out = verify.tool_plan(ROOT, 'full', None)
        self.assertEqual(left_out, [])
        self.assertEqual([step.id for step in plan.steps], [step.id for step in profiles.APPLICATION_STEPS])
        for step in plan.steps:
            with self.subTest(step.id):
                self.assertEqual(step.timeout, profiles.STEPS[step.id].timeout)
                self.assertEqual(step.cwd, ROOT / profiles.STEPS[step.id].cwd if profiles.STEPS[step.id].argv else step.cwd)
        built = {step.id: step.argv for step in plan.steps}
        self.assertEqual(built['web_unit_tests'], ('/fixture/node/bin/node', '--test', 'apps/web/tests/unit/**/*.test.ts'))
        self.assertEqual(built['toolchain_scope_tests'], (sys.executable, '-m', 'unittest', 'test_scaffold_scope', 'test_manifests', 'test_non_mutating.Launchers'))
        self.assertEqual(built['api_client_typecheck'], (str(ROOT / 'apps/web/node_modules/.bin/tsc'), '-p', 'packages/api-client'))

    def test_the_toolchain_builds_exactly_the_registered_steps_with_no_arguments(self) -> None:
        unbuilt = [step.id for step in profiles.APPLICATION_STEPS if step.argv is None]
        self.assertEqual([step.id for step in toolchain.check_steps(ROOT, TOOLS)], unbuilt)

    def test_classes_transports_and_self_reporting_come_from_the_registry(self) -> None:
        for step in profiles.STEPS.values():
            with self.subTest(step.id):
                self.assertEqual(verify.classify(step.id), {'class': step.klass, 'model_transport': step.transport})
                self.assertEqual(step.id in verify.SELF_REPORTING_STEPS, step.self_reporting)
        self.assertEqual(verify.classify('unregistered'), {'class': 'static', 'model_transport': 'none'})

    def test_the_harness_checks_run_the_registered_commands(self) -> None:
        ran: list[tuple[str, list[str]]] = []

        def record(_root: Path, name: str, argv: list[str]) -> dict[str, object]:
            ran.append((name, argv))
            return {'id': name, 'status': 'passed', 'exit_code': 0, 'output': 'Ran 1 test in 0.1s\n\nOK'}

        with mock.patch('verify.run_check', side_effect=record), mock.patch('verify.config_errors', return_value=[]):
            verify.harness_checks(ROOT)
        self.assertEqual(ran, [('backlog_validation', [sys.executable, 'scripts/specs.py', 'validate']),
                               ('harness_behavior_tests', [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests/harness', '-p', 'test_*.py', '-v'])])

    def test_scope_and_not_tested_are_the_registrys(self) -> None:
        self.assertIn('Disposable evidence only, not H1 or product acceptance', profiles.PROFILES['operations'].scope)
        self.assertEqual(profiles.PROFILES['harness'].not_tested[0], 'application')


class ReportStateReadsIt(unittest.TestCase):
    def test_a_passing_report_holds_every_check_its_profile_requires(self) -> None:
        self.assertEqual(profiles.required_checks('harness'), profiles.HARNESS_CHECKS)
        self.assertEqual(profiles.required_checks('fast'), profiles.HARNESS_CHECKS | {'non_mutation_guard'})
        for name, own in (('full', profiles.FULL_CHECKS), ('db', profiles.DB_CHECKS), ('operations', profiles.OPERATIONS_CHECKS)):
            with self.subTest(name):
                self.assertEqual(profiles.required_checks(name), profiles.HARNESS_CHECKS | {'non_mutation_guard'} | own)
                self.assertEqual(own, profiles.PROFILES[name].step_ids)

    def test_an_unknown_profile_is_not_current(self) -> None:
        self.assertFalse(harness_lib.report_state(ROOT, 'nonexistent')[0])


class EvidenceReadsIt(unittest.TestCase):
    def provenance(self, klass: str, transport: str) -> list[str]:
        cited = {'id': 'app_db_qualification', 'class': klass, 'model_transport': transport, 'status': 'passed', 'exit_code': 0}
        report = {'status': 'passed', 'checks': [cited]}
        check = {'id': 'db.app_db_qualification', 'source': {'kind': 'report', 'profile': 'db', 'check': 'app_db_qualification'},
                 'verification_class': klass, 'model_transport': transport, 'status': 'passed', 'exit_code': 0}
        with mock.patch.object(evidence, 'read_report', return_value=report), mock.patch.object(evidence, 'report_problem', return_value=None):
            return evidence.provenance_errors(ROOT, [check])

    def test_a_cited_check_keeps_its_registered_class_and_transport(self) -> None:
        self.assertEqual(self.provenance('disposable', 'mock'), [])

    def test_a_report_cannot_claim_another_class_for_a_registered_step(self) -> None:
        for klass, transport in (('live', 'openrouter_live'), ('disposable', 'none'), ('static', 'none')):
            with self.subTest(klass=klass, transport=transport):
                errors = self.provenance(klass, transport)
                self.assertEqual(len(errors), 1)
                self.assertRegex(errors[0], re.escape('another class or model transport than its registered step'))


if __name__ == '__main__':
    unittest.main()
