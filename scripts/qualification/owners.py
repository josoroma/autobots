"""Owners a qualifier bootstraps on its disposable stack, through the product's own entry point (SCRP-06).

Moved from qualify_identity.py, which seven scripts imported for them.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from qualification.children import CHECK_PYTHON, SERVICE_SOURCE, tool_env
from qualification.errors import Unavailable
from qualification.net import http


def bootstrap_owner(root: Path, base: str, service_key: str, database_url: str, email: str, password: str) -> dict[str, Any]:
    """Create an owner and a workspace of its own through the Auth admin API, as `make owner` does. One that could
    not be bootstrapped raises Unavailable, since nothing after it would show anything."""
    result = subprocess.run([str(root / CHECK_PYTHON), '-m', 'autobots.operations.bootstrap_owner', '--email', email, '--workspace-name', email],
                            env={**tool_env(), 'PYTHONPATH': str(root / SERVICE_SOURCE), 'PYTHONDONTWRITEBYTECODE': '1',
                                 'AUTOBOTS_SUPABASE_URL': base, 'AUTOBOTS_SERVICE_ROLE_KEY': service_key,
                                 'AUTOBOTS_OWNER_PASSWORD': password, 'AUTOBOTS_DATABASE_URL': database_url},
                            capture_output=True, text=True, timeout=60, check=False)
    if result.returncode:
        raise Unavailable(f'owner bootstrap failed: {result.stderr.strip()[-200:]}')
    try:
        owner: object = json.loads(result.stdout)
    except ValueError as error:
        raise Unavailable(f'owner bootstrap printed no JSON: {result.stdout.strip()[-200:]}') from error
    if not isinstance(owner, dict):
        raise Unavailable('owner bootstrap printed no JSON object')
    return owner


def password_token(base: str, anon: str, email: str, password: str) -> tuple[int, str]:
    """Sign in with a local password: the status, and the access token when it is 200."""
    status, body = http('POST', f'{base}/auth/v1/token?grant_type=password', {'apikey': anon, 'Content-Type': 'application/json'},
                        json.dumps({'email': email, 'password': password}).encode())
    if status != 200:
        return status, ''
    reply: object = json.loads(body)
    return status, str(reply.get('access_token', '')) if isinstance(reply, dict) else ''
