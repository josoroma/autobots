"""What US-11.12's review of the harness found, held in place. No Docker and no model."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))

import generate_contracts  # noqa: E402
import harness_lib  # noqa: E402
import persistent_install  # noqa: E402
import qualify_web  # noqa: E402
import qualify_worker_inference  # noqa: E402
import toolchain  # noqa: E402
import verify  # noqa: E402
from qualification import profiles  # noqa: E402


def report(path: Path, specs: list[dict], errors: list[str] | None = None) -> Path:
    path.write_text(json.dumps({'suites': [{'file': 'x', 'specs': specs}], 'errors': errors or [], 'stats': {}}))
    return path


class BrowserRuns(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'report.json'
        self.one = [{'title': 't', 'tests': [{'results': [{'status': 'passed'}]}]}]

    def test_a_clean_run_has_no_problem(self) -> None:
        self.assertEqual(qualify_web.run_problems(report(self.path, self.one), 0), [])

    def test_a_non_zero_exit_counts_though_every_case_passed(self) -> None:
        self.assertIn('exit 1', qualify_web.run_problems(report(self.path, self.one), 1))

    def test_a_run_of_no_tests_isnt_a_pass(self) -> None:
        self.assertIn('no tests ran', qualify_web.run_problems(report(self.path, []), 0))

    def test_an_error_outside_any_test_counts(self) -> None:
        self.assertIn('errors outside any test', qualify_web.run_problems(report(self.path, self.one, ['load error']), 0))

    def test_no_report_counts(self) -> None:
        self.assertIn('no report', qualify_web.run_problems(self.path, 0))


class Fingerprint(unittest.TestCase):
    def test_what_checks_read_is_in_the_manifest(self) -> None:
        manifest = harness_lib.input_manifest(ROOT)
        self.assertIn('docs/design/luma.css', manifest)
        self.assertIn('tests/qualification/tasks.json', manifest)


class Domains(unittest.TestCase):
    def test_the_persistent_path_is_a_database_change(self) -> None:
        for name in ('scripts/persistent_install.py', 'scripts/qualify_persistent_apply.py'):
            self.assertIn('db', harness_lib.check_domains(name))

    def test_the_db_plan_and_its_required_checks_agree(self) -> None:
        with mock.patch('verify.find_tools'), mock.patch('verify.missing_prepared_paths', return_value=[]):
            plan, _ = verify.tool_plan(ROOT, 'db', None)
        self.assertEqual({step.id for step in plan.steps}, set(profiles.DB_CHECKS))

    def test_steps_with_a_scripted_model_say_so(self) -> None:
        self.assertEqual(verify.STEP_CLASSES['identity_qualification'][1], 'mock')
        self.assertEqual(verify.STEP_CLASSES['app_db_qualification'][1], 'mock')


class PaidWorkerGuard(unittest.TestCase):
    def test_other_queued_work_refuses_a_paid_goal(self) -> None:
        persistent_install.refuse_other_work('0')
        with self.assertRaisesRegex(persistent_install.Refused, '3 other queued'):
            persistent_install.refuse_other_work('3')

    def test_an_unreadable_answer_refuses_too_and_says_so(self) -> None:
        with self.assertRaisesRegex(persistent_install.Refused, 'Could not read'):
            persistent_install.refuse_other_work('')


    def test_every_failed_check_stays_listed(self) -> None:
        report: dict = {}
        persistent_install.note_failed(report, 'first')
        persistent_install.note_failed(report, 'second')
        self.assertEqual(report['after_run_check_failed'], 'first; second')

    def test_a_paid_goal_really_asks(self) -> None:
        """`goal` itself, on a fake install whose database reports 3 queued jobs: it refuses before the key,
        the owner's sign-in, an admission or a worker, and releases its reservation (SCRP-03)."""
        settled: list[tuple[int | None, str]] = []

        class Ledger:
            def settle(self, entry: dict, reported: int | None, state: str) -> None:
                settled.append((reported, state))
                entry['state'] = state

            def committed(self) -> int:
                return 0

        class Install:
            def runtime(self, statements: str) -> subprocess.CompletedProcess[str]:
                queued = 'app_private.run_jobs' in statements
                return subprocess.CompletedProcess([], 0 if queued else 1, '3\n' if queued else '', '')

        record = persistent_install.Record('autobots-install', 'install-id', 1, 2, 3, 4, Path(tempfile.gettempdir()))
        entry = {'label': 'install-goal', 'worst_case': 1000, 'reported': None, 'state': 'reserved', 'at': 'now'}
        nothing_sent = AssertionError('nothing may be sent')
        with mock.patch.object(persistent_install, 'reserve_goal', return_value=(Ledger(), entry)), \
             mock.patch.object(persistent_install, 'install_stack', return_value=Install()), \
             mock.patch.object(persistent_install, 'require_install'), \
             mock.patch.object(persistent_install, 'read_values', return_value={}), \
             mock.patch('subprocess.run', side_effect=nothing_sent) as helper, \
             mock.patch('subprocess.Popen', side_effect=nothing_sent) as worker, \
             mock.patch('urllib.request.urlopen', side_effect=nothing_sent) as request:
            with self.assertRaisesRegex(persistent_install.Refused, '3 other queued'):
                persistent_install.goal(ROOT, record, 'autobots-install', Path('key'), 1000, Path('ledger.json'), 'a goal', [])
        self.assertEqual((helper.called, worker.called, request.called), (False, False, False))
        self.assertEqual(settled, [(0, 'not_started')])


