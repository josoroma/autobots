#!/usr/bin/env python3
"""Run the real checkers on known-good and known-bad fixtures. Calls no model and installs nothing.

A good fixture must exit 0. A bad one must fail with its case's marker in the output, so a bad
fixture failing for another reason, such as a crashed tool, does not count as a detected fault.

Exit codes: 0 every case behaved as expected, 1 a case did not, 2 prerequisite unavailable.
Passing shows these checkers catch these faults. It establishes neither H1 nor product acceptance.
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from harness_lib import fingerprint, project_root
from toolchain import Step, Unavailable, child_env, find_tools, missing_prepared_paths, run_step

FAULTS = Path('tests/faults')
CONFIG = 'services/agent/pyproject.toml'
ARRANGED_KEY = 'arranged-not-a-real-key'
REPORT = Path('.checks/faults/latest.json')
KINDS = ('python', 'typescript', 'contract', 'state', 'model_transport')


@dataclass(frozen=True)
class Case:
    id: str
    kind: str
    # None means the fixture is good and must pass.
    marker: str | None
    argv: tuple[str, ...]
    cwd: str = '.'
    with_arranged_key: bool = False


def cases(root: Path) -> list[Case]:
    venv = root / 'services/agent/.venv/bin'
    python, ruff, mypy, pytest = (str(venv / name) for name in ('python', 'ruff', 'mypy', 'pytest'))
    web_bin = root / 'apps/web/node_modules/.bin'
    tsc = (str(web_bin / 'tsc'), '--noEmit', '--strict', '--skipLibCheck', '--target', 'es2022', '--module', 'esnext',
           '--moduleResolution', 'bundler', '--pretty', 'false')
    eslint = (str(web_bin / 'eslint'), '--config', 'apps/web/eslint.config.mjs', '--no-warn-ignored')
    ruff_check = (ruff, 'check', '--no-cache', '--config', CONFIG)
    mypy_check = (mypy, '--config-file', CONFIG, '--cache-dir', os.devnull)
    pytest_run = (pytest, '-c', CONFIG, '-p', 'no:cacheprovider', '--rootdir', str(FAULTS))
    state = (sys.executable, str(FAULTS / 'state/check.py'))
    contract = (python, 'check.py')
    transport = FAULTS / 'model_transport'
    python_good = str(FAULTS / 'python/good/sample.py')
    typescript_good = str(FAULTS / 'typescript/good/sample.ts')
    return [
        Case('python_lint_good', 'python', None, (*ruff_check, python_good)),
        Case('python_lint_bad', 'python', 'F401', (*ruff_check, str(FAULTS / 'python/bad_lint/sample.py'))),
        Case('python_type_good', 'python', None, (*mypy_check, python_good)),
        Case('python_type_bad', 'python', 'return-value', (*mypy_check, str(FAULTS / 'python/bad_type/sample.py'))),
        Case('python_behavior_good', 'python', None, (*pytest_run, str(FAULTS / 'python/good_behavior'))),
        Case('python_behavior_bad', 'python', 'test_sample.py::test_total', (*pytest_run, str(FAULTS / 'python/bad_behavior'))),
        Case('typescript_type_good', 'typescript', None, (*tsc, typescript_good)),
        Case('typescript_type_bad', 'typescript', 'TS2322', (*tsc, str(FAULTS / 'typescript/bad_type/sample.ts'))),
        Case('typescript_lint_good', 'typescript', None, (*eslint, typescript_good)),
        Case('typescript_lint_bad', 'typescript', 'no-explicit-any', (*eslint, str(FAULTS / 'typescript/bad_lint/sample.ts'))),
        Case('contract_good', 'contract', None, (*contract, 'good/expected.json'), str(FAULTS / 'contract')),
        Case('contract_bad', 'contract', 'CONTRACT DRIFT', (*contract, 'bad/expected.json'), str(FAULTS / 'contract')),
        Case('state_good', 'state', None, (*state, str(FAULTS / 'state/good.json'))),
        Case('state_cancel_good', 'state', None, (*state, str(FAULTS / 'state/good_cancel.json'))),
        Case('state_terminal_bad', 'state', 'INVALID TRANSITION', (*state, str(FAULTS / 'state/bad_terminal_resume.json'))),
        Case('state_skipped_bad', 'state', 'INVALID TRANSITION', (*state, str(FAULTS / 'state/bad_skipped_verification.json'))),
        Case('state_reducer_bad', 'state', 'REDUCER', (*state, str(FAULTS / 'state/bad_reducer.json'))),
        Case('state_private_bad', 'state', 'PRIVATE DATA', (*state, str(FAULTS / 'state/bad_private_event.json'))),
        Case('model_fake_good', 'model_transport', None, (*pytest_run, str(transport / 'test_good_fake_transport.py'))),
        Case('model_real_bad', 'model_transport', 'SocketBlockedError',
             (*pytest_run, str(transport / 'test_bad_real_transport.py')), with_arranged_key=True),
        Case('model_unapproved_bad', 'model_transport', 'not an approved profile',
             (*pytest_run, str(transport / 'test_bad_unapproved_model.py'))),
    ]


def outcome(case: Case, record: Mapping) -> str | None:
    """Why this case did not behave as expected, or None if it did."""
    if record['exit_code'] is None:
        return 'did not run to a result'
    if case.marker is None:
        if record['status'] != 'passed':
            return 'a good fixture failed'
        return 'a good fixture skipped its test' if re.search(r'\b\d+ (?:skipped|xfailed)\b', record['output']) else None
    if record['exit_code'] == 0:
        return 'a bad fixture passed, so its fault went undetected'
    if case.marker not in record['output']:
        return f'failed without the expected marker {case.marker!r}'
    return None


def run_cases(root: Path, selected: Sequence[Case], env: Mapping[str, str]) -> list[dict]:
    results = []
    for case in selected:
        case_env = {**env, 'PYTHONDONTWRITEBYTECODE': '1'}
        if case.with_arranged_key:
            case_env['OPENROUTER_API_KEY'] = ARRANGED_KEY
        record = run_step(Step(case.id, case.argv, root / case.cwd), case_env)
        problem = outcome(case, record)
        print(f"{'PASS' if problem is None else 'FAIL'}: {case.id}" + (f': {problem}' if problem else ''))
        results.append({'id': case.id, 'kind': case.kind, 'expected': 'fail' if case.marker else 'pass',
                        'marker': case.marker, 'argv': record['argv'], 'exit_code': record['exit_code'],
                        'model_transport': 'none' if case.kind != 'model_transport' else 'mock',
                        'status': 'passed' if problem is None else 'failed', 'problem': problem,
                        'output': record['output'][-2000:]})
    return results


def main() -> int:
    if sys.version_info < (3, 12):  # noqa: UP036 - a guard for an older interpreter running this script
        print('ERROR: Python 3.12+ is required.', file=sys.stderr)
        return 2
    root = project_root()
    # A run that cannot finish leaves no earlier result to be mistaken for this one.
    (root / REPORT).unlink(missing_ok=True)
    try:
        tools = find_tools(root)
        missing = missing_prepared_paths(root, tools)
        if missing:
            raise Unavailable('not prepared, run scripts/toolchain.py bootstrap explicitly; missing: ' + ', '.join(missing))
    except Unavailable as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 2
    results = run_cases(root, cases(root), child_env(root, tools, verifying=True))
    passed = all(result['status'] == 'passed' for result in results)
    path = root / REPORT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'schema_version': 'autobots.fault-qualification/v1',
                                'completed_at_utc': datetime.now(UTC).isoformat(),
                                'input_fingerprint': fingerprint(root),
                                'status': 'passed' if passed else 'failed', 'cases': results,
                                'not_established': ['H1', 'product acceptance', 'live inference']}, indent=2) + '\n')
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
