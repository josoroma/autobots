#!/usr/bin/env python3
"""Pinned self-hosted Supabase release plus local overlay: preflight, rendering and disposable qualification.

`preflight` reports a host port conflict and never stops another process. `qualify` runs the real
release on a new disposable project with generated secrets, inspects actual listeners, and removes
only that project. Nothing here starts or changes a persistent stack, or pulls an image.

Exit codes: 0 passed, 1 a conflict or a failed case, 2 prerequisite unavailable.
Passing establishes neither H1 nor product acceptance.
"""
from __future__ import annotations

import argparse
import base64
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
from urllib import error as urlerror, request as urlrequest

from disposable_db import (PROJECT_PREFIX, RUN_LABEL, TARGET_LABEL, Cases, Refused, Stack, Target, Unavailable, free_port, jwt,
                           other_resources, remove_stack, require_identity, run, tool_env)
from harness_lib import fingerprint, project_root

UPSTREAM = Path('infra/supabase/upstream')
COMPOSE_FILES = (UPSTREAM / 'docker-compose.yml', Path('infra/supabase/compose.overlay.yaml'),
                 Path('infra/supabase/compose.disposable.yaml'))
REPORT = Path('.checks/supabase/qualification.json')
PROPOSED_PORTS = {'gateway': 54321, 'direct database': 54322}
REQUIRED_SERVICES = frozenset({'db', 'auth', 'rest', 'storage', 'imgproxy', 'meta', 'studio', 'api-gw'})
PUBLISHED_SERVICES = {'api-gw': 8000, 'db': 5432}
# Removed from the default profile, with their reasons in the overlay.
REMOVED_SERVICES = frozenset({'realtime', 'functions', 'supavisor'})
WAIT_SECONDS = 240
SECRET_NAMES = frozenset({'POSTGRES_PASSWORD', 'JWT_SECRET', 'ANON_KEY', 'SERVICE_ROLE_KEY', 'DASHBOARD_PASSWORD',
                          'SECRET_KEY_BASE', 'REALTIME_DB_ENC_KEY', 'VAULT_ENC_KEY', 'PG_META_CRYPTO_KEY',
                          'LOGFLARE_PUBLIC_ACCESS_TOKEN', 'LOGFLARE_PRIVATE_ACCESS_TOKEN',
                          'S3_PROTOCOL_ACCESS_KEY_ID', 'S3_PROTOCOL_ACCESS_KEY_SECRET', 'MINIO_ROOT_PASSWORD'})


def port_conflict(port: int) -> str | None:
    """Who holds this port, or None. It only looks. A wildcard listener also blocks this loopback bind."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind(('127.0.0.1', port))
            return None
        except OSError:
            pass
    try:
        listing = subprocess.run(['lsof', '-nP', f'-iTCP:{port}', '-sTCP:LISTEN'], capture_output=True, text=True,
                                 errors='replace', timeout=10, check=False).stdout.splitlines()[1:]
    except (OSError, subprocess.TimeoutExpired):
        listing = []
    owners = sorted({f'{line.split()[0]} on {line.split()[8]}' for line in listing if len(line.split()) > 8})
    return ', '.join(owners) or 'an unidentified process'


def preflight(ports: Mapping[str, int]) -> list[str]:
    conflicts = []
    for label, port in ports.items():
        owner = port_conflict(port)
        if owner:
            conflicts.append(f'{label} port {port} is held by {owner}. Stop it yourself or choose another port; nothing was stopped.')
    return conflicts


def generated_values(gateway_port: int, db_port: int) -> dict[str, str]:
    """Every secret is new for this run. Non-secrets keep the release's example values."""
    secret = secrets.token_urlsafe(48)
    values = {name: secrets.token_hex(32) for name in SECRET_NAMES}
    values.update(JWT_SECRET=secret, ANON_KEY=jwt_key(secret, 'anon'), SERVICE_ROLE_KEY=jwt_key(secret, 'service_role'),
                  VAULT_ENC_KEY=secrets.token_hex(16), PG_META_CRYPTO_KEY=secrets.token_hex(16),
                  DASHBOARD_USERNAME='operator', API_GW_HTTP_PORT=str(gateway_port),
                  AUTOBOTS_GATEWAY_HOST_PORT=str(gateway_port), AUTOBOTS_DB_HOST_PORT=str(db_port),
                  SUPABASE_PUBLIC_URL=f'http://127.0.0.1:{gateway_port}', API_EXTERNAL_URL=f'http://127.0.0.1:{gateway_port}',
                  SITE_URL='http://127.0.0.1:3000', DISABLE_SIGNUP='true', ENABLE_ANONYMOUS_USERS='false',
                  ENABLE_EMAIL_AUTOCONFIRM='false', ENABLE_PHONE_SIGNUP='false')
    return values


