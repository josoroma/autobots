#!/usr/bin/env python3
"""The guarded persistent apply's refusals and its normal path, on a disposable stack, US-11.3.

Only this script calls the guard with `expected_class='disposable'`, and only from Python, so no flag
can do that to a real install. It removes only its own project. Exit codes: 0 passed, 1 a case failed,
2 prerequisite unavailable. Passing establishes nothing about the real install, H1 or product acceptance.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

from app_db import MIGRATIONS, AppStack
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
    rows,
    run,
    tool_env,
)
from harness_lib import fingerprint, project_root
from persistent_install import (
    STORAGE_SQL,
    Record,
    first_setup,
    guarded_apply,
    read_record,
    write_install,
)
from supabase_stack import generated_values, require_images, require_rendered

REPORT = Path('.checks/persistent-apply/qualification.json')
PYTHON = Path('services/agent/.venv/bin/python')
STATE = "select (select count(*) from autobots_install.migrations) || '/' || (select count(*) from pg_tables where schemaname in ('public', 'app_private', 'agent_runtime'));"


def refused(cases: Cases, name: str, call, stack: AppStack, expected_text: str) -> None:
    before = rows(stack, STATE)
    try:
        call()
        observed, passed = 'not refused', False
    except Refused as refusal:
        observed, passed = str(refusal)[:200], expected_text in str(refusal)
    after = rows(stack, STATE)
    cases.check(name, f'refused, naming "{expected_text}", nothing changed', f'{observed}, {before} then {after}', passed and before == after)


def migration_copy(root: Path, folder: Path) -> Path:
    folder.mkdir()
    for path in (root / MIGRATIONS).glob('*.sql'):
        shutil.copyfile(path, folder / path.name)
    return folder


def cli_cases(root: Path, cases: Cases, work: Path, used: list[int]) -> None:
    def cli(directory: Path, *argv: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([str(root / PYTHON), str(root / 'scripts/persistent_install.py'), '--install-dir', str(directory), *argv], env={**tool_env(), 'PYTHONDONTWRITEBYTECODE': '1'},
                              capture_output=True, text=True, errors='replace', timeout=60, check=False)

    recorded = work / 'recorded'
    ports = []
    for _ in range(4):
        ports.append(free_port([*used, *ports]))
    fresh = write_install(recorded, 'autobots-test-install', *ports, root)
    modes = sorted({oct(path.stat().st_mode)[-3:] for path in recorded.iterdir() if path.is_file()})
    cases.check('its files are private, and hold the identity', '600 only', str(modes), modes == ['600'] and read_record(recorded).install_id == fresh.install_id)
    project = ('--project', 'autobots-test-install')
    for command in (('reset', *project), ('apply', *project, '--reset')):
        done = cli(recorded, *command)
        name = 'apply --reset' if '--reset' in command else 'reset'
        cases.check(f'{name} is refused', 'exit 1, never reset', f'exit {done.returncode}, {done.stderr.strip()[:80]}', done.returncode == 1 and 'never reset' in done.stderr)
    done = cli(recorded, 'apply', '--project', 'supabase_db_finance')
    cases.check('the command line refuses another project', 'exit 1', f'exit {done.returncode}, {done.stderr.strip()[:90]}', done.returncode == 1 and 'not the recorded install' in done.stderr)
    done = cli(recorded, 'init', *project)
    cases.check('init never replaces a record', 'exit 1', f'exit {done.returncode}', done.returncode == 1 and 'never replaces' in done.stderr)
    done = cli(work / 'other', 'init', '--project', f'{PROJECT_PREFIX}x')
    cases.check('init refuses a disposable name', 'exit 1', f'exit {done.returncode}', done.returncode == 1)
    done = cli(recorded, 'goal', *project, '--limit-micro-usd', '100')
    cases.check('a goal needs --paid', 'exit 1', f'exit {done.returncode}', done.returncode == 1 and '--paid' in done.stderr)
    ledger = work / 'ledger.json'
    ledger.write_text(json.dumps({'cap_micro_usd': 1_000_000, 'committed': 999_990, 'entries': [{'label': 'arranged', 'worst_case': 999_990, 'reported': 999_990, 'state': 'settled'}]}))
    done = cli(recorded, 'goal', *project, '--paid', '--limit-micro-usd', '100', '--ledger', str(ledger))
    left = json.loads(ledger.read_text())['entries']
    cases.check('no goal starts past the shared cap', 'refused before any request, nothing reserved', f'exit {done.returncode}, {len(left)} entries, {done.stderr.strip()[:110]}',
                done.returncode == 1 and 'past' in done.stderr and len(left) == 1)


def qualify(root: Path) -> int:
    project = f'{PROJECT_PREFIX}{secrets.token_hex(4)}'
    gateway_port = free_port()
    db_port = free_port([gateway_port])
    target = Target(project, db_port, gateway_port)
    stack = AppStack(target, root, root / 'infra/supabase/upstream/docker-compose.yml', values=generated_values(gateway_port, db_port))
    stack.migrator_password, stack.runtime_password = secrets.token_hex(24), secrets.token_hex(24)
    require_identity(target, tool_env())
    if run(['docker', 'info', '--format', '{{.ServerVersion}}'], tool_env(), 30).returncode:
        raise Unavailable('the Docker engine is not reachable')
    require_images(require_rendered(stack))
    (root / REPORT).unlink(missing_ok=True)
    cases = Cases()
    before_resources = other_resources(project)
    started_at = time.monotonic()
    work = Path(tempfile.mkdtemp(prefix='autobots-apply-'))
    record = Record(project, 'arranged-install-id', gateway_port, db_port, 1, 2, work)
    try:
        up = stack.compose('up', '-d', '--wait', '--wait-timeout', '240', timeout=300)
        if up.returncode:
            raise Unavailable(f'the stack did not start: {up.stderr[-300:]}')

        def attempt(requested: str = project, stored: Record = record, expected: str = 'disposable', folder: Path | None = None) -> dict:
            return guarded_apply(stack, root, stored, requested, expected, directory=folder)

        try:
            attempt()
            cases.check('a database with no identity row is refused', 'refused', 'not refused', False)
        except Refused as refusal:
            cases.check('a database with no identity row is refused', 'refused', str(refusal)[:160], 'no identity row' in str(refusal))
        first_setup(stack, root, record, project, 'disposable')
        written = rows(stack, 'select install_id from autobots_install.identity;')
        cases.check('setup writes the identity row', record.install_id, written, written == record.install_id)
        try:
            first_setup(stack, root, record, project, 'disposable')
            cases.check('setup never runs twice', 'refused', 'not refused', False)
        except Refused as refusal:
            cases.check('setup never runs twice', 'refused', str(refusal)[:160], 'already holds' in str(refusal))

        applied = attempt()
        names = sorted(path.name for path in (root / MIGRATIONS).glob('*.sql'))
        cases.check('the normal path applies every migration in order, each with a history row', f'{len(names)} applied', str(len(applied['applied'])), applied['applied'] == names)
        again = attempt()
        cases.check('a second apply has nothing pending', '0 applied', str(len(again['applied'])), again['applied'] == [] and again['already_applied'] == len(names))
        reading = stack.runtime('select count(*) from autobots_install.identity;')
        cases.check('the runtime role cannot read the install schema', 'refused', str(reading.returncode), reading.returncode != 0)
        writing = stack.migrator("insert into autobots_install.identity values ('x', 'x');")
        cases.check('the migration role cannot change the identity', 'refused', str(writing.returncode), writing.returncode != 0)

        refused(cases, 'another project is refused', lambda: attempt('supabase_db_finance'), stack, 'is not the recorded install')
        refused(cases, 'another install id is refused', lambda: attempt(stored=Record(project, 'another-id', gateway_port, db_port, 1, 2, work)), stack, 'no identity row')
        refused(cases, 'a record naming another port is refused', lambda: attempt(stored=Record(project, record.install_id, gateway_port, 1, 1, 2, work)), stack, 'publishes its database')
        refused(cases, 'a disposable target is refused on the real path', lambda: attempt(expected='persistent'), stack, 'labelled disposable')
        refused(cases, 'a target with no hold is refused as a restored copy', lambda: guarded_apply(stack, root, record, project, restored_copy=True), stack, 'restore hold')
        refused(cases, 'a real project is refused as a restored copy', lambda: guarded_apply(stack, root, record, 'autobots-install', restored_copy=True), stack, f'always {PROJECT_PREFIX}')
        refused(cases, 'first setup refuses a record naming another port', lambda: first_setup(stack, root, Record(project, record.install_id, gateway_port, 1, 1, 2, work), project, 'disposable'), stack, 'publishes its database')
        # The install's own schema refuses the migrator, so this uses the owner's connection, as setup does.
        changed = stack.sql("update autobots_install.migrations set sha256 = 'arranged' where name = 'bootstrap/storage.sql' returning sha256;")
        if changed.returncode or 'arranged' not in changed.stdout:
            raise Unavailable('could not arrange a changed storage record')
        real_digest = hashlib.sha256((root / STORAGE_SQL).read_bytes()).hexdigest()
        try:
            refused(cases, 'a changed storage file is refused', lambda: attempt(), stack, 'changed after it was applied')
        finally:
            stack.sql(f"update autobots_install.migrations set sha256 = '{real_digest}' where name = 'bootstrap/storage.sql';")
        edited = migration_copy(root, work / 'edited')
        first = sorted(edited.glob('*.sql'))[0]
        first.write_text(first.read_text() + '\n-- edited\n')
        refused(cases, 'an edited applied migration is refused', lambda: attempt(folder=edited), stack, 'never edit an applied migration')
        older = migration_copy(root, work / 'older')
        sorted(older.glob('*.sql'))[-1].unlink()
        refused(cases, 'an older checkout missing an applied migration is refused', lambda: attempt(folder=older), stack, 'not in this checkout')
        pending = migration_copy(root, work / 'pending')
        (pending / 'bad-name.sql').write_text('select 1;\n')
        refused(cases, 'a badly named file is refused before anything applies', lambda: attempt(folder=pending), stack, 'is not named')
        (pending / 'bad-name.sql').unlink()
        (pending / '20991231000001_breaks.sql').write_text('create table public.half_done (id int);\nselect no_such_function();\n')
        before = rows(stack, STATE)
        try:
            attempt(folder=pending)
            cases.check('a failing migration rolls back whole', 'reported', 'not reported', False)
        except Unavailable as problem:
            cases.check('a failing migration rolls back whole', 'reported, nothing changed', f'{str(problem)[:120]}, {before} then {rows(stack, STATE)}', rows(stack, STATE) == before and '20991231000001' in str(problem))
        cli_cases(root, cases, work, [gateway_port, db_port])
    finally:
        remove_stack(stack)
        shutil.rmtree(work, ignore_errors=True)
    label = f'label=com.docker.compose.project={project}'
    left = (run(['docker', 'volume', 'ls', '--filter', label, '--format', '{{.Name}}'], tool_env()).stdout + run(['docker', 'ps', '-a', '--filter', label, '--format', '{{.Names}}'], tool_env()).stdout).strip()
    cases.check('cleanup removed the owned containers and volumes', 'none left', left or 'none', not left)
    after_resources = other_resources(project)
    cases.check('other Docker resources are untouched', 'same', f'{len(before_resources)} before, {len(after_resources)} after', before_resources == after_resources)
    passed = all(case['status'] == 'passed' for case in cases.records)
    path = root / REPORT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'schema_version': 'autobots.persistent-apply/v1', 'completed_at_utc': datetime.now(UTC).isoformat(), 'duration_seconds': round(time.monotonic() - started_at, 1),
                                'input_fingerprint': fingerprint(root), 'status': 'passed' if passed else 'failed', 'target_class': 'disposable', 'cases': cases.records,
                                'not_established': ['the real install', 'H1', 'product acceptance']}, indent=2) + '\n')
    return 0 if passed else 1


def main() -> int:
    try:
        return qualify(project_root())
    except Refused as refusal:
        print(f'REFUSED before any change: {refusal}', file=sys.stderr)
        return 1
    except Unavailable as problem:
        print(f'ERROR: {problem}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
