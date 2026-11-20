"""US-17.3, Decision 0035 Y8: browser-use 1.0.6 in its own uv-locked environment under services/browser-use,
apart from the worker's lock, built into its image only from that lock, with telemetry and the update check off.

Nothing here installs, resolves or builds: it reads the project file, the two locks, the ignore files and the
Dockerfile.
"""
from __future__ import annotations

import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / 'services/browser-use'


def locked(path: Path) -> dict[str, str]:
    """Each package a uv lock resolves, by name, at its version."""
    return {package['name']: package.get('version', '') for package in tomllib.loads(path.read_text())['package']}


class Lock(unittest.TestCase):
    def test_the_project_pins_browser_use_1_0_6_on_python_3_12(self) -> None:
        project = tomllib.loads((PROJECT / 'pyproject.toml').read_text())
        self.assertEqual(project['project']['dependencies'], ['browser-use==1.0.6'])
        self.assertEqual(project['project']['requires-python'], '>=3.12,<3.13')
        self.assertIs(project['tool']['uv']['package'], False)

    def test_its_lock_resolves_browser_use_1_0_6_apart_from_the_workers_lock(self) -> None:
        own = locked(PROJECT / 'uv.lock')
        self.assertEqual(own['browser-use'], '1.0.6')
        self.assertNotIn('browser-use', locked(ROOT / 'services/agent/uv.lock'))

    def test_its_local_environment_is_ignored(self) -> None:
        ignored = (PROJECT / '.gitignore').read_text().splitlines()
        self.assertIn('.venv/', ignored)

    def test_the_image_installs_only_what_the_lock_names_with_telemetry_off(self) -> None:
        dockerfile = (ROOT / 'infra/browser/browser-use.Dockerfile').read_text()
        self.assertIn('uv sync --frozen --no-dev --no-install-project', dockerfile)
        self.assertIn('UV_PYTHON_DOWNLOADS=never', dockerfile)
        for name in ('ANONYMIZED_TELEMETRY=false', 'BH_TELEMETRY=0', 'BROWSER_USE_NO_UPDATE_CHECK=1'):
            self.assertIn(name, dockerfile)
        self.assertRegex(dockerfile, r'(?m)^USER pwuser$')
        instructions = '\n'.join(line for line in dockerfile.splitlines() if not line.startswith('#'))
        self.assertNotRegex(instructions, r'(?i)browser_use_api_key|sensitive_data|cloud')

    def test_the_runner_keeps_vision_and_the_judge_off_and_uses_no_cloud(self) -> None:
        runner = (PROJECT / 'runner.py').read_text()
        for setting in ('use_vision=False', 'judge=False', 'cdp_url=spec["cdp_url"]', 'base_url=spec["base_url"]'):
            self.assertIn(setting, runner)
        self.assertNotRegex(runner, r'sensitive_data|use_cloud|ChatBrowserUse|Browser\(\s*["\']cloud')


if __name__ == '__main__':
    unittest.main()
