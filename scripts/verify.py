#!/usr/bin/env python3
"""One local verification runner. It never installs, and it never claims unimplemented gates.

Exit codes: 0 passed, 1 a required check failed, 2 a prerequisite is unavailable or a check could
not run to a result. Passing `harness`, `fast`, `full` or `db` establishes neither H0, H1 nor product
acceptance. `operations` is not implemented, and reports that with exit code 2.
"""
from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

from harness_lib import (FULL_ONLY_CHECKS, adapter_status, changed_paths, check_domains, config_errors,
                         fingerprint, input_manifest, project_root, reduced_env)
from toolchain import (LONG, Step, Unavailable, check_steps, child_env, find_tools, missing_prepared_paths,
                       run_step, snapshot, snapshot_differences)

EXIT_PASSED, EXIT_FAILED, EXIT_UNAVAILABLE = 0, 1, 2
IMPLEMENTED_PROFILES = ('harness', 'fast', 'full', 'db')
# These report exit 2 for a missing prerequisite, which is not a failed check.
SELF_REPORTING_STEPS = frozenset({'fault_qualification', 'disposable_qualification'})
PYTHON_STEPS = frozenset({'python_lock', 'python_env', 'ruff_check', 'ruff_format', 'mypy', 'pytest'})
WEB_STEPS = frozenset({'node_lock', 'node_version', 'lint', 'format_check', 'typegen', 'typecheck'})
OUTSIDE_SCOPE = 'outside the changed scope of this fast run'
NOT_TESTED = ['Claude event delivery', 'Supabase', 'Docker', 'OpenRouter inference', 'complete H0/H1']
APPLICATION_NOT_TESTED = ['generated contract drift, no contract exists yet', 'browser fixtures, none are configured']
DB_NOT_TESTED = ['the persistent database', 'the pinned self-hosted release', 'generated database type drift, no types exist yet']


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_check(root: Path, name: str, argv: list[str]) -> dict:
    start = utc()
    began = time.monotonic()
    # Tests receive no inherited API keys, credentials or assistant configuration.
    env = reduced_env()
    env.update(PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8')
    try:
        result = subprocess.run(argv, cwd=root, env=env, capture_output=True,
                                text=True, timeout=60, check=False)
        status, code = ('passed' if result.returncode == 0 else 'failed'), result.returncode
        output = (result.stdout + result.stderr)[-16000:]
    except (OSError, subprocess.TimeoutExpired) as exc:
        status, code, output = 'error', None, type(exc).__name__
    return {'id': name, 'class': 'static_or_fixture', 'model_transport': 'none',
            'command_argv': argv, 'cwd': str(root), 'started_at_utc': start,
            'finished_at_utc': utc(), 'duration_seconds': round(time.monotonic()-began, 3),
            'exit_code': code, 'status': status, 'output': output}


def harness_checks(root: Path) -> list[dict]:
    problems = config_errors(root)
    checks = [{'id': 'project_configuration', 'class': 'static', 'model_transport': 'none',
               'status': 'passed' if not problems else 'failed', 'errors': problems},
              run_check(root, 'backlog_validation', [sys.executable, 'scripts/specs.py', 'validate']),
              run_check(root, 'harness_behavior_tests',
                        [sys.executable, '-m', 'unittest', 'discover', '-s',
                         'tests/harness', '-p', 'test_*.py', '-v'])]
    test_count = re.search(r'Ran (\d+) tests?', checks[-1].get('output', ''))
    checks[-1]['tests_executed'] = int(test_count.group(1)) if test_count else 0
    if checks[-1]['tests_executed'] == 0:
        if checks[-1]['status'] == 'passed':
            checks[-1]['status'] = 'failed'
        checks[-1]['output'] += '\nNo executed tests were reported; an empty suite is not a pass.'
    return checks


def selected_steps(profile: str, step_ids: Sequence[str], changed: Sequence[str] | None) -> set[str]:
    """Which toolchain steps a profile runs. An unknown change set runs both application domains."""
    if profile == 'full':
        return set(step_ids)
    domains = {'python', 'web'} if changed is None else {d for path in changed for d in check_domains(path)}
    return set(step_ids) & ((PYTHON_STEPS if 'python' in domains else frozenset())
                            | (WEB_STEPS if 'web' in domains else frozenset()))


@dataclass(frozen=True)
class ToolPlan:
    steps: Sequence[Step] = ()
    env: Mapping[str, str] = field(default_factory=dict)


def tool_plan(root: Path, profile: str, changed: Sequence[str] | None) -> tuple[ToolPlan, list[dict]]:
    """The toolchain steps to run and the ones left out. Needs tools only when a step needs them."""
    if profile == 'db':
        step = Step('disposable_qualification', (sys.executable, 'scripts/disposable_db.py', 'qualify'), root, LONG)
        return ToolPlan([step], reduced_env() | ({'HOME': os.environ['HOME']} if 'HOME' in os.environ else {})), []
    known = {*PYTHON_STEPS, *WEB_STEPS, *FULL_ONLY_CHECKS}
    chosen = selected_steps(profile, sorted(known), changed)
    left_out = [{'id': name, 'status': 'not_run', 'reason': OUTSIDE_SCOPE} for name in sorted(known - chosen)]
    if not chosen:
        return ToolPlan(), left_out
    tools = find_tools(root)
    missing = missing_prepared_paths(root, tools)
    if missing:
        raise Unavailable('not prepared, run scripts/toolchain.py bootstrap explicitly; missing: ' + ', '.join(missing))
    qualification = Step('fault_qualification', (sys.executable, 'scripts/qualify_faults.py'), root, LONG)
    steps = [step for step in (*check_steps(root, tools), qualification) if step.id in chosen]
    return ToolPlan(steps, child_env(root, tools, verifying=True)), left_out


def toolchain_checks(root: Path, profile: str, plan: Callable = tool_plan) -> list[dict]:
    """Toolchain step records plus a guard that nothing was installed or rewritten."""
    try:
        before = snapshot(root)
        selection, left_out = plan(root, profile, changed_paths(root))
    except (Unavailable, ValueError, OSError) as error:
        return [{'id': 'non_mutation_guard', 'status': 'error', 'model_transport': 'none',
                 'output': f'prerequisite unavailable: {error}'}]
    records = [{**run_step(step, selection.env), 'class': 'static_or_fixture', 'model_transport': 'none'}
               for step in selection.steps]
    for record in records:
        if record['id'] in SELF_REPORTING_STEPS and record['exit_code'] == EXIT_UNAVAILABLE:
            record['status'] = 'error'
    differences = snapshot_differences(before, snapshot(root))
    return [*left_out, *records, {'id': 'non_mutation_guard', 'class': 'static', 'model_transport': 'none',
                                  'status': 'failed' if differences else 'passed',
                                  'output': '\n'.join(differences)}]


def exit_code_for(checks: Sequence[Mapping], stable: bool) -> int:
    """A failed check outranks an unavailable one, so a known failure is never reported as missing tools."""
    statuses = {check['status'] for check in checks}
    if 'failed' in statuses or not stable:
        return EXIT_FAILED
    if 'error' in statuses:
        return EXIT_UNAVAILABLE
    return EXIT_PASSED


def run_profile(root: Path, profile: str, *, base_checks: Callable[[Path], list[dict]] = harness_checks,
                plan: Callable = tool_plan) -> int:
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
        scope = {'harness': 'Project configuration, backlog structure and deterministic harness fixtures only',
                 'db': 'Harness checks plus synthetic migrations, seeds and authorization on a disposable target'
                 }.get(profile, 'Harness checks plus local static checks, focused tests and, for full, the production build')
        not_tested = {'harness': ['application', *NOT_TESTED], 'db': [*DB_NOT_TESTED, *NOT_TESTED]
                      }.get(profile, [*APPLICATION_NOT_TESTED, *NOT_TESTED])
        report = {'schema_version': 'autobots.harness-result/v1', 'template': False,
                  'profile': profile, 'status': status,
                  'completed_at_utc': utc(), 'python_version': sys.version.split()[0],
                  'input_fingerprint': final, 'inputs_unchanged_during_check': stable,
                  'input_manifest': input_manifest(root), 'checks': checks,
                  'assistant_adapter': adapter, 'scope': scope, 'not_tested': not_tested}
        temporary = directory / 'latest.tmp'
        temporary.write_text(json.dumps(report, indent=2) + '\n')
        temporary.replace(directory / 'latest.json')
        print(json.dumps({'profile': profile, 'status': status, 'inputs_stable': stable,
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
    if sys.version_info < (3, 12):
        print('Python 3.12+ is required; use the qualified python3.12 interpreter.', file=sys.stderr)
        return EXIT_UNAVAILABLE
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--profile', required=True, choices=[*IMPLEMENTED_PROFILES, 'operations'])
    args = parser.parse_args()
    if args.profile not in IMPLEMENTED_PROFILES:
        print(json.dumps({'profile': args.profile, 'status': 'not_implemented',
                          'reason': 'Operations checks are not yet implemented; '
                                    'a passing harness, fast, full or db profile does not substitute for them.'}))
        return EXIT_UNAVAILABLE
    return run_profile(project_root(), args.profile)


if __name__ == '__main__':
    raise SystemExit(main())
