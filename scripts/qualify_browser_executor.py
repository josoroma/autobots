#!/usr/bin/env python3
"""Qualify the isolated browser executor live, US-14.13, PRD-Tool-Catalog BX-05 and Decision 0018.

Needs Docker, the two images built from infra/browser (see the operations runbook), and outbound
network to the one qualification host, https://example.com/. A disposable database gives the
cancel, lease and sweeper cases real runs. A scripted driver, never a model, uses the browser.
The report binds the result to the image definitions and the proxy's code; the executor reports
qualified only from a passing report at today's fingerprint.

In no verification profile: it needs network and images a check never builds or fetches.
Exit codes: 0 qualified, 1 a case failed, 2 a prerequisite is missing.
"""
from __future__ import annotations

import json
import secrets
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from app_db import AppStack, apply_migrations, bootstrap, seed, MIGRATIONS, WORKSPACE_A
from disposable_db import (PROJECT_PREFIX, Cases, Refused, Target, Unavailable, free_port, other_resources,
                           remove_stack, require_identity, run, tool_env)
from harness_lib import project_root
from supabase_stack import generated_values, require_images, require_rendered

REPORT = Path('.checks/browser-executor/qualification.json')
IMAGES = ('autobots-browser:local', 'autobots-egress:local')
PYTHON = Path('services/agent/.venv/bin/python')


def executor_fingerprint(root: Path) -> dict[str, str]:
    completed = subprocess.run([str(root / PYTHON), '-c', 'import json, sys; from pathlib import Path; '
                                'from autobots.adapters.browser_executor import images_fingerprint; '
                                'print(json.dumps(images_fingerprint(Path(sys.argv[1]))))', str(root)],
                               env={**tool_env(), 'PYTHONPATH': str(root / 'services/agent/src')}, capture_output=True, text=True, check=False)
    if completed.returncode:
        raise Unavailable('the executor fingerprint could not be computed')
    return json.loads(completed.stdout)


def qualify(root: Path) -> int:
    for image in IMAGES:
        if run(['docker', 'image', 'inspect', image], tool_env()).returncode:
            raise Unavailable(f'{image} is not built; build it as the operations runbook says')
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
    cases = Cases()
    before = other_resources(project)
    started_at = time.monotonic()
    try:
        started = stack.compose('up', '-d', '--wait', '--wait-timeout', '120', 'db')
        if started.returncode:
            raise Unavailable(f'the disposable database did not start: {started.stderr[-300:]}')
        bootstrap(stack, root)
        applied, failure = apply_migrations(stack, root / MIGRATIONS)
        cases.check('the disposable database is migrated', 'no failure', failure or f'{applied} migrations', failure is None)
        seeded = seed(stack, root)
        workspace = stack.migrator(f"insert into public.workspaces (id, name) values ('{WORKSPACE_A}', 'Workspace A');")
        cases.check('the disposable database is seeded', 'exit 0', f'{seeded.returncode}, {workspace.returncode}', seeded.returncode == 0 == workspace.returncode)
        url = f'postgresql://autobots_runtime:{stack.runtime_password}@127.0.0.1:{db_port}/postgres'
        result = subprocess.run([str(root / PYTHON), str(root / 'tests/db/browser_executor_check.py'), WORKSPACE_A, str(db_port), str(gateway_port)],
                                env={**tool_env(), 'AUTOBOTS_DATABASE_URL': url, 'PYTHONPATH': str(root / 'services/agent/src'),
                                     'PYTHONDONTWRITEBYTECODE': '1'},
                                capture_output=True, text=True, timeout=900, check=False, cwd=root)
        if result.returncode or not result.stdout.strip():
            (root / REPORT).parent.mkdir(parents=True, exist_ok=True)
            (root / REPORT).with_suffix('.err').write_text(result.stderr)
            cases.check('the executor check ran', 'exit 0', f'exit {result.returncode}: {result.stderr.strip()[-600:]}', False)
        else:
            for case in json.loads(result.stdout.strip().splitlines()[-1])['cases']:
                cases.check(case['id'], case['expected'], case['observed'], case['passed'])
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
    passed = all(record['status'] == 'passed' for record in cases.records)
    path = root / REPORT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        'schema_version': 'autobots.browser-executor-qualification/v1', 'completed_at_utc': datetime.now(timezone.utc).isoformat(),
        'duration_seconds': round(time.monotonic() - started_at, 1), 'status': 'passed' if passed else 'failed',
        'executor_fingerprint': executor_fingerprint(root), 'target_class': 'disposable', 'driver': 'scripted',
        'network': 'outbound to https://example.com/ only for the allowed case', 'cases': cases.records,
        'not_established': ['H1', 'product acceptance', 'browsing with a real model', 'a server-side redirect to a private address']}, indent=2) + '\n')
    print(f"{'PASS' if passed else 'FAIL'}: {sum(r['status'] == 'passed' for r in cases.records)} of {len(cases.records)} executor cases passed.")
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
