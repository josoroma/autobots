#!/usr/bin/env python3
"""One local verification runner. It never installs, and it never claims unimplemented gates.

Exit codes: 0 passed, 1 a required check failed, 2 a prerequisite is unavailable or a check could
not run to a result. Passing any profile establishes neither H0, H1 nor product acceptance. `operations`
is disposable evidence: it exercises runbooks on throwaway Compose projects with a scripted model.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from harness_lib import (
    EXIT_FAILED,
    EXIT_PASSED,
    EXIT_UNAVAILABLE,
    adapter_status,
    check_domains,
    config_errors,
    derived_domains,
    fingerprint,
    input_manifest,
    project_root,
    reduced_env,
    run_bounded,
    scope_paths,
    utc,
)
from qualification.errors import Unavailable
from qualification.profiles import (
    HARNESS_SECONDS,
    HARNESS_STEPS,
    PROFILES,
    PYTHON_STEPS,
    REPO_PYTHON_STEPS,
    SPREAD,
    STEPS,
    WEB_STEPS,
    CheckStep,
    declared,
)
from qualification.records import StepClass
from suites import API_CLIENT_TESTS, HARNESS_PATTERN, TOOLCHAIN_OFFLINE, WEB_UNIT_TESTS
from toolchain import (
    Step,
    check_steps,
    child_env,
    find_tools,
    missing_prepared_paths,
    run_step,
    snapshot,
    snapshot_differences,
)

# The profiles, in the order .claude/autobots.json lists them as implemented.
IMPLEMENTED_PROFILES = tuple(PROFILES)
# These report exit 2 for a missing prerequisite, which is not a failed check (qualification/profiles.py).
SELF_REPORTING_STEPS = frozenset(step.id for step in STEPS.values() if step.self_reporting)
# DH-09.2 class and model transport by step, from qualification/profiles.py. Evidence holds a cited check to
# them, and a plan cannot override them.
STEP_CLASSES = {step.id: (step.klass, step.transport) for step in STEPS.values() if (step.klass, step.transport) != ('static', 'none')}
OUTSIDE_SCOPE = 'outside the changed scope of this fast run'
NODE_TEST_STEPS = frozenset({'web_unit_tests', 'api_client_tests'})
# The test selections a step's arguments name, from scripts/suites.py.
SELECTIONS: dict[str, str | tuple[str, ...]] = {'harness_pattern': HARNESS_PATTERN, 'web_unit_tests': WEB_UNIT_TESTS,
                                                'api_client_tests': API_CLIENT_TESTS, SPREAD.strip('{}'): TOOLCHAIN_OFFLINE}
OUTPUT_LIMIT = 16000


def classify(step_id: str) -> StepClass:
    klass, transport = declared(step_id)
    return {'class': klass, 'model_transport': transport}


def arguments(step: CheckStep, values: Mapping[str, str | tuple[str, ...]]) -> tuple[str, ...]:
    """A registered step's arguments, each `{name}` filled in from `values`. A tuple value spreads into arguments."""
    resolved: list[str] = []
    for part in step.argv or ():
        spread = values.get(part.strip('{}')) if part.startswith('{') and part.endswith('}') else None
        if isinstance(spread, tuple):
            resolved.extend(spread)
        else:
            resolved.append(part.format_map({name: value for name, value in values.items() if isinstance(value, str)}))
    return tuple(resolved)


