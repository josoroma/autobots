#!/usr/bin/env python3
"""Target-guarded disposable database wrappers and their qualification. Never touches a persistent target.

`reset`, `cleanup` and `migrate` refuse anything but a marked disposable target, before any Docker
call that could change it. `qualify` creates its own target, runs synthetic migrations, seeds and
authorization cases against it, and removes only what it proves it owns.

Exit codes: 0 passed, 1 refused or a case failed, 2 prerequisite unavailable, such as Docker or a
pinned image. Nothing is pulled. Passing establishes neither H1 nor product acceptance.
"""
from __future__ import annotations

import argparse
import base64
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys
import time
from urllib import error as urlerror, request as urlrequest
from urllib.parse import urlsplit

from harness_lib import fingerprint, project_root, reduced_env

PROJECT_PREFIX = 'autobots-disposable-'
PROJECT = re.compile(r'autobots-disposable-[a-z0-9]{1,24}')
PORT_RANGE = range(55400, 56000)
# The proposed persistent gateway and direct database ports, LM-04, and this machine's CLI defaults.
RESERVED_PORTS = frozenset({54321, 54322, 54323, 5432})
LOOPBACK_HOSTS = frozenset({'127.0.0.1', 'localhost'})
TARGET_LABEL = 'autobots.target'
RUN_LABEL = 'autobots.run'
COMPOSE = Path('infra/disposable/compose.yaml')
FIXTURES = Path('tests/db')
REPORT = Path('.checks/db/qualification.json')
USER_A, USER_B = 'a1111111-1111-4111-8111-111111111111', 'b2222222-2222-4222-8222-222222222222'
WORKSPACE_A = 'a0000000-0000-4000-8000-000000000001'
NOTE_A = 'a3333333-3333-4333-8333-333333333333'
COMMAND_TIMEOUT = 180.0
EXPECTED_MIGRATIONS = 2


class Refused(Exception):
    """The target is not a marked disposable one. Nothing was changed."""


class Unavailable(Exception):
    """Docker, Compose or a pinned image is missing."""


@dataclass(frozen=True)
class Target:
    project: str
    db_port: int | None = None
    storage_port: int | None = None
    volumes: tuple[str, ...] = ()


@dataclass
class Stack:
    target: Target
    root: Path
    compose_file: Path
    secrets_env: dict[str, str] = field(default_factory=dict)

    def compose(self, *arguments: str, timeout: float = COMMAND_TIMEOUT,
                stdin: str | None = None) -> subprocess.CompletedProcess[str]:
        return run(['docker', 'compose', '-p', self.target.project, '-f', str(self.compose_file), *arguments],
                   self.env(), timeout, stdin)

    def env(self) -> dict[str, str]:
        env = {**tool_env(), 'AUTOBOTS_DISPOSABLE_PROJECT': self.target.project,
               'AUTOBOTS_DISPOSABLE_DB_PORT': str(self.target.db_port or PORT_RANGE.start),
               'AUTOBOTS_DISPOSABLE_STORAGE_PORT': str(self.target.storage_port or PORT_RANGE.start + 1)}
        # Rendering needs a value for every variable. A real run sets generated ones below.
        for name in ('PASSWORD', 'JWT_SECRET', 'ANON_KEY', 'SERVICE_KEY'):
            env[f'AUTOBOTS_DISPOSABLE_{name}'] = 'unset-placeholder'
        return {**env, **self.secrets_env}

    def sql(self, statements: str) -> subprocess.CompletedProcess[str]:
        """Run SQL on the disposable database, stopping at the first error, as its superuser."""
        return self.compose('exec', '-T', 'db', 'psql', '-U', 'supabase_admin', '-d', 'postgres', '-X', '-q', '-A',
                            '-t', '-v', 'ON_ERROR_STOP=1', stdin=statements)

    def as_role(self, role: str, user: str | None, statement: str) -> subprocess.CompletedProcess[str]:
        """Run one statement as an actual nonprivileged role, then roll back."""
        # This image's `auth.uid()` reads the older per-claim setting until GoTrue's migrations replace it.
        claims = json.dumps({'role': role, **({'sub': user} if user else {})})
        return self.sql(f"begin;\nset local role {role};\nselect set_config('request.jwt.claims', '{claims}', true), "
                        f"set_config('request.jwt.claim.sub', '{user or ''}', true);\n{statement};\nrollback;\n")


