"""R-01: every test file is run by a verification step, or is manual with a reason.

scripts/suites.py holds each step's selection. A file that no selection claims fails here, which is
how schema-value.test.ts and the offline toolchain pins went unrun before. Browser specs are claimed
through the Playwright projects that suites.BROWSER_PROJECTS lists and the runners pass (R-58).
"""
from __future__ import annotations

import json
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import harness_lib  # noqa: E402
import suites  # noqa: E402
import verify  # noqa: E402
from qualification.profiles import PROFILES  # noqa: E402

BROWSER_DIR = 'apps/web/tests/browser/'
TEST_FILES = ('apps/web/tests/unit/**/*.test.ts', 'packages/api-client/tests/**/*.test.ts',
              'tests/toolchain/test_*.py', 'tests/harness/test_*.py', 'services/agent/tests/**/test_*.py',
              'apps/web/tests/browser/**/*.spec.ts', 'tests/db/*_check.py')
# The runner that passes each project, by the suites constant naming it.
PROJECT_RUNNERS = (('scripts/qualify_web.py', 'WEB_PROJECT'), ('scripts/qualify_identity.py', 'IDENTITY_PROJECT'),
                   ('scripts/qualify_identity.py', 'ARRANGED_PROJECT'), ('scripts/qualify_identity.py', 'SLICE_PROJECT'),
                   ('scripts/qualify_release.py', 'RELEASE_PROJECT'),
                   ('scripts/persistent_install.py', 'INSTALL_CURRENT_PROJECT'))


def relative(root: Path, pattern: str) -> set[str]:
    return {path.relative_to(root).as_posix() for path in root.glob(pattern)}


def browser_projects(root: Path) -> dict[str, list[str]]:
    """Each Playwright project's spec files, relative to the browser folder, as playwright.config.ts reads them."""
    path = root / suites.BROWSER_PROJECTS
    if not path.exists():
        return {}
    projects: dict[str, list[str]] = json.loads(path.read_text())
    return projects


def pytest_paths(root: Path) -> tuple[str, ...]:
    pyproject = root / 'services/agent/pyproject.toml'
    if not pyproject.exists():
        return ()
    paths = tomllib.loads(pyproject.read_text())['tool']['pytest']['ini_options']['testpaths']
    return tuple(f'services/agent/{path}/' for path in paths)


def profile_scripts(root: Path) -> set[Path]:
    """The qualifier scripts the full, db and operations profiles run (qualification/profiles.py), and every sibling
    script or package module they import, transitively, as harness_lib walks them for the Stop hook (R-65)."""
    entries = [script for name in ('full', 'db', 'operations') for script in PROFILES[name].scripts]
    return {root / path for path in harness_lib.import_closure(root, entries)}


def unclaimed(root: Path) -> list[str]:
    """Test files under `root` that no verification step runs and that aren't manual."""
    claimed = relative(root, suites.WEB_UNIT_TESTS) | relative(root, suites.API_CLIENT_TESTS)
    claimed |= relative(root, f'tests/harness/{suites.HARNESS_PATTERN}')
    projects = browser_projects(root)
    claimed |= {f'{BROWSER_DIR}{spec}' for name in suites.PROFILE_PROJECTS for spec in projects.get(name, [])}
    offline = {name.split('.')[0] for name in suites.TOOLCHAIN_OFFLINE}
    # Only scripts a profile runs count: a check named by a live or manual qualifier runs in no profile.
    scripts = ' '.join(path.read_text() for path in sorted(profile_scripts(root)))
    left = []
    for path in sorted(set().union(*(relative(root, pattern) for pattern in TEST_FILES))):
        name = Path(path).stem
        if (path in claimed or path in suites.MANUAL
                or path.startswith(pytest_paths(root))
                or (path.startswith('tests/toolchain/') and name in offline)
                or (path.startswith('tests/db/') and name in scripts)):
            continue
        left.append(path)
    return left