def jwt_key(secret: str, role: str) -> str:
    return jwt(secret, {'role': role, 'iss': 'supabase', 'exp': int(time.time()) + 86400 * 30})


def example_defaults(root: Path) -> dict[str, str]:
    """The release's non-secret defaults. COMPOSE_FILE must not reselect files behind this wrapper's back."""
    defaults = {}
    for line in (root / UPSTREAM / 'env.example').read_text().splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            name, value = line.split('=', 1)
            if name.strip() != 'COMPOSE_FILE' and name.strip() not in SECRET_NAMES:
                defaults[name.strip()] = value.strip()
    return defaults


@dataclass
class SupabaseStack(Stack):
    values: dict[str, str] = field(default_factory=dict)

    def compose(self, *arguments: str, timeout: float = 300.0, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
        files = [item for path in COMPOSE_FILES for item in ('-f', str(self.root / path))]
        return run(['docker', 'compose', '-p', self.target.project, '--project-directory', str(self.root / UPSTREAM),
                    *files, *arguments], self.env(), timeout, stdin)

    def env(self) -> dict[str, str]:
        return {**tool_env(), **example_defaults(self.root), **self.values, 'AUTOBOTS_DISPOSABLE_PROJECT': self.target.project}

    def sql(self, statements: str) -> subprocess.CompletedProcess[str]:
        return self.compose('exec', '-T', 'db', 'psql', '-U', 'supabase_admin', '-d', 'postgres', '-X', '-q', '-A', '-t',
                            '-v', 'ON_ERROR_STOP=1', stdin=statements)


def rendered_refusals(rendered: Mapping, project: str, root: Path, marked: bool = True) -> list[str]:
    """What Compose would actually do, after merging. Appended ports would keep an upstream wildcard, so check all.

    `marked=False` is the persistent install, which carries no disposable marking. Everything else still applies.
    """
    reasons = []
    services = rendered.get('services') or {}
    if set(services) != REQUIRED_SERVICES:
        reasons.append(f'services differ from the qualified set: {sorted(set(services) ^ REQUIRED_SERVICES)}')
    allowed_root = (root / UPSTREAM / 'volumes').resolve()
    for name, service in services.items():
        if service.get('pull_policy') != 'never' or '@sha256:' not in str(service.get('image')):
            reasons.append(f'service {name} is not a digest-pinned local image')
        if service.get('container_name'):
            reasons.append(f'service {name} keeps a fixed container name, which is not project-scoped')
        if service.get('network_mode') or service.get('privileged') or service.get('pid'):
            reasons.append(f'service {name} leaves the isolated project network')
        labels = service.get('labels') or {}
        if marked and (labels.get(TARGET_LABEL) != 'disposable' or labels.get(RUN_LABEL) != project):
            reasons.append(f'service {name} lacks the disposable labels')
        ports = service.get('ports') or []
        if bool(ports) != (name in PUBLISHED_SERVICES):
            reasons.append(f'service {name} has an unapproved publication')
        for port in ports:
            if port.get('host_ip') != '127.0.0.1' or port.get('target') != PUBLISHED_SERVICES.get(name):
                reasons.append(f"service {name} publishes {port.get('host_ip', 'every address')}:{port.get('target')}")
        for mount in service.get('volumes') or []:
            if mount.get('type') == 'bind':
                source = Path(str(mount.get('source'))).resolve()
                if not mount.get('read_only') or not source.is_relative_to(allowed_root):
                    reasons.append(f"service {name} has a writable or foreign bind mount at {mount.get('target')}")
            elif mount.get('type') != 'volume':
                reasons.append(f"service {name} has an unexpected mount at {mount.get('target')}")
    for key, volume in (rendered.get('volumes') or {}).items():
        if volume.get('external') or (marked and (volume.get('labels') or {}).get(TARGET_LABEL) != 'disposable'):
            reasons.append(f'volume {key} is external or unmarked')
        if not str(volume.get('name', '')).startswith(f'{project}_'):
            reasons.append(f'volume {key} is not owned by the project')
    studio = (services.get('studio') or {}).get('environment') or {}
    if studio.get('OPENAI_API_KEY') not in ('', None):
        reasons.append('Studio keeps an OpenAI key, so its assistant would be enabled')
    if studio.get('NEXT_TELEMETRY_DISABLED') != '1':
        reasons.append('Studio telemetry is not disabled')
    for name, service in services.items():
        if any('OPENROUTER' in str(key).upper() or 'OPENROUTER' in str(value).upper()
               for key, value in (service.get('environment') or {}).items()):
            reasons.append(f'service {name} receives an OpenRouter setting')
    return reasons


def require_rendered(stack: SupabaseStack) -> dict:
    # The host's own keys are offered on purpose: the overlay must not let them through.
    result = run(['docker', 'compose', '-p', stack.target.project, '--project-directory', str(stack.root / UPSTREAM),
                  *[item for path in COMPOSE_FILES for item in ('-f', str(stack.root / path))], 'config', '--format', 'json'],
                 {**stack.env(), 'OPENAI_API_KEY': 'arranged-host-value', 'OPENROUTER_API_KEY': 'arranged-host-value'}, 60)
    if result.returncode:
        raise Unavailable('docker compose could not render the pinned configuration')
    rendered = json.loads(result.stdout)
    reasons = rendered_refusals(rendered, stack.target.project, stack.root)
    if reasons:
        raise Refused('; '.join(reasons))
    return rendered


def require_images(rendered: Mapping) -> list[str]:
    """Each pinned image must be present and ARM64. Nothing is pulled here."""
    summary = []
    for service in rendered['services'].values():
        image = service['image']
        result = run(['docker', 'image', 'inspect', image, '--format', '{{.Architecture}}'], tool_env(), 30)
        if result.returncode:
            raise Unavailable(f'{image} is not on this machine; pull it deliberately, the check never pulls')
        summary.append(f'{image.split("@")[0]} {result.stdout.strip()}')
    return sorted(summary)


def http(method: str, url: str, headers: Mapping[str, str] | None = None) -> tuple[int, str]:
    class NoRedirect(urlrequest.HTTPRedirectHandler):
        def redirect_request(self, *_args: object, **_kwargs: object) -> None:
            return None
    opener = urlrequest.build_opener(NoRedirect)
    try:
        with opener.open(urlrequest.Request(url, method=method, headers=dict(headers or {})), timeout=20) as reply:
            return reply.status, reply.read(4096).decode(errors='replace')
    except urlerror.HTTPError as error:
        return error.code, error.read(4096).decode(errors='replace')
    except (OSError, urlerror.URLError) as error:
        return 0, type(error).__name__


def listener_addresses(port: int) -> list[str]:
    result = subprocess.run(['lsof', '-nP', f'-iTCP:{port}', '-sTCP:LISTEN'], capture_output=True, text=True, errors='replace',
                            timeout=10, check=False)
    return sorted({line.split()[8] for line in result.stdout.splitlines()[1:] if len(line.split()) > 8})


def reachable_from_lan(port: int) -> bool | None:
    """Whether this machine's non-loopback address answers. None when it has none."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(('192.0.2.1', 9))  # Chooses a route and sends nothing.
            address = probe.getsockname()[0]
    except OSError:
        return None
    if address.startswith('127.'):
        return None
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as attempt:
        attempt.settimeout(2)
        return attempt.connect_ex((address, port)) == 0


def direct_system_id(root: Path, port: int, password: str) -> str:
    """Connect through the published port with the pinned driver, so the host path is what is tested."""
    code = ('import psycopg, sys\n'
            'row = psycopg.connect(host="127.0.0.1", port=int(sys.argv[1]), user="supabase_admin", dbname="postgres", connect_timeout=10)'
            '.execute("select system_identifier::text || \'|\' || inet_server_port()::text from pg_control_system()").fetchone()\n'
            'print(row[0])\n')
    result = subprocess.run([str(root / 'services/agent/.venv/bin/python'), '-c', code, str(port)],
                            env={**tool_env(), 'PGPASSWORD': password}, capture_output=True, text=True, errors='replace',
                            timeout=30, check=False)
    return result.stdout.strip() if result.returncode == 0 else f'ERROR: {result.stderr.strip()[-160:]}'


def qualify(root: Path) -> int:
    project = f'{PROJECT_PREFIX}{secrets.token_hex(4)}'
    gateway_port = free_port()
    db_port = free_port([gateway_port])
    target = Target(project, db_port, gateway_port)
    stack = SupabaseStack(target, root, root / COMPOSE_FILES[0], values=generated_values(gateway_port, db_port))
    cases = Cases()
    require_identity(target, tool_env())
    if run(['docker', 'info', '--format', '{{.ServerVersion}}'], tool_env(), 30).returncode:
        raise Unavailable('the Docker engine is not reachable')
    (root / REPORT).unlink(missing_ok=True)
    rendered = require_rendered(stack)
    cases.check('rendered configuration is safe', 'no refusal', '8 services, loopback, pinned, labeled; host keys not inherited', True)
    images = require_images(rendered)
    cases.check('pinned images are ARM64', 'all arm64', f'{sum(item.endswith(" arm64") for item in images)} of {len(images)}',
                all(item.endswith(' arm64') for item in images))
    before = other_resources(project)
    started_at = time.monotonic()
    try:
        started = stack.compose('up', '-d', '--wait', '--wait-timeout', str(WAIT_SECONDS), timeout=WAIT_SECONDS + 60)
        states = stack.compose('ps', '-a', '--format', '{{.Service}} {{.State}} {{.Health}}').stdout.splitlines()
        cases.check('every service is healthy', 'running and healthy', '; '.join(sorted(states))[:400], started.returncode == 0)
        if started.returncode:
            print(started.stderr[-600:], file=sys.stderr)
        else:
            qualify_addresses(stack, cases, gateway_port, db_port)
    finally:
        remove_stack(stack)
    return finish(root, cases, stack, before, started_at, images)


def qualify_addresses(stack: SupabaseStack, cases: Cases, gateway_port: int, db_port: int) -> None:
    for label, port in (('gateway', gateway_port), ('direct database', db_port)):
        addresses = listener_addresses(port)
        cases.check(f'{label} listens only on loopback', f'127.0.0.1:{port} only', ', '.join(addresses),
                    addresses == [f'127.0.0.1:{port}'])
        lan = reachable_from_lan(port)
        cases.check(f'{label} refuses a non-loopback address', 'refused, or no such address', str(lan), lan is not True)
    direct = direct_system_id(stack.root, db_port, stack.values['POSTGRES_PASSWORD'])
    # Over its own socket the container has no server port, so only the cluster identity is compared.
    inside = stack.sql('select system_identifier::text from pg_control_system();').stdout.strip()
    cases.check('the direct port reaches db:5432', 'the db container\'s cluster, server port 5432',
                'same cluster, port ' + direct.split('|')[-1] if direct.startswith(f'{inside}|') else direct,
                bool(inside) and direct == f'{inside}|5432')
    published = [line for line in stack.compose('ps', '--format', '{{.Service}} {{.Ports}}').stdout.splitlines() if '->' in line]
    expected = {f'api-gw 127.0.0.1:{gateway_port}->8000/tcp', f'db 127.0.0.1:{db_port}->5432/tcp'}
    cases.check('only the gateway and direct database are published', 'exactly those two', '; '.join(sorted(published)),
                set(published) == expected)
    base = f'http://127.0.0.1:{gateway_port}'
    status, _ = http('GET', f'{base}/')
    cases.check('Studio refuses an anonymous request', '401', str(status), status == 401)
    status, _ = http('GET', f'{base}/', {'Authorization': 'Basic ' + base64.b64encode(b'operator:wrong').decode()})
    cases.check('Studio refuses a wrong password', '401', str(status), status == 401)
    token = base64.b64encode(f"operator:{stack.values['DASHBOARD_PASSWORD']}".encode()).decode()
    status, _ = http('GET', f'{base}/', {'Authorization': f'Basic {token}'})
    cases.check('Studio answers the operator through the gateway', 'not 401 or 5xx', str(status), 200 <= status < 400)
    apikey = {'apikey': stack.values['ANON_KEY']}
    status, _ = http('GET', f'{base}/auth/v1/health', apikey)
    cases.check('Auth answers through the gateway', '200', str(status), status == 200)
    status, body = http('GET', f'{base}/auth/v1/settings', apikey)
    cases.check('public signup is disabled', 'disable_signup true', str('"disable_signup":true' in body), '"disable_signup":true' in body)
    status, _ = http('GET', f'{base}/rest/v1/')
    cases.check('REST refuses a request with no key', '401', str(status), status == 401)
    environment = stack.compose('exec', '-T', 'studio', 'printenv', 'OPENAI_API_KEY')
    cases.check('Studio has no OpenAI key at runtime', 'empty', 'empty' if not environment.stdout.strip() else 'set', not environment.stdout.strip())


def finish(root: Path, cases: Cases, stack: Stack, before: Sequence[str], started_at: float, images: Sequence[str]) -> int:
    project = stack.target.project
    label = f'label=com.docker.compose.project={project}'
    left = (run(['docker', 'volume', 'ls', '--filter', label, '--format', '{{.Name}}'], tool_env()).stdout
            + run(['docker', 'ps', '-a', '--filter', label, '--format', '{{.Names}}'], tool_env()).stdout).strip()
    cases.check('cleanup removed the owned containers and volumes', 'none left', left or 'none', not left)
    cases.check('other Docker resources are untouched', 'same containers and volumes',
                f'{len(before)} before, {len(after := other_resources(project))} after', before == after)
    passed = all(record['status'] == 'passed' for record in cases.records)
    path = root / REPORT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'schema_version': 'autobots.supabase-qualification/v1',
                                'completed_at_utc': datetime.now(timezone.utc).isoformat(),
                                'duration_seconds': round(time.monotonic() - started_at, 1),
                                'input_fingerprint': fingerprint(root), 'status': 'passed' if passed else 'failed',
                                'target_class': 'disposable', 'project': project, 'images': list(images), 'cases': cases.records,
                                'not_established': ['H1', 'product acceptance', 'the persistent stack', 'the proposed ports 54321 and 54322']},
                               indent=2) + '\n')
    return 0 if passed else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('verb', choices=('preflight', 'qualify'))
    parser.add_argument('--gateway-port', type=int, default=PROPOSED_PORTS['gateway'])
    parser.add_argument('--db-port', type=int, default=PROPOSED_PORTS['direct database'])
    args = parser.parse_args(argv)
    root = project_root()
    try:
        if args.verb == 'preflight':
            conflicts = preflight({'gateway': args.gateway_port, 'direct database': args.db_port})
            for conflict in conflicts:
                print(f'CONFLICT: {conflict}')
            if not conflicts:
                print('PASS: the proposed ports are free.')
            return 1 if conflicts else 0
        return qualify(root)
    except Refused as refusal:
        print(f'REFUSED before any change: {refusal}', file=sys.stderr)
        return 1
    except Unavailable as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
