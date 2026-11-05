#!/usr/bin/env python3
"""Verify the delivered repository harness, never claim unimplemented app gates."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

from harness_lib import adapter_status, config_errors, fingerprint, input_manifest, project_root, reduced_env


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


def main() -> int:
    if sys.version_info < (3, 12):
        print('Python 3.12+ is required; use the qualified python3.12 interpreter.', file=sys.stderr)
        return 2
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', required=True,
                        choices=['harness', 'fast', 'full', 'db', 'operations'])
    args = parser.parse_args()
    root = project_root()
    if args.profile != 'harness':
        print(json.dumps({'profile': args.profile, 'status': 'not_implemented',
                          'reason': 'Application toolchain/database checks are not yet implemented; '
                                    'a passing harness profile does not substitute for them.'}))
        return 2
    directory = root / '.checks/harness'
    directory.mkdir(parents=True, exist_ok=True)
    lock = directory / 'verify.lock'
    try:
        fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        print('Another check owns verify.lock; inspect its recorded PID before manual stale-lock removal.',
              file=sys.stderr)
        return 2
    try:
        with os.fdopen(fd, 'w') as handle:
            handle.write(str(os.getpid()))
        initial = fingerprint(root)
        problems = config_errors(root)
        checks = [{'id': 'project_configuration', 'class': 'static', 'model_transport': 'none',
                   'status': 'passed' if not problems else 'failed', 'errors': problems}]
        adapter = adapter_status(root)
        checks.append(run_check(root, 'backlog_validation',
                                [sys.executable, 'scripts/specs.py', 'validate']))
        checks.append(run_check(root, 'harness_behavior_tests',
                                [sys.executable, '-m', 'unittest', 'discover', '-s',
                                 'tests/harness', '-p', 'test_*.py', '-v']))
        test_count = re.search(r'Ran (\d+) tests?', checks[-1].get('output', ''))
        checks[-1]['tests_executed'] = int(test_count.group(1)) if test_count else 0
        if checks[-1]['tests_executed'] == 0:
            checks[-1]['status'] = 'failed'
            checks[-1]['output'] += '\nNo executed tests were reported; an empty suite is not a pass.'
        final = fingerprint(root)
        stable = final == initial
        passed = stable and all(check['status'] == 'passed' for check in checks)
        report = {'schema_version': 'autobots.harness-result/v1', 'template': False,
                  'profile': 'harness', 'status': 'passed' if passed else 'failed',
                  'completed_at_utc': utc(), 'python_version': sys.version.split()[0],
                  'input_fingerprint': final, 'inputs_unchanged_during_check': stable,
                  'input_manifest': input_manifest(root), 'checks': checks,
                  'assistant_adapter': adapter,
                  'scope': 'Project configuration, backlog structure and deterministic harness fixtures only',
                  'not_tested': ['Claude event delivery', 'application', 'Supabase',
                                 'Docker', 'OpenRouter inference', 'complete H0/H1']}
        temporary = directory / 'latest.tmp'
        temporary.write_text(json.dumps(report, indent=2) + '\n')
        temporary.replace(directory / 'latest.json')
        print(json.dumps({'profile': 'harness', 'status': report['status'],
                          'inputs_stable': stable, 'checks': [{k: c[k] for k in ('id', 'status')}
                                                            for c in checks],
                          'assistant_adapter': {k: adapter[k] for k in ('state', 'reason')},
                          'report': '.checks/harness/latest.json'}, indent=2))
        if not passed:
            for check in checks:
                if check['status'] != 'passed':
                    print(check.get('output') or '\n'.join(check.get('errors', [])), file=sys.stderr)
        return 0 if passed else 1
    finally:
        lock.unlink(missing_ok=True)


if __name__ == '__main__':
    raise SystemExit(main())
