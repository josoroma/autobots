#!/usr/bin/env python3
"""The one live browse trial on Sol, US-14.16 and Decision 0019 S6, on a disposable stack.

Authorized once, capped at US$1 by the run's own budget. This wrapper starts a disposable database,
then runs `autobots.operations.browse_trial`, whose own process reads only OPENROUTER_API_KEY from
the key file named here; this wrapper never opens it. The browser reaches example.com and iana.org
through the isolated executor. A recorded trial refuses to run again, before any container starts,
unless the owner asked for a repeat (--owner-requested-repeat).

In no verification profile: it spends money and needs network, a key and built images.
Exit codes: 0 ran, 1 refused or a case failed, 2 a prerequisite is missing.
"""
from __future__ import annotations

import argparse
import json
import secrets
import subprocess
import sys
from pathlib import Path

from app_db import MIGRATIONS, WORKSPACE_A, AppStack, apply_migrations, bootstrap, seed
from browser_images import require_current_images
from disposable_db import (
    PROJECT_PREFIX,
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
from qualify_browser_executor import executor_fingerprint
from supabase_stack import generated_values, require_images, require_rendered

OUT = Path('.checks/browse-trial')
PYTHON = Path('services/agent/.venv/bin/python')


def trial(root: Path, key_file: Path, repeat: bool) -> int:
    if (root / OUT / 'result.json').exists() and not repeat:
        raise Refused("this trial already ran; a repeat needs the owner's request (--owner-requested-repeat)")
    if not key_file.is_file():
        raise Unavailable(f'no key file at {key_file}')
    # Both images carry today's fingerprint label, or the executor reads as unqualified (refactor plan R-57).
    require_current_images(executor_fingerprint(root))
    project = f'{PROJECT_PREFIX}{secrets.token_hex(4)}'
    gateway_port = free_port()
    db_port = free_port([gateway_port])
    target = Target(project, db_port, gateway_port)
    stack = AppStack(target, root, root / 'infra/supabase/upstream/docker-compose.yml', values=generated_values(gateway_port, db_port))
    stack.migrator_password, stack.runtime_password = secrets.token_hex(24), secrets.token_hex(24)
    require_identity(target, tool_env())
    rendered = require_rendered(stack)
    require_images({'services': {'db': rendered['services']['db']}})
    before = other_resources(project)
    try:
        started = stack.compose('up', '-d', '--wait', '--wait-timeout', '120', 'db')
        if started.returncode:
            raise Unavailable(f'the disposable database did not start: {started.stderr[-300:]}')
        bootstrap(stack, root)
        _, failure = apply_migrations(stack, root / MIGRATIONS)
        if failure:
            raise Unavailable(f'the disposable database was not migrated: {failure}')
        seed(stack, root)
        stack.migrator(f"insert into public.workspaces (id, name) values ('{WORKSPACE_A}', 'Workspace A');")
        url = f'postgresql://autobots_runtime:{stack.runtime_password}@127.0.0.1:{db_port}/postgres'
        argv = [str(root / PYTHON), '-m', 'autobots.operations.browse_trial', '--key-file', str(key_file),
                '--workspace', WORKSPACE_A, '--out', str(root / OUT)]
        if repeat:
            argv.append('--owner-requested-repeat')
        completed = subprocess.run(argv, env={**tool_env(), 'AUTOBOTS_DATABASE_URL': url, 'PYTHONPATH': str(root / 'services/agent/src'),
                                              'PYTHONDONTWRITEBYTECODE': '1'},
                                   capture_output=True, text=True, timeout=900, check=False, cwd=root)
        print(completed.stdout.strip())
        if completed.returncode:
            print(completed.stderr.strip()[-800:], file=sys.stderr)
    finally:
        remove_stack(stack)
        leftover = run(['docker', 'ps', '-a', '--filter', 'label=autobots.browser=1', '--format', '{{.Names}}'], tool_env()).stdout.split()
        for name in leftover:
            run(['docker', 'rm', '-f', name], tool_env())
    after = other_resources(project)
    print(json.dumps({'executor_containers_left': len(leftover), 'other_docker_resources_unchanged': before == after}))
    return completed.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--key-file', default='.env')
    parser.add_argument('--owner-requested-repeat', action='store_true')
    arguments = parser.parse_args()
    root = project_root()
    try:
        return trial(root, (root / arguments.key_file).resolve(), arguments.owner_requested_repeat)
    except Refused as refusal:
        print(f'REFUSED before anything started: {refusal}', file=sys.stderr)
        return 1
    except Unavailable as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
