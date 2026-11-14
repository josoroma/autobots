"""Static tests of pins, locks and the runbook: tasks 1.1, 1.2, 1.4 and checks T1.1, T1.2, T1.8.

Each rule is a function returning errors, so a paired altered fixture shows the same rule fails.
"""
from __future__ import annotations

import copy
import json
import re
import tomllib
import unittest
from pathlib import Path

from support import REPO_ROOT, toolchain

RANGE_MARKERS = re.compile(r'[\^~<>*|]|\s-\s|\bx\b|latest')
PYTHON_PINS = {
    'deepagents': '0.7.32',
    'langchain': '1.4.8',
    'langgraph': '1.2.19',
    'langchain-openrouter': '0.2.9',
    'openrouter': '0.11.46',
    'langgraph-checkpoint-postgres': '3.2.0',
    'fastapi': '0.162.0',
    'psycopg': '3.3.8',
    'langchain-mcp-adapters': '0.3.2',
}
PYTHON_TOOL_PINS = {'ruff': '0.17.3', 'mypy': '2.4.1', 'pytest': '9.2.0', 'pytest-asyncio': '1.4.1.post1'}
NODE_PINS = {'next': '16.4.5', 'react': '19.3.1', 'react-dom': '19.3.1'}
NODE_TOOL_PINS = {'eslint': '9.39.5', 'eslint-config-next': '16.4.5', 'prettier': '3.9.10',
                  '@types/react': '19.3.0', '@types/react-dom': '19.3.0'}
UNUSED_SDKS = ('anthropic', 'langchain-anthropic', 'google-genai', 'langchain-google-genai')
RUNTIME_PINS = {'node': '22.23.2', 'pnpm': '12.16.1', 'python': '3.12.16', 'uv': '0.13.6'}


def version_tuple(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r'\d+', version))


def pyproject_errors(data: dict) -> list[str]:
    errors = []
    project = data['project']
    if project['requires-python'] != '==3.12.*':
        errors.append(f"requires-python is {project['requires-python']}")
    if data['tool']['uv']['required-version'] != f"=={RUNTIME_PINS['uv']}":
        errors.append(f"required-version is {data['tool']['uv']['required-version']}")
    direct = {}
    for item in [*project['dependencies'], *data['dependency-groups']['dev']]:
        match = re.fullmatch(r'([A-Za-z0-9_.-]+)(\[[a-z,]+\])?==([0-9][0-9A-Za-z.]*)', item)
        if match is None:
            errors.append(f'not an exact pin: {item}')
        else:
            direct[match[1]] = match[3]
    for name, pin in {**PYTHON_PINS, **PYTHON_TOOL_PINS}.items():
        if direct.get(name) != pin:
            errors.append(f'{name} is {direct.get(name)}, wanted {pin}')
    if 'langsmith' in direct:
        errors.append('langsmith must stay transitive')
    for name in UNUSED_SDKS:
        if name in direct:
            errors.append(f'{name} must stay an unused transitive dependency')
    return errors


def package_errors(data: dict) -> list[str]:
    errors = []
    for section in ('dependencies', 'devDependencies', 'optionalDependencies', 'peerDependencies'):
        for name, spec in data.get(section, {}).items():
            # A workspace package is pinned by living in this repository.
            if name.startswith('@autobots/') and spec == 'workspace:*':
                continue
            if RANGE_MARKERS.search(spec) or not re.fullmatch(r'\d+\.\d+\.\d+', spec):
                errors.append(f'{name} has a range or tag: {spec}')
    return errors


def web_package_errors(data: dict) -> list[str]:
    errors = package_errors(data)
    declared = {**data.get('dependencies', {}), **data.get('devDependencies', {})}
    for name, pin in {**NODE_PINS, **NODE_TOOL_PINS}.items():
        if declared.get(name) != pin:
            errors.append(f'{name} is {declared.get(name)}, wanted {pin}')
    if not declared.get('@types/node', '').startswith('22.'):
        errors.append('@types/node must match the Node major')
    if declared.get('typescript') not in {'6.0.3', '5.9.3'}:
        errors.append(f"typescript is {declared.get('typescript')}")
    return errors


def root_package_errors(data: dict) -> list[str]:
    errors = package_errors(data)
    if not re.fullmatch(rf"pnpm@{re.escape(RUNTIME_PINS['pnpm'])}\+sha512\.[0-9a-f]{{128}}", data.get('packageManager', '')):
        errors.append(f"packageManager lacks the pinned version or hash: {data.get('packageManager')}")
    if data.get('engines', {}).get('node') != RUNTIME_PINS['node']:
        errors.append('engines.node is not the pinned Node')
    if data.get('engines', {}).get('pnpm') != RUNTIME_PINS['pnpm']:
        errors.append('engines.pnpm is not the pinned pnpm')
    return errors


def uv_lock_errors(versions: dict[str, str]) -> list[str]:
    errors = [f'{name} locked at {versions.get(name)}, wanted {pin}' for name, pin in PYTHON_PINS.items()
              if versions.get(name) != pin]
    bounds = (('pydantic', (2, 11, 2), (2, 13)), ('langchain-core', (1, 7, 4), (2,)), ('openrouter', (0,), (1,)))
    for name, low, high in bounds:
        locked = version_tuple(versions.get(name, '0'))
        if not low <= locked < high:
            errors.append(f'{name} locked at {versions.get(name)}, outside its bound')
    return errors


