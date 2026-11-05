"""The rule that outlasts the minimal scaffold: owned code never imports the unused provider SDKs.

They are locked only because deepagents 0.7.32 requires both adapters. The user decided on 2026-11-05
that owned code never imports them. US-1.3's allow-list of scaffold paths ended when product code began.
"""
from __future__ import annotations

import ast
import unittest

from support import REPO_ROOT

UNUSED_SDK_IMPORTS = {'anthropic', 'langchain_anthropic', 'google', 'langchain_google_genai'}


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


def python_sources(*directories: str) -> dict[str, str]:
    found = {}
    for directory in directories:
        for path in (REPO_ROOT / directory).rglob('*.py'):
            if '.venv' not in path.parts:
                found[path.relative_to(REPO_ROOT).as_posix()] = path.read_text()
    return found


class ProductImports(unittest.TestCase):
    def test_owned_code_never_imports_the_unused_sdks(self) -> None:
        sources = python_sources('services/agent/src', 'services/agent/tests')
        self.assertTrue(sources)
        self.assertEqual(import_errors(sources, UNUSED_SDK_IMPORTS), [])

    def test_each_forbidden_import_form_is_detected(self) -> None:
        for source in ('import anthropic', 'from anthropic.types import Message', 'import google.genai',
                       'from google import genai', 'from langchain_anthropic import ChatAnthropic',
                       'import langchain_google_genai', 'def build():\n    import anthropic\n'):
            self.assertNotEqual(import_errors({'fixture.py': source}, UNUSED_SDK_IMPORTS), [], source)


if __name__ == '__main__':
    unittest.main()