class SuiteClaims(unittest.TestCase):
    def test_every_test_file_is_run_by_a_step_or_manual_with_a_reason(self) -> None:
        self.assertEqual(unclaimed(ROOT), [])

    def test_an_unclaimed_test_file_is_caught(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for path in ('apps/web/tests/unit/new.test.ts', 'apps/web/tests/unit/deep/newer.test.ts',
                         'tests/toolchain/test_scaffold_scope.py', 'tests/toolchain/test_new_pins.py',
                         'apps/web/tests/browser/composer.spec.ts', 'apps/web/tests/browser/zzz-new.spec.ts',
                         'tests/db/known_check.py', 'tests/db/new_check.py', 'tests/harness/test_new.py'):
                (root / path).parent.mkdir(parents=True, exist_ok=True)
                (root / path).write_text('')
            # The main project names composer.spec.ts, and no project names zzz-new.spec.ts.
            (root / suites.BROWSER_PROJECTS).write_text(json.dumps({suites.IDENTITY_PROJECT: ['composer.spec.ts']}))
            (root / 'scripts/qualification').mkdir(parents=True)
            # The db profile runs app_db.py, which imports runner.py, which names known_check, and a module
            # of a package, which names packaged_check.
            (root / 'scripts/app_db.py').write_text('import runner\nfrom qualification.tables import CHILDREN\n')
            (root / 'scripts/runner.py').write_text("CHECKS = ['known_check.py']\n")
            (root / 'scripts/qualification/tables.py').write_text("CHILDREN = ['packaged_check.py']\n")
            (root / 'tests/db/packaged_check.py').write_text('')
            # A live qualifier that no profile runs names live_check, so it isn't claimed.
            (root / 'tests/db/live_check.py').write_text('')
            (root / 'scripts/qualify_live.py').write_text("CHECK = 'live_check.py'\n")
            self.assertEqual(unclaimed(root), ['apps/web/tests/browser/zzz-new.spec.ts', 'tests/db/live_check.py',
                                               'tests/db/new_check.py', 'tests/toolchain/test_new_pins.py'])

    def test_each_unit_test_glob_selects_files(self) -> None:
        # Node passes an empty glob with no tests, so an emptied folder must fail here.
        for pattern in (suites.WEB_UNIT_TESTS, suites.API_CLIENT_TESTS):
            with self.subTest(pattern):
                self.assertTrue(relative(ROOT, pattern))

    def test_verify_builds_the_qualifier_steps_from_the_registry(self) -> None:
        """No script keeps its own copy of a profile's qualifiers: verify plans exactly the registry's (R-65)."""
        for name in ('db', 'operations'):
            with self.subTest(name), mock.patch('verify.find_tools'), mock.patch('verify.missing_prepared_paths', return_value=[]):
                plan, _ = verify.tool_plan(ROOT, name, None)
                self.assertEqual([step.argv[1:] for step in plan.steps], [step.argv[1:] for step in PROFILES[name].steps if step.argv])
        self.assertEqual(set(PROFILES['full'].scripts), {'scripts/generate_contracts.py', 'scripts/qualify_web.py', 'scripts/qualify_faults.py'})
        self.assertNotIn("'scripts/qualify_", (ROOT / 'scripts/verify.py').read_text())

    def test_each_spec_is_in_exactly_one_project(self) -> None:
        # One project per file, so no spec runs twice or under another runner's environment, and none is listed
        # that doesn't exist.
        listed = [spec for specs in browser_projects(ROOT).values() for spec in specs]
        on_disk = [path.removeprefix(BROWSER_DIR) for path in relative(ROOT, f'{BROWSER_DIR}**/*.spec.ts')]
        self.assertEqual(sorted(listed), sorted(on_disk))

    def test_no_project_is_empty(self) -> None:
        # Playwright runs no test for a project with no files, and the runner would report only that none ran.
        for name, specs in browser_projects(ROOT).items():
            with self.subTest(name):
                self.assertTrue(specs)

    def test_the_config_builds_each_project_from_the_list(self) -> None:
        # Otherwise the list read here could drift from what Playwright selects.
        text = (ROOT / 'apps/web/playwright.config.ts').read_text()
        self.assertIn('import projects from "./tests/browser/projects.json";', text)
        self.assertRegex(text, r'testMatch: specs\.map\(')
        self.assertRegex(text, r'projects: Object\.entries\(projects\)\.map\(')

    def test_the_projects_are_the_ones_suites_names(self) -> None:
        self.assertEqual(sorted(browser_projects(ROOT)), sorted((*suites.PROFILE_PROJECTS, *suites.MANUAL_PROJECTS)))

    def test_a_project_no_profile_runs_holds_only_manual_specs(self) -> None:
        projects = browser_projects(ROOT)
        for name in suites.MANUAL_PROJECTS:
            for spec in projects[name]:
                with self.subTest(name=name, spec=spec):
                    self.assertIn(f'{BROWSER_DIR}{spec}', suites.MANUAL)
        for name in suites.PROFILE_PROJECTS:
            for spec in projects[name]:
                with self.subTest(name=name, spec=spec):
                    self.assertNotIn(f'{BROWSER_DIR}{spec}', suites.MANUAL)

    def test_each_runner_passes_its_project(self) -> None:
        profiled = profile_scripts(ROOT)
        for script, constant in PROJECT_RUNNERS:
            with self.subTest(script=script, constant=constant):
                self.assertIn(f"'--project', {constant}", (ROOT / script).read_text())
                if getattr(suites, constant) in suites.PROFILE_PROJECTS:
                    self.assertIn(ROOT / script, profiled)

    def test_manual_files_exist_and_say_why(self) -> None:
        for path, reason in suites.MANUAL.items():
            with self.subTest(path):
                self.assertTrue((ROOT / path).is_file())
                self.assertGreater(len(reason.split()), 4)

    def test_offline_toolchain_modules_exist(self) -> None:
        for name in suites.TOOLCHAIN_OFFLINE:
            with self.subTest(name):
                self.assertTrue((ROOT / 'tests/toolchain' / f"{name.split('.')[0]}.py").is_file())


if __name__ == '__main__':
    unittest.main()
