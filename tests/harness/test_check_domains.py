"""Script domains come from what each profile's scripts import, so an edit to a helper a qualifier imports needs that
profile's report (refactor plan R-65, SCRP-06). Derivation only adds a domain to the static lists; it never removes
one. No profile runs here."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import harness_lib  # noqa: E402
import verify  # noqa: E402
from qualification import profiles  # noqa: E402
from qualification.profiles import PROFILES  # noqa: E402

spec = importlib.util.spec_from_file_location('autobots_hook_domains', ROOT / '.claude/hooks/dispatch.py')
assert spec is not None and spec.loader is not None
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


def write(root: Path, files: dict[str, str]) -> None:
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text)


class RealTree(unittest.TestCase):
    def test_everything_the_db_profile_imports_is_a_database_change(self) -> None:
        closure = harness_lib.import_closure(ROOT, PROFILES['db'].scripts)
        derived = harness_lib.derived_domains(ROOT)
        self.assertIn('scripts/qualification/children.py', closure)
        missing = sorted(path for path in closure if 'db' not in harness_lib.check_domains(path, derived=derived))
        self.assertEqual(missing, [])

    def test_the_finding_s_examples_now_need_db(self) -> None:
        """SCRP-06: these were on the db profile's import path and mapped to python and web, or harness only."""
        derived = harness_lib.derived_domains(ROOT)
        for path in ('scripts/qualify_web.py', 'scripts/toolchain.py', 'scripts/live_goal.py', 'scripts/suites.py'):
            with self.subTest(path):
                self.assertIn('db', harness_lib.check_domains(path, derived=derived))

    def test_derivation_never_removes_a_domain(self) -> None:
        derived = harness_lib.derived_domains(ROOT)
        for path in sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / 'scripts').rglob('*.py') if '__pycache__' not in p.parts):
            with self.subTest(path):
                self.assertLessEqual(harness_lib.check_domains(path) - {'harness'}, harness_lib.check_domains(path, derived=derived))

    def test_what_the_verifier_imports_needs_every_application_profile(self) -> None:
        derived = harness_lib.derived_domains(ROOT)
        for path in harness_lib.import_closure(ROOT, ['scripts/verify.py']):
            with self.subTest(path):
                self.assertLessEqual({'python', 'web', 'db'}, harness_lib.check_domains(path, derived=derived))


class Fixture(unittest.TestCase):
    """A checkout whose db step imports a helper only inside a function, and a package module."""

    def setUp(self) -> None:
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name).resolve()
        write(self.root, {'scripts/app_db.py': 'def qualify():\n    import helper\n    from tables.rows import ROWS\n',
                          'scripts/helper.py': 'import transitive\n',
                          'scripts/transitive.py': '',
                          'scripts/tables/__init__.py': '',
                          'scripts/tables/rows.py': 'ROWS = 1\n',
                          'scripts/unrelated.py': '',
                          'scripts/broken.py': 'def (:\n'})

    def test_a_helper_a_db_step_imports_needs_db(self) -> None:
        for path in ('scripts/helper.py', 'scripts/transitive.py', 'scripts/tables/rows.py', 'scripts/tables/__init__.py'):
            with self.subTest(path):
                self.assertEqual(harness_lib.check_domains(path, self.root), {'db', 'repo_python'})
        self.assertEqual(harness_lib.check_domains('scripts/unrelated.py', self.root), {'harness', 'repo_python'})

    def test_without_the_import_it_needs_only_the_harness(self) -> None:
        (self.root / 'scripts/app_db.py').write_text('def qualify():\n    pass\n')
        self.assertEqual(harness_lib.check_domains('scripts/helper.py', self.root), {'harness', 'repo_python'})

    def test_a_file_that_does_not_parse_is_kept_in_the_closure(self) -> None:
        (self.root / 'scripts/app_db.py').write_text('import broken\n')
        self.assertIn('scripts/broken.py', harness_lib.import_closure(self.root, ['scripts/app_db.py']))
        self.assertEqual(harness_lib.check_domains('scripts/broken.py', self.root), {'db', 'repo_python'})

    def test_the_hook_names_the_db_profile_for_a_helper(self) -> None:
        response = hook.handle(self.root, {'hook_event_name': 'PostToolUse', 'tool_name': 'Edit',
                                           'tool_input': {'file_path': str(self.root / 'scripts/helper.py')}})
        context = response['hookSpecificOutput']['additionalContext']
        self.assertIn('Affected check domains: db, repo_python.', context)
        self.assertIn('--profile fast, then python3.12 scripts/verify.py --profile db', context)

    def test_fast_selects_by_the_derived_domains_too(self) -> None:
        steps = sorted(profiles.FULL_CHECKS)
        self.assertEqual(verify.selected_steps('fast', steps, ['scripts/helper.py'], self.root), set(verify.REPO_PYTHON_STEPS))

    def test_stop_asks_for_a_db_report_after_a_helper_changes(self) -> None:
        derived = harness_lib.derived_domains(self.root)
        manifest = harness_lib.input_manifest(self.root)
        self.assertTrue(harness_lib.needs_profile(self.root, ('db',), {'db'}, manifest=manifest, derived=derived))
        # With no db step left, nothing here is a database change.
        (self.root / 'scripts/app_db.py').unlink()
        self.assertFalse(harness_lib.needs_profile(self.root, ('db',), {'db'}, derived=harness_lib.derived_domains(self.root)))


if __name__ == '__main__':
    unittest.main()
