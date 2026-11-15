"""One list of secret-file names, in harness_lib, which the input manifest uses, held equal to the hook's own copy
(refactor plan R-65, SCRP-13). The hook keeps its list, since only its domain derivation changed in R-65."""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import harness_lib  # noqa: E402
import persistent_install  # noqa: E402

spec = importlib.util.spec_from_file_location('autobots_hook_secrets', ROOT / '.claude/hooks/dispatch.py')
assert spec is not None and spec.loader is not None
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)

NAMES = sorted({*harness_lib.SECRET_FILE_NAMES, '.env', '.env.local', '.ENV', '.Env.Local', 'Master.Key', 'STACK.ENV'})
NOT_SECRET = ('.env.example', 'environment.md', 'stack.env.example', 'master.key.md', 'notes.env.txt')


class OneList(unittest.TestCase):
    def test_the_hook_and_the_shared_list_agree_on_every_name(self) -> None:
        for name in (*NAMES, *NOT_SECRET):
            with self.subTest(name):
                self.assertEqual(hook.is_secret(Path(name)), harness_lib.is_secret_name(name))

    def test_the_hook_refuses_every_listed_name(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            for name in NAMES:
                with self.subTest(name):
                    self.assertIsNotNone(hook.guard(Path(folder), 'Read', {'file_path': name}))

    def test_no_listed_name_is_hashed_into_a_report(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in NAMES:
                (root / 'services/agent' / name).parent.mkdir(parents=True, exist_ok=True)
                (root / 'services/agent' / name).write_text('PRIVATE=1\n')
            (root / 'services/agent/code.py').write_text('x = 1\n')
            self.assertEqual(sorted(harness_lib.input_manifest(root)), ['services/agent/code.py'])

    def test_the_install_directory_is_one_the_hook_refuses(self) -> None:
        folded = f'{persistent_install.DEFAULT_DIR.as_posix().casefold()}/'
        self.assertTrue(any(marker in folded for marker in harness_lib.INSTALL_MARKERS))
        self.assertIsNotNone(hook.guard(ROOT, 'Read', {'file_path': str(persistent_install.DEFAULT_DIR / 'install.json')}))


if __name__ == '__main__':
    unittest.main()