def tool_env() -> dict[str, str]:
    """No inherited credential, and no inherited target: only what Docker needs to find its engine."""
    env = reduced_env()
    for name in ('HOME', 'DOCKER_HOST', 'DOCKER_CONTEXT', 'DOCKER_CONFIG'):
        if name in os.environ:
            env[name] = os.environ[name]
    return env


def run(argv: Sequence[str], env: Mapping[str, str], timeout: float = COMMAND_TIMEOUT,
        stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(list(argv), env=dict(env), input=stdin, capture_output=True, text=True,
                              errors='replace', timeout=timeout, check=False)
    except FileNotFoundError as error:
        raise Unavailable(f'{argv[0]} is not installed; nothing was installed') from error
    except subprocess.TimeoutExpired as error:
        raise Unavailable(f'{argv[0]} {argv[1] if len(argv) > 1 else ""} timed out after {timeout} seconds') from error


def identity_refusals(target: Target, env: Mapping[str, str]) -> list[str]:
    """Every reason this is not a disposable target. Needs no Docker, so it runs before any mutation."""
    reasons = []
    if not PROJECT.fullmatch(target.project):
        reasons.append(f'project {target.project!r} lacks the disposable form {PROJECT_PREFIX}<id>')
    ports = [port for port in (target.db_port, target.storage_port) if port is not None]
    for port in ports:
        if port in RESERVED_PORTS:
            reasons.append(f'port {port} belongs to a persistent or shared database')
        elif port not in PORT_RANGE:
            reasons.append(f'port {port} is outside the disposable range')
    for volume in target.volumes:
        if not volume.startswith(f'{target.project}_'):
            reasons.append(f'volume {volume!r} is not owned by project {target.project!r}')
    for name in ('DATABASE_URL', 'SUPABASE_DB_URL', 'POSTGRES_URL', 'PGPORT', 'PGHOST', 'PGDATABASE'):
        if name in env:
            reasons.extend(environment_refusal(name, env[name]))
    return reasons


def environment_refusal(name: str, value: str) -> list[str]:
    """A connection variable naming another target is refused, never ignored. Its value is not repeated."""
    if name == 'PGPORT':
        return [f'{name} points outside the disposable range'] if not value.isdigit() or int(value) not in PORT_RANGE else []
    if name in {'PGHOST', 'PGDATABASE'}:
        return [f'{name} is set, so this environment may name another target']
    try:
        parts = urlsplit(value)
        port, host = parts.port, parts.hostname
    except ValueError:
        port, host = None, None
    return [f'{name} points outside the disposable range'] if port not in PORT_RANGE or host not in LOOPBACK_HOSTS else []


def require_identity(target: Target, env: Mapping[str, str]) -> None:
    reasons = identity_refusals(target, env)
    if reasons:
        raise Refused('; '.join(reasons))


def rendered_refusals(rendered: Mapping, project: str) -> list[str]:
    """Check what Compose would actually do: loopback publications, owned volumes, pinned local images."""
    reasons = []
    if rendered.get('name') != project:
        reasons.append('the rendered project name differs')
    for name, service in (rendered.get('services') or {}).items():
        if service.get('pull_policy') != 'never' or '@sha256:' not in str(service.get('image')):
            reasons.append(f'service {name} is not a digest-pinned local image')
        if service.get('network_mode') or service.get('privileged') or service.get('pid'):
            reasons.append(f'service {name} leaves the isolated project network')
        labels = service.get('labels') or {}
        if labels.get(TARGET_LABEL) != 'disposable' or labels.get(RUN_LABEL) != project:
            reasons.append(f'service {name} lacks the disposable labels')
        for port in service.get('ports') or []:
            if port.get('host_ip') != '127.0.0.1':
                reasons.append(f'service {name} publishes beyond loopback')
            published = int(port.get('published') or 0)
            if published not in PORT_RANGE:
                reasons.append(f'service {name} publishes port {published} outside the disposable range')
        for mount in service.get('volumes') or []:
            if mount.get('type') != 'volume':
                reasons.append(f'service {name} mounts a host path')
    for key, volume in (rendered.get('volumes') or {}).items():
        labels = volume.get('labels') or {}
        if volume.get('external') or labels.get(TARGET_LABEL) != 'disposable':
            reasons.append(f'volume {key} is external or unmarked')
        if not str(volume.get('name', '')).startswith(f'{project}_'):
            reasons.append(f'volume {key} is not owned by the project')
    return reasons


def require_rendered(stack: Stack) -> None:
    result = stack.compose('--profile', 'storage', 'config', '--format', 'json')
    if result.returncode:
        raise Unavailable('docker compose could not render the disposable configuration')
    reasons = rendered_refusals(json.loads(result.stdout), stack.target.project)
    if reasons:
        raise Refused('; '.join(reasons))


def require_labels(stack: Stack) -> None:
    """Prove ownership of every resource before removing anything. An empty project owns nothing to refuse."""
    project = stack.target.project
    env = stack.env()
    for command in (['docker', 'ps', '-a', '--filter', f'label=com.docker.compose.project={project}',
                     '--format', '{{.Label "' + TARGET_LABEL + '"}} {{.Label "' + RUN_LABEL + '"}}'],
                    ['docker', 'volume', 'ls', '--filter', f'label=com.docker.compose.project={project}',
                     '--format', '{{.Label "' + TARGET_LABEL + '"}} {{.Label "' + RUN_LABEL + '"}}']):
        result = run(command, env)
        if result.returncode:
            raise Unavailable('docker could not list the disposable project')
        for line in result.stdout.splitlines():
            if line.split() != ['disposable', project]:
                raise Refused(f'project {project} holds a resource without its disposable labels')


def require_marker(stack: Stack) -> None:
    """A destructive operation needs the marker row written when this target was created."""
    result = stack.sql('select run_id from autobots_disposable.marker;')
    if result.returncode or result.stdout.strip() != stack.target.project:
        raise Refused(f'{stack.target.project} holds no matching disposable marker')


def write_marker(stack: Stack) -> None:
    result = stack.sql('create schema autobots_disposable;\ncreate table autobots_disposable.marker (run_id text primary key);\n'
                       'create table autobots_disposable.migrations (name text primary key, sha256 text not null);\n'
                       f"insert into autobots_disposable.marker values ('{stack.target.project}');\n")
    if result.returncode:
        raise Unavailable(f'could not write the disposable marker: {result.stderr.strip()[-300:]}')


def apply_sql_file(stack: Stack, path: Path) -> subprocess.CompletedProcess[str]:
    return stack.sql(f'begin;\n{path.read_text()}\ncommit;\n')


def apply_migrations(stack: Stack, directory: Path, upto: int | None = None) -> tuple[int, str | None]:
    """Apply in order, each in its own transaction with its history row. Returns (applied, error)."""
    history = stack.sql('select name, sha256 from autobots_disposable.migrations;')
    if history.returncode:
        return 0, 'the migration history is unreadable'
    recorded = dict(line.split('|') for line in history.stdout.splitlines() if line)
    applied = 0
    for path in sorted(directory.glob('*.sql'))[:upto]:
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        if path.name in recorded:
            if recorded[path.name] != checksum:
                return applied, f'{path.name} changed after it was applied; never edit an applied migration'
            continue
        result = stack.sql(f"begin;\n{path.read_text()}\ninsert into autobots_disposable.migrations values "
                           f"('{path.name}', '{checksum}');\ncommit;\n")
        if result.returncode:
            return applied, f'{path.name} failed and was rolled back'
        applied += 1
    return applied, None


def reset_fixture_schema(stack: Stack) -> None:
    require_marker(stack)
    result = stack.sql('drop schema if exists app cascade;\ndrop schema if exists app_private cascade;\n'
                       'truncate autobots_disposable.migrations;\n')
    if result.returncode:
        raise Unavailable('the disposable reset failed')


def remove_stack(stack: Stack) -> None:
    """Remove the project's containers and volumes, after proving it owns them."""
    require_identity(stack.target, tool_env())
    require_labels(stack)
    result = stack.compose('--profile', 'storage', 'down', '--volumes', '--remove-orphans', '--timeout', '5')
    if result.returncode:
        raise Unavailable('docker compose could not remove the disposable project')


def free_port(excluded: Sequence[int] = ()) -> int:
    for port in PORT_RANGE:
        if port in excluded:
            continue
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind(('127.0.0.1', port))
            except OSError:
                continue
            return port
    raise Unavailable(f'no free port in {PORT_RANGE.start}-{PORT_RANGE.stop - 1}')


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()


def jwt(secret: str, claims: Mapping[str, object]) -> str:
    body = {'iat': int(time.time()), 'exp': int(time.time()) + 900, **claims}
    signing = f"{b64(json.dumps({'alg': 'HS256', 'typ': 'JWT'}).encode())}.{b64(json.dumps(body).encode())}"
    return f'{signing}.{b64(hmac.new(secret.encode(), signing.encode(), hashlib.sha256).digest())}'


def http(method: str, url: str, token: str | None, body: bytes | None = None,
         content_type: str = 'text/plain') -> tuple[int, str]:
    headers = {'Authorization': f'Bearer {token}'} if token else {}
    if body is not None:
        headers['Content-Type'] = content_type
    try:
        with urlrequest.urlopen(urlrequest.Request(url, data=body, method=method, headers=headers), timeout=15) as reply:
            return reply.status, reply.read().decode(errors='replace')
    except urlerror.HTTPError as error:
        return error.code, error.read().decode(errors='replace')


def other_resources(project: str) -> list[str]:
    """Containers outside this project with their start and finish times, and its volumes by name.

    A restart or a stop changes a container's line. Their data is not compared.
    """
    env = tool_env()
    ids = run(['docker', 'ps', '-aq'], env)
    volumes = run(['docker', 'volume', 'ls', '--format', '{{.Name}}'], env)
    if ids.returncode or volumes.returncode:
        raise Unavailable('docker is not reachable')
    containers = ''
    if ids.stdout.split():
        inspected = run(['docker', 'inspect', '--format',
                         '{{.Id}} {{.Name}} {{.State.StartedAt}} {{.State.FinishedAt}} {{index .Config.Labels "com.docker.compose.project"}}',
                         *ids.stdout.split()], env)
        if inspected.returncode:
            raise Unavailable('docker could not inspect the containers')
        containers = inspected.stdout
    return sorted(line for line in (*containers.splitlines(), *volumes.stdout.splitlines()) if project not in line)


class Cases:
    def __init__(self) -> None:
        self.records: list[dict] = []

    def check(self, case_id: str, expected: str, observed: str, passed: bool) -> None:
        print(f"{'PASS' if passed else 'FAIL'}: {case_id}: {observed[:140]}")
        self.records.append({'id': case_id, 'class': 'disposable', 'model_transport': 'none', 'expected': expected,
                             'observed': observed[:400], 'status': 'passed' if passed else 'failed'})

    def denied(self, case_id: str, result: subprocess.CompletedProcess[str], marker: str) -> None:
        self.check(case_id, f'refused with {marker}', (result.stderr or result.stdout).strip()[-140:] or f'exit {result.returncode}',
                   result.returncode != 0 and marker in result.stderr)


def rows(stack: Stack, statement: str) -> str:
    result = stack.sql(statement)
    return result.stdout.strip() if result.returncode == 0 else f'ERROR: {result.stderr.strip()[-120:]}'


def last_line(result: subprocess.CompletedProcess[str]) -> str:
    lines = result.stdout.strip().splitlines()
    return lines[-1] if lines else ''


FINGERPRINT_QUERY = ("select md5(string_agg(t::text, ',' order by t::text)) from ("
                     "select 'workspaces' as source, to_jsonb(w) as row from app.workspaces w "
                     "union all select 'members', to_jsonb(m) from app.workspace_members m "
                     "union all select 'notes', to_jsonb(n) from app.notes n "
                     "union all select 'credentials', to_jsonb(c) from app_private.credentials c) t;")


def identity_cases(cases: Cases) -> None:
    persistent = {'persistent project': Target('autobots'), 'persistent port': Target(f'{PROJECT_PREFIX}x', 54322),
                  'persistent volume': Target(f'{PROJECT_PREFIX}x', 55400, volumes=('autobots_db-data',)),
                  'another stack': Target('supabase_mentor', 54322)}
    for label, target in persistent.items():
        reasons = identity_refusals(target, {})
        cases.check(f'refuse {label}', 'refused without any Docker call', '; '.join(reasons)[:140], bool(reasons))
    reasons = identity_refusals(Target(f'{PROJECT_PREFIX}x', 55400), {'DATABASE_URL': 'postgres://u@127.0.0.1:54322/postgres'})
    cases.check('refuse an environment naming the persistent port', 'refused, value not repeated', '; '.join(reasons), bool(reasons))


def migration_cases(stack: Stack, cases: Cases, root: Path) -> None:
    migrations = root / FIXTURES / 'migrations'
    applied, error = apply_migrations(stack, migrations)
    cases.check('fresh replay', f'{EXPECTED_MIGRATIONS} applied', f'{applied} applied, error {error}',
                applied == EXPECTED_MIGRATIONS and error is None)
    schema = rows(stack, "select count(*) from information_schema.columns where table_schema in ('app', 'app_private');")
    applied, error = apply_migrations(stack, migrations)
    cases.check('repeated apply', '0 applied, schema unchanged', f'{applied} applied, {schema} columns',
                applied == 0 and error is None
                and schema == rows(stack, "select count(*) from information_schema.columns where table_schema in ('app', 'app_private');"))
    bad_applied, bad_error = apply_migrations(stack, root / FIXTURES / 'bad_migrations')
    remains = rows(stack, "select (select count(*) from information_schema.tables where table_name = 'partial_migration') "
                          "+ (select count(*) from autobots_disposable.migrations where name like '0099%');")
    cases.check('a failing migration rolls back', 'error, no table and no history row', f'{bad_applied} applied, {bad_error}, {remains} remain',
                bad_applied == 0 and bool(bad_error) and remains == '0')
    stack.sql("update autobots_disposable.migrations set sha256 = 'edited' where name = '0001_workspaces.sql';")
    _, error = apply_migrations(stack, migrations)
    cases.check('an edited applied migration is refused', 'refused by checksum', str(error), bool(error and 'never edit' in error))
    reset_fixture_schema(stack)
    applied, error = apply_migrations(stack, migrations, upto=1)
    stack.sql(f"insert into app.workspaces values ('{WORKSPACE_A}', 'prior');\n"
              f"insert into app.notes (id, workspace_id, body) values ('{NOTE_A}', '{WORKSPACE_A}', 'prior body');\n")
    applied_next, error = apply_migrations(stack, migrations)
    prior = rows(stack, f"select body || '|' || title from app.notes where id = '{NOTE_A}';")
    cases.check('upgrade from the prior fixture keeps data', 'prior body kept, default title', f'{applied_next} applied, {prior}',
                applied_next == 1 and error is None and prior == 'prior body|untitled')
    reset_fixture_schema(stack)
    apply_migrations(stack, migrations)


def seed_cases(stack: Stack, cases: Cases, root: Path) -> None:
    seed = root / FIXTURES / 'seeds/fixtures.sql'
    first = apply_sql_file(stack, seed)
    before = rows(stack, FINGERPRINT_QUERY)
    second = apply_sql_file(stack, seed)
    after = rows(stack, FINGERPRINT_QUERY)
    cases.check('a second seed run changes nothing', 'same rows', f'{before} then {after}',
                first.returncode == 0 and second.returncode == 0 and before == after and len(before) == 32)
    stack.sql(f"update app.notes set body = 'edited by a user' where id = '{NOTE_A}';")
    apply_sql_file(stack, seed)
    edited = rows(stack, f"select body from app.notes where id = '{NOTE_A}';")
    cases.check('a repeated seed keeps a user edit', 'edit survives', edited, edited == 'edited by a user')


def authorization_cases(stack: Stack, cases: Cases) -> None:
    denied = 'permission denied'
    cases.denied('anonymous cannot read notes', stack.as_role('anon', None, 'select * from app.notes'), denied)
    cases.denied('anonymous cannot read private schema', stack.as_role('anon', None, 'select * from app_private.credentials'), denied)
    cases.denied('authenticated cannot read private schema',
                 stack.as_role('authenticated', USER_A, 'select * from app_private.credentials'), denied)
    own = last_line(stack.as_role('authenticated', USER_A, 'select count(*) from app.notes'))
    cases.check('a member reads only its workspace', '1 note', own, own == '1')
    # This positive control shows that the denials below come from the policy, not from an unset identity.
    wrote = stack.as_role('authenticated', USER_A, f"insert into app.notes (id, workspace_id, body) values (gen_random_uuid(), '{WORKSPACE_A}', 'x')")
    cases.check('a member can insert in its workspace', 'exit 0', f'exit {wrote.returncode}', wrote.returncode == 0)
    other = last_line(stack.as_role('authenticated', USER_B, f"select count(*) from app.notes where id = '{NOTE_A}'"))
    cases.check('another workspace reads nothing', '0 notes', other, other == '0')
    cases.denied('another workspace cannot insert',
                 stack.as_role('authenticated', USER_B,
                               f"insert into app.notes (id, workspace_id, body) values (gen_random_uuid(), '{WORKSPACE_A}', 'x')"),
                 'row-level security')
    updated = stack.as_role('authenticated', USER_B,
                            f"with changed as (update app.notes set body = 'x' where id = '{NOTE_A}' returning 1) select count(*) from changed")
    cases.check('another workspace updates nothing', '0 rows', last_line(updated), last_line(updated) == '0')


def wait_for(check: Callable[[], bool], seconds: float) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            if check():
                return True
        except (OSError, urlerror.URLError):
            pass
        time.sleep(1)
    return False


def storage_cases(stack: Stack, cases: Cases, root: Path) -> None:
    password = stack.secrets_env['AUTOBOTS_DISPOSABLE_PASSWORD']
    role = stack.sql(f"alter role supabase_storage_admin with password '{password}';\n")
    if role.returncode:
        raise Unavailable('could not prepare the storage role')
    started = stack.compose('--profile', 'storage', 'up', '-d', 'storage')
    if started.returncode:
        raise Unavailable(f'the storage service did not start: {started.stderr[-200:]}')
    base = f'http://127.0.0.1:{stack.target.storage_port}'
    ready = wait_for(lambda: http('GET', f'{base}/status', None)[0] == 200, 90)
    cases.check('storage service is healthy', 'status 200', f'ready {ready}', ready)
    if not ready:
        return
    policies = apply_sql_file(stack, root / FIXTURES / 'storage_policies.sql')
    cases.check('storage policies apply', 'exit 0', f'exit {policies.returncode}', policies.returncode == 0)
    secret = stack.secrets_env['AUTOBOTS_DISPOSABLE_JWT_SECRET']
    user_a = jwt(secret, {'role': 'authenticated', 'sub': USER_A, 'aud': 'authenticated'})
    user_b = jwt(secret, {'role': 'authenticated', 'sub': USER_B, 'aud': 'authenticated'})
    anon = stack.secrets_env['AUTOBOTS_DISPOSABLE_ANON_KEY']
    path = f'workspace-files/{WORKSPACE_A}/note.txt'
    upload = f'{base}/object/{path}'
    read = f'{base}/object/authenticated/{path}'
    status, body = http('POST', upload, user_a, b'fixture bytes')
    cases.check('a member can upload', 'status 200', f'{status}', status == 200)
    status, body = http('GET', read, user_a)
    cases.check('a member can read its object', 'status 200 and the bytes', f'{status} {body[:20]}', status == 200 and body == 'fixture bytes')
    for label, token in (('anonymous', anon), ('another workspace', user_b), ('no token', None)):
        status, body = http('GET', read, token)
        cases.check(f'{label} cannot read the object', 'a 4xx refusal', f'{status}', denied_status(status) and 'fixture bytes' not in body)
    status, _ = http('POST', f'{base}/object/workspace-files/{WORKSPACE_A}/other.txt', user_b, b'x')
    cases.check('another workspace cannot upload', 'a 4xx refusal', f'{status}', denied_status(status))
    status, _ = http('POST', f'{base}/object/workspace-files/{WORKSPACE_A}/anon.txt', anon, b'x')
    cases.check('anonymous cannot upload', 'a 4xx refusal', f'{status}', denied_status(status))
    status, body = http('GET', f'{base}/object/public/{path}', None)
    cases.check('a private bucket has no public read', 'a 4xx refusal', f'{status}', denied_status(status) and 'fixture bytes' not in body)


def denied_status(status: int) -> bool:
    """A refusal, not a server error, which would prove nothing about authorization."""
    return 400 <= status < 500


def worker_cases(stack: Stack, cases: Cases, root: Path) -> None:
    """DH-A09 on a stub: a crash, a duplicate delivery and an expired lease, in database time."""
    created = apply_sql_file(stack, root / FIXTURES / 'worker_fixture.sql')
    cases.check('stub worker fixture applies', 'exit 0', f'exit {created.returncode}', created.returncode == 0)
    if created.returncode:
        return
    def call(statement: str) -> str:
        return rows(stack, f'select worker_fixture.{statement};')
    first = call("claim('worker-a', interval '1 second')")
    second = call("claim('worker-b', interval '1 second')")
    cases.check('a held lease cannot be claimed again', 'generation 1, then no claim', f'{first!r}, {second!r}', first == '1' and second == '')
    alive = call("heartbeat(1, 1, interval '1 second')")
    cases.check('the current owner can heartbeat', 'true', alive, alive == 't')
    applied = call("apply_effect(1, 1, 'operation-1')")
    duplicate = call("apply_effect(1, 1, 'operation-1')")
    effects = rows(stack, "select count(*) from worker_fixture.effects where operation_id = 'operation-1';")
    cases.check('a duplicate delivery repeats no effect', 'applied, duplicate, 1 effect', f'{applied}, {duplicate}, {effects}',
                (applied, duplicate, effects) == ('applied', 'duplicate', '1'))
    time.sleep(1.2)  # Worker A has crashed: it stops heartbeating, and its lease lapses on database time.
    expired = call("heartbeat(1, 1, interval '1 second')")
    late_unclaimed = call("apply_effect(1, 1, 'operation-unclaimed')")
    complete_unclaimed = call('complete(1, 1)')
    cases.check('an expired lease cannot act, even unclaimed', 'fenced, not completed', f'{late_unclaimed}, {complete_unclaimed}',
                (late_unclaimed, complete_unclaimed) == ('fenced', 'f'))
    claimed = call("claim('worker-b', interval '30 seconds')")
    cases.check('an expired lease moves to a new generation', 'no heartbeat, generation 2', f'{expired}, {claimed}', expired == 'f' and claimed == '2')
    late = call("apply_effect(1, 1, 'operation-2')")
    late_complete = call('complete(1, 1)')
    state = rows(stack, "select status || '|' || owner from worker_fixture.jobs where id = 1;")
    cases.check('the crashed worker is fenced', 'fenced, not completed, still running under B', f'{late}, {late_complete}, {state}',
                (late, late_complete, state) == ('fenced', 'f', 'running|worker-b'))
    retried = call("apply_effect(1, 2, 'operation-1')")
    effects = rows(stack, "select count(*) from worker_fixture.effects where operation_id = 'operation-1';")
    done = call('complete(1, 2)')
    again = call('complete(1, 2)')
    cases.check('recovery does not repeat a known effect', 'duplicate, 1 effect, completes once', f'{retried}, {effects}, {done}, {again}',
                (retried, effects, done, again) == ('duplicate', '1', 't', 'f'))
    terminal = call("apply_effect(1, 2, 'operation-after-success')")
    cases.check('a terminal job takes no new effect', 'fenced', terminal, terminal == 'fenced')


def guard_cases_on_real_target(stack: Stack, cases: Cases) -> None:
    wrong = Stack(Target(f'{PROJECT_PREFIX}wrong', stack.target.db_port), stack.root, stack.compose_file)
    try:
        require_marker(wrong)
        cases.check('a project without containers is refused', 'refused', 'not refused', False)
    except Refused as refusal:
        cases.check('a project without containers is refused', 'refused', str(refusal), True)
    stack.sql("update autobots_disposable.marker set run_id = 'something-else';")
    before = rows(stack, 'select count(*) from app.notes;')
    try:
        reset_fixture_schema(stack)
        cases.check('a wrong marker refuses reset', 'refused, rows remain', 'reset ran', False)
    except Refused as refusal:
        cases.check('a wrong marker refuses reset', 'refused, rows remain',
                    f"{refusal}; {rows(stack, 'select count(*) from app.notes;')} notes", rows(stack, 'select count(*) from app.notes;') == before)
    stack.sql(f"update autobots_disposable.marker set run_id = '{stack.target.project}';")


def qualify(root: Path) -> int:
    project = f'{PROJECT_PREFIX}{secrets.token_hex(4)}'
    db_port = free_port()
    target = Target(project, db_port, free_port([db_port]))
    secret = secrets.token_urlsafe(32)
    stack = Stack(target, root, root / COMPOSE, {
        'AUTOBOTS_DISPOSABLE_PASSWORD': secrets.token_hex(24), 'AUTOBOTS_DISPOSABLE_JWT_SECRET': secret,
        'AUTOBOTS_DISPOSABLE_ANON_KEY': jwt(secret, {'role': 'anon'}),
        'AUTOBOTS_DISPOSABLE_SERVICE_KEY': jwt(secret, {'role': 'service_role'})})
    cases = Cases()
    identity_cases(cases)
    require_identity(target, tool_env())
    if run(['docker', 'info', '--format', '{{.ServerVersion}}'], tool_env(), 30).returncode:
        raise Unavailable('the Docker engine is not reachable')
    (root / REPORT).unlink(missing_ok=True)  # A run that cannot finish leaves no earlier result behind.
    require_rendered(stack)
    cases.check('the real Compose file renders safely', 'no refusal', 'loopback, pinned, labeled and owned', True)
    before = other_resources(project)
    started_at = time.monotonic()
    try:
        started = stack.compose('up', '-d', '--wait', 'db')
        if started.returncode:
            raise Unavailable(f'the disposable database did not start: {started.stderr[-300:]}')
        write_marker(stack)
        migration_cases(stack, cases, root)
        seed_cases(stack, cases, root)
        authorization_cases(stack, cases)
        storage_cases(stack, cases, root)
        worker_cases(stack, cases, root)
        guard_cases_on_real_target(stack, cases)
    finally:
        remove_stack(stack)
    label = f'label=com.docker.compose.project={project}'
    left_volumes = run(['docker', 'volume', 'ls', '--filter', label, '--format', '{{.Name}}'], tool_env())
    left_containers = run(['docker', 'ps', '-a', '--filter', label, '--format', '{{.Names}}'], tool_env())
    if left_volumes.returncode or left_containers.returncode:
        raise Unavailable('docker could not list what cleanup left')
    left = (left_volumes.stdout + left_containers.stdout).strip()
    cases.check('cleanup removed the owned containers and volumes', 'none left', left or 'none', not left)
    after = other_resources(project)
    cases.check('other Docker resources are untouched', 'same containers and volumes', f'{len(before)} before, {len(after)} after', before == after)
    passed = all(record['status'] == 'passed' for record in cases.records)
    path = root / REPORT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'schema_version': 'autobots.disposable-qualification/v1',
                                'completed_at_utc': datetime.now(timezone.utc).isoformat(),
                                'duration_seconds': round(time.monotonic() - started_at, 1),
                                'input_fingerprint': fingerprint(root),
                                'status': 'passed' if passed else 'failed', 'target_class': 'disposable',
                                'project': project, 'cases': cases.records,
                                'not_established': ['H1', 'product acceptance', 'the persistent stack',
                                                    'the pinned self-hosted release']}, indent=2) + '\n')
    return 0 if passed else 1


