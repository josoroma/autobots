#!/usr/bin/env python3
"""Qualify the isolated browser executor live, US-14.13, PRD-Tool-Catalog BX-05 and Decision 0018.

Needs Docker, the two images built by `make browser-images` (scripts/browser_images.py), and outbound
network to the one qualification host, https://example.com/. A disposable database gives the
cancel, lease and sweeper cases real runs. A scripted driver, never a model, uses the browser.
It refuses images whose fingerprint label isn't today's before it starts anything (refactor plan R-57),
and the report binds the result to the fingerprint it started with. The executor reports qualified only
from a passing report at today's fingerprint, while both images carry that fingerprint's label.

In no verification profile: it needs network and images a check never builds or fetches.
Exit codes: 0 qualified, 1 a case failed, 2 a prerequisite is missing.
"""
from __future__ import annotations

import secrets
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from app_db import MIGRATIONS, WORKSPACE_A, AppStack, apply_migrations, bootstrap, seed
from browser_images import (
    TAGS,
    fingerprint_digest,
    image_states,
    images_fingerprint,
    require_current_images,
)
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
from supabase_stack import generated_values, require_images, require_rendered

REPORT = Path('.checks/browser-executor/qualification.json')
# The images the executor starts; qualify_browse_goal checks the same tags.
IMAGES = TAGS


def executor_fingerprint(root: Path) -> dict[str, str]:
    """The service's fingerprint of the images' sources, which a report binds; qualify_browse_goal records it too."""
    try:
        return images_fingerprint(root)
    except OSError as error:
        raise Unavailable(f'the executor fingerprint could not be computed: {error}') from error


def qualify(root: Path) -> int:
    fingerprint = executor_fingerprint(root)
    require_current_images(fingerprint)
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
        cases.arranged('the disposable database migrated', 'no failure', failure or f'{applied} migrations', failure is None)
        cases.arrange('the disposable database seeded, with workspace A', seed(stack, root),
                      stack.migrator(f"insert into public.workspaces (id, name) values ('{WORKSPACE_A}', 'Workspace A');"))
        url = f'postgresql://autobots_runtime:{stack.runtime_password}@127.0.0.1:{db_port}/postgres'
        run_child_check(cases, root, 'browser_executor_check.py', WORKSPACE_A, str(db_port), str(gateway_port), label='the executor check',
                        env=service_env(root, url), timeout=900, cwd=root, err_dir=root / REPORT.parent, err_name=REPORT.stem)
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
    states = image_states(fingerprint)
    cases.check('the images still carry the fingerprint the check started with', 'both current',
                ', '.join(f'{tag}: {state}' for tag, state in states.items()), all(state == 'current' for state in states.values()))
    passed = cases.status == 'passed'
    write_report(root / REPORT, {
        'schema_version': 'autobots.browser-executor-qualification/v1', 'completed_at_utc': datetime.now(UTC).isoformat(),
        'duration_seconds': round(time.monotonic() - started_at, 1), 'status': cases.status,
        'executor_fingerprint': fingerprint, 'image_label': fingerprint_digest(fingerprint), 'target_class': 'disposable', 'driver': 'scripted',
        'network': 'outbound to https://example.com/ only for the allowed case', 'cases': cases.records,
        'not_established': ['H1', 'product acceptance', 'browsing with a real model', 'a server-side redirect to a private address']})
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
