"""Blockers B1, B2, B6, B8 and B9 from review round 1, on a real database through the runtime role. JSON cases."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any
from unittest.mock import patch
from uuid import UUID, uuid4

import psycopg
from autobots.application import assignments, tool_gateway
from autobots.application.approvals import (
    ARGUMENT_LIMIT,
    ApprovalRefused,
    decide,
    exceeds_review_limit,
    list_approvals,
)
from autobots.application.compaction import CompactionPolicy, offload_large
from autobots.application.experts import create_expert
from autobots.application.memory import READ_OFFLOAD
from autobots.application.plans import load_goal
from autobots.application.reconciliation import record_evidence
from autobots.application.run_lifecycle import LoopConfig, finish
from autobots.application.runs import admit_run, apply_command
from autobots.application.tool_gateway import (
    ApprovalPolicy,
    Call,
    ToolContext,
    ToolDefinition,
    ToolGateway,
    ToolRegistry,
    ToolScope,
    record_receipt,
    resolve,
)
from autobots.application.worker_leases import claim_next
from autobots.application.workflow_runner import InstanceStopped, call_tool, run_workflow
from autobots.application.workflows import create_execution, create_workflow, publish_version
from autobots.contracts.experts import ExpertConfig
from autobots.contracts.workflows import WorkflowGraph
from autobots.domain.models import resolve_role_policy
from autobots.domain.runs import Actor, RunCommand
from autobots.domain.tools import DELEGATION_TOOL, LOOP_TOOL_GRANTS, OperationClass
from autobots.operations.job_dispatch import drive_lease, process_next
from checklib import Cases, Db
from goal_loop_script import ROUTE, Script, say
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


async def pause_inside_assignment(db: Db) -> None:
    """B6 inside an agent step (PPRD-03, R-29). A person's pause lands after the tool gateway admitted
    the assignment and before the assignment's leased read of its run, which then refuses with
    parent_not_running. The step must stop without failing, so the run resumes it rather than ending
    workflow_node_failed, a failure no one can resume (SP-010), and the pass lets the paused run's
    job go (R-34). The run has no money, so its child stops at admission with no model call."""
    cases = db.cases
    expert = await create_expert(db.connection, workspace_id=db.workspace, actor_id=db.actor, idempotency_key='blocker-race-helper',
                                 name='Blocker race helper', config=ExpertConfig(tools=['calculate']))
    graph = {
        'nodes': [{'id': 'in', 'block': 'input', 'version': 1, 'config': {'type': 'string'}},
                  {'id': 'ask', 'block': 'agent', 'version': 1, 'config': {'expert_id': str(expert.id)}},
                  {'id': 'out', 'block': 'output', 'version': 1, 'config': {}}],
        'links': [{'source': 'in', 'source_port': 'value', 'target': 'ask', 'target_port': 'goal'},
                  {'source': 'ask', 'source_port': 'result', 'target': 'out', 'target_port': 'value'}],
    }
    flow = await create_workflow(db.connection, workspace_id=db.workspace, actor_id=db.actor, idempotency_key='blocker-race',
                                 name='Blocker pause inside an assignment')
    await publish_version(db.connection, workspace_id=db.workspace, actor_id=db.actor, workflow_id=flow.id, idempotency_key='blocker-race-p',
                          expected_version=0, graph=WorkflowGraph.model_validate(graph), source='user')
    execution = await create_execution(db.connection, workspace_id=db.workspace, actor_id=db.actor, workflow_id=flow.id,
                                       idempotency_key='blocker-race-e', version=1, inputs={'in': 'Work it out'})
    run = execution.run_id
    await db.connection.execute('update public.runs set limit_micro_usd = 0 where id = %s', (run,))
    config = LoopConfig(route=ROUTE, sleep=lambda _: asyncio.sleep(0))
    receipt_sql = 'select status, failure_code from app_private.tool_receipts where run_id = %s and tool_id = %s'

    async def ask() -> tuple[Any, ...] | None:
        found = await (await db.connection.execute(
            "select status, error_code from public.workflow_node_instances where execution_id = %s and instance_key = 'ask'",
            (execution.id,))).fetchone()
        return None if found is None else tuple(found)

    async def standing() -> tuple[str, int]:
        return (await db.value('select status from public.runs where id = %s', run),
                await db.value('select count(*) from app_private.assignments where parent_run_id = %s', run))

    real_binding = assignments.resolve_binding
    seen: list[tuple[str, str]] = []

    async def pause_then_bind(*args: Any, **kwargs: Any) -> Any:
        # Read before the assignment's leased transaction opens, so the pause can't wait on its lock.
        if not seen:
            seen.append((await db.value('select status from public.runs where id = %s', run), (await db.row(receipt_sql, run, DELEGATION_TOOL))[0]))
            await db.command(run, RunCommand.PAUSE, Actor.USER)
        return await real_binding(*args, **kwargs)

    lease = await db.claim(run, worker_id='b6-assignment')
    with patch.object(assignments, 'resolve_binding', pause_then_bind):
        ended = await run_workflow(db.connection, URL, lease, Script(items=[]), config, drive=drive_lease)
    cases.check('arranged: the pause lands after the gateway admitted the assignment, before its leased read',
                "once, on a running run whose receipt is started", seen, lambda found: found == [('running', 'started')])
    status, children = await standing()
    cases.check('a pause inside an assignment stops the agent step without failing it',
                'ask has no instance, run paused, receipt failed with parent_not_running, no child',
                (await ask(), status, await db.row(receipt_sql, run, DELEGATION_TOOL), children),
                lambda found: found == (None, 'paused', ('failed', 'parent_not_running'), 0))
    # A paused run refuses the step's suspension, so finish lets the job go and nobody holds the run
    # until a person resumes it (R-34).
    cases.check('the pass ends as run_not_running and lets the paused run\'s job go',
                'lost, run_not_running, job done with no owner',
                (ended.outcome, ended.code, await db.row('select status, lease_owner from app_private.run_jobs where run_id = %s', run)),
                lambda found: found == ('lost', 'run_not_running', ('done', None)))
    await db.command(run, RunCommand.RESUME, Actor.USER)
    lease = await db.claim(run, worker_id='b6-assignment-resume')
    model = Script(items=[say('never asked')])
    await run_workflow(db.connection, URL, lease, model, config, drive=drive_lease)
    status, children = await standing()
    cases.check('resumed, the step runs its assignment again and the run stays resumable',
                'ask has no instance, one child, run paused, no model call',
                (await ask(), children, status, len(model.seen)), lambda found: found == (None, 1, 'paused', 0))


async def stale_writers(db: Db) -> None:
    """B2: a stale worker can't admit an effect, and a late writer can't rewrite a receipt (SP-012).
    Re-admission that finds a success landed since its read returns it and sends nothing."""
    cases, connection = db.cases, db.connection
    sends: list[str] = []

    async def send(arguments: Note, _: ToolContext) -> Sent:
        sends.append(arguments.text)
        return Sent(delivered=True)

    async def receipt(operation: str) -> tuple[Any, ...]:
        return await db.row('select status, generation from app_private.tool_receipts where operation_id = %s', operation)

    def scope_of(lease: Any, tools: dict[str, int]) -> ToolScope:
        return ToolScope(db.workspace, lease.run_id, lease.generation, tools)

    def resolved(scope: ToolScope, text: str) -> Any:
        return resolve(gateway.registry, scope, 'send_once', {'text': text})

    effect = ToolDefinition(tool_id='send_once', version=1, description='Send.', input_model=Note, output_model=Sent, operation_class=OperationClass.REVERSIBLE_INTERNAL_WRITE, handler=send)
    gateway = ToolGateway(ToolRegistry())
    gateway.registry.register(effect)
    run = await db.admit('Blocker goal')
    first = await db.claim(run, worker_id='w1')
    await db.expire(run)
    second = await db.claim(run, worker_id='w2')
    cases.check('two workers hold two generations', 'a higher second', (first.generation, second.generation), second.generation > first.generation)
    done = await gateway.execute(connection, scope_of(second, {'send_once': 1}), 'send_once', {'text': 'hello'})
    operation = done.operation_id
    cases.check('the current owner sends once', 'succeeded, one send', (done.outcome.value, len(sends)), done.outcome.value == 'succeeded' and len(sends) == 1)
    # The state a worker wakes into after passing its check: straight to admission, with the call it resolved.
    stale_scope = scope_of(first, {'send_once': 1})
    late = await gateway.admit_effect(connection, stale_scope, resolved(stale_scope, 'hello'))
    cases.check('a worker that stalled after its check admits nothing', 'lease_lost, still one send', (late.code, len(sends)), late.code == 'lease_lost' and len(sends) == 1)
    fresh = await gateway.admit_effect(connection, stale_scope, resolved(stale_scope, 'another'))
    none = await db.value('select count(*) from app_private.tool_receipts where run_id = %s and status = %s', run, 'started')
    cases.check('and a new operation from it writes no receipt', 'lease_lost, none started, one send', (fresh.code, none, len(sends)), fresh.code == 'lease_lost' and none == 0 and len(sends) == 1)
    stale_context = ToolContext(connection, stale_scope, operation)
    await record_receipt(stale_context, operation, 'failed', None)
    status, _ = await receipt(operation)
    cases.check("a late failure can't overwrite a success", 'succeeded', status, status == 'succeeded')
    replay = await gateway.execute(connection, scope_of(second, {'send_once': 1}), 'send_once', {'text': 'hello'})
    cases.check('so the next replay reads it instead of sending again', 'replayed, one send', (replay.replayed, len(sends)), replay.replayed and len(sends) == 1)
    # An in-flight attempt by the current owner, and a stale writer behind it.
    operation_two = 'arranged-started'
    await connection.execute("insert into app_private.tool_receipts (operation_id, run_id, workspace_id, tool_id, tool_version, argument_hash, status, generation) values (%s, %s, %s, 'send_once', 1, 'x', 'started', %s)", (operation_two, run, db.workspace, second.generation))
    await record_receipt(stale_context, operation_two, 'failed', None)
    cases.check("a late failure can't end the owner's attempt", 'started', (await receipt(operation_two))[0], lambda found: found == 'started')
    await record_receipt(ToolContext(connection, scope_of(second, {}), operation_two), operation_two, 'unknown', None)
    await record_evidence(connection, workspace_id=db.workspace, run_id=run, operation_id=operation_two, actor_id=db.actor, idempotency_key=str(uuid4()), outcome='not_delivered', evidence='Checked the destination.')
    await record_receipt(stale_context, operation_two, 'succeeded', {'late': True})
    kept = await db.value('select evidence from app_private.tool_receipts where operation_id = %s', operation_two)
    cases.check("a real late success outranks a ruling that it didn't happen", 'succeeded, evidence kept', (await receipt(operation_two))[0], lambda found: found == 'succeeded' and kept is not None)
    await record_receipt(stale_context, operation_two, 'failed', None)
    cases.check("and a late failure can't undo it", 'succeeded', (await receipt(operation_two))[0], lambda found: found == 'succeeded')
    # The review's case: a person rules it wasn't delivered, and the fresh attempt delivers.
    ruled = await gateway.execute(connection, scope_of(second, {'send_once': 1}), 'send_once', {'text': 'ruled'})
    await connection.execute("update app_private.tool_receipts set status = 'unknown' where operation_id = %s", (ruled.operation_id,))
    await record_evidence(connection, workspace_id=db.workspace, run_id=run, operation_id=ruled.operation_id, actor_id=db.actor, idempotency_key=str(uuid4()), outcome='not_delivered', evidence='Checked the destination.')
    count = len(sends)
    again = await gateway.execute(connection, scope_of(second, {'send_once': 1}), 'send_once', {'text': 'ruled'})
    final = (await receipt(ruled.operation_id))[0]
    cases.check('a fresh attempt after a ruling is recorded', 'succeeded, sent once more, receipt succeeded', (again.outcome.value, len(sends) - count, final), again.outcome.value == 'succeeded' and len(sends) - count == 1 and final == 'succeeded')
    # Re-admission finding a success landed since its read: it returns that, and doesn't send.
    raced = await gateway.execute(connection, scope_of(second, {'send_once': 1}), 'send_once', {'text': 'raced'})
    await connection.execute("update app_private.tool_receipts set status = 'failed' where operation_id = %s", (raced.operation_id,))
    real_replay = tool_gateway.replay_receipt
    calls_made = 0

    async def landed_after_read(context: ToolContext, call: Call) -> Any:
        nonlocal calls_made
        calls_made += 1
        if calls_made == 1:
            # The read says failed, then a late success lands before re-admission.
            await connection.execute("update app_private.tool_receipts set status = 'succeeded', result = %s where operation_id = %s", (json.dumps({'delivered': True}), call.operation_id))
            return None
        return await real_replay(context, call)

    count = len(sends)
    with patch.object(tool_gateway, 'replay_receipt', landed_after_read):
        duplicate = await gateway.execute(connection, scope_of(second, {'send_once': 1}), 'send_once', {'text': 'raced'})
    cases.check("re-admission won't send over a success that landed after its read", 'replayed, no send', (duplicate.replayed, len(sends) - count), duplicate.replayed and len(sends) == count)


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
        approved_tool = ToolDefinition(tool_id='send_note', version=1, description='Send.', input_model=Note, output_model=Sent, operation_class=OperationClass.CONSEQUENTIAL_EXTERNAL_WRITE, handler=needs_approval, approval=ApprovalPolicy(always=True))
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

        # B2 through checklib (R-38): its cases join this check's line.
        stale = Cases()
        with stale.scenario('stale writers'):
            await stale_writers(Db(db, stale, WORKSPACE, ACTOR))
        cases.extend(stale.records)

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
            await call_tool(gateway, db, scope_of(lease, {'upload': 1}), 'upload', {'text': 'bytes'})
            stopped = 'no stop'
        except InstanceStopped as stop:
            stopped = stop.code
        check('a pause during a node stops it without failing it', 'run_not_running', stopped, stopped == 'run_not_running')
        stored = await value('select status from app_private.tool_receipts where run_id = %s', run)
        check('and the effect is on record', 'succeeded', stored, stored == 'succeeded')
        version = await value('select version from public.runs where id = %s', run)
        await apply_command(db, workspace_id=WORKSPACE, run_id=run, command=RunCommand.RESUME, actor=Actor.USER, expected_version=version)
        await db.execute("update app_private.run_jobs set lease_expires_at = clock_timestamp() - interval '1 second' where run_id = %s", (run,))
        lease = await claim_next(db, worker_id='b6-resume')
        output = await call_tool(gateway, db, scope_of(lease, {'upload': 1}), 'upload', {'text': 'bytes'})
        check('on resume the node gets its result without uploading again', 'delivered, one upload', (output, len(uploads)), output == {'delivered': True} and len(uploads) == 1)

        # B6 inside an agent step, through checklib (R-38): its cases join this check's line.
        race = Cases()
        with race.scenario('a pause inside an assignment'):
            await pause_inside_assignment(Db(db, race, WORKSPACE, ACTOR))
        cases.extend(race.records)

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
        lost = await finish(db, stale, await load_goal(db, run), 'budget_exceeded')
        untouched = (await value('select status from public.runs where id = %s', run), (await receipt('stale-open'))[0])
        check('a stale worker can not settle a cancelling run', 'lease_lost, cancelling, effect still started', (lost.code, untouched), lost.code == 'lease_lost' and untouched == ('cancelling', 'started'))
        await finish(db, owner, await load_goal(db, run), 'budget_exceeded')
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
