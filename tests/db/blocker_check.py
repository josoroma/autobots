"""Blockers B1, B2, B6, B8 and B9 from review round 1, on a real database through the runtime role. JSON cases."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any
from uuid import UUID, uuid4

import psycopg
from autobots.application.approvals import (
    ARGUMENT_LIMIT,
    ApprovalRefused,
    decide,
    exceeds_review_limit,
    list_approvals,
)
from autobots.application.compaction import CompactionPolicy, offload_large
from autobots.application.goal_loop import LoopConfig, _finish, process_next
from autobots.application.memory import READ_OFFLOAD
from autobots.application.plans import load_goal
from autobots.application.reconciliation import record_evidence
from autobots.application.runs import admit_run, apply_command
from autobots.application.tool_gateway import (
    ToolContext,
    ToolDefinition,
    ToolGateway,
    ToolRegistry,
    ToolScope,
    _record,
)
from autobots.application.worker_leases import claim_next
from autobots.application.workflow_runner import _Stop, _tool
from autobots.domain.models import resolve_role_policy
from autobots.domain.runs import Actor, RunCommand
from autobots.domain.tools import LOOP_TOOL_GRANTS, OperationClass
from goal_loop_script import ROUTE
from langchain_core.messages import ToolMessage
from pydantic import BaseModel

URL = os.environ['AUTOBOTS_DATABASE_URL']
WORKSPACE = UUID(sys.argv[1])
ACTOR = uuid4()
cases: list[dict[str, Any]] = []


def check(name: str, expected: str, observed: object, passed: bool) -> None:
    cases.append({'id': name, 'expected': expected, 'observed': str(observed), 'passed': bool(passed)})


class Note(BaseModel):
    text: str


class Sent(BaseModel):
    delivered: bool


async def main() -> None:
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        async def value(sql: str, *values: object) -> Any:
            return (await (await db.execute(sql, values)).fetchone())[0]

        async def admit() -> UUID:
            await db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null where status <> 'done'")
            return (await admit_run(db, workspace_id=WORKSPACE, actor_id=ACTOR, idempotency_key=str(uuid4()), goal_text='Blocker goal', limit_micro_usd=1_000_000, policy=resolve_role_policy())).run_id

        async def expire(run: UUID) -> None:
            await db.execute("update app_private.run_jobs set lease_expires_at = clock_timestamp() - interval '1 second' where run_id = %s", (run,))

        async def receipt(operation: str) -> tuple[str, int]:
            return await (await db.execute('select status, generation from app_private.tool_receipts where operation_id = %s', (operation,))).fetchone()

        def scope_of(lease: Any, tools: dict[str, int]) -> ToolScope:
            return ToolScope(WORKSPACE, lease.run_id, lease.generation, tools)

        # B1: what a reviewer reads is what they approve.
        async def needs_approval(_: Note, __: ToolContext) -> Sent:
            return Sent(delivered=True)
        approved_tool = ToolDefinition(tool_id='send_note', version=1, description='Send.', input_model=Note, output_model=Sent, operation_class=OperationClass.CONSEQUENTIAL_EXTERNAL_WRITE, handler=needs_approval, approval_required=True)
        gateway = ToolGateway(ToolRegistry())
        gateway.registry.register(approved_tool)
        for label, size in (('over the old 4,000 cut', 5_000), ('over the review limit', ARGUMENT_LIMIT + 1_000)):
            run = await admit()
            lease = await claim_next(db, worker_id='b1')
            text = 'x' * size + 'CONSEQUENTIAL-TAIL'
            pending = await gateway.execute(db, scope_of(lease, {'send_note': 1}), 'send_note', {'text': text})
            check(f'a proposal {label} waits for approval', 'approval_pending', pending.code, pending.code == 'approval_pending')
            rows = [row for row in await list_approvals(db, WORKSPACE, 'pending') if row['run_id'] == run]
            row = rows[0]
            if size < ARGUMENT_LIMIT:
                check('the whole proposal reaches the reviewer, tail included', 'not over the limit', exceeds_review_limit(row['arguments']), not exceeds_review_limit(row['arguments']) and 'CONSEQUENTIAL-TAIL' in row['arguments'])
            else:
                try:
                    await decide(db, workspace_id=WORKSPACE, actor_id=ACTOR, approval_id=row['id'], idempotency_key=str(uuid4()), decision='approve', argument_hash=row['argument_hash'])
                    refused = 'approved'
                except ApprovalRefused as error:
                    refused = error.code
                check('one too long to show whole cannot be approved', 'approval_too_large', refused, refused == 'approval_too_large')
                try:
                    decided = await decide(db, workspace_id=WORKSPACE, actor_id=ACTOR, approval_id=row['id'], idempotency_key=str(uuid4()), decision='reject', argument_hash=row['argument_hash'])
                    outcome = decided.status
                except ApprovalRefused as error:
                    outcome = error.code
                check('and it can still be rejected', 'not refused for its size', outcome, outcome != 'approval_too_large')

        # Left pending, for the browser suite to read.
        await admit()
        lease = await claim_next(db, worker_id='b1-page')
        await gateway.execute(db, scope_of(lease, {'send_note': 1}), 'send_note', {'text': 'y' * (ARGUMENT_LIMIT + 500)})

        # B2: a stale worker can't admit an effect, and a late writer can't rewrite a receipt.
        sends: list[str] = []

        async def send(arguments: Note, _: ToolContext) -> Sent:
            sends.append(arguments.text)
            return Sent(delivered=True)
        effect = ToolDefinition(tool_id='send_once', version=1, description='Send.', input_model=Note, output_model=Sent, operation_class=OperationClass.REVERSIBLE_INTERNAL_WRITE, handler=send)
        gateway = ToolGateway(ToolRegistry())
        gateway.registry.register(effect)
        run = await admit()
        first = await claim_next(db, worker_id='w1')
        await expire(run)
        second = await claim_next(db, worker_id='w2')
        check('two workers hold two generations', 'a higher second', (first.generation, second.generation), second.generation > first.generation)
        done = await gateway.execute(db, scope_of(second, {'send_once': 1}), 'send_once', {'text': 'hello'})
        operation = done.operation_id
        check('the current owner sends once', 'succeeded, one send', (done.outcome.value, len(sends)), done.outcome.value == 'succeeded' and len(sends) == 1)
        # The state a worker wakes into after passing its check: straight to admission.
        stale_scope = scope_of(first, {'send_once': 1})
        late = await gateway._effect(db, stale_scope, effect, Note(text='hello'))
        check('a worker that stalled after its check admits nothing', 'lease_lost, still one send', (late.code, len(sends)), late.code == 'lease_lost' and len(sends) == 1)
        fresh = await gateway._effect(db, stale_scope, effect, Note(text='another'))
        none = await value('select count(*) from app_private.tool_receipts where run_id = %s and status = %s', run, 'started')
        check('and a new operation from it writes no receipt', 'lease_lost, none started, one send', (fresh.code, none, len(sends)), fresh.code == 'lease_lost' and none == 0 and len(sends) == 1)
        stale_context = ToolContext(db, stale_scope, operation)
        await _record(stale_context, operation, 'failed', None)
        status, _ = await receipt(operation)
        check("a late failure can't overwrite a success", 'succeeded', status, status == 'succeeded')
        replay = await gateway.execute(db, scope_of(second, {'send_once': 1}), 'send_once', {'text': 'hello'})
        check('so the next replay reads it instead of sending again', 'replayed, one send', (replay.replayed, len(sends)), replay.replayed and len(sends) == 1)
        # An in-flight attempt by the current owner, and a stale writer behind it.
        operation_two = 'arranged-started'
        await db.execute("insert into app_private.tool_receipts (operation_id, run_id, workspace_id, tool_id, tool_version, argument_hash, status, generation) values (%s, %s, %s, 'send_once', 1, 'x', 'started', %s)", (operation_two, run, WORKSPACE, second.generation))
        await _record(stale_context, operation_two, 'failed', None)
        check("a late failure can't end the owner's attempt", 'started', (await receipt(operation_two))[0], (await receipt(operation_two))[0] == 'started')
        await _record(ToolContext(db, scope_of(second, {}), operation_two), operation_two, 'unknown', None)
        await record_evidence(db, workspace_id=WORKSPACE, run_id=run, operation_id=operation_two, actor_id=ACTOR, idempotency_key=str(uuid4()), outcome='not_delivered', evidence='Checked the destination.')
        await _record(stale_context, operation_two, 'succeeded', {'late': True})
        check("a real late success outranks a ruling that it didn't happen", 'succeeded, evidence kept', (await receipt(operation_two))[0], (await receipt(operation_two))[0] == 'succeeded' and await value('select evidence from app_private.tool_receipts where operation_id = %s', operation_two) is not None)
        await _record(stale_context, operation_two, 'failed', None)
        check("and a late failure can't undo it", 'succeeded', (await receipt(operation_two))[0], (await receipt(operation_two))[0] == 'succeeded')
        # The review's case: a person rules it wasn't delivered, and the fresh attempt delivers.
        ruled = await gateway.execute(db, scope_of(second, {'send_once': 1}), 'send_once', {'text': 'ruled'})
        await db.execute("update app_private.tool_receipts set status = 'unknown' where operation_id = %s", (ruled.operation_id,))
        await record_evidence(db, workspace_id=WORKSPACE, run_id=run, operation_id=ruled.operation_id, actor_id=ACTOR, idempotency_key=str(uuid4()), outcome='not_delivered', evidence='Checked the destination.')
        count = len(sends)
        again = await gateway.execute(db, scope_of(second, {'send_once': 1}), 'send_once', {'text': 'ruled'})
        final = (await receipt(ruled.operation_id))[0]
        check('a fresh attempt after a ruling is recorded', 'succeeded, sent once more, receipt succeeded', (again.outcome.value, len(sends) - count, final), again.outcome.value == 'succeeded' and len(sends) - count == 1 and final == 'succeeded')
        # Re-admission finding a success landed since its read: it returns that, and doesn't send.
        raced = await gateway.execute(db, scope_of(second, {'send_once': 1}), 'send_once', {'text': 'raced'})
        await db.execute("update app_private.tool_receipts set status = 'failed' where operation_id = %s", (raced.operation_id,))
        real_replay = ToolGateway._replay
        calls_made = 0

        async def landed_after_read(self: Any, context: Any, tool: Any, parsed: Any, operation_id: str) -> Any:
            nonlocal calls_made
            calls_made += 1
            if calls_made == 1:
                # The read says failed, then a late success lands before re-admission.
                await db.execute("update app_private.tool_receipts set status = 'succeeded', result = %s where operation_id = %s", (json.dumps({'delivered': True}), operation_id))
                return None
            return await real_replay(self, context, tool, parsed, operation_id)

        ToolGateway._replay = landed_after_read
        count = len(sends)
        try:
            duplicate = await gateway.execute(db, scope_of(second, {'send_once': 1}), 'send_once', {'text': 'raced'})
        finally:
            ToolGateway._replay = real_replay
        check("re-admission won't send over a success that landed after its read", 'replayed, no send', (duplicate.replayed, len(sends) - count), duplicate.replayed and len(sends) == count)

        # B6: a pause during a node stops it, and its result comes back from the receipt.
        run = await admit()
        lease = await claim_next(db, worker_id='b6')
        uploads: list[str] = []

        async def upload_then_pause(arguments: Note, context: ToolContext) -> Sent:
            uploads.append(arguments.text)
            version = await value('select version from public.runs where id = %s', context.scope.run_id)
            await apply_command(db, workspace_id=WORKSPACE, run_id=context.scope.run_id, command=RunCommand.PAUSE, actor=Actor.USER, expected_version=version)
            return Sent(delivered=True)
        uploader = ToolDefinition(tool_id='upload', version=1, description='Upload.', input_model=Note, output_model=Sent, operation_class=OperationClass.REVERSIBLE_INTERNAL_WRITE, handler=upload_then_pause)
        gateway = ToolGateway(ToolRegistry())
        gateway.registry.register(uploader)
        try:
            await _tool(gateway, db, scope_of(lease, {'upload': 1}), 'upload', {'text': 'bytes'})
            stopped = 'no stop'
        except _Stop as stop:
            stopped = stop.code
        check('a pause during a node stops it without failing it', 'run_not_running', stopped, stopped == 'run_not_running')
        stored = await value('select status from app_private.tool_receipts where run_id = %s', run)
        check('and the effect is on record', 'succeeded', stored, stored == 'succeeded')
        version = await value('select version from public.runs where id = %s', run)
        await apply_command(db, workspace_id=WORKSPACE, run_id=run, command=RunCommand.RESUME, actor=Actor.USER, expected_version=version)
        await db.execute("update app_private.run_jobs set lease_expires_at = clock_timestamp() - interval '1 second' where run_id = %s", (run,))
        lease = await claim_next(db, worker_id='b6-resume')
        output = await _tool(gateway, db, scope_of(lease, {'upload': 1}), 'upload', {'text': 'bytes'})
        check('on resume the node gets its result without uploading again', 'delivered, one upload', (output, len(uploads)), output == {'delivered': True} and len(uploads) == 1)

        # B8: a cancel settles even when the release can't run this work, with what it left classified.
        run = await admit()
        lease = await claim_next(db, worker_id='old-release')
        await db.execute('update public.runs set execution_contract = %s where id = %s', (json.dumps({'graph_state': 99, 'tools': {}}), run))
        await db.execute("insert into app_private.tool_receipts (operation_id, run_id, workspace_id, tool_id, tool_version, argument_hash, status, generation) values ('b8-open', %s, %s, 'send_once', 1, 'x', 'started', %s)", (run, WORKSPACE, lease.generation))
        await expire(run)
        version = await value('select version from public.runs where id = %s', run)
        await apply_command(db, workspace_id=WORKSPACE, run_id=run, command=RunCommand.CANCEL, actor=Actor.USER, expected_version=version)
        before = await value('select status from public.runs where id = %s', run)
        result = await process_next(db, URL, 'new-release', _no_model, LoopConfig(route=ROUTE))
        after = await value('select status from public.runs where id = %s', run)
        left = (await receipt('b8-open'))[0]
        check('an incompatible run being cancelled settles', 'cancelling then cancelled, its open effect unknown', (before, after, left, result.code if result else None), before == 'cancelling' and after == 'cancelled' and left == 'unknown')

        # An incompatible run the owner hasn't cancelled gets what it left classified too.
        run = await admit()
        lease = await claim_next(db, worker_id='old-release-2')
        await db.execute('update public.runs set execution_contract = %s where id = %s', (json.dumps({'graph_state': 99, 'tools': {}}), run))
        await db.execute("insert into app_private.tool_receipts (operation_id, run_id, workspace_id, tool_id, tool_version, argument_hash, status, generation) values ('b8-paused', %s, %s, 'send_once', 1, 'x', 'started', %s)", (run, WORKSPACE, lease.generation))
        await expire(run)
        result = await process_next(db, URL, 'new-release', _no_model, LoopConfig(route=ROUTE))
        check('a paused incompatible run has what it left classified', 'paused, unknown', (await value('select status from public.runs where id = %s', run), (await receipt('b8-paused'))[0]), await value('select status from public.runs where id = %s', run) == 'paused' and (await receipt('b8-paused'))[0] == 'unknown')

        # A worker that lost the run settles nothing, whatever stopped it.
        run = await admit()
        stale = await claim_next(db, worker_id='stale-finish')
        await db.execute("insert into app_private.tool_receipts (operation_id, run_id, workspace_id, tool_id, tool_version, argument_hash, status, generation) values ('stale-open', %s, %s, 'send_once', 1, 'x', 'started', %s)", (run, WORKSPACE, stale.generation))
        await expire(run)
        owner = await claim_next(db, worker_id='current-owner')
        version = await value('select version from public.runs where id = %s', run)
        await apply_command(db, workspace_id=WORKSPACE, run_id=run, command=RunCommand.CANCEL, actor=Actor.USER, expected_version=version)
        lost = await _finish(db, stale, await load_goal(db, run), 'budget_exceeded')
        untouched = (await value('select status from public.runs where id = %s', run), (await receipt('stale-open'))[0])
        check('a stale worker can not settle a cancelling run', 'lease_lost, cancelling, effect still started', (lost.code, untouched), lost.code == 'lease_lost' and untouched == ('cancelling', 'started'))
        await _finish(db, owner, await load_goal(db, run), 'budget_exceeded')
        check('the current owner can', 'cancelled, effect unknown', (await value('select status from public.runs where id = %s', run), (await receipt('stale-open'))[0]), await value('select status from public.runs where id = %s', run) == 'cancelled' and (await receipt('stale-open'))[0] == 'unknown')

        # B9: stored evidence reads back whole, in pages, through the tool a model calls.
        run = await admit()
        lease = await claim_next(db, worker_id='b9')
        long_text = ''.join(f'line {index}\n' for index in range(3_000))
        policy = CompactionPolicy()
        message = ToolMessage(content=long_text, tool_call_id='call-b9', name='read_run_file')
        view = await offload_large(db, run, [message], policy)
        pointer = json.loads(view[0].content)
        gateway = ToolGateway(ToolRegistry())
        gateway.registry.register(READ_OFFLOAD)
        scope = scope_of(lease, {'read_offload': 1})
        collected, offset, pages, rows_before = '', 0, 0, await value('select count(*) from app_private.run_offloads where run_id = %s', run)
        while offset is not None and pages < 100:
            page = await gateway.execute(db, scope, 'read_offload', {'offload_id': pointer['offloaded'], 'offset': offset})
            collected += page.output['content']
            offset = page.output['next_offset']
            pages += 1
            reply = ToolMessage(content=json.dumps(page.output), tool_call_id=f'page-{pages}', name='read_offload')
            kept = await offload_large(db, run, [reply], policy)
            if kept[0].content != reply.content:
                check('a page reaches the model as it is', 'not offloaded again', kept[0].content[:60], False)
        rows_after = await value('select count(*) from app_private.run_offloads where run_id = %s', run)
        check('a long result reads back whole, a page at a time', f'{len(long_text)} characters, in pages', f'{len(collected)} characters, {pages} pages', collected == long_text and pages > 1)
        check('and reading it stores nothing new', str(rows_before), rows_after, rows_after == rows_before)
        import hashlib
        check('its hash matches what was stored', 'equal', hashlib.sha256(collected.encode()).hexdigest() == page.output['sha256'], hashlib.sha256(collected.encode()).hexdigest() == page.output['sha256'])

        # Finding 5: a long read can't resend every page.
        replies = [ToolMessage(content='p' * 5_000, tool_call_id=f'many-{index}', name='read_offload') for index in range(5)]
        seen = await offload_large(db, run, replies, policy)
        whole = [item.content == 'p' * 5_000 for item in seen]
        check('only the latest pages stay in view', 'the last two', whole, whole == [False, False, False, True, True])

        # B10: the grant is deliberate.
        check('a run with no Expert has no proposal tool', 'absent', LOOP_TOOL_GRANTS.get('propose_improvement'), 'propose_improvement' not in LOOP_TOOL_GRANTS)
        await db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null where status <> 'done'")
    print(json.dumps({'cases': cases}))


def _no_model() -> Any:
    raise AssertionError('a model was built for a run that must not continue')


asyncio.run(main())
