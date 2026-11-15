"""One vocabulary and one exception per exit code across the qualification scripts (refactor plan R-39).

The verification classes and model transports are DH-09.2's, which docs/engineering/evidence/README.md
extends with local_runtime (SCRP-10). A script that mixes the toolchain's and the disposable target's
helpers catches the same Unavailable for exit code 2 (SCRP-08), and every arrangement is recorded or
stops the run (SCRP-09).
"""
from __future__ import annotations

import ast
import contextlib
import io
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import get_args

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import disposable_db  # noqa: E402
import evidence  # noqa: E402
import qualify_operations  # noqa: E402
import toolchain  # noqa: E402
import verify  # noqa: E402
from qualification import errors, records  # noqa: E402
from qualification.profiles import PROFILES  # noqa: E402

# The qualifiers whose child checks and arrangements go through the shared package.
QUALIFIERS = ('app_db', 'qualify_identity', 'qualify_operations', 'qualify_upgrade', 'qualify_backup', 'qualify_browse_goal',
              'qualify_browser_executor', 'disposable_db')
# What the verifier and evidence.py read of a case record (PRD-Development-Harness DH-W04).
CASE_FIELDS = {'id', 'class', 'model_transport', 'expected', 'observed', 'status'}
# A statement whose result says whether a fixture exists, so dropping it lets a later case pass vacuously.
ARRANGING_CALLS = frozenset({'sql', 'runtime', 'migrator', 'apply_sql_file', 'apply_migrations', 'seed'})


def source(name: str) -> str:
    return (ROOT / 'scripts' / f'{name}.py').read_text()


def lines_matching(name: str, pattern: str) -> list[int]:
    return [number for number, line in enumerate(source(name).splitlines(), start=1) if re.search(pattern, line)]


class OneException(unittest.TestCase):
    def test_each_exit_code_has_one_class(self) -> None:
        self.assertIs(toolchain.Unavailable, errors.Unavailable)
        self.assertIs(disposable_db.Unavailable, errors.Unavailable)
        self.assertIs(disposable_db.Refused, errors.Refused)
        self.assertEqual((errors.Refused.exit_code, errors.Unavailable.exit_code), (1, 2))

    def test_no_script_defines_its_own_unavailable(self) -> None:
        defined = sorted(path.relative_to(ROOT).as_posix() for path in (ROOT / 'scripts').rglob('*.py')
                         if re.search(r'^class Unavailable\b', path.read_text(), re.MULTILINE))
        self.assertEqual(defined, ['scripts/qualification/errors.py'])

    def test_a_missing_tool_in_a_mixed_script_is_caught_as_unavailable(self) -> None:
        """qualify_identity catches disposable_db's name and calls find_tools, which raises toolchain's."""
        with tempfile.TemporaryDirectory() as folder, self.assertRaises(disposable_db.Unavailable):
            toolchain.read_pins(Path(folder))


