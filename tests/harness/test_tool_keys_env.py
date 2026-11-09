"""US-14.17, Decision 0024 K2 and K7 and PK-06: `make start` passes only the Tavily and Jina keys,
the GitHub repository and token (Decision 0025 V5) and the exact browsing switch, as data.

Runs the Makefile's own TOOL_KEYS and BROWSER_SWITCH lines in a shell, against fixture `.env` files in a temporary
directory, so nothing reads the repository's real `.env`.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts/tool_keys_env.py'
MAKEFILE = (ROOT / 'Makefile').read_text()


def launch_env(dotenv: str) -> tuple[dict[str, str], Path]:
    """The environment a launched process would get, with both lines run as the Makefile runs them."""
    work = Path(tempfile.mkdtemp(prefix='tool-keys-env-'))
    (work / '.env').write_text(dotenv)
    commands = []
    for name in ('TOOL_KEYS', 'BROWSER_SWITCH'):
        line = re.search(rf'^{name} := (.+)$', MAKEFILE, re.MULTILINE)
        assert line is not None
        commands.append(line.group(1).replace('$$', '$').replace('$(PY)', f'{sys.executable}').replace('scripts/tool_keys_env.py', str(SCRIPT)))
    shell = f'{" ".join(commands)} env -0'
    result = subprocess.run(['/bin/sh', '-c', shell], cwd=work, env={'PATH': os.environ.get('PATH', '/usr/bin:/bin')},
                            capture_output=True, check=True)
    pairs = [item.split(b'=', 1) for item in result.stdout.split(b'\0') if b'=' in item]
    return {name.decode(): value.decode() for name, value in pairs}, work


class ToolKeysEnv(unittest.TestCase):
    def test_the_browsing_switch_passes_only_as_exactly_enabled(self):
        """Decision 0024 K7: nothing else reaches the process, and no other value turns it on."""
        env, _ = launch_env('AUTOBOTS_BROWSER_EXECUTOR=enabled\nAUTOBOTS_WORKER_INFERENCE=enabled\n')
        self.assertEqual(env.get('AUTOBOTS_BROWSER_EXECUTOR'), 'enabled')
        self.assertNotIn('AUTOBOTS_WORKER_INFERENCE', env)
        for value in ('', 'Enabled', 'true', "enabled'; touch pwned; '", '1'):
            env, work = launch_env(f'AUTOBOTS_BROWSER_EXECUTOR={value}\n')
            self.assertNotIn('AUTOBOTS_BROWSER_EXECUTOR', env, value)
            self.assertEqual(sorted(path.name for path in work.iterdir()), ['.env'])

    def test_only_the_listed_variables_are_passed_and_shell_syntax_stays_data(self):
        hostile = "tvly-fixture$(touch pwned)`touch pwned2`'\"; touch pwned3"
        env, work = launch_env(f"TAVILY_API_KEY='{hostile}'\nJINA_API_KEY=jina_fixtureOnly0001\nOPENROUTER_API_KEY=sk-or-fixture\nOTHER=1\n"
                               "GITHUB_REPOSITORY=owner/throwaway\nGITHUB_TOKEN='github_pat_fixture; touch pwned4'\n")
        self.assertEqual(env.get('TAVILY_API_KEY'), hostile.strip("'"))
        self.assertEqual(env.get('JINA_API_KEY'), 'jina_fixtureOnly0001')
        self.assertEqual(env.get('GITHUB_REPOSITORY'), 'owner/throwaway')
        self.assertEqual(env.get('GITHUB_TOKEN'), 'github_pat_fixture; touch pwned4')
        self.assertNotIn('OPENROUTER_API_KEY', env)
        self.assertNotIn('OTHER', env)
        self.assertEqual(sorted(path.name for path in work.iterdir()), ['.env'])

    def test_blank_keys_and_a_missing_file_pass_nothing(self):
        env, _ = launch_env('TAVILY_API_KEY=\nJINA_API_KEY=   \nGITHUB_REPOSITORY=\nGITHUB_TOKEN= \n')
        for name in ('TAVILY_API_KEY', 'JINA_API_KEY', 'GITHUB_REPOSITORY', 'GITHUB_TOKEN'):
            self.assertNotIn(name, env)
        missing = subprocess.run([sys.executable, str(SCRIPT), '/nonexistent/.env'], capture_output=True, text=True, check=False)
        self.assertEqual((missing.returncode, missing.stdout, missing.stderr), (0, '', ''))

    def test_only_the_api_and_the_worker_get_the_keys(self):
        launches = dict(re.findall(r'^\t\$\(call launch,(\w+),(.+)\)$', MAKEFILE, re.MULTILINE))
        self.assertEqual(sorted(launches), ['api', 'web', 'worker'])
        self.assertTrue(launches['api'].endswith(',keys'))
        self.assertTrue(launches['worker'].endswith(',keys'))
        self.assertFalse(launches['web'].endswith(',keys'))
        self.assertIn('$(if $(3),$(TOOL_KEYS) $(BROWSER_SWITCH))', MAKEFILE)
        self.assertNotRegex(MAKEFILE, r'(?m)^\s*(set -a; )?\.\s+["\']?\.env')


if __name__ == '__main__':
    unittest.main()
