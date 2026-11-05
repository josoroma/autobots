"""Negative tests N1 to N7: `check` cannot install, and a mutation fails even when every step passes.

The conditions are arranged in one disposable copy, built once per run with fresh caches, so these
results are `disposable` evidence, except N5, whose stub steps are `mock`, and N7, which is `static`.
Bytes in `.next`, caches and bytecode may change. The scenario concerns dependencies and the lock.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import sys
import unittest

import support
from support import REPO_ROOT, toolchain


class Launchers(unittest.TestCase):
    """N7: no download-at-runtime launcher in `check` or in a package script."""

    def commands(self) -> list[str]:
        placeholder = toolchain.Tools(node_dir='/stub', python='/stub/python', uv='uv', corepack='corepack',
                                      pins=toolchain.read_pins(REPO_ROOT))
        commands = [' '.join(step.argv) for step in toolchain.check_steps(REPO_ROOT, placeholder)]
        for path in ('package.json', 'apps/web/package.json', 'packages/api-client/package.json',
                     'packages/db-types/package.json'):
            commands += json.loads((REPO_ROOT / path).read_text()).get('scripts', {}).values()
        return commands

    def test_n7_no_launcher_in_steps_or_scripts(self) -> None:
        commands = self.commands()
        self.assertGreater(len(commands), 10)
        self.assertEqual(support.launcher_violations(commands), [])

    def test_n7_fixture_of_each_launcher_fails(self) -> None:
        for command in ('uv run pytest', 'uv sync', 'uv sync --locked', 'npx eslint .', 'pnpm dlx prettier',
                        'pnpm install', 'corepack pnpm install --lockfile-only'):
            self.assertEqual(support.launcher_violations([command]), [command])

    def test_n7_bootstrap_stays_out_of_check(self) -> None:
        placeholder = toolchain.Tools(node_dir='/stub', python='/stub/python', uv='uv', corepack='corepack',
                                      pins=toolchain.read_pins(REPO_ROOT))
        ids = {step.id for step in toolchain.check_steps(REPO_ROOT, placeholder)}
        self.assertFalse(ids & {step.id for step in toolchain.bootstrap_steps(REPO_ROOT, placeholder)})
        self.assertFalse(ids & {step.id for step in toolchain.lock_steps(REPO_ROOT, placeholder)})


class NoPreparedEnvironment(unittest.TestCase):
    """N3: no environment means exit 2 before any tool runs, and nothing installed or fetched."""

    def test_n3_unprepared_copy_exits_2_and_stays_unprepared(self) -> None:
        root = support.make_copy()
        try:
            result = support.run_toolchain(root, 'check')
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn('not prepared', result.stderr)
            self.assertEqual(result.stdout, '')
            for name in ('services/agent/.venv', 'node_modules', '.corepack', '.uv'):
                self.assertFalse((root / name).exists(), name)
        finally:
            support.remove_copy(root)

    def test_versions_on_an_unprepared_copy_creates_nothing(self) -> None:
        root = support.make_copy()
        try:
            result = support.run_toolchain(root, 'versions')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            runtime = json.loads(result.stdout)['runtime']
            self.assertIsNone(runtime['pnpm']['through_corepack'])
            self.assertIsNone(runtime['node']['through_package_script'])
            for name in ('services/agent/.venv', 'node_modules', '.corepack', '.uv', '.cache'):
                self.assertFalse((root / name).exists(), name)
        finally:
            support.remove_copy(root)


class PreparedCopy(unittest.TestCase):
    """N1, N2, N4, N5 and N6 on one prepared copy. Test names set the order: drift goes last."""

    root: Path

    @classmethod
    def setUpClass(cls) -> None:
        cls.root = support.make_copy()
        try:
            support.bootstrap_copy(cls.root)
        except BaseException:
            support.remove_copy(cls.root)
            raise

    @classmethod
    def tearDownClass(cls) -> None:
        support.remove_copy(cls.root)

    def state(self) -> tuple[str, str, list[str], list[str]]:
        return (support.sha256(self.root / toolchain.UV_LOCK), support.sha256(self.root / toolchain.PNPM_LOCK),
                support.python_distributions(self.root), support.pnpm_entries(self.root))

    def edit(self, relative: Path, change) -> None:
        """Edit a manifest for one test. uv treats any later pyproject change as requiring a re-sync."""
        path = self.root / relative
        original = path.read_text()

        def restore() -> None:
            path.write_text(original)
            if relative == toolchain.PYPROJECT:
                support.bootstrap_copy(self.root)

        self.addCleanup(restore)
        path.write_text(change(original))

    def test_a_prepared_copy_checks_clean(self) -> None:
        before = self.state()
        result = support.run_toolchain(self.root, 'check')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.state(), before)

    def test_n1_stale_python_manifest(self) -> None:
        before = self.state()
        self.edit(toolchain.PYPROJECT, lambda text: text.replace('dependencies = [\n', 'dependencies = [\n  "idna==3.20",\n', 1))
        result = support.run_toolchain(self.root, 'check')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(support.failed_steps(result), ['python_lock'])
        self.assertEqual(self.state(), before)

    def test_n2_stale_node_manifest(self) -> None:
        before = self.state()
        self.edit(toolchain.WEB_PACKAGE, lambda text: text.replace('"dependencies": {\n', '"dependencies": {\n    "is-odd": "3.0.1",\n', 1))
        result = support.run_toolchain(self.root, 'check')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(support.failed_steps(result), ['node_lock'])
        self.assertEqual(self.state(), before)

    def test_n5_guard_fails_a_step_that_rewrites_a_lock(self) -> None:
        lock = self.root / toolchain.PNPM_LOCK
        original = lock.read_bytes()
        self.addCleanup(lock.write_bytes, original)
        stub = toolchain.Step('stub', (sys.executable, '-c', f"open({str(lock)!r}, 'a').write('# stub\\n')"), self.root)
        code, report = toolchain.run_guarded(self.root, [stub], support.tool_env())
        self.assertEqual(code, 1)
        self.assertEqual(report['steps'][0]['exit_code'], 0)
        self.assertIn('changed: pnpm-lock.yaml', report['guard_differences'])

    def test_n5_guard_fails_a_step_that_adds_an_installed_entry(self) -> None:
        entry = self.root / toolchain.PNPM_VIRTUAL_STORE / 'stub@1.0.0'
        self.addCleanup(lambda: entry.exists() and entry.rmdir())
        stub = toolchain.Step('stub', (sys.executable, '-c', f'import os; os.mkdir({str(entry)!r})'), self.root)
        code, report = toolchain.run_guarded(self.root, [stub], support.tool_env())
        self.assertEqual(code, 1)
        self.assertEqual(report['steps'][0]['exit_code'], 0)
        self.assertIn('changed: node_modules/.pnpm: stub@1.0.0', report['guard_differences'])

    def test_n5_guard_passes_a_step_that_changes_nothing(self) -> None:
        stub = toolchain.Step('stub', (sys.executable, '-c', ''), self.root)
        code, report = toolchain.run_guarded(self.root, [stub], support.tool_env())
        self.assertEqual((code, report['guard_differences']), (0, []))

    def test_n6_wrong_uv_pin_exits_2_with_no_download(self) -> None:
        before = self.state()
        self.edit(toolchain.PYPROJECT, lambda text: text.replace('required-version = "==0.13.6"', 'required-version = "==0.99.0"'))
        result = support.run_toolchain(self.root, 'check')
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('uv 0.99.0', result.stderr)
        self.assertEqual(result.stdout, '')
        self.assertEqual(self.state(), before)

    def test_n6_uninstalled_node_pin_exits_2_with_no_download(self) -> None:
        path = self.root / toolchain.NODE_PIN
        original = path.read_text()
        self.addCleanup(path.write_text, original)
        path.write_text('22.99.0\n')
        versions_before = sorted(p.name for p in (self.root / '.corepack/v1/pnpm').iterdir())
        for verb in ('check', 'versions'):
            result = support.run_toolchain(self.root, verb)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn('node 22.99.0', result.stderr)
        self.assertEqual(sorted(p.name for p in (self.root / '.corepack/v1/pnpm').iterdir()), versions_before)

    def test_node_is_the_pin_through_package_scripts(self) -> None:
        result = support.run_toolchain(self.root, 'versions')
        self.assertEqual(result.returncode, 0, result.stderr)
        runtime = json.loads(result.stdout)['runtime']
        self.assertEqual(runtime['node']['through_package_script'], f"v{runtime['node']['pin']}")
        self.assertEqual(runtime['pnpm']['through_corepack'], runtime['pnpm']['pin'])

    def test_zz_n4_drifted_environment_is_not_repaired(self) -> None:
        # Last, because it leaves this copy's environment changed.
        removed = support.uv_pip(self.root, 'uninstall', 'idna')
        self.assertEqual(removed.returncode, 0, removed.stderr)
        before = self.state()
        self.assertFalse([name for name in before[2] if re.match(r'idna-', name)])
        result = support.run_toolchain(self.root, 'check')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(support.failed_steps(result), ['python_env'])
        self.assertEqual(self.state(), before)


if __name__ == '__main__':
    unittest.main()
