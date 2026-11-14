"""R-07, STD-48: every name that tests/ and scripts/ import from `autobots` exists in the service.

The database checks run only inside Docker, so a renamed service function used to fail about ten
minutes into a db run. Here it fails in the harness, with stdlib `ast` and no service import.
"""
from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'services/agent/src'


def _top_level(nodes: list[ast.stmt]) -> set[str]:
    names: set[str] = set()
    for node in nodes:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names |= {target.id for target in node.targets if isinstance(target, ast.Name)}
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, ast.TypeAlias):
            names.add(node.name.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names |= {(alias.asname or alias.name).split('.')[0] for alias in node.names}
        elif isinstance(node, ast.If):
            names |= _top_level(node.body) | _top_level(node.orelse)
        elif isinstance(node, ast.Try):
            names |= _top_level(node.body) | _top_level(node.orelse) | _top_level(node.finalbody)
            for handler in node.handlers:
                names |= _top_level(handler.body)
    return names


def defined(source: Path, module: str) -> set[str] | None:
    """The names a module defines, plus its submodules if it is a package. None if it doesn't exist."""
    base = source / module.replace('.', '/')
    file = base.with_suffix('.py') if base.with_suffix('.py').is_file() else base / '__init__.py'
    if not file.is_file():
        return None
    names = _top_level(ast.parse(file.read_text()).body)
    if file.name == '__init__.py':
        names |= {child.stem for child in base.glob('*.py')} | {child.name for child in base.iterdir() if child.is_dir()}
    return names


def missing(files: list[Path], source: Path, root: Path) -> list[str]:
    problems = []
    for path in files:
        for node in ast.walk(ast.parse(path.read_text())):
            if not (isinstance(node, ast.ImportFrom) and node.module and node.module.split('.')[0] == 'autobots'):
                continue
            names = defined(source, node.module)
            where = f'{path.relative_to(root)}:{node.lineno}'
            if names is None:
                problems.append(f'{where}: no module {node.module}')
                continue
            problems += [f'{where}: {node.module} has no {alias.name}' for alias in node.names
                         if alias.name != '*' and alias.name not in names]
    return problems


def repository_python(root: Path) -> list[Path]:
    return sorted(path for folder in ('scripts', 'tests') for path in (root / folder).rglob('*.py')
                  if 'faults' not in path.relative_to(root).parts)


class ImportContract(unittest.TestCase):
    def test_every_imported_service_name_exists(self) -> None:
        files = repository_python(ROOT)
        self.assertGreater(sum('autobots' in path.read_text() for path in files), 40, 'the importers have moved')
        self.assertEqual(missing(files, SOURCE, ROOT), [])

    def test_a_renamed_name_is_caught(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            package = root / 'src/autobots/application'
            package.mkdir(parents=True)
            (root / 'src/autobots/__init__.py').write_text('')
            (package / '__init__.py').write_text('')
            (package / 'runs.py').write_text('from typing import Any\n\ndef admit_run() -> None: ...\nLIMIT = 3\n')
            check = root / 'tests/db/run_check.py'
            check.parent.mkdir(parents=True)
            check.write_text('from autobots.application.runs import admit_run, LIMIT, start_run\n'
                             'from autobots.application import runs\nfrom autobots.adapters.gone import x\n')
            self.assertEqual(missing([check], root / 'src', root),
                             ['tests/db/run_check.py:1: autobots.application.runs has no start_run',
                              'tests/db/run_check.py:3: no module autobots.adapters.gone'])


if __name__ == '__main__':
    unittest.main()
