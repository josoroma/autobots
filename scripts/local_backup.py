#!/usr/bin/env python3
"""Cold, encrypted backup of one local Compose project, and restore to a new isolated one.

Run with services/agent/.venv/bin/python, which has `cryptography`. `backup` refuses while workers or
leases are live, stops the project's containers, captures every named volume, then starts them again.
It never removes anything. `restore` only creates a new `autobots-disposable-*` project, and leaves it
under a hold so no job, routine or retention pass runs until a person releases it.

Exit codes: 0 done, 1 refused before any change, 2 a prerequisite is unavailable.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import secrets
import shutil
import struct
import subprocess
import sys
import time
from typing import IO
from urllib import request as urlrequest

from app_db import AppStack
from disposable_db import PROJECT_PREFIX, Refused, Target, Unavailable, free_port, require_identity, tool_env
from harness_lib import project_root

MANIFEST_VERSION = 'autobots.backup/v1'
CHUNK = 1024 * 1024
LABEL = 'label=com.docker.compose.project='
PORT_VALUES = ('API_GW_HTTP_PORT', 'AUTOBOTS_GATEWAY_HOST_PORT', 'AUTOBOTS_DB_HOST_PORT', 'SUPABASE_PUBLIC_URL', 'API_EXTERNAL_URL')
FACTS = """select json_build_object(
  'runs', (select count(*) from public.runs),
  'events', (select count(*) from public.run_events),
  'tool_receipts', (select count(*) from app_private.tool_receipts),
  'model_invocations', (select count(*) from app_private.model_invocations),
  'checkpoints', (select count(*) from agent_runtime.checkpoints),
  'users', (select count(*) from auth.users),
  'credentials', (select count(*) from app_private.provider_credentials),
  'live_leases', (select count(*) from app_private.run_jobs where status = 'claimed' and lease_expires_at > now()),
  'live_workers', (select count(*) from app_private.worker_heartbeats where state <> 'stopped' and beat_at > now() - interval '60 seconds'),
  'artifacts', (select coalesce(json_agg(json_build_object('id', id, 'workspace_id', workspace_id, 'sha256', sha256, 'size_bytes', size_bytes)), '[]') from public.artifacts where status = 'published'),
  'threads', (select coalesce(json_agg(t), '[]') from (select thread_id, max(checkpoint_id) as latest, count(*) as count from agent_runtime.checkpoints group by 1) t),
  'migrations', {migrations}
);"""


def docker(*arguments: str, timeout: float = 120.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(['docker', *arguments], env=tool_env(), capture_output=True, text=True, timeout=timeout, check=False)


def lines(result: subprocess.CompletedProcess[str]) -> list[str]:
    return [line for line in result.stdout.splitlines() if line.strip()]


def project_containers(project: str) -> list[str]:
    return lines(docker('ps', '-a', '--filter', f'{LABEL}{project}', '--format', '{{.Names}}'))


def project_volumes(project: str) -> dict[str, str]:
    """Compose's name for each volume, mapped to Docker's. Restore maps by the first, across projects."""
    listing = lines(docker('volume', 'ls', '--filter', f'{LABEL}{project}', '--format', '{{.Name}} {{.Label "com.docker.compose.volume"}}'))
    return {line.split()[1]: line.split()[0] for line in listing if len(line.split()) == 2}


def db_container(project: str) -> str:
    found = lines(docker('ps', '-a', '--filter', f'{LABEL}{project}', '--filter', 'label=com.docker.compose.service=db', '--format', '{{.Names}}'))
    if len(found) != 1:
        raise Refused(f'{project} has {len(found)} database containers')
    return found[0]


def read_facts(project: str) -> dict:
    container = db_container(project)
    # A name in a query has to exist when it's parsed, so which history table is read is decided first.
    command = ('psql', '-U', 'supabase_admin', '-d', 'postgres', '-X', '-q', '-A', '-t', '-c')
    which = docker('exec', container, *command, "select coalesce(to_regclass('autobots_install.migrations')::text, to_regclass('autobots_disposable.migrations')::text, '');")
    history = which.stdout.strip()
    migrations = f"(select coalesce(json_agg(name order by name), '[]') from {history})" if history else "'[]'::json"
    result = docker('exec', container, *command, FACTS.replace('{migrations}', migrations))
    if which.returncode or result.returncode:
        raise Refused(f'the running database of {project} could not be read')
    return json.loads(result.stdout)


def _cipher(key: bytes):
    # Here, not at the top, so a qualifier on the plain interpreter can use the pure helpers below.
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    return AESGCM(key)


# Sealed files: chunks that can't be reordered, dropped or moved to another component.
def _aad(component: str, index: int, final: bool) -> bytes:
    return f'{MANIFEST_VERSION}|{component}|{index}|{int(final)}'.encode()


def seal_stream(source: IO[bytes], path: Path, key: bytes, component: str) -> tuple[str, int]:
    cipher, digest, size, index = _cipher(key), hashlib.sha256(), 0, 0
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'wb') as output:
        current = source.read(CHUNK)
        while True:
            following = source.read(CHUNK)
            final = not following
            nonce = secrets.token_bytes(12)
            sealed = cipher.encrypt(nonce, current, _aad(component, index, final))
            frame = struct.pack('>BI', int(final), len(sealed)) + nonce + sealed
            output.write(frame)
            digest.update(frame)
            size += len(frame)
            index += 1
            if final:
                return digest.hexdigest(), size
            current = following


def open_stream(path: Path, key: bytes, component: str, sink: IO[bytes] | None) -> None:
    from cryptography.exceptions import InvalidTag
    cipher, index = _cipher(key), 0
    with path.open('rb') as source:
        while True:
            header = source.read(5)
            if len(header) != 5:
                raise Refused(f'{component} is truncated')
            final, length = struct.unpack('>BI', header)
            nonce, sealed = source.read(12), source.read(length)
            try:
                plain = cipher.decrypt(nonce, sealed, _aad(component, index, bool(final)))
            except InvalidTag as error:
                raise Refused(f'{component} does not open with this backup key, or was changed') from error
            if sink is not None:
                sink.write(plain)
            index += 1
            if final:
                return


def read_key(path: Path) -> bytes:
    if not path.is_file():
        raise Refused('the backup key file does not exist')
    if path.stat().st_mode & 0o077:
        raise Refused('the backup key file is readable by others')
    key = bytes.fromhex(path.read_text().strip())
    if len(key) != 32:
        raise Refused('the backup key must be 32 bytes of hex')
    return key


def inside(child: Path, parent: Path) -> bool:
    return child.resolve().is_relative_to(parent.resolve())


def parse_env(text: str) -> dict[str, str]:
    values = {}
    for line in text.splitlines():
        if line.strip() and not line.lstrip().startswith('#') and '=' in line:
            name, _, value = line.partition('=')
            values[name.strip()] = value.strip()
    return values


def backup(project: str, env_file: Path, out: Path, backup_key: Path, key_dir: Path, master_key: Path) -> dict:
    # Every refusal comes before anything stops.
    if out.exists():
        raise Refused('the backup directory already exists, and a backup never overwrites one')
    if inside(backup_key, out) or inside(key_dir, out):
        raise Refused('keys must stay outside the backup directory')
    if key_dir.resolve() == backup_key.parent.resolve():
        raise Refused('keep the provider key apart from the backup key')
    key = read_key(backup_key)
    if not master_key.is_file():
        raise Refused('the provider master key file does not exist')
    if not env_file.is_file():
        raise Refused('the configuration file does not exist')
    containers = project_containers(project)
    volumes = project_volumes(project)
    if not containers or not volumes:
        raise Refused(f'{project} has no containers or volumes')
    facts = read_facts(project)
    if facts.pop('live_workers') or facts.pop('live_leases'):
        raise Refused('workers or job leases are live. Drain and stop workers first')
    images = sorted({line.split('|')[0] for line in lines(docker('inspect', '-f', '{{.Config.Image}}|', *containers))})
    tool_image = lines(docker('inspect', '-f', '{{.Config.Image}}', db_container(project)))[0]

    out.mkdir(parents=True, mode=0o700)
    key_dir.mkdir(parents=True, mode=0o700, exist_ok=True)
    os.chmod(key_dir, 0o700)
    manifest: dict = {'schema_version': MANIFEST_VERSION, 'created_at': datetime.now(timezone.utc).isoformat(), 'source_project': project,
                      'images': images, 'tool_image': tool_image, 'facts': facts, 'components': {}, 'compose_files': compose_hashes(project_root())}
    with env_file.open('rb') as source:
        digest, size = seal_stream(source, out / 'configuration.sealed', key, 'configuration')
    manifest['components']['configuration'] = {'file': 'configuration.sealed', 'sha256': digest, 'size': size}
    kept = key_dir / 'provider-master.key'
    shutil.copyfile(master_key, kept)
    os.chmod(kept, 0o600)
    # A hash of a random 256-bit key reveals nothing and lets a restore match the right key.
    manifest['provider_key_sha256'] = hashlib.sha256(master_key.read_bytes()).hexdigest()

    try:
        try:
            stopped = docker('stop', '-t', '30', *containers, timeout=240)
        except subprocess.TimeoutExpired:
            raise Unavailable('stopping the project timed out, so no consistent backup was taken') from None
        if stopped.returncode:
            raise Unavailable('the project could not be stopped, so no consistent backup was taken')
        for logical, name in sorted(volumes.items()):
            component = f'volume:{logical}'
            capture = subprocess.Popen(['docker', 'run', '--rm', '-i', '--pull=never', '--network', 'none', '--user', 'root', '--entrypoint', 'tar',
                                        '-v', f'{name}:/data:ro', tool_image, '--numeric-owner', '-C', '/data', '-cf', '-', '.'],
                                       env=tool_env(), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            file_name = f'volume-{logical}.sealed'
            digest, size = seal_stream(capture.stdout, out / file_name, key, component)
            if capture.wait(60):
                raise Unavailable(f'capturing the {logical} volume failed')
            manifest['components'][component] = {'file': file_name, 'sha256': digest, 'size': size}
    finally:
        start_again(project, containers)
    body = json.dumps(manifest, indent=2, sort_keys=True).encode()
    descriptor = os.open(out / 'manifest.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'wb') as handle:
        handle.write(body)
    descriptor = os.open(out / 'manifest.hmac', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w') as handle:
        handle.write(hmac.new(key, body, hashlib.sha256).hexdigest())
    return manifest


def start_again(project: str, containers: list[str]) -> None:
    """The database first, then what depends on it, each back to healthy."""
    database = db_container(project)
    docker('start', database)
    wait_healthy([database], 120)
    others = [name for name in containers if name != database]
    docker('start', *others, timeout=180)
    wait_healthy(others, 180)


def wait_healthy(containers: list[str], seconds: float) -> None:
    deadline = time.monotonic() + seconds
    template = '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}'
    while time.monotonic() < deadline:
        states = lines(docker('inspect', '-f', template, *containers))
        # One-shot containers exit after their job, which is fine for them.
        if states and all(state in ('healthy', 'running', 'exited') for state in states):
            return
        time.sleep(1)
    raise Unavailable('containers did not return to healthy')


def compose_hashes(root: Path) -> dict[str, str]:
    from supabase_stack import COMPOSE_FILES
    return {str(path): hashlib.sha256((root / path).read_bytes()).hexdigest() for path in COMPOSE_FILES}


def load_manifest(backup_dir: Path, key: bytes) -> dict:
    body = (backup_dir / 'manifest.json').read_bytes()
    signature = (backup_dir / 'manifest.hmac').read_text().strip()
    if not hmac.compare_digest(signature, hmac.new(key, body, hashlib.sha256).hexdigest()):
        raise Refused('the manifest was changed, or this is the wrong backup key')
    manifest = json.loads(body)
    if manifest.get('schema_version') != MANIFEST_VERSION:
        raise Refused(f"this tool restores {MANIFEST_VERSION}, not {manifest.get('schema_version')}")
    return manifest


def verify_backup(backup_dir: Path, key: bytes) -> dict:
    """All of it, with Docker untouched: a damaged backup fails here, not halfway into a restore."""
    manifest = load_manifest(backup_dir, key)
    for component, entry in manifest['components'].items():
        path = backup_dir / entry['file']
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']:
            raise Refused(f'{component} does not match the manifest')
        open_stream(path, key, component, None)
    return manifest


def record_restore(backup_dir: Path, result: str, passed: int | None = None, total: int | None = None) -> None:
    """Beside the backup, where Operations reads it. A date and a result, and nothing about the instance."""
    entry = {'at': datetime.now(timezone.utc).isoformat(), 'result': result, 'checks_passed': passed, 'checks_total': total}
    descriptor = os.open(backup_dir / 'restores.jsonl', os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(descriptor, 'a') as handle:
        handle.write(json.dumps(entry) + '\n')


def recorded(backup_dir: Path, result: str, passed: int | None = None, total: int | None = None) -> None:
    """The result is already out by now, so a failed write is reported and costs nothing else."""
    try:
        record_restore(backup_dir, result, passed, total)
    except OSError as problem:
        print(f'WARNING: Operations will not show this restore: {type(problem).__name__}', file=sys.stderr)


def restored_values(values: dict[str, str], gateway_port: int, db_port: int) -> dict[str, str]:
    """The source's secrets, so Auth tokens and role passwords still hold, on this target's ports."""
    url = f'http://127.0.0.1:{gateway_port}'
    return {**values, 'API_GW_HTTP_PORT': str(gateway_port), 'AUTOBOTS_GATEWAY_HOST_PORT': str(gateway_port),
            'AUTOBOTS_DB_HOST_PORT': str(db_port), 'SUPABASE_PUBLIC_URL': url, 'API_EXTERNAL_URL': url}


def restore(backup_dir: Path, backup_key: Path, project: str, gateway_port: int, db_port: int) -> dict:
    key = read_key(backup_key)
    manifest = verify_backup(backup_dir, key)
    if not project.startswith(PROJECT_PREFIX):
        raise Refused(f'a restore only creates a new {PROJECT_PREFIX}* project')
    if project == manifest['source_project']:
        raise Refused('a restore never targets its source')
    if project_containers(project) or project_volumes(project):
        raise Refused(f'{project} already exists, and a restore never writes into existing volumes')
    root = project_root()
    current = compose_hashes(root)
    if current != manifest['compose_files']:
        raise Refused('the Compose files differ from the backup. Restore from the matching revision')
    sink = io.BytesIO()
    open_stream(backup_dir / manifest['components']['configuration']['file'], key, 'configuration', sink)
    values = parse_env(sink.getvalue().decode())
    target = Target(project, db_port, gateway_port)
    require_identity(target, tool_env())
    stack = AppStack(target, root, root / 'infra/supabase/upstream/docker-compose.yml', values=restored_values(values, gateway_port, db_port))
    rendered = set(stack.compose('config', '--images').stdout.split())
    if not set(manifest['images']) <= rendered:
        raise Refused('the pinned images differ from the backup')
    if stack.compose('create', timeout=240).returncode:
        raise Unavailable('the isolated project could not be created')
    volumes = project_volumes(project)
    tool_image = manifest['tool_image']
    for component, entry in manifest['components'].items():
        if not component.startswith('volume:'):
            continue
        logical = component.removeprefix('volume:')
        if logical not in volumes:
            raise Unavailable(f'the isolated project has no {logical} volume')
        loader = subprocess.Popen(['docker', 'run', '--rm', '-i', '--pull=never', '--network', 'none', '--user', 'root', '--entrypoint', 'tar',
                                   '-v', f'{volumes[logical]}:/data', tool_image, '--numeric-owner', '--same-permissions', '-C', '/data', '-xf', '-'],
                                  env=tool_env(), stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        open_stream(backup_dir / entry['file'], key, component, loader.stdin)
        loader.stdin.close()
        if loader.wait(120):
            raise Unavailable(f'loading the {logical} volume failed')
    # The database alone first, on ports nobody has yet, so the hold is in before any other service
    # starts and stays in if one of them fails. No job, routine or retention pass until it's released.
    if stack.compose('up', '-d', '--wait', '--wait-timeout', '180', '--no-deps', 'db', timeout=240).returncode:
        raise Unavailable('the isolated database did not become healthy')
    held = stack.sql("insert into app_private.installation_holds (hold, detail) values ('restore', 'Restored from a backup. Inspect, then release.') on conflict do nothing;\n"
                     "create schema if not exists autobots_disposable;\n"
                     'create table if not exists autobots_disposable.marker (run_id text primary key);\n'
                     f"delete from autobots_disposable.marker;\ninsert into autobots_disposable.marker values ('{project}');\n")
    if held.returncode:
        raise Unavailable(f'the restore hold could not be set: {held.stderr.strip()[-200:]}')
    if stack.compose('up', '-d', '--wait', '--wait-timeout', '240', timeout=300).returncode:
        raise Unavailable('the isolated project did not become healthy. Its database is up, and held')
    return {'project': project, 'gateway_port': gateway_port, 'db_port': db_port, 'volumes': sorted(volumes.values()), 'held': True}


def verify_restore(backup_dir: Path, backup_key: Path, key_dir: Path, project: str) -> list[dict]:
    """Every fact the manifest records, read back from the restored instance. Only reads."""
    key = read_key(backup_key)
    manifest = load_manifest(backup_dir, key)
    cases: list[dict] = []

    def check(name: str, expected: object, observed: object) -> None:
        cases.append({'id': name, 'expected': str(expected), 'observed': str(observed), 'passed': expected == observed})

    facts = read_facts(project)
    live = {name: facts.pop(name) for name in ('live_workers', 'live_leases')}
    check('no worker or lease is live', {'live_workers': 0, 'live_leases': 0}, live)
    recorded = manifest['facts']
    for name in ('runs', 'events', 'tool_receipts', 'model_invocations', 'checkpoints', 'users', 'credentials', 'migrations'):
        check(f'{name} match the manifest', recorded[name], facts[name])
    key_threads = lambda rows: sorted((row['thread_id'], row['latest'], row['count']) for row in rows)  # noqa: E731
    check('checkpoint threads end where the manifest says', key_threads(recorded['threads']), key_threads(facts['threads']))
    kept = key_dir / 'provider-master.key'
    check('the provider key is the one backed up', manifest['provider_key_sha256'], hashlib.sha256(kept.read_bytes()).hexdigest() if kept.is_file() else None)
    database = db_container(project)

    def sql(statement: str) -> subprocess.CompletedProcess[str]:
        return docker('exec', database, 'psql', '-U', 'supabase_admin', '-d', 'postgres', '-X', '-q', '-A', '-t', '-c', statement)

    check('the restore hold is in place', '1', sql('select count(*) from app_private.installation_holds;').stdout.strip())
    anon = sql('begin; set local role anon; select count(*) from public.runs; rollback;')
    check('an anonymous role reads no runs', True, anon.returncode != 0 or anon.stdout.strip() == '0')
    sink = io.BytesIO()
    open_stream(backup_dir / manifest['components']['configuration']['file'], key, 'configuration', sink)
    values = parse_env(sink.getvalue().decode())
    port = lines(docker('ps', '--filter', f'{LABEL}{project}', '--filter', 'label=com.docker.compose.service=api-gw', '--format', '{{.Ports}}'))[0].split('->')[0].rsplit(':', 1)[-1]
    service = values['SERVICE_ROLE_KEY']
    for artifact in recorded['artifacts']:
        path = sql(f"select object_path from public.artifacts where id = '{artifact['id']}';").stdout.strip()
        address = f'http://127.0.0.1:{port}/storage/v1/object/workspace-artifacts/{path}'
        reply = urlrequest.Request(address, headers={'apikey': service, 'Authorization': f'Bearer {service}'})
        try:
            with urlrequest.urlopen(reply, timeout=30) as response:
                digest = hashlib.sha256(response.read()).hexdigest()
        except OSError as error:
            digest = type(error).__name__
        check('an artifact reads back with its recorded hash', artifact['sha256'], digest)
    return cases


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest='command', required=True)
    make_key = commands.add_parser('keygen')
    make_key.add_argument('--out', type=Path, required=True)
    take = commands.add_parser('backup')
    take.add_argument('--project', required=True)
    take.add_argument('--env-file', type=Path, required=True)
    take.add_argument('--out', type=Path, required=True)
    take.add_argument('--backup-key', type=Path, required=True)
    take.add_argument('--key-dir', type=Path, required=True)
    take.add_argument('--master-key', type=Path, required=True)
    back = commands.add_parser('restore')
    back.add_argument('--backup', type=Path, required=True)
    back.add_argument('--backup-key', type=Path, required=True)
    back.add_argument('--project', required=True)
    back.add_argument('--gateway-port', type=int, default=0)
    back.add_argument('--db-port', type=int, default=0)
    verify = commands.add_parser('verify')
    verify.add_argument('--backup', type=Path, required=True)
    verify.add_argument('--backup-key', type=Path, required=True)
    verify.add_argument('--key-dir', type=Path, required=True)
    verify.add_argument('--project', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'verify':
            cases = verify_restore(args.backup, args.backup_key, args.key_dir, args.project)
            passed = sum(1 for case in cases if case['passed'])
            print(json.dumps({'cases': cases}))
            recorded(args.backup, 'passed' if passed == len(cases) else 'failed', passed, len(cases))
            return 0 if all(case['passed'] for case in cases) else 1
        if args.command == 'keygen':
            if args.out.exists():
                raise Refused('that key file already exists')
            args.out.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
            descriptor = os.open(args.out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, 'w') as handle:
                handle.write(secrets.token_hex(32))
            print('PASS: the backup key is written, and belongs apart from the backup')
        elif args.command == 'backup':
            manifest = backup(args.project, args.env_file, args.out, args.backup_key, args.key_dir, args.master_key)
            print(json.dumps({'status': 'backed_up', 'components': sorted(manifest['components'])}))
        else:
            gateway = args.gateway_port or free_port()
            database = args.db_port or free_port([gateway])
            restored = restore(args.backup, args.backup_key, args.project, gateway, database)
            print(json.dumps(restored))
            recorded(args.backup, 'not_verified')
        return 0
    except Refused as refusal:
        print(f'REFUSED before any change: {refusal}', file=sys.stderr)
        return 1
    except Unavailable as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
