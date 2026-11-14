"""R-01: every test file is run by a verification step, or is manual with a reason.

scripts/suites.py holds each step's selection. A file that no selection claims fails here, which is
how schema-value.test.ts and the offline toolchain pins went unrun before.
"""
from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import suites  # noqa: E402

BROWSER_ROOT = 'apps/web/'
TEST_FILES = ('apps/web/tests/unit/**/*.test.ts', 'packages/api-client/tests/**/*.test.ts',
              'tests/toolchain/test_*.py', 'tests/harness/test_*.py', 'services/agent/tests/**/test_*.py',
              'apps/web/tests/browser/**/*.spec.ts', 'tests/db/*_check.py')
BROWSER_FILTERS = (*suites.WEB_SUITES, *suites.IDENTITY_SUITES, *suites.IDENTITY_TITLED_SUITES, *suites.SLICE_SUITES)


def relative(root: Path, pattern: str) -> set[str]:
    return {path.relative_to(root).as_posix() for path in root.glob(pattern)}


def pytest_paths(root: Path) -> tuple[str, ...]:
    pyproject = root / 'services/agent/pyproject.toml'
    if not pyproject.exists():
        return ()
    paths = tomllib.loads(pyproject.read_text())['tool']['pytest']['ini_options']['testpaths']
    return tuple(f'services/agent/{path}/' for path in paths)


def unclaimed(root: Path) -> list[str]:
    """Test files under `root` that no verification step runs and that aren't manual."""
    claimed = relative(root, suites.WEB_UNIT_TESTS) | relative(root, suites.API_CLIENT_TESTS)
    claimed |= relative(root, f'tests/harness/{suites.HARNESS_PATTERN}')
    offline = {name.split('.')[0] for name in suites.TOOLCHAIN_OFFLINE}
    scripts = ' '.join(path.read_text() for path in sorted((root / 'scripts').glob('*.py')))
    left = []
    for path in sorted(set().union(*(relative(root, pattern) for pattern in TEST_FILES))):
        name = Path(path).stem
        if (path in claimed or path in suites.MANUAL
                or path.startswith(pytest_paths(root))
                or (path.startswith('tests/toolchain/') and name in offline)
                or (path.startswith('tests/db/') and name in scripts)
                or (path.startswith('apps/web/tests/browser/')
                    and any(item in path.removeprefix(BROWSER_ROOT) for item in BROWSER_FILTERS))):
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
            (root / 'scripts').mkdir()
            (root / 'scripts/runner.py').write_text("CHECKS = ['known_check.py']\n")
            self.assertEqual(unclaimed(root), ['apps/web/tests/browser/zzz-new.spec.ts', 'tests/db/new_check.py',
                                               'tests/toolchain/test_new_pins.py'])

    def test_every_suite_filter_selects_a_spec(self) -> None:
        specs = [path.removeprefix(BROWSER_ROOT) for path in relative(ROOT, 'apps/web/tests/browser/**/*.spec.ts')]
        for item in BROWSER_FILTERS:
            with self.subTest(item):
                self.assertTrue(any(item in spec for spec in specs), f'{item} selects no spec')

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
