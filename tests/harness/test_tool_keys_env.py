"""US-14.17, Decision 0024 K2 and K7 and PK-06: `make start` passes only the Tavily and Jina keys,
the GitHub repository and token (Decision 0025 V5) and the exact browsing switch, as data.

Builds the environment scripts/local_app.py gives a launched process from fixture `.env` files in a temporary
directory, so nothing reads the repository's real `.env`, and checks that the Makefile asks for the keys only for
the API and the worker (R-65 moved the launch out of Makefile shell).
"""
from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts/tool_keys_env.py'
MAKEFILE = (ROOT / 'Makefile').read_text()
sys.path.insert(0, str(ROOT / 'scripts'))
import local_app  # noqa: E402
from harness_support import run_cli  # noqa: E402


class ToolKeysEnv(unittest.TestCase):
    def launch_env(self, dotenv: str) -> tuple[dict[str, str], Path]:
        """The environment a launched process would get, with the keys asked for, from a fixture `.env` in a folder
        the test removes when it ends (THRN-17)."""
        work = Path(self.enterContext(tempfile.TemporaryDirectory(prefix='tool-keys-env-')))
        (work / '.env').write_text(dotenv)
        env = local_app.launch_env({'PATH': '/usr/bin:/bin'}, 'AUTOBOTS_DATABASE_URL=postgresql://arranged\n',
                                   dotenv=(work / '.env').read_text(), node_bin='', inference='')
        return env, work

    def test_the_browsing_switch_passes_only_as_exactly_enabled(self):
        """Decision 0024 K7: nothing else reaches the process, and no other value turns it on."""
        env, _ = self.launch_env('AUTOBOTS_BROWSER_EXECUTOR=enabled\nAUTOBOTS_WORKER_INFERENCE=enabled\n')
        self.assertEqual(env.get('AUTOBOTS_BROWSER_EXECUTOR'), 'enabled')
        # Inference stays as the Makefile sets it, empty and so off, whatever the file says.
        self.assertEqual(env['AUTOBOTS_WORKER_INFERENCE'], '')
        for value in ('', 'Enabled', 'true', "enabled'; touch pwned; '", '1'):
            env, work = self.launch_env(f'AUTOBOTS_BROWSER_EXECUTOR={value}\n')
            self.assertNotIn('AUTOBOTS_BROWSER_EXECUTOR', env, value)
            self.assertEqual(sorted(path.name for path in work.iterdir()), ['.env'])

    def test_only_the_listed_variables_are_passed_and_shell_syntax_stays_data(self):
        hostile = "tvly-fixture$(touch pwned)`touch pwned2`'\"; touch pwned3"
        env, work = self.launch_env(f"TAVILY_API_KEY='{hostile}'\nJINA_API_KEY=jina_fixtureOnly0001\nOPENROUTER_API_KEY=sk-or-fixture\nOTHER=1\n"
                               "GITHUB_REPOSITORY=owner/throwaway\nGITHUB_TOKEN='github_pat_fixture; touch pwned4'\n"
                               "SERPAPI_API_KEY='serpapi_fixture; touch pwned5'\n")
        self.assertEqual(env.get('TAVILY_API_KEY'), hostile.strip("'"))
        self.assertEqual(env.get('JINA_API_KEY'), 'jina_fixtureOnly0001')
        self.assertEqual(env.get('SERPAPI_API_KEY'), 'serpapi_fixture; touch pwned5')
        self.assertEqual(env.get('GITHUB_REPOSITORY'), 'owner/throwaway')
        self.assertEqual(env.get('GITHUB_TOKEN'), 'github_pat_fixture; touch pwned4')
        self.assertNotIn('OPENROUTER_API_KEY', env)
        self.assertNotIn('OTHER', env)
        self.assertEqual(sorted(path.name for path in work.iterdir()), ['.env'])

    def test_the_command_quotes_each_value_for_a_shell(self):
        hostile = "tvly-fixture$(touch pwned)`touch pwned2`'\"; touch pwned3"
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            (work / '.env').write_text(f"TAVILY_API_KEY='{hostile}'\nOTHER=1\n")
            printed = run_cli([sys.executable, str(SCRIPT), '.env'], cwd=work, text=True, check=True).stdout
            shell = run_cli(['/bin/sh', '-c', f'{printed}\nprintf %s "$TAVILY_API_KEY"'], cwd=work, text=True, check=True)
            self.assertEqual(shell.stdout, hostile.strip("'"))
            self.assertEqual(sorted(path.name for path in work.iterdir()), ['.env'])
        self.assertNotIn('OTHER', printed)

    def test_blank_keys_and_a_missing_file_pass_nothing(self):
        env, _ = self.launch_env('TAVILY_API_KEY=\nJINA_API_KEY=   \nSERPAPI_API_KEY=\nGITHUB_REPOSITORY=\nGITHUB_TOKEN= \n')
        for name in ('TAVILY_API_KEY', 'JINA_API_KEY', 'SERPAPI_API_KEY', 'GITHUB_REPOSITORY', 'GITHUB_TOKEN'):
            self.assertNotIn(name, env)
        missing = run_cli([sys.executable, str(SCRIPT), '/nonexistent/.env'], text=True)
        self.assertEqual((missing.returncode, missing.stdout, missing.stderr), (0, '', ''))

    def test_only_the_api_and_the_worker_get_the_keys(self):
        launches = dict(re.findall(r'^\t@\$\(LAUNCH\) (\w+) (.+)$', MAKEFILE, re.MULTILINE))
        self.assertEqual(sorted(launches), ['api', 'web', 'worker'])
        self.assertIn('--keys .env --', launches['api'])
        self.assertIn('--keys .env', launches['worker'])
        self.assertNotIn('--keys', launches['web'])
        self.assertNotRegex(MAKEFILE, r'(?m)^\s*(set -a; )?\.\s+["\']?\.env')


if __name__ == '__main__':
    unittest.main()
