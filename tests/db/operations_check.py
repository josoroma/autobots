"""Retention against a real database and Storage, through the runtime role. `admit` queues one fixture job."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import psycopg
from pydantic import SecretStr

sys.path.insert(0, str(Path(__file__).parent))

from autobots.adapters.object_storage import SupabaseObjectStore
from autobots.application.artifacts import ArtifactUnavailable, object_path, read_artifact
from autobots.application.retention import RetentionPolicy, apply_retention, write_policy
from autobots.application.runs import admit_run, apply_command
from autobots.domain.models import resolve_role_policy
from autobots.domain.runs import Actor, RunCommand

URL = os.environ['AUTOBOTS_DATABASE_URL']
cases: list[dict[str, Any]] = []


def check(name: str, expected: str, observed: object, passed: bool) -> None:
    cases.append({'id': name, 'expected': expected, 'observed': str(observed), 'passed': bool(passed)})


async def admit(workspace: str) -> None:
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        accepted = await admit_run(db, workspace_id=UUID(workspace), actor_id=uuid4(), idempotency_key=str(uuid4()),
                                   goal_text='Write the report', limit_micro_usd=1_000_000, policy=resolve_role_policy())
        print(accepted.run_id)


async def resume(workspace: str, run: str) -> None:
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        version = (await (await db.execute("select version from public.runs where id = %s", (run,))).fetchone())[0]
        await apply_command(db, workspace_id=UUID(workspace), run_id=UUID(run), command=RunCommand.RESUME, actor=Actor.USER, expected_version=version)


async def cancel(workspace: str, run: str) -> None:
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        version = (await (await db.execute("select version from public.runs where id = %s", (run,))).fetchone())[0]
        await apply_command(db, workspace_id=UUID(workspace), run_id=UUID(run), command=RunCommand.CANCEL, actor=Actor.USER, expected_version=version)


class Down:
    async def remove(self, path: str) -> None:
        raise RuntimeError('storage is down')


async def retention(workspace_a: UUID, workspace_b: UUID, real_run: UUID) -> None:
    store = SupabaseObjectStore(os.environ['AUTOBOTS_STORAGE_BASE'], SecretStr(os.environ['AUTOBOTS_STORAGE_SERVICE']))
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        async def value(sql: str, *values: object) -> Any:
            return (await (await db.execute(sql, values)).fetchone())[0]

        async def arranged(workspace: UUID, status: str = 'succeeded', days: int = 90, root: UUID | None = None, continues: UUID | None = None) -> UUID:
            run = uuid4()
            await db.execute("insert into public.runs (id, workspace_id, limit_micro_usd, status, updated_at, root_run_id, continues_run_id) "
                             "values (%s, %s, 1, %s, now() - make_interval(days => %s), %s, %s)",
                             (run, workspace, status, days, root, continues))
            await db.execute("insert into app_private.run_files (run_id, path, version, content, sha256, media_type, operation_id) "
                             "values (%s, 'outputs/kept.md', 1, 'kept', 'x', 'text/markdown', %s)", (run, str(uuid4())))
            return run

        async def files(run: UUID) -> int:
            return await value("select count(*) from app_private.run_files where run_id = %s", run)

        async def receipt(run: UUID, workspace: UUID, status: str) -> None:
            await db.execute("insert into app_private.tool_receipts (operation_id, run_id, workspace_id, tool_id, tool_version, argument_hash, status, generation) "
                             "values (%s, %s, %s, 'mock', 1, 'x', %s, 0)", (str(uuid4()), run, workspace, status))

        # A real run the loop finished, aged, with one stored artifact arranged on it.
        thread = await value("select checkpoint_thread_id from public.runs where id = %s", real_run)
        before = {
            'checkpoints': await value("select count(*) from agent_runtime.checkpoints where thread_id = %s", thread),
            'events': await value("select count(*) from public.run_events where run_id = %s", real_run),
            'receipts': await value("select count(*) from app_private.tool_receipts where run_id = %s", real_run),
            'files': await files(real_run),
        }
        check('the real finished run has content to purge', 'checkpoints, files and receipts', before, before['checkpoints'] > 0 and before['files'] > 0 and before['receipts'] > 0)
        artifact = uuid4()
        path = object_path(workspace_a, real_run, 'retention-op', 'kept.txt')
        await store.put(path, b'retained bytes', 'text/plain')
        await db.execute("insert into public.artifacts (id, workspace_id, run_id, operation_id, name, object_path, media_type, size_bytes, sha256, status) "
                         "values (%s, %s, %s, 'retention-op', 'kept.txt', %s, 'text/plain', 14, %s, 'published')",
                         (artifact, workspace_a, real_run, path, '0' * 64))
        await db.execute("update public.runs set updated_at = now() - interval '90 days' where id = %s", (real_run,))

        # No policy keeps everything.
        report = await apply_retention(db, store, workspace_a)
        kept = await value("select count(*) from agent_runtime.checkpoints where thread_id = %s", thread)
        check('with no declared window nothing is removed', '0 purged, checkpoints unchanged', f'{report.purged_runs} purged, {kept} checkpoints', report.purged_runs == 0 and kept == before['checkpoints'])

        young = await arranged(workspace_a, days=1)
        unknown = await arranged(workspace_a)
        await receipt(unknown, workspace_a, 'unknown')
        started = await arranged(workspace_a)
        await receipt(started, workspace_a, 'started')
        active = await arranged(workspace_a, status='running')
        root = await arranged(workspace_a, status='running', days=1)
        child = await arranged(workspace_a, root=root)
        source = await arranged(workspace_a)
        await arranged(workspace_a, status='queued', continues=source)
        waiting = await arranged(workspace_a)
        await db.execute("insert into app_private.run_obligations (id, run_id, kind, detail) values (%s, %s, 'input', 'x')", (uuid4(), waiting))
        other = await arranged(workspace_b)
        await receipt(other, workspace_b, 'succeeded')
        old_key, active_key = str(uuid4()), str(uuid4())
        for key, target in ((old_key, str(uuid4())), (active_key, str(active))):
            await db.execute("insert into app_private.idempotency_receipts (workspace_id, actor_id, operation, target, idempotency_key, request_hash, result, created_at) "
                             "values (%s, %s, 'run.admit', %s, %s, 'x', '{}', now() - interval '90 days')", (workspace_a, uuid4(), target, key))

        await write_policy(db, workspace_a, uuid4(), RetentionPolicy(run_days=7, receipt_days=7))
        # Storage failing first: rows commit, bytes wait for the next pass.
        report = await apply_retention(db, Down(), workspace_a)
        stored = await store.get(path)
        check('a Storage failure leaves bytes pending, not lost track of', '1+ pending, object still there', f'{report.objects_pending} pending, stored {stored is not None}', report.objects_pending >= 1 and stored is not None)
        check('the old finished runs are purged', 'at least the real run', f'{report.purged_runs}, refused {report.refused}', report.purged_runs >= 1)
        check('a run with an unresolved effect is refused', 'unresolved_effect 2 (unknown, started)', report.refused, report.refused.get('unresolved_effect') == 2)
        check('a child of an active run is refused', 'run_tree_active 1', report.refused, report.refused.get('run_tree_active') == 1)
        check('the source of an active continuation is refused', 'continuation_active 1', report.refused, report.refused.get('continuation_active') == 1)
        check('a finished run with a stale obligation still purges', 'not refused for it', report.refused, 'open_obligation' not in report.refused)
        for name, run in (('unknown effect', unknown), ('started effect', started), ('active', active), ('child', child), ('continued', source), ('young', young)):
            remaining = await files(run)
            check(f'the {name} run keeps its files', '1', remaining, remaining == 1)
        direct = await value("select app_private.purge_run_content(%s, %s, now())", workspace_a, active)
        check('an active run is refused by the database itself', 'run_active', direct, direct.get('refused') == 'run_active')

        after = {
            'checkpoints': await value("select count(*) from agent_runtime.checkpoints where thread_id = %s", thread),
            'blobs': await value("select count(*) from agent_runtime.checkpoint_blobs where thread_id = %s", thread),
            'files': await files(real_run),
            'events': await value("select count(*) from public.run_events where run_id = %s", real_run),
            'receipts': await value("select count(*) from app_private.tool_receipts where run_id = %s", real_run),
        }
        check('declared content is gone from the real run', '0 checkpoints, blobs, files', after, after['checkpoints'] == 0 and after['blobs'] == 0 and after['files'] == 0)
        check('its events and operation receipts remain', f"{before['events']} events, {before['receipts']} receipts", after, after['events'] == before['events'] and after['receipts'] == before['receipts'])
        status = await value("select status from public.runs where id = %s", real_run)
        check('the run record remains, terminal', 'succeeded', status, status == 'succeeded')

        report = await apply_retention(db, store, workspace_a)
        gone = await store.get(path)
        check('the next pass removes the pending bytes', 'object gone', f'{report.objects_removed} removed, present {gone is not None}', report.objects_removed >= 1 and gone is None)
        try:
            await read_artifact(db, store, workspace_a, artifact)
            refused = 'readable'
        except ArtifactUnavailable as error:
            refused = str(error)
        check('an expired artifact reads as unavailable', 'artifact_missing', refused, refused == 'artifact_missing')
        check('a second pass purges nothing more', '0', report.purged_runs, report.purged_runs == 0)

        expired = await value("select count(*) from app_private.idempotency_receipts where idempotency_key = %s", old_key)
        kept_key = await value("select count(*) from app_private.idempotency_receipts where idempotency_key = %s", active_key)
        check('an old key expires, and one for an active run stays', '0 and 1', f'{expired} and {kept_key}', expired == 0 and kept_key == 1)
        receipts = await value("select count(*) from app_private.tool_receipts where run_id = %s", real_run)
        check('expiring keys leaves effect receipts', str(before['receipts']), receipts, receipts == before['receipts'])

        other_files = await files(other)
        crossed = await value("select app_private.purge_run_content(%s, %s, now())", workspace_a, other)
        check("another workspace's old run is untouched", '1 file, and run_not_found across workspaces', f'{other_files}, {crossed}', other_files == 1 and crossed.get('refused') == 'run_not_found')
        logged = await value("select count(*) from app_private.retention_log where workspace_id = %s and action = 'run_content_purged'", workspace_a)
        leak = await value("select count(*) from app_private.retention_log where workspace_id = %s", workspace_b)
        check('each purge is logged in its own workspace', '1+ in A, 0 in B', f'{logged}, {leak}', logged >= 1 and leak == 0)
        try:
            await db.execute("delete from app_private.run_files where run_id = %s", (young,))
            denied = 'deleted'
        except psycopg.errors.InsufficientPrivilege:
            denied = 'denied'
        check('the runtime role still cannot delete directly', 'denied', denied, denied == 'denied')
    print(json.dumps({'cases': cases}))


if __name__ == '__main__':
    if sys.argv[1] == 'admit':
        asyncio.run(admit(sys.argv[2]))
    elif sys.argv[1] == 'cancel':
        asyncio.run(cancel(sys.argv[2], sys.argv[3]))
    elif sys.argv[1] == 'resume':
        asyncio.run(resume(sys.argv[2], sys.argv[3]))
    else:
        asyncio.run(retention(UUID(sys.argv[2]), UUID(sys.argv[3]), UUID(sys.argv[4])))
