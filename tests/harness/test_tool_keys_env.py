"""US-14.17, Decision 0024 K2 and PK-06: `make start` passes only the Tavily and Jina keys, as data.

Runs the Makefile's own TOOL_KEYS line in a shell, against fixture `.env` files in a temporary
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
    """The environment a launched process would get, with the script run as the Makefile runs it."""
    work = Path(tempfile.mkdtemp(prefix='tool-keys-env-'))
    (work / '.env').write_text(dotenv)
    line = re.search(r'^TOOL_KEYS := (.+)$', MAKEFILE, re.MULTILINE)
    assert line is not None
    command = line.group(1).replace('$$', '$').replace('$(PY)', f'{sys.executable}').replace('scripts/tool_keys_env.py', str(SCRIPT))
    shell = f'{command} env -0'
    result = subprocess.run(['/bin/sh', '-c', shell], cwd=work, env={'PATH': os.environ.get('PATH', '/usr/bin:/bin')},
                            capture_output=True, check=True)
    pairs = [item.split(b'=', 1) for item in result.stdout.split(b'\0') if b'=' in item]
    return {name.decode(): value.decode() for name, value in pairs}, work


class ToolKeysEnv(unittest.TestCase):
    def test_only_the_two_keys_are_passed_and_shell_syntax_stays_data(self):
        hostile = "tvly-fixture$(touch pwned)`touch pwned2`'\"; touch pwned3"
        env, work = launch_env(f"TAVILY_API_KEY='{hostile}'\nJINA_API_KEY=jina_fixtureOnly0001\nOPENROUTER_API_KEY=sk-or-fixture\nOTHER=1\n")
        self.assertEqual(env.get('TAVILY_API_KEY'), hostile.strip("'"))
        self.assertEqual(env.get('JINA_API_KEY'), 'jina_fixtureOnly0001')
        self.assertNotIn('OPENROUTER_API_KEY', env)
        self.assertNotIn('OTHER', env)
        self.assertEqual(sorted(path.name for path in work.iterdir()), ['.env'])

    def test_blank_keys_and_a_missing_file_pass_nothing(self):
        env, _ = launch_env('TAVILY_API_KEY=\nJINA_API_KEY=   \n')
        self.assertNotIn('TAVILY_API_KEY', env)
        self.assertNotIn('JINA_API_KEY', env)
        missing = subprocess.run([sys.executable, str(SCRIPT), '/nonexistent/.env'], capture_output=True, text=True, check=False)
        self.assertEqual((missing.returncode, missing.stdout, missing.stderr), (0, '', ''))

    def test_only_the_api_and_the_worker_get_the_keys(self):
        launches = dict(re.findall(r'^\t\$\(call launch,(\w+),(.+)\)$', MAKEFILE, re.MULTILINE))
        self.assertEqual(sorted(launches), ['api', 'web', 'worker'])
        self.assertTrue(launches['api'].endswith(',keys'))
        self.assertTrue(launches['worker'].endswith(',keys'))
        self.assertFalse(launches['web'].endswith(',keys'))
        self.assertIn('$(if $(3),$(TOOL_KEYS))', MAKEFILE)
        self.assertNotRegex(MAKEFILE, r'(?m)^\s*(set -a; )?\.\s+["\']?\.env')


if __name__ == '__main__':
    unittest.main()
