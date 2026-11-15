"""R-07: repository Python (scripts, tests and the hooks) has its own check domain and steps."""
from __future__ import annotations

import configparser
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import harness_lib  # noqa: E402
import toolchain  # noqa: E402
import verify  # noqa: E402
from qualification import profiles  # noqa: E402

# The hook's trust boundary, which mypy checks strictly (STD-48).
# The hook's trust boundary, the runner that records every qualifier's child checks (R-39) and the
# paid-run session that guards real spend (R-23).
TRUST_BOUNDARY = {'.claude/hooks/dispatch.py', 'scripts/harness_lib.py', 'scripts/verify.py', 'scripts/specs.py',
                  'scripts/evidence.py', 'scripts/toolchain.py', 'scripts/qualification/', 'scripts/paid_run.py',
                  'scripts/local_app.py'}


class RepositoryPython(unittest.TestCase):
    def test_scripts_tests_and_hooks_are_repository_python(self) -> None:
        for path in ('scripts/verify.py', 'scripts/qualify_backup.py', 'tests/harness/test_hooks.py',
                     'tests/db/memory_check.py', 'tests/toolchain/support.py', '.claude/hooks/dispatch.py'):
            with self.subTest(path):
                self.assertIn('repo_python', harness_lib.check_domains(path))
        for path in ('tests/faults/python/bad_lint/module.py', 'scripts/README.md', 'docs/note.md',
                     'services/agent/src/autobots/api/app.py', 'apps/web/lib/bff.ts'):
            with self.subTest(path):
                self.assertNotIn('repo_python', harness_lib.check_domains(path))

    def test_the_gate_configuration_is_an_input_of_what_it_gates(self) -> None:
        # The review of wave 0: weakening a gate's configuration must make its reports stale.
        manifest = harness_lib.input_manifest(ROOT)
        for path, domains in (('ruff.toml', {'repo_python'}), ('mypy.ini', {'repo_python'}),
                              ('.prettierrc.json', {'web'})):
            with self.subTest(path):
                self.assertIn(path, manifest)
                self.assertEqual(harness_lib.check_domains(path), domains)
                chosen = verify.selected_steps('fast', sorted(profiles.FULL_CHECKS), [path])
                expected = profiles.WEB_STEPS if 'web' in domains else profiles.REPO_PYTHON_STEPS
                self.assertTrue(expected <= chosen)

    def test_fast_runs_the_repository_steps_for_those_files(self) -> None:
        step_ids = sorted(profiles.FULL_CHECKS)
        self.assertEqual(verify.selected_steps('fast', step_ids, ['tests/harness/test_hooks.py']),
                         set(profiles.REPO_PYTHON_STEPS))
        self.assertTrue(profiles.REPO_PYTHON_STEPS <= verify.selected_steps('fast', step_ids, ['scripts/verify.py']))
        self.assertTrue(profiles.REPO_PYTHON_STEPS <= verify.selected_steps('fast', step_ids, None))
        self.assertFalse(profiles.REPO_PYTHON_STEPS & verify.selected_steps('fast', step_ids, ['docs/note.md']))
        self.assertTrue(profiles.REPO_PYTHON_STEPS <= profiles.FULL_CHECKS)

    def test_the_steps_run_prepared_binaries_from_the_root_and_install_nothing(self) -> None:
        tools = toolchain.Tools(node_dir='/stub', python='/stub/python', uv='uv', corepack='corepack',
                                pins=toolchain.read_pins(ROOT))
        steps = {step.id: step for step in toolchain.check_steps(ROOT, tools)}
        for name, binary in (('repo_ruff_check', 'ruff'), ('repo_mypy', 'mypy')):
            with self.subTest(name):
                step = steps[name]
                self.assertEqual(Path(step.argv[0]), ROOT / toolchain.VENV / 'bin' / binary)
                self.assertEqual(step.cwd, ROOT)
                self.assertFalse({'install', 'sync', 'add', '--fix'} & set(step.argv))

    def test_mypy_checks_the_trust_boundary_strictly(self) -> None:
        config = configparser.ConfigParser()
        config.read(ROOT / 'mypy.ini')
        self.assertEqual(config['mypy']['strict'], 'True')
        files = {item.strip() for item in config['mypy']['files'].split(',')}
        self.assertEqual(files, TRUST_BOUNDARY)


if __name__ == '__main__':
    unittest.main()
