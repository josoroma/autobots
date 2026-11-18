#!/usr/bin/env python3
"""Check browse_goal live, US-14.12, PRD-Tool-Catalog "Autonomous browsing" and Decision 0020.

browse_goal runs through the real gateway, approvals, loop middleware, admission and isolated
executor, on a disposable database, against https://example.com/ (Decision 0018's qualification
host). The model is scripted, so no inference provider is called and nothing is spent. Needs Docker,
the executor's images and a passing executor qualification at today's fingerprint.

In no verification profile: it needs network and images a check never builds or fetches.
Exit codes: 0 passed, 1 a case failed, 2 a prerequisite is missing.
"""
from __future__ import annotations

import secrets
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from app_db import MIGRATIONS, WORKSPACE_A, AppStack, apply_migrations, bootstrap, seed
from disposable_db import (
    PROJECT_PREFIX,
    Cases,
    Refused,
    Target,
    Unavailable,
    free_port,
    other_resources,
    remove_stack,
    require_identity,
    run,
    tool_env,
)
from harness_lib import project_root
from qualification.children import run_child_check, service_env
from qualification.records import write_report
from qualify_browser_executor import IMAGES, executor_fingerprint
from qualify_browser_executor import REPORT as EXECUTOR_REPORT
from supabase_stack import generated_values, require_images, require_rendered

REPORT = Path('.checks/browse-goal/check.json')
# The model is scripted: no inference provider is called.
MODEL_TRANSPORT = 'mock'


def qualify(root: Path) -> int:
    for image in IMAGES:
        if run(['docker', 'image', 'inspect', image], tool_env()).returncode:
            raise Unavailable(f'{image} is not built; build it as the operations runbook says')
    if not (root / EXECUTOR_REPORT).exists():
        raise Unavailable('the executor is not qualified; run scripts/qualify_browser_executor.py first')
    project = f'{PROJECT_PREFIX}{secrets.token_hex(4)}'
    gateway_port = free_port()
    db_port = free_port([gateway_port])
    target = Target(project, db_port, gateway_port)
    stack = AppStack(target, root, root / 'infra/supabase/upstream/docker-compose.yml', values=generated_values(gateway_port, db_port))
    stack.migrator_password, stack.runtime_password = secrets.token_hex(24), secrets.token_hex(24)
    require_identity(target, tool_env())
    (root / REPORT).unlink(missing_ok=True)
    rendered = require_rendered(stack)
    require_images({'services': {'db': rendered['services']['db']}})
    cases = Cases(model_transport=MODEL_TRANSPORT)
    before = other_resources(project)
    started_at = time.monotonic()
    try:
        started = stack.compose('up', '-d', '--wait', '--wait-timeout', '120', 'db')
        if started.returncode:
            raise Unavailable(f'the disposable database did not start: {started.stderr[-300:]}')
        bootstrap(stack, root)
        applied, failure = apply_migrations(stack, root / MIGRATIONS)
        cases.arranged('the disposable database migrated', 'no failure', failure or f'{applied} migrations', failure is None)
        cases.arrange('the disposable database seeded, with workspace A', seed(stack, root),
                      stack.migrator(f"insert into public.workspaces (id, name) values ('{WORKSPACE_A}', 'Workspace A');"))
        url = f'postgresql://autobots_runtime:{stack.runtime_password}@127.0.0.1:{db_port}/postgres'
        run_child_check(cases, root, 'checks/browse_goal_check.py', WORKSPACE_A, label='the browse_goal check', env=service_env(root, url), timeout=900,
                        cwd=root, err_dir=root / REPORT.parent, err_name=REPORT.stem)
    finally:
        remove_stack(stack)
        leftover = run(['docker', 'ps', '-a', '--filter', 'label=autobots.browser=1', '--format', '{{.Names}}'], tool_env()).stdout.split()
        for name in leftover:
            run(['docker', 'rm', '-f', name], tool_env())
        networks = run(['docker', 'network', 'ls', '--filter', 'label=autobots.browser=1', '--format', '{{.Name}}'], tool_env()).stdout.split()
        for name in networks:
            run(['docker', 'network', 'rm', name], tool_env())
    cases.check('no executor container or network is left', 'none', f'{len(leftover)} containers, {len(networks)} networks removed after the check',
                not leftover and not networks)
    after = other_resources(project)
    cases.check('other Docker resources are untouched', 'same', f'{len(before)} before, {len(after)} after', before == after)
    passed = cases.status == 'passed'
    write_report(root / REPORT, {
        'schema_version': 'autobots.browse-goal-check/v1', 'completed_at_utc': datetime.now(UTC).isoformat(),
        'duration_seconds': round(time.monotonic() - started_at, 1), 'status': cases.status,
        'executor_fingerprint': executor_fingerprint(root), 'target_class': 'disposable', 'driver': 'scripted',
        'network': 'outbound to https://example.com/ only', 'model': 'scripted, no provider', 'cases': cases.records,
        'not_established': ['H1', 'product acceptance', 'browsing with a real model', 'the persistent database']})
    print(f"{'PASS' if passed else 'FAIL'}: {sum(r['status'] == 'passed' for r in cases.records)} of {len(cases.records)} browse_goal cases passed.")
    return 0 if passed else 1


def main() -> int:
    try:
        return qualify(project_root())
    except Refused as refusal:
        print(f'REFUSED before any change: {refusal}', file=sys.stderr)
        return 1
    except Unavailable as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
