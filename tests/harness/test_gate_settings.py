"""R-01: the gates' own settings. A weakened gate fails here, where it can't pass unnoticed.

Each check reads the real file, and an altered copy proves the check catches that weakening.
"""
from __future__ import annotations

import copy
import json
import re
import sys
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import toolchain  # noqa: E402

RUFF_RULES = {'E', 'F', 'W', 'I', 'B', 'UP', 'ASYNC', 'RUF',
              # R-05's ratchets: size, complexity, Any and broad catches.
              'C90', 'PLR0911', 'PLR0912', 'PLR0913', 'PLR0915', 'ANN401', 'BLE001', 'S110', 'S112',
              'DTZ', 'S602', 'S604', 'S605', 'FAST002', 'FAST003', 'TID251'}
# Repository Python (R-07): the shared families, broad catches, the subprocess and time rules, and the SDK ban.
REPO_RUFF_RULES = {'E', 'F', 'W', 'I', 'B', 'UP', 'ASYNC', 'RUF', 'BLE001', 'S110', 'S112', 'DTZ', 'S602', 'S604',
                   'S605', 'TID251'}
# R-05's Any baseline: files may only leave it, it ignores nothing but ANN401, and api/ and domain/ stay out.
ANN401_BASELINE = frozenset({
    'src/autobots/adapters/browser_executor.py',
    'src/autobots/adapters/checkpoints.py',
    'src/autobots/adapters/github_issues.py',
    'src/autobots/adapters/github_pulls.py',
    'src/autobots/adapters/github_reads.py',
    'src/autobots/adapters/jina.py',
    'src/autobots/adapters/loop_middleware.py',
    'src/autobots/adapters/models/openrouter_metadata.py',
    'src/autobots/adapters/object_storage.py',
    'src/autobots/adapters/result_stream.py',
    'src/autobots/adapters/tavily.py',
    'src/autobots/adapters/tool_middleware.py',
    'src/autobots/application/approvals.py',
    'src/autobots/application/artifacts.py',
    'src/autobots/application/assignments.py',
    'src/autobots/application/browsing_loop.py',
    'src/autobots/application/compaction.py',
    'src/autobots/application/credentials/store.py',
    'src/autobots/application/cronjob_tool.py',
    'src/autobots/application/experts.py',
    'src/autobots/application/goal_loop.py',
    'src/autobots/application/improvements.py',
    'src/autobots/application/memory.py',
    'src/autobots/application/model_admission.py',
    'src/autobots/application/operations.py',
    'src/autobots/application/plans.py',
    'src/autobots/application/profiles.py',
    'src/autobots/application/provider_settings.py',
    'src/autobots/application/reconciliation.py',
    'src/autobots/application/recovery.py',
    'src/autobots/application/retention.py',
    'src/autobots/application/routines.py',
    'src/autobots/application/run_projection.py',
    'src/autobots/application/run_usage.py',
    'src/autobots/application/runs.py',
    'src/autobots/application/search.py',
    'src/autobots/application/tool_catalog.py',
    'src/autobots/application/tool_gateway.py',
    'src/autobots/application/tool_grants.py',
    'src/autobots/application/tool_key_settings.py',
    'src/autobots/application/tool_keys.py',
    'src/autobots/application/tool_uses.py',
    'src/autobots/application/verification.py',
    'src/autobots/application/worker_inference.py',
    'src/autobots/application/worker_leases.py',
    'src/autobots/application/workflow_overview.py',
    'src/autobots/application/workflow_runner.py',
    'src/autobots/application/workflows.py',
    'src/autobots/operations/browse_trial.py',
    'src/autobots/operations/concept_seed.py',
    'src/autobots/operations/reasoning_trial.py',
    'src/autobots/operations/route_qualification.py',
    'src/autobots/operations/worker.py',
    'tests/test_browse_trial.py',
    'tests/test_browsing_loop.py',
    'tests/test_browsing_tool.py',
    'tests/test_contracts.py',
    'tests/test_execution_contract.py',
    'tests/test_final_review.py',
    'tests/test_github_issues.py',
    'tests/test_github_reads.py',
    'tests/test_model_attempts.py',
    'tests/test_operation_values.py',
    'tests/test_operations.py',
    'tests/test_readiness.py',
    'tests/test_reasoning_trial.py',
    'tests/test_result_stream.py',
    'tests/test_route_qualification.py',
    'tests/test_schema_release.py',
    'tests/test_tavily.py',
    'tests/test_tool_keys.py',
    'tests/test_worker_inference.py',
    'tests/test_workflow_execution.py',
    'tests/test_workflows.py',
})
REPO_EXCLUDED = {'services', 'research', 'apps', 'packages', 'docs', 'openspec', '.checks', 'node_modules'}
BANNED_SDKS = {'anthropic', 'langchain_anthropic', 'google', 'langchain_google_genai', 'openai', 'langchain_openai'}
# R-06's ESLint ratchets, as their configuration states them.
ESLINT_RULES = (r'complexity:\s*\[\s*"error",\s*15\s*\]', r'"max-depth":\s*\[\s*"error",\s*4\s*\]',
                r'"max-lines-per-function":\s*\[\s*"error",\s*\{\s*max:\s*150\b',
                r'"max-lines":\s*\[\s*"error",\s*\{\s*max:\s*400\b', r'"import/no-cycle":\s*"error"',
                r'"@typescript-eslint/consistent-type-assertions":\s*\[\s*"error"',
                r'"no-restricted-syntax":\s*\[\s*"error"')
