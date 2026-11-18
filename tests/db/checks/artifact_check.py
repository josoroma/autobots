"""Publication, interruption and reconciliation on real Storage and Postgres. JSON cases."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any
from uuid import UUID, uuid4

import psycopg
from autobots.adapters import tool_registry
from autobots.adapters.object_storage import BUCKET, SupabaseObjectStore
from autobots.application.artifact_tool import publish_tool, read_tool
from autobots.application.artifacts import (
    ArtifactUnavailable,
    publish,
    read_artifact,
    reconcile_run,
)
from autobots.application.goal_loop import run_goal
from autobots.application.run_lifecycle import LoopConfig
from autobots.application.runs import LeaseLost, admit_run
from autobots.application.tool_definitions import ToolFailed, ToolRegistry, ToolScope
from autobots.application.tool_gateway import ToolGateway
from autobots.application.tools import SAVE_ARTIFACT
from autobots.application.worker_leases import claim_next
from autobots.domain.models import resolve_role_policy
from autobots.operations.job_dispatch import drive_lease
from goal_loop_script import PLAN, ROUTE, calls, say
from pydantic import SecretStr

URL, BASE, ANON = os.environ['AUTOBOTS_DATABASE_URL'], os.environ['AUTOBOTS_STORAGE_BASE'], os.environ['AUTOBOTS_STORAGE_ANON']
SERVICE = SecretStr(os.environ['AUTOBOTS_STORAGE_SERVICE'])
TOKEN_A, TOKEN_B = os.environ['AUTOBOTS_TOKEN_A'], os.environ['AUTOBOTS_TOKEN_B']
WORKSPACE, OTHER = UUID(sys.argv[1]), UUID(sys.argv[2])
cases = []
TEXT = b'# Report\nbytes that really exist\n'


def check(name: str, expected: str, observed: object, passed: bool) -> None:
    cases.append({'id': name, 'expected': expected, 'observed': str(observed), 'passed': bool(passed)})


def rest(method: str, path: str, token: str | None, body: bytes | None = None) -> tuple[int, bytes]:
    headers = {'apikey': ANON, **({'Authorization': f'Bearer {token}'} if token else {})}
    request = urllib.request.Request(f'{BASE}{path}', method=method, headers=headers, data=body)
    try:
        with urllib.request.urlopen(request, timeout=20) as reply:
            return reply.status, reply.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


class Interrupted(Exception):
    pass


class Failing:
    """Real storage underneath. One step raises, as a dying worker or a lost connection would."""

    def __init__(self, store: Any, fail_on: str) -> None:
        self._store, self._fail_on = store, fail_on

    def __getattr__(self, name: str) -> Any:
        return getattr(self._store, name)

    async def put(self, path: str, content: bytes, media_type: str) -> bool:
        if self._fail_on == 'before_upload':
            raise Interrupted
        return await self._store.put(path, content, media_type)

    async def get(self, path: str) -> bytes | None:
        if self._fail_on == 'after_upload':
            raise Interrupted
        return await self._store.get(path)


async def main() -> dict[str, Any]:
    store = SupabaseObjectStore(BASE, SERVICE)
    result: dict[str, Any] = {}
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        async def value(sql: str, *values: object) -> Any:
            return (await (await db.execute(sql, values)).fetchone())[0]

        async def scope_for(workspace: UUID = WORKSPACE) -> ToolScope:
            await db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null where status <> 'done'")
            await admit_run(db, workspace_id=workspace, actor_id=uuid4(), idempotency_key=str(uuid4()), goal_text='artifacts', limit_micro_usd=1_000_000, policy=resolve_role_policy())
            lease = await claim_next(db, worker_id='artifacts', lease_seconds=120)
            return ToolScope(workspace, lease.run_id, lease.generation, {'save_artifact': 1, 'publish_artifact': 1}, ('outputs',))

        async def status_of(operation: str) -> str:
            return await value('select status from public.artifacts where operation_id = %s', operation)

        scope = await scope_for()
        operation = 'a' * 64
        published = await publish(db, store, scope, operation_id=operation, name='report.md', media_type='text/markdown', content=TEXT)
        result.update(run_id=str(scope.run_id), artifact_id=published.artifact_id, expected_text=TEXT.decode())
        row = await (await db.execute('select object_path, sha256, size_bytes, status from public.artifacts where id = %s', (published.artifact_id,))).fetchone()
        check('a verified upload commits metadata with its hash', 'published, the sha256', row[1:], row[3] == 'published' and row[1] == hashlib.sha256(TEXT).hexdigest() and row[2] == len(TEXT))
        check('the object lives in the workspace and run namespace', 'scoped', row[0][:80], row[0].startswith(f'{WORKSPACE}/{scope.run_id}/'))
        stored = await store.get(row[0])
        check('the stored bytes are the bytes', 'equal', stored == TEXT, stored == TEXT)
        event = await value("select payload ->> 'type' from public.run_events where run_id = %s order by sequence desc limit 1", scope.run_id)
        check('the commit adds an event', 'artifact.published', event, event == 'artifact.published')
        sequences = [r[0] for r in await (await db.execute('select sequence from public.run_events where run_id = %s order by sequence', (scope.run_id,))).fetchall()]
        check('event sequences stay gapless with status changes', '1, 2, 3', sequences, sequences == [1, 2, 3])
        again = await publish(db, store, scope, operation_id=operation, name='report.md', media_type='text/markdown', content=TEXT)
        count = await value('select count(*) from public.artifacts where run_id = %s', scope.run_id)
        check('repeating an operation reuses the artifact', 'same id, 1 row', (again.artifact_id == published.artifact_id, count), again.artifact_id == published.artifact_id and count == 1)

        # Size, type and name are checked before anything is stored.
        for label, options, code in (('a name with a slash', {'name': '../x.md', 'media_type': 'text/plain', 'content': b'x'}, 'artifact_name_invalid'),
                                     ('an executable type', {'name': 'x.html', 'media_type': 'text/html', 'content': b'x'}, 'artifact_type_refused'),
                                     ('an oversized file', {'name': 'x.md', 'media_type': 'text/plain', 'content': b'x' * 1_000_001}, 'artifact_too_large')):
            try:
                await publish(db, store, scope, operation_id=str(uuid4()), **options)
                check(f'{label} is refused', code, 'published', False)
            except ToolFailed as error:
                check(f'{label} is refused', code, str(error), str(error) == code)

        # Cross-workspace denial. The service key is held by the API alone.
        status, body = rest('GET', f'/rest/v1/artifacts?id=eq.{published.artifact_id}&select=id,sha256', TOKEN_A)
        check('a member sees the metadata', '1 row', status, status == 200 and len(json.loads(body)) == 1)
        status, body = rest('GET', f'/rest/v1/artifacts?id=eq.{published.artifact_id}&select=id', TOKEN_B)
        check('another workspace sees no metadata', 'no rows', body[:40], status == 200 and json.loads(body) == [])
        status, _ = rest('GET', '/rest/v1/artifacts?select=object_path', TOKEN_A)
        check('a member cannot read the storage path column', 'a 4xx refusal', status, 400 <= status < 500)
        status, _ = rest('GET', f'/storage/v1/object/authenticated/{BUCKET}/{row[0]}', TOKEN_B)
        check('another workspace cannot fetch the object', 'a 4xx refusal', status, 400 <= status < 500)
        try:
            await read_artifact(db, store, OTHER, UUID(published.artifact_id))
            check('reading through the wrong workspace gives nothing', 'artifact_not_found', 'bytes', False)
        except ArtifactUnavailable as error:
            check('reading through the wrong workspace gives nothing', 'artifact_not_found', error.code, error.code == 'artifact_not_found')
        try:
            await store.get('../../etc/passwd')
            check('the storage adapter refuses an unscoped path', 'refused', 'requested', False)
        except ValueError:
            check('the storage adapter refuses an unscoped path', 'refused', 'refused', True)

        # Interruption: nothing is assumed about what committed.
        scope = await scope_for()
        before_upload = 'b' * 64
        try:
            await publish(db, Failing(store, 'before_upload'), scope, operation_id=before_upload, name='never.md', media_type='text/plain', content=b'never')
        except Interrupted:
            pass
        after_upload = 'c' * 64
        try:
            await publish(db, Failing(store, 'after_upload'), scope, operation_id=after_upload, name='uploaded.md', media_type='text/plain', content=b'uploaded')
        except Interrupted:
            pass
        check('both interruptions leave staged rows, which members cannot see', 'staged, staged', (await status_of(before_upload), await status_of(after_upload)), await status_of(before_upload) == 'staged' and await status_of(after_upload) == 'staged')
        status, body = rest('GET', f'/rest/v1/artifacts?run_id=eq.{scope.run_id}&select=id', TOKEN_A)
        check('a staged artifact is not visible as delivered', 'no rows', body[:40], json.loads(body) == [])
        orphan = f'{WORKSPACE}/{scope.run_id}/orphan.md'
        await store.put(orphan, b'nobody knows me', 'text/plain')
        report = await reconcile_run(db, store, WORKSPACE, scope.run_id)
        check('recovery publishes the object it can verify', "['uploaded.md']", report.published, report.published == ('uploaded.md',) and await status_of(after_upload) == 'published')
        check('and reports what it cannot deliver', "['never.md'], failed", report.incomplete, report.incomplete == ('never.md',) and await status_of(before_upload) == 'failed' and not report.complete)
        check('and removes the orphan upload', 'removed', report.orphans_removed, report.orphans_removed == (orphan,) and await store.get(orphan) is None)
        repeat = await reconcile_run(db, store, WORKSPACE, scope.run_id)
        check('reconciling again changes nothing', 'nothing new', repeat, not repeat.published and not repeat.incomplete and not repeat.orphans_removed)

        # A wrong object never publishes, and an altered one stops being served.
        scope = await scope_for()
        wrong = 'd' * 64
        await store.put(f'{WORKSPACE}/{scope.run_id}/{wrong}-wrong.md', b'other bytes', 'text/plain')
        try:
            await publish(db, store, scope, operation_id=wrong, name='wrong.md', media_type='text/plain', content=b'right bytes')
            check('an existing object with other bytes is not accepted', 'artifact_hash_mismatch', 'published', False)
        except ToolFailed as error:
            check('an existing object with other bytes is not accepted', 'artifact_hash_mismatch, failed', (str(error), await status_of(wrong)), str(error) == 'artifact_hash_mismatch' and await status_of(wrong) == 'failed')
        lost = 'e' * 64
        gone = await publish(db, store, scope, operation_id=lost, name='gone.md', media_type='text/plain', content=b'gone soon')
        tampered_op = 'f' * 64
        tampered = await publish(db, store, scope, operation_id=tampered_op, name='tampered.md', media_type='text/plain', content=b'original')
        tampered_path = f'{WORKSPACE}/{scope.run_id}/{tampered_op}-tampered.md'
        await store.remove(tampered_path)
        await store.put(tampered_path, b'altered', 'text/plain')
        result['tampered_id'] = tampered.artifact_id
        try:
            await read_artifact(db, store, WORKSPACE, UUID(tampered.artifact_id))
            check('an altered object is not served', 'artifact_missing', 'bytes', False)
        except ArtifactUnavailable as error:
            check('an altered object is not served', 'artifact_missing', error.code, error.code == 'artifact_missing')
        await store.remove(f'{WORKSPACE}/{scope.run_id}/{lost}-gone.md')
        result['gone_id'] = gone.artifact_id
        report = await reconcile_run(db, store, WORKSPACE, scope.run_id)
        check('recovery finds published objects that are gone or altered', 'both missing', report.missing, set(report.missing) == {'gone.md', 'tampered.md'} and not report.complete)
        event = await value("select payload ->> 'type' from public.run_events where run_id = %s order by sequence desc limit 1", scope.run_id)
        check('and records that in the event log', 'artifact.missing', event, event == 'artifact.missing')

        # A lost lease: the upload exists, the publication doesn't, and recovery can finish it.
        scope = await scope_for()
        fenced = '1' * 64
        stale = ToolScope(scope.workspace_id, scope.run_id, scope.generation + 1, scope.tools, scope.paths)
        try:
            await publish(db, store, stale, operation_id=fenced, name='fenced.md', media_type='text/plain', content=b'fenced')
            check('a stale worker cannot publish', 'lease lost', 'published', False)
        except LeaseLost:
            check('a stale worker cannot publish', 'lease lost, staged', await status_of(fenced), await status_of(fenced) == 'staged')

        # Through the gateway, including a replay that finds an unfinished operation.
        registry = ToolRegistry()
        registry.register(SAVE_ARTIFACT)
        registry.register(publish_tool(store))
        gateway = ToolGateway(registry)
        scope = await scope_for()
        saved = await gateway.execute(db, scope, 'save_artifact', {'path': 'outputs/final.md', 'content': 'final'})
        arguments = {'path': 'outputs/final.md', 'version': saved.output['version']}
        out = await gateway.execute(db, scope, 'publish_artifact', {'path': '/etc/passwd', 'version': 1})
        check('the tool honors the path grant', 'resource_not_granted', out.code, out.code == 'resource_not_granted')
        out = await gateway.execute(db, scope, 'publish_artifact', {'path': 'outputs/none.md', 'version': 1})
        check('a file that was never saved cannot be published', 'file_not_found', out.code, out.code == 'file_not_found')
        interrupted = ToolRegistry()
        interrupted.register(SAVE_ARTIFACT)
        interrupted.register(publish_tool(Failing(store, 'after_upload')))
        out = await ToolGateway(interrupted).execute(db, scope, 'publish_artifact', arguments)
        check('an interrupted publish reports an unknown outcome', 'unknown', out.outcome.value, out.outcome.value == 'unknown')
        rows = await value('select count(*) from public.artifacts where run_id = %s', scope.run_id)
        out = await gateway.execute(db, scope, 'publish_artifact', arguments)
        again_rows = await value('select count(*) from public.artifacts where run_id = %s', scope.run_id)
        check('replaying it finishes the same operation', 'succeeded, 1 row', (out.outcome.value, again_rows), out.outcome.value == 'succeeded' and rows == 1 and again_rows == 1)
        repeat = await gateway.execute(db, scope, 'publish_artifact', arguments)
        check('and a later repeat reuses the receipt', 'replayed, same id', repeat.replayed, repeat.replayed and repeat.output['artifact_id'] == out.output['artifact_id'])

        # read_artifact (Decision 0034 A1, A2): a published text artifact of the run's workspace, by its ID, through
        # the gateway. The image is arranged: the table takes any media type, and its bytes still match their hash.
        readers = ToolRegistry()
        readers.register(read_tool(store))
        reader = ToolGateway(readers)

        async def read_as(workspace: UUID, artifact_id: object, **paging: int) -> Any:
            claimed = await scope_for(workspace)
            granted = ToolScope(claimed.workspace_id, claimed.run_id, claimed.generation, {'read_artifact': 1})
            return await reader.execute(db, granted, 'read_artifact', {'artifact_id': str(artifact_id), **paging})

        out = await read_as(WORKSPACE, published.artifact_id)
        fields = out.output or {}
        check('read_artifact returns a published text artifact of the run\'s workspace', 'report.md, text/markdown, its hash, size and bytes',
              (out.outcome.value, fields.get('name'), fields.get('media_type'), fields.get('size_bytes'), fields.get('total_lines')),
              out.outcome.value == 'succeeded' and fields.get('name') == 'report.md' and fields.get('media_type') == 'text/markdown'
              and fields.get('content') == TEXT.decode() and fields.get('sha256') == hashlib.sha256(TEXT).hexdigest()
              and fields.get('size_bytes') == len(TEXT) and fields.get('total_lines') == 2 and fields.get('truncated') is False)
        out = await read_as(WORKSPACE, published.artifact_id, offset=1, limit=1)
        check('it reads a page of lines', 'the second line, the last, so not cut', ((out.output or {}).get('content'), (out.output or {}).get('truncated')),
              (out.output or {}).get('content') == 'bytes that really exist\n' and (out.output or {}).get('truncated') is False)
        staged_id = await value('select id from public.artifacts where operation_id = %s', fenced)
        picture_scope = await scope_for()
        picture = await publish(db, store, picture_scope, operation_id='2' * 64, name='picture.md', media_type='text/plain', content=b'not text really')
        await db.execute("update public.artifacts set media_type = 'image/png' where id = %s", (picture.artifact_id,))
        for label, workspace, artifact_id, code in (
            ('a staged artifact', WORKSPACE, staged_id, 'artifact_not_found'),
            ("another workspace's run", OTHER, published.artifact_id, 'artifact_not_found'),
            ('an unknown ID', WORKSPACE, uuid4(), 'artifact_not_found'),
            ('a published image', WORKSPACE, picture.artifact_id, 'artifact_not_text'),
            ('a published artifact whose bytes are gone', WORKSPACE, gone.artifact_id, 'artifact_missing'),
        ):
            out = await read_as(workspace, artifact_id)
            check(f'read_artifact refuses {label} with no content', f'{code}, no content', (out.code, out.output),
                  out.code == code and not (out.output or {}).get('content'))

        # The real loop publishes through the same tool.
        await db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null where status <> 'done'")
        await admit_run(db, workspace_id=WORKSPACE, actor_id=uuid4(), idempotency_key=str(uuid4()), goal_text='Write the report', limit_micro_usd=1_000_000, policy=resolve_role_policy(), acceptance_criteria=('Has a summary', 'Has figures'))
        lease = await claim_next(db, worker_id='loop', lease_seconds=300)
        from goal_loop_script import Script
        model = Script(items=[calls(PLAN), calls(('save_artifact', {'path': 'outputs/loop.md', 'content': 'from the loop'})), calls(('publish_artifact', {'path': 'outputs/loop.md', 'version': 1})), say('stop')], seen=[], bound=[])
        await run_goal(db, URL, lease, model, LoopConfig(route=ROUTE, object_store=store, tool_set=tool_registry.build_registry), drive=drive_lease)
        name = await value("select name from public.artifacts where run_id = %s and status = 'published'", lease.run_id)
        result['loop_run'] = str(lease.run_id)
        check('the loop publishes through the gateway', 'loop.md', name, name == 'loop.md')
        check('the model is offered the publish tool only when storage exists', 'present', 'publish_artifact' in model.bound[0], 'publish_artifact' in model.bound[0])
    return result


try:
    output = asyncio.run(main())
    print(json.dumps({'cases': cases, **output}))
except Exception:
    print(json.dumps({'cases': cases}))
    raise
