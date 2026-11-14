"""Task 3.3 and check T1.3: a fresh-cache bootstrap reproduces the prepared tree from its locks.

`disposable` evidence on this Mac only. It needs the real tree bootstrapped, and registries
reachable for the copy. Neither absence is a skip: each fails the test.
"""
from __future__ import annotations

import unittest
from pathlib import Path

import support
from support import REPO_ROOT, toolchain


def freeze(root: Path) -> list[str]:
    """Installed Python set, without the project's own editable line, whose path differs per tree."""
    result = support.uv_pip(root, 'freeze')
    if result.returncode != 0:
        raise AssertionError(f'uv pip freeze failed: {result.stderr[-2000:]}')
    return sorted(line for line in result.stdout.splitlines()
                  if line.strip() and not line.startswith('-e ') and not line.startswith('autobots'))


class FreshBootstrap(unittest.TestCase):
    root: Path

    @classmethod
    def setUpClass(cls) -> None:
        cls.root = support.make_copy()
        try:
            for name in ('.uv', '.corepack', '.pnpm-store', '.cache', 'node_modules', 'services/agent/.venv'):
                if (cls.root / name).exists():
                    raise AssertionError(f'a fresh copy already held {name}')
            support.bootstrap_copy(cls.root)
        except BaseException:
            support.remove_copy(cls.root)
            raise

    @classmethod
    def tearDownClass(cls) -> None:
        support.remove_copy(cls.root)

    def test_locks_are_unchanged_and_equal_the_real_tree(self) -> None:
        for lock in (toolchain.UV_LOCK, toolchain.PNPM_LOCK):
            self.assertEqual(support.sha256(self.root / lock), support.sha256(REPO_ROOT / lock), lock)

    def test_python_set_equals_the_real_tree(self) -> None:
        installed = freeze(self.root)
        self.assertGreater(len(installed), 50)
        self.assertEqual(installed, freeze(REPO_ROOT))

    def test_node_set_equals_the_real_tree(self) -> None:
        installed = support.pnpm_entries(self.root)
        self.assertGreater(len(installed), 50)
        self.assertEqual(installed, support.pnpm_entries(REPO_ROOT))

    def test_check_passes_in_the_copy(self) -> None:
        result = support.run_toolchain(self.root, 'check')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