# Upper limits. A refactor may lower one; raising it fails here.
RUFF_LIMITS = {('mccabe', 'max-complexity'): 15, ('pylint', 'max-branches'): 15, ('pylint', 'max-returns'): 8,
               ('pylint', 'max-statements'): 60, ('pylint', 'max-args'): 8}
TS_FLAGS = ('strict', 'noUncheckedIndexedAccess', 'exactOptionalPropertyTypes')
TSCONFIGS = ('apps/web/tsconfig.json', 'packages/api-client/tsconfig.json')
ESLINT_PRESETS = ('eslint-config-next/core-web-vitals', 'eslint-config-next/typescript')
WEB_SCRIPTS = {'lint': 'eslint --max-warnings=0 .', 'typecheck': 'tsc --noEmit',
               'format:check': 'prettier --check app components lib tests eslint.config.mjs next.config.ts '
                               'playwright.config.ts postcss.config.mjs package.json tsconfig.json '
                               '../../packages/api-client/src/runtime.ts ../../packages/api-client/tests'}
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
    ruff = tool.get('ruff', {})
    lint = ruff.get('lint', {})
    if lint.get('ignore') or lint.get('extend-ignore') or ruff.get('exclude') or ruff.get('extend-exclude'):
        errors.append('ruff ignores rules or excludes files')
    ignores = lint.get('per-file-ignores', {})
    if (any(codes != ['ANN401'] for codes in ignores.values()) or not set(ignores) <= ANN401_BASELINE
            or any(path.startswith(('src/autobots/api/', 'src/autobots/domain/')) for path in ignores)):
        errors.append('the per-file ignores reach beyond the shrinking ANN401 baseline')
    if set(lint.get('flake8-tidy-imports', {}).get('banned-api', {})) != BANNED_SDKS:
        errors.append('the provider SDK ban changed')
    for (section, name), limit in RUFF_LIMITS.items():
        if not lint.get(section, {}).get(name, limit + 1) <= limit:
            errors.append(f'ruff {section} {name} is above {limit}')
    return errors


def typescript_errors(name: str, config: dict) -> list[str]:
    options = config.get('compilerOptions', {})
    return [f'{name}: {flag} is off' for flag in TS_FLAGS if options.get(flag) is not True]


def eslint_errors(config: str) -> list[str]:
    # Comments don't count, so a rule commented out reads as gone.
    code = re.sub(r'^\s*//[^\n]*', '', config, flags=re.M)
    errors = [f'ESLint no longer extends {preset}' for preset in ESLINT_PRESETS if f'"{preset}"' not in code]
    return errors + [f'ESLint no longer enforces {rule}' for rule in ESLINT_RULES if not re.search(rule, code)]


def repo_ruff_errors(config: dict) -> list[str]:
    lint = config.get('lint', {})
    errors = [f'ruff.toml no longer selects {rule}' for rule in sorted(REPO_RUFF_RULES - set(lint.get('select', [])))]
    allowed = {'tests/faults/**': ['ALL'], 'scripts/**': ['E501'], 'tests/**': ['E501'], '.claude/hooks/**': ['E501']}
    if any(allowed.get(path) != codes for path, codes in lint.get('per-file-ignores', {}).items()):
        errors.append('ruff.toml ignores more than the fault fixtures and, until reformatting, long lines')
    if lint.get('ignore') or lint.get('extend-ignore'):
        errors.append('ruff.toml ignores rules')
    if set(config.get('extend-exclude', [])) != REPO_EXCLUDED:
        errors.append('ruff.toml excludes more than the folders other gates own')
    if set(lint.get('flake8-tidy-imports', {}).get('banned-api', {})) != BANNED_SDKS:
        errors.append('ruff.toml changed the provider SDK ban')
    return errors


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
        self.repo_ruff = tomllib.loads((ROOT / 'ruff.toml').read_text())

    def test_the_gates_are_as_strict_as_recorded(self) -> None:
        errors = (python_errors(self.pyproject) + eslint_errors(self.eslint) + script_errors(self.scripts)
                  + repo_ruff_errors(self.repo_ruff))
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
                       lambda d: d['tool']['ruff']['lint']['select'].remove('ANN401'),
                       lambda d: d['tool']['ruff']['lint'].__setitem__('extend-ignore', ['B']),
                       lambda d: d['tool']['ruff'].__setitem__('extend-exclude', ['src/autobots/api']),
                       lambda d: d['tool']['ruff']['lint']['per-file-ignores'].__setitem__('src/new.py', ['ANN401', 'B']),
                       lambda d: d['tool']['ruff']['lint']['per-file-ignores'].__setitem__('src/new.py', ['ANN401']),
                       lambda d: d['tool']['ruff']['lint']['per-file-ignores'].__setitem__(
                           'src/autobots/api/app.py', ['ANN401']),
                       lambda d: d['tool']['ruff']['lint']['flake8-tidy-imports']['banned-api'].pop('openai')):
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
        self.assertTrue(script_errors({**self.scripts, 'format:check': 'prettier --check app'}))
        self.assertTrue(eslint_errors(self.eslint.replace('"import/no-cycle": "error"', '// "import/no-cycle": "error"')))
        self.assertTrue(eslint_errors(self.eslint.replace('complexity: ["error", 15]', 'complexity: ["error", 25]')))

    def test_a_weakened_repository_gate_is_caught(self) -> None:
        for weaken in (lambda d: d['lint']['select'].remove('BLE001'),
                       lambda d: d['lint']['per-file-ignores'].__setitem__('scripts/**', ['E501', 'B']),
                       lambda d: d['lint'].__setitem__('ignore', ['S602'])):
            altered = copy.deepcopy(self.repo_ruff)
            weaken(altered)
            self.assertTrue(repo_ruff_errors(altered))

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
