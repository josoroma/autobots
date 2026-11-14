"""R-01: the gates' own settings. A weakened gate fails here, where it can't pass unnoticed.

Each check reads the real file, and an altered copy proves the check catches that weakening.
"""
from __future__ import annotations

import copy
import json
import sys
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import toolchain  # noqa: E402

RUFF_RULES = {'E', 'F', 'W', 'I', 'B', 'UP', 'ASYNC', 'RUF',
              # R-05's ratchets: size, complexity, Any and broad catches.
              'C90', 'PLR0911', 'PLR0912', 'PLR0913', 'PLR0915', 'ANN401', 'BLE001', 'S110', 'S112'}
# Upper limits. A refactor may lower one; raising it fails here.
RUFF_LIMITS = {('mccabe', 'max-complexity'): 15, ('pylint', 'max-branches'): 15, ('pylint', 'max-returns'): 8,
               ('pylint', 'max-statements'): 60, ('pylint', 'max-args'): 8}
TS_FLAGS = ('strict', 'noUncheckedIndexedAccess', 'exactOptionalPropertyTypes')
TSCONFIGS = ('apps/web/tsconfig.json', 'packages/api-client/tsconfig.json')
ESLINT_PRESETS = ('eslint-config-next/core-web-vitals', 'eslint-config-next/typescript')
WEB_SCRIPTS = {'lint': 'eslint --max-warnings=0 .', 'typecheck': 'tsc --noEmit'}
# Each step's arguments after its executable. Anything added could narrow what the step checks.
STEP_ARGUMENTS = {'ruff_check': ('check',), 'ruff_format': ('format', '--check'), 'mypy': (), 'pytest': (),
                  'repo_ruff_check': ('check', 'scripts', 'tests', '.claude/hooks'), 'repo_mypy': ()}


def python_errors(pyproject: dict) -> list[str]:
    tool = pyproject.get('tool', {})
    mypy = tool.get('mypy', {})
    errors = [] if mypy.get('strict') is True else ['mypy is not strict']
    if set(mypy.get('files', [])) != {'src', 'tests'}:
        errors.append('mypy no longer checks src and tests')
    missing = RUFF_RULES - set(tool.get('ruff', {}).get('lint', {}).get('select', []))
    errors += [f'ruff no longer selects {rule}' for rule in sorted(missing)]
    lint = tool.get('ruff', {}).get('lint', {})
    if lint.get('ignore'):
        errors.append('ruff ignores rules')
    for (section, name), limit in RUFF_LIMITS.items():
        if not lint.get(section, {}).get(name, limit + 1) <= limit:
            errors.append(f'ruff {section} {name} is above {limit}')
    return errors


def typescript_errors(name: str, config: dict) -> list[str]:
    options = config.get('compilerOptions', {})
    return [f'{name}: {flag} is off' for flag in TS_FLAGS if options.get(flag) is not True]


def eslint_errors(config: str) -> list[str]:
    return [f'ESLint no longer extends {preset}' for preset in ESLINT_PRESETS if f'"{preset}"' not in config]


def script_errors(scripts: dict) -> list[str]:
    return [f'web script {name} is not {value!r}' for name, value in WEB_SCRIPTS.items() if scripts.get(name) != value]


def step_errors(steps: list) -> list[str]:
    found = {step.id: tuple(step.argv[1:]) for step in steps}
    return [f'step {name} runs with {found.get(name)!r}' for name, value in STEP_ARGUMENTS.items()
            if found.get(name) != value]


def placeholder_steps() -> list:
    tools = toolchain.Tools(node_dir='/stub', python='/stub/python', uv='uv', corepack='corepack',
                            pins=toolchain.read_pins(ROOT))
    return toolchain.check_steps(ROOT, tools)


class GateSettings(unittest.TestCase):
    def setUp(self) -> None:
        self.pyproject = tomllib.loads((ROOT / 'services/agent/pyproject.toml').read_text())
        self.tsconfigs = {name: json.loads((ROOT / name).read_text()) for name in TSCONFIGS}
        self.eslint = (ROOT / 'apps/web/eslint.config.mjs').read_text()
        self.scripts = json.loads((ROOT / 'apps/web/package.json').read_text())['scripts']

    def test_the_gates_are_as_strict_as_recorded(self) -> None:
        errors = python_errors(self.pyproject) + eslint_errors(self.eslint) + script_errors(self.scripts)
        for name, config in self.tsconfigs.items():
            errors += typescript_errors(name, config)
        self.assertEqual(errors + step_errors(placeholder_steps()), [])

    def test_a_weakened_python_gate_is_caught(self) -> None:
        for weaken in (lambda d: d['tool']['mypy'].__setitem__('strict', False),
                       lambda d: d['tool']['mypy'].__setitem__('files', ['src']),
                       lambda d: d['tool']['ruff']['lint']['select'].remove('B'),
                       lambda d: d['tool']['ruff']['lint'].__setitem__('ignore', ['E501']),
                       lambda d: d['tool']['ruff']['lint']['mccabe'].__setitem__('max-complexity', 20),
                       lambda d: d['tool']['ruff']['lint']['pylint'].pop('max-args'),
                       lambda d: d['tool']['ruff']['lint']['select'].remove('ANN401')):
            altered = copy.deepcopy(self.pyproject)
            weaken(altered)
            self.assertTrue(python_errors(altered))

    def test_a_weakened_typescript_or_eslint_gate_is_caught(self) -> None:
        for flag in TS_FLAGS:
            altered = copy.deepcopy(self.tsconfigs['apps/web/tsconfig.json'])
            altered['compilerOptions'][flag] = False
            self.assertTrue(typescript_errors('web', altered), flag)
        self.assertTrue(eslint_errors(self.eslint.replace('eslint-config-next/typescript', 'nothing')))
        self.assertTrue(script_errors({**self.scripts, 'lint': 'eslint .'}))
        self.assertTrue(script_errors({**self.scripts, 'typecheck': 'tsc --noEmit || true'}))

    def test_a_narrowed_step_is_caught(self) -> None:
        steps = placeholder_steps()
        narrowed = [step if step.id != 'pytest' else toolchain.Step(step.id, (*step.argv, '-k', 'not slow'), step.cwd)
                    for step in steps]
        self.assertTrue(step_errors(narrowed))
        relaxed = [step if step.id != 'ruff_check' else toolchain.Step(step.id, (*step.argv, '--exit-zero'), step.cwd)
                   for step in steps]
        self.assertTrue(step_errors(relaxed))


if __name__ == '__main__':
    unittest.main()