class RequestShape(unittest.TestCase):
    """The check in `qualify_worker_inference.py`, on requests that break it."""

    def test_a_plain_request_passes(self) -> None:
        self.assertEqual(qualify_worker_inference.request_shape_problems(['max_tokens', 'messages', 'model', 'provider', 'tools'], None), [])

    def test_an_unadvertised_flag_fails(self) -> None:
        for flag in ('temperature', 'top_p', 'parallel_tool_calls', 'seed'):
            self.assertTrue(qualify_worker_inference.request_shape_problems(['model', flag], None), flag)

    def test_reasoning_off_or_malformed_fails(self) -> None:
        for reasoning in ({'effort': 'none'}, 'high', {'unknown': 1}):
            self.assertTrue(qualify_worker_inference.request_shape_problems(['model', 'reasoning'], reasoning), reasoning)
        self.assertEqual(qualify_worker_inference.request_shape_problems(['model', 'reasoning'], {'effort': 'high'}), [])


class NonMutationGuard(unittest.TestCase):
    def test_the_hooks_delivery_record_isnt_a_change_by_the_run(self) -> None:
        with mock.patch.object(toolchain, 'git_paths', side_effect=[[toolchain.DELIVERY_RECORD, 'scripts/verify.py'], []]), \
             mock.patch.object(toolchain, 'entry_names', return_value=[]), mock.patch.object(toolchain, 'file_hash', return_value='x'):
            found = toolchain.snapshot(ROOT)
        self.assertEqual(list(found['changed']), ['scripts/verify.py'])


class ContractDrift(unittest.TestCase):
    """The real `check`, on a tree whose artifact has really drifted."""

    def run_check(self, drift: bool) -> int:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = json.loads((ROOT / generate_contracts.OPENAPI).read_text())
            (root / generate_contracts.PYTHON).parent.mkdir(parents=True)
            (root / generate_contracts.PYTHON).write_text('')
            # The runtime lists the schema keywords it enforces, which `check` reads (R-03).
            (root / generate_contracts.RUNTIME).parent.mkdir(parents=True, exist_ok=True)
            (root / generate_contracts.RUNTIME).write_text((ROOT / generate_contracts.RUNTIME).read_text())
            for path, content in ((generate_contracts.OPENAPI, json.dumps(document, indent=2, sort_keys=True) + '\n'),
                                  (generate_contracts.CLIENT, generate_contracts.typescript_client(document))):
                (root / path).parent.mkdir(parents=True, exist_ok=True)
                (root / path).write_text(content + ('// drifted\n' if drift else ''))
            with mock.patch.object(generate_contracts, 'project_root', return_value=root), \
                 mock.patch.object(generate_contracts, 'export_document', return_value=document), \
                 mock.patch.object(sys, 'argv', ['generate_contracts.py', 'check']):
                return generate_contracts.main()

    def test_matching_artifacts_pass(self) -> None:
        self.assertEqual(self.run_check(drift=False), 0)

    def test_a_drifted_artifact_fails(self) -> None:
        self.assertEqual(self.run_check(drift=True), 1)


if __name__ == '__main__':
    unittest.main()