class Vocabulary(unittest.TestCase):
    def setUp(self) -> None:
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))

    def test_evidence_and_the_verifier_share_the_vocabulary(self) -> None:
        self.assertEqual(evidence.CLASSES, set(get_args(records.VerificationClass)))
        self.assertEqual(evidence.TRANSPORTS, set(get_args(records.ModelTransport)))
        self.assertEqual(set(get_args(records.VerificationClass)), {'static', 'mock', 'disposable', 'local_runtime', 'live'})
        self.assertEqual(set(get_args(records.ModelTransport)), {'none', 'mock', 'openrouter_live'})
        for step, (klass, transport) in verify.STEP_CLASSES.items():
            with self.subTest(step):
                self.assertIn(klass, evidence.CLASSES)
                self.assertIn(transport, evidence.TRANSPORTS)

    def test_a_case_record_has_the_shape_readers_parse(self) -> None:
        cases = records.Cases(model_transport='mock')
        cases.check('a case', 'expected', 'x' * 900, 1)
        record = cases.records[0]
        self.assertEqual(set(record), CASE_FIELDS)
        self.assertEqual(set(records.CaseRecord.__annotations__), CASE_FIELDS)
        self.assertEqual((record['class'], record['model_transport'], record['status'], len(record['observed'])),
                         ('disposable', 'mock', 'passed', records.OBSERVED_LIMIT))
        self.assertEqual(cases.status, 'passed')
        cases.check('another', 'expected', 3, False)
        self.assertEqual((cases.records[1]['observed'], cases.status), ('3', 'failed'))

    def test_operations_cases_name_the_scripted_model_their_step_declares(self) -> None:
        """Their fixture workers run a scripted model, as their registered steps say (SCRP-10, qualification/profiles.py)."""
        for step in PROFILES['operations'].steps:
            with self.subTest(step.id):
                self.assertEqual(verify.STEP_CLASSES[step.id], ('disposable', 'mock'))
                self.assertIn('Cases(model_transport=MODEL_TRANSPORT)', (ROOT / str(step.script)).read_text())
        self.assertEqual(qualify_operations.MODEL_TRANSPORT, 'mock')

    def test_a_written_report_round_trips(self) -> None:
        cases = records.Cases()
        cases.check('a case', 'yes', 'yes', True)
        report: records.QualificationReport = {
            'schema_version': 'autobots.fixture-qualification/v1', 'completed_at_utc': '2026-11-14T00:00:00+00:00',
            'duration_seconds': 1.0, 'status': cases.status, 'target_class': 'disposable', 'cases': cases.records,
            'not_established': ['H1']}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'nested/qualification.json'
            records.write_report(path, report)
            self.assertEqual(json.loads(path.read_text()), report)
            self.assertTrue(path.read_text().endswith('}\n'))


class SharedRunner(unittest.TestCase):
    def test_no_qualifier_replays_a_child_report_by_hand(self) -> None:
        """The runner is the only place a child's last line is parsed (SCRP-01)."""
        for name in QUALIFIERS:
            with self.subTest(name):
                self.assertEqual(lines_matching(name, r"splitlines\(\)\[-1\]\)\['cases'\]|cases\.check\(case\['id'\]"), [])

    def test_no_qualifier_writes_an_escaped_newline(self) -> None:
        for name in QUALIFIERS:
            with self.subTest(name):
                self.assertEqual(lines_matching(name, r'\\\\n'), [])

    def test_no_qualifier_discards_an_arrangement(self) -> None:
        """Each arranging statement's result is kept, so `Cases.arrange` can record it (SCRP-09)."""
        for name in QUALIFIERS:
            discarded = []
            for node in ast.walk(ast.parse(source(name))):
                if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                    function = node.value.func
                    called = function.attr if isinstance(function, ast.Attribute) else getattr(function, 'id', '')
                    if called in ARRANGING_CALLS:
                        discarded.append(node.lineno)
            with self.subTest(name):
                self.assertEqual(discarded, [])

    def test_no_identity_case_reads_a_vacuous_query(self) -> None:
        self.assertEqual(lines_matching('qualify_identity', 'where false;'), [])

    def test_the_runner_records_one_case_per_failure_kind_in_a_real_qualifier_process(self) -> None:
        """A qualifier process imports the package from its own folder, as verify.py runs it."""
        script = ('import sys\nfrom pathlib import Path\nfrom qualification.children import run_child_check\n'
                  'from qualification.records import Cases\ncases = Cases()\n'
                  "run_child_check(cases, Path(sys.argv[1]), 'gone_check.py', label='a gone check', env={}, timeout=5, err_dir=None)\n"
                  "print(cases.status, len(cases.records))\n")
        with tempfile.TemporaryDirectory() as folder:
            result = subprocess.run([sys.executable, '-c', script, folder], cwd=ROOT / 'scripts', capture_output=True,
                                    text=True, timeout=60, check=False)
        self.assertEqual((result.returncode, result.stdout.splitlines()[-1]), (0, 'failed 1'), result.stderr)



class Verdicts(unittest.TestCase):
    def test_a_qualifier_case_refuses_a_predicate_that_would_always_pass(self) -> None:
        cases = records.Cases()
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(TypeError):
                cases.check('a predicate', 'false', 'x', lambda _seen: False)
            cases.check('a verdict', 'false', 'x', False)
        self.assertEqual([(record['id'], record['status']) for record in cases.records], [('a verdict', 'failed')])


if __name__ == '__main__':
    unittest.main()