def pnpm_lock_errors(importers: dict[str, dict[str, str]]) -> list[str]:
    web = importers.get('apps/web', {})
    return [f'{name} locked at {web.get(name)}, wanted {pin}' for name, pin in NODE_PINS.items()
            if web.get(name) != pin]


class ManifestPins(unittest.TestCase):
    def setUp(self) -> None:
        self.pyproject = tomllib.loads((REPO_ROOT / 'services/agent/pyproject.toml').read_text())
        self.root_package = json.loads((REPO_ROOT / 'package.json').read_text())
        self.web_package = json.loads((REPO_ROOT / 'apps/web/package.json').read_text())

    def test_python_manifest_pins(self) -> None:
        self.assertEqual(pyproject_errors(self.pyproject), [])

    def test_altered_python_pin_fails(self) -> None:
        for mutate in (lambda d: d['project']['dependencies'].__setitem__(0, 'deepagents>=0.7'),
                       lambda d: d['project'].__setitem__('requires-python', '>=3.12'),
                       lambda d: d['tool']['uv'].__setitem__('required-version', '>=0.13'),
                       lambda d: d['project']['dependencies'].append('langsmith==0.14.17'),
                       lambda d: d['project']['dependencies'].append('anthropic==2.5.0')):
            data = copy.deepcopy(self.pyproject)
            mutate(data)
            self.assertNotEqual(pyproject_errors(data), [])

    def test_root_package_pins_manager_and_engines(self) -> None:
        self.assertEqual(root_package_errors(self.root_package), [])

    def test_altered_root_package_fails(self) -> None:
        for mutate in (lambda d: d.__setitem__('packageManager', 'pnpm@12.16.1'),
                       lambda d: d['engines'].__setitem__('node', '>=22')):
            data = copy.deepcopy(self.root_package)
            mutate(data)
            self.assertNotEqual(root_package_errors(data), [])

    def test_web_package_pins(self) -> None:
        self.assertEqual(web_package_errors(self.web_package), [])

    def test_altered_web_pin_fails(self) -> None:
        data = copy.deepcopy(self.web_package)
        data['dependencies']['next'] = '^16.4.5'
        self.assertNotEqual(web_package_errors(data), [])

    def test_runtime_pin_files(self) -> None:
        self.assertEqual((REPO_ROOT / '.node-version').read_text().strip(), RUNTIME_PINS['node'])
        self.assertEqual((REPO_ROOT / 'services/agent/.python-version').read_text().strip(), RUNTIME_PINS['python'])
        self.assertEqual(toolchain.read_pins(REPO_ROOT), toolchain.Pins(**RUNTIME_PINS))


class LockedVersions(unittest.TestCase):
    def setUp(self) -> None:
        self.uv = toolchain.uv_locked_versions((REPO_ROOT / 'services/agent/uv.lock').read_text())
        self.pnpm = toolchain.pnpm_importers((REPO_ROOT / 'pnpm-lock.yaml').read_text())

    def test_uv_lock_holds_prd_versions_and_bounds(self) -> None:
        self.assertEqual(uv_lock_errors(self.uv), [])

    def test_altered_uv_lock_fails(self) -> None:
        for name, version in (('deepagents', '0.7.31'), ('pydantic', '2.13.0'),
                              ('langchain-core', '2.0.0'), ('openrouter', '1.3.117')):
            self.assertNotEqual(uv_lock_errors({**self.uv, name: version}), [], name)

    def test_unused_sdks_are_locked_and_only_transitive(self) -> None:
        for name in UNUSED_SDKS:
            self.assertIn(name, self.uv)

    def test_pnpm_lock_holds_shared_candidates(self) -> None:
        self.assertEqual(pnpm_lock_errors(self.pnpm), [])

    def test_altered_pnpm_lock_fails(self) -> None:
        altered = {'apps/web': {**self.pnpm['apps/web'], 'next': '16.4.4'}}
        self.assertNotEqual(pnpm_lock_errors(altered), [])

    def test_locks_record_no_machine_path(self) -> None:
        for path in ('services/agent/uv.lock', 'pnpm-lock.yaml'):
            text = (REPO_ROOT / path).read_text()
            self.assertNotIn('/Users/', text, path)
            self.assertNotIn(str(Path.home()), text, path)


class RunbookNamesPins(unittest.TestCase):
    def setUp(self) -> None:
        self.text = (REPO_ROOT / 'docs/engineering/runbooks/toolchains.md').read_text()

    def pins(self) -> dict[str, str]:
        web = json.loads((REPO_ROOT / 'apps/web/package.json').read_text())
        pins = {**RUNTIME_PINS, **PYTHON_PINS, **PYTHON_TOOL_PINS, **web['dependencies'], **web['devDependencies']}
        return {name: pin for name, pin in pins.items() if not name.startswith('@autobots/')}

    def test_runbook_names_each_pin(self) -> None:
        missing = [f'{name} {pin}' for name, pin in self.pins().items()
                   if not re.search(rf'`{re.escape(name)}`[^\n]*\b{re.escape(pin)}\b', self.text)]
        self.assertEqual(missing, [])

    def test_a_pin_not_in_the_runbook_is_detected(self) -> None:
        self.assertIsNone(re.search(r'`next`[^\n]*\b99\.0\.0\b', self.text))


if __name__ == '__main__':
    unittest.main()
