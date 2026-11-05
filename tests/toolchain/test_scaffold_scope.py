"""Make "minimal" and "non-feature" checkable: task 2.5 and check T1.6.

The Anthropic and Google SDKs are locked only because deepagents 0.7.32 requires both adapters.
The user decided on 2026-11-05 that owned code never imports them, and this file enforces that.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
import unittest

from support import REPO_ROOT, git_paths

SCAFFOLD_ROOTS = ('apps/', 'contracts/', 'packages/', 'services/')
ALLOWED_PATHS = {
    'apps/web/app/layout.tsx',
    'apps/web/app/page.tsx',
    'apps/web/eslint.config.mjs',
    'apps/web/next.config.ts',
    'apps/web/package.json',
    'apps/web/tsconfig.json',
    'contracts/generated/README.md',
    'packages/api-client/README.md',
    'packages/api-client/package.json',
    'packages/db-types/README.md',
    'packages/db-types/package.json',
    'services/agent/.python-version',
    'services/agent/pyproject.toml',
    'services/agent/src/autobots/__init__.py',
    'services/agent/src/autobots/api/__init__.py',
    'services/agent/src/autobots/api/app.py',
    'services/agent/src/autobots/py.typed',
    'services/agent/tests/conftest.py',
    'services/agent/tests/fake_openrouter.py',
    'services/agent/tests/test_model_transport.py',
    'services/agent/tests/test_app_factory.py',
    'services/agent/tests/test_environment.py',
    'services/agent/uv.lock',
}
FORBIDDEN_ROOTS = ('supabase', 'infra')
# US-1.7's disposable fixtures. Product infrastructure stays out until its own story.
ALLOWED_UNDER_FORBIDDEN = ('infra/disposable/',)
# Importable names of the selected packages. The scaffold's source uses none of them yet.
PRODUCT_IMPORTS = {'deepagents', 'langgraph', 'langchain', 'langchain_core', 'langchain_openrouter',
                   'langchain_mcp_adapters', 'openrouter', 'psycopg'}
UNUSED_SDK_IMPORTS = {'anthropic', 'langchain_anthropic', 'google', 'langchain_google_genai'}
WEB_DEPENDENCIES = {'next', 'react', 'react-dom'}
WEB_DEV_DEPENDENCIES = {'@types/node', '@types/react', '@types/react-dom', 'eslint', 'eslint-config-next',
                        'prettier', 'typescript'}
PLACEHOLDER_PACKAGES = ('packages/api-client/package.json', 'packages/db-types/package.json')


def path_errors(paths: set[str]) -> list[str]:
    scaffold = {path for path in paths if path.startswith(SCAFFOLD_ROOTS)}
    errors = [f'unexpected scaffold path: {path}' for path in sorted(scaffold - ALLOWED_PATHS)]
    errors += [f'missing scaffold path: {path}' for path in sorted(ALLOWED_PATHS - scaffold)]
    errors += [f'forbidden path: {path}' for path in sorted(paths)
               if path.split('/', 1)[0] in FORBIDDEN_ROOTS and not path.startswith(ALLOWED_UNDER_FORBIDDEN)]
    return errors


def imported_roots(source: str) -> set[str]:
    roots = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split('.', 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split('.', 1)[0])
    return roots


def import_errors(sources: dict[str, str], forbidden: set[str]) -> list[str]:
    return [f'{name} imports {root}' for name, source in sorted(sources.items())
            for root in sorted(imported_roots(source) & forbidden)]


def web_dependency_errors(data: dict) -> list[str]:
    errors = []
    if set(data.get('dependencies', {})) != WEB_DEPENDENCIES:
        errors.append(f"web dependencies are {sorted(data.get('dependencies', {}))}")
    if set(data.get('devDependencies', {})) != WEB_DEV_DEPENDENCIES:
        errors.append(f"web devDependencies are {sorted(data.get('devDependencies', {}))}")
    return errors


def python_sources(*directories: str) -> dict[str, str]:
    found = {}
    for directory in directories:
        for path in (REPO_ROOT / directory).rglob('*.py'):
            if '.venv' not in path.parts:
                found[path.relative_to(REPO_ROOT).as_posix()] = path.read_text()
    return found


class ScaffoldPaths(unittest.TestCase):
    def test_paths_equal_the_allow_list(self) -> None:
        paths = set(git_paths(REPO_ROOT, 'ls-files', '-co', '--exclude-standard'))
        self.assertEqual(path_errors(paths), [])

    def test_extra_path_fails(self) -> None:
        self.assertIn('unexpected scaffold path: apps/web/app/feature/page.tsx',
                      path_errors(ALLOWED_PATHS | {'apps/web/app/feature/page.tsx'}))

    def test_missing_path_fails(self) -> None:
        self.assertIn('missing scaffold path: apps/web/app/page.tsx',
                      path_errors(ALLOWED_PATHS - {'apps/web/app/page.tsx'}))

    def test_forbidden_root_fails(self) -> None:
        self.assertIn('forbidden path: supabase/migrations/0001.sql',
                      path_errors(ALLOWED_PATHS | {'supabase/migrations/0001.sql'}))

    def test_forbidden_roots_do_not_exist(self) -> None:
        for root in FORBIDDEN_ROOTS:
            present = [path for path in git_paths(REPO_ROOT, 'ls-files', '-co', '--exclude-standard')
                       if path.startswith(f'{root}/') and not path.startswith(ALLOWED_UNDER_FORBIDDEN)]
            self.assertEqual(present, [], root)

    def test_placeholders_hold_no_generated_artifact(self) -> None:
        for directory, owner in (('packages/api-client', 'US-2.2'), ('packages/db-types', 'US-2.4'),
                                 ('contracts/generated', 'US-2.2')):
            self.assertIn(owner, (REPO_ROOT / directory / 'README.md').read_text(), directory)
            names = {path.name for path in (REPO_ROOT / directory).iterdir()}
            self.assertLessEqual(names, {'README.md', 'package.json', 'node_modules'}, directory)


class ProductImports(unittest.TestCase):
    def test_source_imports_no_product_package(self) -> None:
        sources = python_sources('services/agent/src')
        self.assertTrue(sources)
        self.assertEqual(import_errors(sources, PRODUCT_IMPORTS | UNUSED_SDK_IMPORTS), [])

    def test_owned_code_never_imports_the_unused_sdks(self) -> None:
        sources = python_sources('services/agent/src', 'services/agent/tests')
        self.assertTrue(sources)
        self.assertEqual(import_errors(sources, UNUSED_SDK_IMPORTS), [])

    def test_each_forbidden_import_form_is_detected(self) -> None:
        for source in ('import anthropic', 'from anthropic.types import Message', 'import google.genai',
                       'from google import genai', 'from langchain_anthropic import ChatAnthropic',
                       'import langchain_google_genai', 'def build():\n    import anthropic\n'):
            self.assertNotEqual(import_errors({'fixture.py': source}, UNUSED_SDK_IMPORTS), [], source)
        self.assertNotEqual(import_errors({'fixture.py': 'import deepagents'}, PRODUCT_IMPORTS), [])


class WebDependencies(unittest.TestCase):
    def setUp(self) -> None:
        self.web = json.loads((REPO_ROOT / 'apps/web/package.json').read_text())

    def test_web_dependencies_are_only_the_shell(self) -> None:
        self.assertEqual(web_dependency_errors(self.web), [])

    def test_extra_dependency_fails(self) -> None:
        for name in ('zod', '@supabase/supabase-js'):
            altered = {**self.web, 'dependencies': {**self.web['dependencies'], name: '1.0.0'}}
            self.assertNotEqual(web_dependency_errors(altered), [], name)

    def test_placeholders_declare_no_dependency(self) -> None:
        for relative in PLACEHOLDER_PACKAGES:
            data = json.loads((REPO_ROOT / relative).read_text())
            self.assertIs(data.get('private'), True, relative)
            self.assertFalse(set(data) & {'dependencies', 'devDependencies', 'scripts'}, relative)


class WebShellStaysStatic(unittest.TestCase):
    def test_shell_has_no_data_fetching_or_client_boundary(self) -> None:
        for path in sorted(Path(REPO_ROOT / 'apps/web/app').rglob('*.tsx')):
            text = path.read_text()
            for marker in ('use client', 'fetch(', 'useState', 'useEffect', 'process.env'):
                self.assertNotIn(marker, text, path.name)


if __name__ == '__main__':
    unittest.main()