def run_check(root: Path, name: str, argv: list[str]) -> dict[str, Any]:
    """One harness check, with the record fields its readers parse (DH-09.2). A timeout ends what it started too."""
    start = utc()
    began = time.monotonic()
    # Tests receive no inherited API keys, credentials or assistant configuration.
    env = reduced_env()
    env.update(PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8')
    result = run_bounded(argv, cwd=root, env=env, timeout=STEPS[name].timeout if name in STEPS else HARNESS_SECONDS)
    if result.exit_code is None:
        status, code, output = 'error', None, 'TimeoutExpired' if result.failure == 'timeout' else str(result.failure)
    else:
        status, code = ('passed' if result.exit_code == 0 else 'failed'), result.exit_code
        output = (result.stdout + result.stderr)[-OUTPUT_LIMIT:]
    return {'id': name, **classify(name), 'command_argv': argv, 'cwd': str(root), 'started_at_utc': start,
            'finished_at_utc': utc(), 'duration_seconds': round(time.monotonic()-began, 3),
            'exit_code': code, 'status': status, 'output': output}


def harness_checks(root: Path) -> list[dict[str, Any]]:
    problems = config_errors(root)
    checks: list[dict[str, Any]] = [{'id': 'project_configuration', **classify('project_configuration'),
                                     'status': 'passed' if not problems else 'failed', 'errors': problems}]
    values = {'python': sys.executable, **SELECTIONS}
    checks.extend(run_check(root, step.id, list(arguments(step, values))) for step in HARNESS_STEPS if step.commanded)
    for check in checks:
        if check['id'] == 'harness_behavior_tests':
            check.update(judge_unittest(check))
    return checks


def judge_unittest(check: Mapping[str, Any]) -> dict[str, Any]:
    """Counts from unittest's summary. An empty suite or a skipped test is not a pass."""
    output = check.get('output', '')
    ran = re.search(r'Ran (\d+) tests?', output)
    skipped = sum(int(count) for count in re.findall(r'(?:skipped|expected failures)=(\d+)', output))
    executed = int(ran.group(1)) - skipped if ran else 0
    result: dict[str, Any] = {'tests_executed': executed, 'tests_skipped': skipped}
    if check['status'] == 'passed' and (executed < 1 or skipped):
        result['status'] = 'failed'
        result['output'] = output + f'\nExecuted {executed} tests and skipped {skipped}; neither an empty suite nor a skip is a pass.'
    return result


def judge_node(record: Mapping[str, Any]) -> dict[str, Any]:
    """Node's runner passes a glob that matched nothing, so its own count is read (R-01)."""
    output = record.get('output', '')
    found = re.search(r'^# tests (\d+)$', output, re.M)
    executed = int(found.group(1)) if found else 0
    # A skipped or todo test is not a pass, as for unittest and pytest.
    skipped = sum(int(count) for count in re.findall(r'^# (?:skipped|todo) (\d+)$', output, re.M))
    if record['status'] == 'passed' and (executed < 1 or skipped):
        return {'tests_executed': executed, 'tests_skipped': skipped, 'status': 'failed',
                'output': output + f'\nNode ran {executed} tests and skipped {skipped}; neither an empty suite nor a '
                                   'skip is a pass.'}
    return {'tests_executed': executed, 'tests_skipped': skipped}


def judge_pytest(record: Mapping[str, Any]) -> dict[str, Any]:
    """A pytest skip exits 0, so its summary is read too."""
    skipped = sum(int(count) for count in re.findall(r'\b(\d+) (?:skipped|xfailed)\b', record.get('output', '')))
    return {'tests_skipped': skipped, **({'status': 'failed'} if skipped and record['status'] == 'passed' else {})}


def selected_steps(profile: str, step_ids: Sequence[str], changed: Sequence[str] | None, root: Path | None = None) -> set[str]:
    """Which toolchain steps a profile runs. An unknown change set runs both application domains. Given the checkout's
    root, a changed script also brings the domains of the profiles whose scripts import it (SCRP-06)."""
    if not PROFILES[profile].selects_by_change:
        return set(step_ids)
    derived = derived_domains(root) if root is not None else {}
    domains = ({'python', 'web', 'repo_python'} if changed is None
               else {d for path in changed for d in check_domains(path, derived=derived)})
    return set(step_ids) & ((PYTHON_STEPS if 'python' in domains else frozenset())
                            | (WEB_STEPS if 'web' in domains else frozenset())
                            | (REPO_PYTHON_STEPS if 'repo_python' in domains else frozenset()))


@dataclass(frozen=True)
class ToolPlan:
    steps: Sequence[Step] = ()
    env: Mapping[str, str] = field(default_factory=dict)


def registered(root: Path, step: CheckStep, values: Mapping[str, str | tuple[str, ...]]) -> Step:
    return Step(step.id, arguments(step, values), root / step.cwd, step.timeout)


def tool_plan(root: Path, profile: str, changed: Sequence[str] | None) -> tuple[ToolPlan, list[dict[str, Any]]]:
    """The profile's steps to run and the ones left out, from qualification/profiles.py. Needs tools only when a
    step needs them."""
    definition = PROFILES[profile]
    if definition.docker:
        missing = missing_prepared_paths(root, find_tools(root))
        if missing:
            raise Unavailable('not prepared, run scripts/toolchain.py bootstrap explicitly; missing: ' + ', '.join(missing))
        docker_env = reduced_env() | ({'HOME': os.environ['HOME']} if 'HOME' in os.environ else {})
        return ToolPlan([registered(root, step, {'python': sys.executable}) for step in definition.steps], docker_env), []
    known = definition.step_ids
    chosen = selected_steps(profile, sorted(known), changed, root)
    left_out = [{'id': name, 'status': 'not_run', 'reason': OUTSIDE_SCOPE} for name in sorted(known - chosen)]
    if not chosen:
        return ToolPlan(), left_out
    tools = find_tools(root)
    missing = missing_prepared_paths(root, tools)
    if missing:
        raise Unavailable('not prepared, run scripts/toolchain.py bootstrap explicitly; missing: ' + ', '.join(missing))
    values = {'python': sys.executable, 'node': str(Path(tools.node_dir) / 'node'),
              'web_bin': str(root / 'apps/web/node_modules/.bin'), **SELECTIONS}
    built = {step.id: step for step in check_steps(root, tools)}
    steps = [built[step.id] if step.argv is None else registered(root, step, values) for step in definition.steps if step.id in chosen]
    return ToolPlan(steps, child_env(root, tools, verifying=True)), left_out


def toolchain_checks(root: Path, profile: str, plan: Callable[..., tuple[ToolPlan, list[dict[str, Any]]]] = tool_plan) -> list[dict[str, Any]]:
    """Toolchain step records plus a guard that nothing was installed or rewritten."""
    try:
        before = snapshot(root)
        selection, left_out = plan(root, profile, scope_paths(root))
    except (Unavailable, ValueError, OSError) as error:
        return [{'id': 'non_mutation_guard', 'status': 'error', 'model_transport': 'none',
                 'output': f'prerequisite unavailable: {error}'}]
    records = [{**run_step(step, selection.env), **classify(step.id), 'cwd': str(step.cwd)} for step in selection.steps]
    for record in records:
        if record['id'] in SELF_REPORTING_STEPS and record['exit_code'] == EXIT_UNAVAILABLE:
            record['status'] = 'error'
        if record['id'] in NODE_TEST_STEPS:
            record.update(judge_node(record))
        if record['id'] == 'pytest':
            record.update(judge_pytest(record))
        if record['id'] == 'toolchain_scope_tests':
            record.update(judge_unittest(record))
    differences = snapshot_differences(before, snapshot(root))
    return [*left_out, *records, {'id': 'non_mutation_guard', **classify('non_mutation_guard'),
                                  'status': 'failed' if differences else 'passed',
                                  'output': '\n'.join(differences)}]


def exit_code_for(checks: Sequence[Mapping[str, Any]], stable: bool) -> int:
    """A failed check outranks an unavailable one, so a known failure is never reported as missing tools."""
    statuses = {check['status'] for check in checks}
    if 'failed' in statuses or not stable:
        return EXIT_FAILED
    if 'error' in statuses:
        return EXIT_UNAVAILABLE
    return EXIT_PASSED


def run_profile(root: Path, profile: str, *, base_checks: Callable[[Path], list[dict[str, Any]]] = harness_checks,
                plan: Callable[..., tuple[ToolPlan, list[dict[str, Any]]]] = tool_plan) -> int:
    directory = root / '.checks' / profile
    directory.mkdir(parents=True, exist_ok=True)
    lock = root / '.checks/verify.lock'
    try:
        fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        print('Another check owns verify.lock; inspect its recorded PID before manual stale-lock removal.',
              file=sys.stderr)
        return EXIT_UNAVAILABLE
    try:
        with os.fdopen(fd, 'w') as handle:
            handle.write(str(os.getpid()))
        initial = fingerprint(root)
        checks = base_checks(root)
        adapter = adapter_status(root)
        if profile != 'harness':
            checks.extend(toolchain_checks(root, profile, plan))
        final = fingerprint(root)
        stable = final == initial
        code = exit_code_for(checks, stable)
        status = {EXIT_PASSED: 'passed', EXIT_FAILED: 'failed', EXIT_UNAVAILABLE: 'error'}[code]
        scope, not_tested = PROFILES[profile].scope, list(PROFILES[profile].not_tested)
        report = {'schema_version': 'autobots.harness-result/v1', 'template': False,
                  'profile': profile, 'status': status,
                  'completed_at_utc': utc(), 'python_version': sys.version.split()[0],
                  'input_fingerprint': final, 'inputs_unchanged_during_check': stable,
                  'input_manifest': input_manifest(root), 'checks': checks,
                  'assistant_adapter': adapter, 'scope': scope, 'not_tested': not_tested}
        temporary = directory / 'latest.tmp'
        temporary.write_text(json.dumps(report, indent=2) + '\n')
        temporary.replace(directory / 'latest.json')
        print(json.dumps({'profile': profile, 'status': status, 'inputs_stable': stable, 'scope': scope,
                          'checks': [{k: c[k] for k in ('id', 'status')} for c in checks],
                          'assistant_adapter': {k: adapter[k] for k in ('state', 'reason')},
                          'report': f'.checks/{profile}/latest.json'}, indent=2))
        if code != EXIT_PASSED:
            for check in checks:
                if check['status'] not in {'passed', 'not_run'}:
                    detail = check.get('output') or '\n'.join(check.get('errors', []))
                    print(f"{check['id']}: {detail}", file=sys.stderr)
        return code
    finally:
        lock.unlink(missing_ok=True)


def main() -> int:
    if sys.version_info < (3, 12):  # noqa: UP036 - a guard for an older interpreter running this script
        print('Python 3.12+ is required; use the qualified python3.12 interpreter.', file=sys.stderr)
        return EXIT_UNAVAILABLE
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--profile', required=True, choices=IMPLEMENTED_PROFILES)
    args = parser.parse_args()
    return run_profile(project_root(), args.profile)


if __name__ == '__main__':
    raise SystemExit(main())