def guarded_stack(args: argparse.Namespace, root: Path) -> Stack:
    target = Target(args.project, args.db_port, args.storage_port, tuple(args.volume))
    require_identity(target, os.environ)
    stack = Stack(target, root, Path(args.compose_file).resolve() if args.compose_file else root / COMPOSE)
    require_rendered(stack)
    return stack


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('verb', choices=('qualify', 'reset', 'cleanup', 'migrate'))
    parser.add_argument('--project')
    parser.add_argument('--db-port', type=int)
    parser.add_argument('--storage-port', type=int)
    parser.add_argument('--volume', action='append', default=[])
    parser.add_argument('--compose-file')
    args = parser.parse_args(argv)
    root = project_root()
    try:
        if args.verb == 'qualify':
            return qualify(root)
        if not args.project:
            print('ERROR: --project is required.', file=sys.stderr)
            return 2
        stack = guarded_stack(args, root)
        if args.verb == 'cleanup':
            remove_stack(stack)
        elif args.verb == 'reset':
            reset_fixture_schema(stack)
        else:
            require_marker(stack)
            _, problem = apply_migrations(stack, root / FIXTURES / 'migrations')
            if problem:
                print(f'FAIL: {problem}')
                return 1
        print(f'PASS: {args.verb} on {args.project}.')
        return 0
    except Refused as refusal:
        print(f'REFUSED before any change: {refusal}', file=sys.stderr)
        return 1
    except Unavailable as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
