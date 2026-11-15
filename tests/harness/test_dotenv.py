"""The scripts' one env-file reader, harness_lib.parse_dotenv (refactor plan R-65, SCRP-16).

`app` mode must read as the service's own parser does, on the same fixtures. `verbatim` mode keeps how the install
has always read stack.env and the file its values come from, so this refactor changes nothing the persistent install
is given: the four quoted MAILER_URLPATHS_* values keep their quotes, an open question for the owner.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import harness_lib  # noqa: E402
import local_backup  # noqa: E402
import persistent_install  # noqa: E402
import supabase_stack  # noqa: E402

# The service's parser, loaded from its file alone: it needs only the standard library.
spec = importlib.util.spec_from_file_location('service_precedence', ROOT / 'services/agent/src/autobots/application/credentials/precedence.py')
assert spec is not None and spec.loader is not None
service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service)

FIXTURES = (
    'PLAIN=value\n',
    'export EXPORTED=value\n',
    "SINGLE='quoted value'\nDOUBLE=\"double # not a comment\"\n",
    'TRAILING=value # a comment\nHASH=value#kept\n',
    '# a comment\n\n   \nNO_EQUALS\n=nameless\n',
    "HOSTILE='tvly-fixture$(touch pwned)`touch pwned2`'\n",
    'SPACED = spaced value \nUNMATCHED="open\nMIXED=\'one"\n',
    'TAVILY_API_KEY=\nJINA_API_KEY=   \nREPEATED=first\nREPEATED=second\n',
)
MAILER = ('MAILER_URLPATHS_CONFIRMATION', 'MAILER_URLPATHS_INVITE', 'MAILER_URLPATHS_RECOVERY', 'MAILER_URLPATHS_EMAIL_CHANGE')


class AppMode(unittest.TestCase):
    def test_it_reads_each_fixture_as_the_service_does(self) -> None:
        for text in FIXTURES:
            with self.subTest(text=text):
                self.assertEqual(harness_lib.parse_dotenv(text, 'app'), service.parse_dotenv(text))

    def test_it_reads_the_repositorys_example_as_the_service_does(self) -> None:
        for path in (ROOT / '.env.example', ROOT / 'infra/supabase/upstream/env.example'):
            if path.is_file():
                with self.subTest(path.name):
                    text = path.read_text()
                    self.assertEqual(harness_lib.parse_dotenv(text, 'app'), service.parse_dotenv(text))


class VerbatimMode(unittest.TestCase):
    def test_the_install_reads_its_four_quoted_values_as_it_always_has(self) -> None:
        """Pinned: stripping these quotes would recreate the install's auth container at its next start."""
        defaults = supabase_stack.example_defaults(ROOT)
        for name in MAILER:
            with self.subTest(name):
                self.assertEqual(defaults[name], '"/auth/v1/verify"')
        with tempfile.TemporaryDirectory() as folder:
            stack_env = Path(folder) / 'stack.env'
            stack_env.write_text(''.join(f'{name}={value}\n' for name, value in defaults.items()))
            read = persistent_install.read_values(stack_env)
            self.assertEqual(read, defaults)
            self.assertEqual(local_backup.parse_env(stack_env.read_text()), defaults)

    def test_it_keeps_every_value_as_written(self) -> None:
        self.assertEqual(harness_lib.parse_dotenv("A='x'\nexport B=y # z\n C = \"w\" \n", 'verbatim'),
                         {'A': "'x'", 'export B': 'y # z', 'C': '"w"'})

    def test_a_mode_must_be_named(self) -> None:
        with self.assertRaises(TypeError):
            harness_lib.parse_dotenv('A=1\n')  # type: ignore[call-arg]  # the mode is required on purpose


class NeverPrints(unittest.TestCase):
    def test_no_value_reaches_stdout_or_stderr_whatever_the_input(self) -> None:
        planted = 'sk-or-v1-planted-dotenv-value'
        for mode in ('app', 'verbatim'):
            for text in (f'KEY={planted}\n', f'KEY="{planted}\n', f'{planted}\n', f'=\n=={planted}\n\x00{planted}'):
                with self.subTest(mode=mode, text=text), contextlib.redirect_stdout(io.StringIO()) as out, \
                        contextlib.redirect_stderr(io.StringIO()) as err:
                    harness_lib.parse_dotenv(text, mode)  # type: ignore[arg-type]  # each mode by name
                self.assertEqual((out.getvalue(), err.getvalue()), ('', ''))


class OneReader(unittest.TestCase):
    def test_no_script_splits_env_lines_by_hand(self) -> None:
        """The three hand-written loops were the same split on '=' (SCRP-16)."""
        for path in sorted(path for path in (ROOT / 'scripts').glob('*.py') if path.name != 'harness_lib.py'):
            with self.subTest(path.name):
                self.assertNotIn("name, _, value = line.partition('=')", path.read_text())
                self.assertNotIn("name, value = line.split('=', 1)", path.read_text())


if __name__ == '__main__':
    unittest.main()
