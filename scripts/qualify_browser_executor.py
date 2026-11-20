#!/usr/bin/env python3
"""Qualify the isolated browser executor live, US-14.13, PRD-Tool-Catalog BX-05 and Decision 0018.

Needs Docker, the two images built by `make browser-images` (scripts/browser_images.py), and outbound
network to the one qualification host, https://example.com/. A disposable database gives the
cancel, lease and sweeper cases real runs. A scripted driver, never a model, uses the browser.
It refuses images whose fingerprint label isn't today's before it starts anything (refactor plan R-57),
and the report binds the result to the fingerprint it started with. The executor reports qualified only
from a passing report at today's fingerprint, while both images carry that fingerprint's label.

It then qualifies browser-use (Decision 0035 Y8, US-17.3) on a fresh disposable stack, when its image carries
today's browser-use fingerprint: browse_goal runs on browser-use through the real gateway, admission, model endpoint
and relay, with a scripted model, reaching only the qualification host. Its report is its own, bound to its own
fingerprint, and browser-use reports qualified only while the executor does too. Without its image, browse_goal stays
on Autobots' loop. `--browser-use` runs only that phase, which needs the executor qualified already.

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
    BROWSER_USE,
    TAGS,
    browser_use_fingerprint,
    browser_use_state,
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
BROWSER_USE_REPORT = Path('.checks/browser-executor/browser-use.json')
# The images the executor starts; qualify_browse_goal checks the same tags.
IMAGES = TAGS


def executor_fingerprint(root: Path) -> dict[str, str]:
    """The service's fingerprint of the images' sources, which a report binds; qualify_browse_goal records it too."""
    try:
        return images_fingerprint(root)
    except OSError as error:
        raise Unavailable(f'the executor fingerprint could not be computed: {error}') from error


class Stack:
    """A disposable database stack, migrated and seeded with workspace A, removed with any executor container."""

    def __init__(self, root: Path) -> None:
        self.root = root
        project = f'{PROJECT_PREFIX}{secrets.token_hex(4)}'
        self.gateway_port = free_port()
        self.db_port = free_port([self.gateway_port])
        self.target = Target(project, self.db_port, self.gateway_port)
        self.app = AppStack(self.target, root, root / 'infra/supabase/upstream/docker-compose.yml',
                            values=generated_values(self.gateway_port, self.db_port))
        self.app.migrator_password, self.app.runtime_password = secrets.token_hex(24), secrets.token_hex(24)

    def prepare(self) -> list[str]:
        require_identity(self.target, tool_env())
        rendered = require_rendered(self.app)
        require_images({'services': {'db': rendered['services']['db']}})
        return other_resources(self.target.project)

    def up(self, cases: Cases) -> str:
        started = self.app.compose('up', '-d', '--wait', '--wait-timeout', '120', 'db')
        if started.returncode:
            raise Unavailable(f'the disposable database did not start: {started.stderr[-300:]}')
        bootstrap(self.app, self.root)
        applied, failure = apply_migrations(self.app, self.root / MIGRATIONS)
        cases.arranged('the disposable database migrated', 'no failure', failure or f'{applied} migrations', failure is None)
        cases.arrange('the disposable database seeded, with workspace A', seed(self.app, self.root),
                      self.app.migrator(f"insert into public.workspaces (id, name) values ('{WORKSPACE_A}', 'Workspace A');"))
        return f'postgresql://autobots_runtime:{self.app.runtime_password}@127.0.0.1:{self.db_port}/postgres'

    def down(self, cases: Cases, before: list[str]) -> None:
        remove_stack(self.app)
        leftover = run(['docker', 'ps', '-a', '--filter', 'label=autobots.browser=1', '--format', '{{.Names}}'], tool_env()).stdout.split()
        for name in leftover:
            run(['docker', 'rm', '-f', name], tool_env())
        networks = run(['docker', 'network', 'ls', '--filter', 'label=autobots.browser=1', '--format', '{{.Name}}'], tool_env()).stdout.split()
        for name in networks:
            run(['docker', 'network', 'rm', name], tool_env())
        cases.check('no executor container or network is left', 'none', f'{len(leftover)} containers, {len(networks)} networks removed after the check',
                    not leftover and not networks)
        after = other_resources(self.target.project)
        cases.check('other Docker resources are untouched', 'same', f'{len(before)} before, {len(after)} after', before == after)


def qualify(root: Path) -> int:
    fingerprint = executor_fingerprint(root)
    require_current_images(fingerprint)
    stack = Stack(root)
    (root / REPORT).unlink(missing_ok=True)
    before = stack.prepare()
    cases = Cases()
    started_at = time.monotonic()
    try:
        url = stack.up(cases)
        run_child_check(cases, root, 'checks/browser_executor_check.py', WORKSPACE_A, str(stack.db_port), str(stack.gateway_port),
                        label='the executor check', env=service_env(root, url), timeout=900, cwd=root, err_dir=root / REPORT.parent,
                        err_name=REPORT.stem)
    finally:
        stack.down(cases, before)
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


def qualify_browser_use(root: Path) -> int:
    """Decision 0035 Y8: browser-use's own cases, on top of a qualified executor, into its own report."""
    (root / BROWSER_USE_REPORT).unlink(missing_ok=True)
    state = browser_use_state(root)
    if state != 'current':
        raise Unavailable(f'{BROWSER_USE.tag} is {"not built" if state == "missing" else "built from other sources"}: build it with '
                          '`make browser-images`')
    # browser_images put the service's source on the path; this module is standard library only.
    from autobots.adapters.browser_qualification import executor_qualified
    if not executor_qualified(root):
        raise Unavailable('the executor is not qualified at today\'s fingerprint; run this script without --browser-use first')
    fingerprint = browser_use_fingerprint(root)
    stack = Stack(root)
    before = stack.prepare()
    cases = Cases(model_transport='mock')
    started_at = time.monotonic()
    try:
        url = stack.up(cases)
        run_child_check(cases, root, 'checks/browser_use_check.py', WORKSPACE_A, str(stack.db_port), label='the browser-use check',
                        env=service_env(root, url), timeout=1500, cwd=root, err_dir=root / BROWSER_USE_REPORT.parent,
                        err_name=BROWSER_USE_REPORT.stem)
    finally:
        stack.down(cases, before)
    cases.check('the browser-use image still carries the fingerprint the check started with', 'current', browser_use_state(root),
                browser_use_state(root) == 'current' and browser_use_fingerprint(root) == fingerprint)
    passed = cases.status == 'passed'
    write_report(root / BROWSER_USE_REPORT, {
        'schema_version': 'autobots.browser-use-qualification/v1', 'completed_at_utc': datetime.now(UTC).isoformat(),
        'duration_seconds': round(time.monotonic() - started_at, 1), 'status': cases.status,
        'browser_use_fingerprint': fingerprint, 'image_label': fingerprint_digest(fingerprint), 'target_class': 'disposable',
        'driver': 'scripted', 'model': 'scripted, no provider', 'browser_use': '1.0.6',
        'network': 'outbound to https://example.com/ only; localtest.me resolves to loopback and is refused', 'cases': cases.records,
        'not_established': ['H1', 'product acceptance', 'browsing with a real model', 'that browser-use works reliably', 'any real YouTube page']})
    print(f"{'PASS' if passed else 'FAIL'}: {sum(r['status'] == 'passed' for r in cases.records)} of {len(cases.records)} browser-use cases passed.")
    return 0 if passed else 1


def main() -> int:
    root = project_root()
    try:
        if '--browser-use' in sys.argv[1:]:
            return qualify_browser_use(root)
        executor = qualify(root)
        if executor != 0:
            return executor
        if browser_use_state(root) == 'missing':
            (root / BROWSER_USE_REPORT).unlink(missing_ok=True)
            print(f'{BROWSER_USE.tag} is not built, so browser-use is not qualified and browse_goal stays on the loop.')
            return 0
        return qualify_browser_use(root)
    except Refused as refusal:
        print(f'REFUSED before any change: {refusal}', file=sys.stderr)
        return 1
    except Unavailable as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
