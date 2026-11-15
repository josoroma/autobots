"""Majors from review round 1, and the admission gate a due routine shares with a person's run (refactor
plan R-24), on a real database through the runtime role. JSON cases through checklib. No model call."""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import sys
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import psycopg
from autobots.adapters.loop_middleware import LoopMiddleware, LoopStopped
from autobots.application import operations as operations_module
from autobots.application import routines as routines_module
from autobots.application.approvals import decide, list_approvals
from autobots.application.assignments import Delegation, assign_tool
from autobots.application.experts import create_expert, create_session, resolve_binding
from autobots.application.goal_loop import LoopResult, _scope_guidance
from autobots.application.memory import SEARCH_MEMORY, MemoryRefused, search, store_memory
from autobots.application.operations import database_conditions
from autobots.application.plans import load_goal
from autobots.application.readiness import (
    ReadinessSettings,
    first_blocking,
    installation_conditions,
)
from autobots.application.reconciliation import (
    has_unresolvable_effect,
    record_evidence,
    unknown_operations,
)
from autobots.application.recovery import outstanding
from autobots.application.retention import RetentionPolicy, apply_retention, write_policy
from autobots.application.routines import _admit as routine_admit
from autobots.application.routines import create_routine, evaluate_routines
from autobots.application.run_usage import RootLimits
from autobots.application.runs import Inheritance, admit_run, apply_command
from autobots.application.tool_gateway import (
    ApprovalPolicy,
    NotDelivered,
    ToolContext,
    ToolDefinition,
    ToolFailed,
    ToolGateway,
    ToolRegistry,
    ToolScope,
)
from autobots.application.worker_leases import claim_next, claim_run, is_held
from autobots.application.workflows import (
    create_execution,
    create_workflow,
    publish_version,
    read_execution,
)
from autobots.contracts.assignments import AssignSpecialist
from autobots.contracts.experts import ExpertConfig, SessionExpert
from autobots.contracts.operations import RetentionSettings
from autobots.contracts.routines import RoutineConfig, RoutineTarget
from autobots.contracts.workflows import WorkflowGraph
from autobots.domain.models import resolve_role_policy
from autobots.domain.runs import Actor, RunCommand
from autobots.domain.tools import DELEGATION_TOOL, OperationClass
from autobots.operations import worker as worker_module
from checklib import Cases, Db, OnePool, run_check
from goal_loop_script import ROUTE
from pydantic import BaseModel

URL = os.environ['AUTOBOTS_DATABASE_URL']
WORKSPACE = UUID(sys.argv[1])
ACTOR = uuid4()


class Note(BaseModel):
    text: str


class Sent(BaseModel):
    delivered: bool


async def effects_and_assignments(db: Any, cases: Cases) -> None:
    check = cases.check

    async def value(sql: str, *values: object) -> Any:
        return (await (await db.execute(sql, values)).fetchone())[0]

    async def clear() -> None:
        await db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null where status <> 'done'")

    async def admit(**options: Any) -> UUID:
        return (await admit_run(db, workspace_id=WORKSPACE, actor_id=ACTOR, idempotency_key=str(uuid4()), goal_text='A major', limit_micro_usd=1_000_000, policy=resolve_role_policy(), **options)).run_id

    async def command(run: UUID, which: RunCommand) -> Any:
        version = await value('select version from public.runs where id = %s', run)
        return await apply_command(db, workspace_id=WORKSPACE, run_id=run, command=which, actor=Actor.USER, expected_version=version)

    def scope_of(lease: Any, tools: dict[str, int]) -> ToolScope:
        return ToolScope(WORKSPACE, lease.run_id, lease.generation, tools)

    sends: list[str] = []

    async def send(arguments: Note, _: ToolContext) -> Sent:
        sends.append(arguments.text)
        return Sent(delivered=True)

    # M1: the cancel lands during the readback, which then says not delivered.
    cancel_during_readback: list[UUID] = []

    async def not_delivered(_: Note, __: ToolContext) -> Sent:
        await command(cancel_during_readback[0], RunCommand.CANCEL)
        raise NotDelivered

    effect = ToolDefinition(tool_id='send_once', version=1, description='Send.', input_model=Note, output_model=Sent, operation_class=OperationClass.REVERSIBLE_INTERNAL_WRITE, handler=send, reconcile=not_delivered)
    gateway = ToolGateway(ToolRegistry())
    gateway.registry.register(effect)
    await clear()
    run = await admit()
    cancel_during_readback.append(run)
    lease = await claim_next(db, worker_id='m1')
    done = await gateway.execute(db, scope_of(lease, {'send_once': 1}), 'send_once', {'text': 'first'})
    await db.execute("update app_private.tool_receipts set status = 'unknown' where operation_id = %s", (done.operation_id,))
    count = len(sends)
    stopped = await gateway._effect(db, scope_of(lease, {'send_once': 1}), effect, Note(text='first'))
    check('a cancel during the readback stops the resend', 'run_not_running, nothing sent', (stopped.code, len(sends) - count), stopped.code == 'run_not_running' and len(sends) == count)

    async def hangs(_: Note, __: ToolContext) -> Sent:
        await asyncio.sleep(60)
        return Sent(delivered=True)

    hanging = ToolDefinition(tool_id='hang', version=1, description='Hang.', input_model=Note, output_model=Sent, operation_class=OperationClass.REVERSIBLE_INTERNAL_WRITE, handler=send, reconcile=hangs, timeout_seconds=0.2)
    gateway = ToolGateway(ToolRegistry())
    gateway.registry.register(hanging)
    await clear()
    run = await admit()
    lease = await claim_next(db, worker_id='m1-hang')
    done = await gateway.execute(db, scope_of(lease, {'hang': 1}), 'hang', {'text': 'x'})
    await db.execute("update app_private.tool_receipts set status = 'unknown' where operation_id = %s", (done.operation_id,))
    resumed = await asyncio.wait_for(gateway.execute(db, scope_of(lease, {'hang': 1}), 'hang', {'text': 'x'}), 5)
    check('a hung readback is bounded and stays unknown', 'outcome_unknown', resumed.code, resumed.code == 'outcome_unknown')

    # M2: an approval lapses, and a confirmed failure uses it up.
    attempts: list[str] = []

    async def fails(arguments: Note, _: ToolContext) -> Sent:
        attempts.append(arguments.text)
        raise ToolFailed('destination_refused')

    gated = ToolDefinition(tool_id='gated', version=1, description='Send.', input_model=Note, output_model=Sent, operation_class=OperationClass.CONSEQUENTIAL_EXTERNAL_WRITE, handler=fails, approval=ApprovalPolicy(always=True))
    gateway = ToolGateway(ToolRegistry())
    gateway.registry.register(gated)

    async def approved_run(text: str) -> tuple[UUID, Any, Any]:
        await clear()
        run = await admit()
        lease = await claim_next(db, worker_id='m2')
        asked = await gateway.execute(db, scope_of(lease, {'gated': 1}), 'gated', {'text': text})
        assert asked.code == 'approval_pending', asked.code
        row = next(item for item in await list_approvals(db, WORKSPACE, 'pending') if item['run_id'] == run)
        await decide(db, workspace_id=WORKSPACE, actor_id=ACTOR, approval_id=row['id'], idempotency_key=str(uuid4()), decision='approve', argument_hash=row['argument_hash'])
        await db.execute("update app_private.run_jobs set status = 'queued', available_at = clock_timestamp() where run_id = %s", (run,))
        lease = await claim_run(db, run, worker_id='m2-after')
        return run, lease, row

    run, lease, row = await approved_run('lapses')
    await db.execute("update public.approval_requests set expires_at = clock_timestamp() - interval '1 second' where id = %s", (row['id'],))
    late = await gateway.execute(db, scope_of(lease, {'gated': 1}), 'gated', {'text': 'lapses'})
    asked_again = await value('select status from public.approval_requests where id = %s', row['id'])
    check('an unused approval past its time asks a person again', 'approval_pending, nothing attempted', (late.code, asked_again, attempts), late.code == 'approval_pending' and asked_again == 'pending' and not attempts)

    # The blocker from the second review: what already happened is read back, whatever the date.
    delivered: list[str] = []

    async def delivers(arguments: Note, _: ToolContext) -> Sent:
        delivered.append(arguments.text)
        return Sent(delivered=True)

    done_tool = ToolDefinition(tool_id='gated_ok', version=1, description='Send.', input_model=Note, output_model=Sent, operation_class=OperationClass.CONSEQUENTIAL_EXTERNAL_WRITE, handler=delivers, approval=ApprovalPolicy(always=True))
    gateway.registry.register(done_tool)
    await clear()
    run = await admit()
    lease = await claim_next(db, worker_id='replay')
    await gateway.execute(db, scope_of(lease, {'gated_ok': 1}), 'gated_ok', {'text': 'sent once'})
    row = next(item for item in await list_approvals(db, WORKSPACE, 'pending') if item['run_id'] == run)
    await decide(db, workspace_id=WORKSPACE, actor_id=ACTOR, approval_id=row['id'], idempotency_key=str(uuid4()), decision='approve', argument_hash=row['argument_hash'])
    await db.execute("update app_private.run_jobs set status = 'queued', available_at = clock_timestamp() where run_id = %s", (run,))
    lease = await claim_run(db, run, worker_id='replay-2')
    sent = await gateway.execute(db, scope_of(lease, {'gated_ok': 1}), 'gated_ok', {'text': 'sent once'})
    await db.execute("update public.approval_requests set expires_at = clock_timestamp() - interval '1 second' where id = %s", (row['id'],))
    replayed = await gateway.execute(db, scope_of(lease, {'gated_ok': 1}), 'gated_ok', {'text': 'sent once'})
    check('a replay past the approval time returns the delivered result', 'succeeded, replayed, one delivery', (sent.outcome.value, replayed.outcome.value, replayed.replayed, len(delivered)), replayed.outcome.value == 'succeeded' and replayed.replayed and len(delivered) == 1)

    run, lease, row = await approved_run('used up')
    first = await gateway.execute(db, scope_of(lease, {'gated': 1}), 'gated', {'text': 'used up'})
    second = await gateway.execute(db, scope_of(lease, {'gated': 1}), 'gated', {'text': 'used up'})
    check('one confirmed failure uses the approval up', 'destination_refused, then approval_consumed, one attempt', (first.code, second.code, len(attempts)), first.code == 'destination_refused' and second.code == 'approval_consumed' and len(attempts) == 1)

    # M4 and M5: a parent, a child and a grandchild.
    await clear()
    expert = await create_expert(db, workspace_id=WORKSPACE, actor_id=ACTOR, idempotency_key=str(uuid4()), name=f'Major {uuid4().hex[:6]}', config=ExpertConfig(tools=['calculate'], instructions='Work.'))
    session = await create_session(db, workspace_id=WORKSPACE, actor_id=ACTOR, idempotency_key=str(uuid4()), kind='coordinator', experts=[SessionExpert(expert_id=expert.id)])
    binding = await resolve_binding(db, WORKSPACE, session.id, expert_id=expert.id)
    root = await admit(binding=binding)
    snapshot = await value('select policy_snapshot from public.runs where id = %s', root)

    async def child_of(parent: UUID) -> UUID:
        child = (await admit_run(db, workspace_id=WORKSPACE, actor_id=ACTOR, idempotency_key=str(uuid4()), goal_text='Part', limit_micro_usd=1_000_000, inherit=Inheritance(parent_run_id=parent, root_run_id=root, snapshot=snapshot, tools={'calculate': 1}, paths=('outputs/child-1',), instructions='', session_id=session.id, expert_id=binding.expert_id, version=binding.version))).run_id
        await db.execute('insert into app_private.assignments (id, workspace_id, parent_run_id, child_run_id, root_run_id, operation_id, depth, expert_id, expert_version) values (%s, %s, %s, %s, %s, %s, 1, %s, %s)', (uuid4(), WORKSPACE, parent, child, root, str(uuid4()), binding.expert_id, binding.version))
        return child

    child = await child_of(root)
    grandchild = await child_of(child)
    await db.execute("insert into app_private.tool_receipts (operation_id, run_id, workspace_id, tool_id, tool_version, argument_hash, status, generation, can_readback) values (%s, %s, %s, 'send_once', 1, 'x', 'unknown', 0, false)", (f'm4-{grandchild}', grandchild, WORKSPACE))
    left = await outstanding(db, root)
    listed = await unknown_operations(db, root)
    check("a parent counts a descendant's unknown effect", '1 effect, listed, and it blocks resume', (left.unknown_effects, len(listed), await has_unresolvable_effect(db, root)), left.unknown_effects == 1 and len(listed) == 1 and await has_unresolvable_effect(db, root))
    settled = await record_evidence(db, workspace_id=WORKSPACE, run_id=root, operation_id=f'm4-{grandchild}', actor_id=ACTOR, idempotency_key=str(uuid4()), outcome='not_delivered', evidence='Checked.')
    check("and a person can settle it from the parent's page", 'failed, none left', (settled, (await outstanding(db, root)).unknown_effects), settled == 'failed' and (await outstanding(db, root)).unknown_effects == 0)

    await db.execute("update public.runs set status = 'running' where id in (%s, %s, %s)", (root, child, grandchild))
    await db.execute("update app_private.run_jobs set status = 'done' where run_id = %s", (root,))
    lease = await claim_run(db, grandchild, worker_id='m5', lease_seconds=60)
    await db.execute("update public.runs set status = 'running' where id = %s", (grandchild,))
    guard = LoopMiddleware(db, ToolScope(WORKSPACE, grandchild, lease.generation, {'calculate': 1}, root_run_id=root, parent_run_id=child), RootLimits(), ROUTE)
    await guard._guard()
    await db.execute("update public.runs set status = 'paused' where id = %s", (root,))
    try:
        await guard._guard()
        outcome = 'allowed'
    except LoopStopped as stopped_error:
        outcome = str(stopped_error)
    check('pausing the root stops a grandchild whose parent is still running', 'parent_not_running', outcome, outcome == 'parent_not_running')
    await db.execute("update public.runs set status = 'cancelled' where id in (%s, %s, %s)", (root, child, grandchild))

    # M3: a child waiting for a person keeps its assignment open and pauses the parent.
    await clear()
    parent = await admit(binding=binding)
    snapshot = await value('select policy_snapshot from public.runs where id = %s', parent)
    root = parent
    waiting_child = await child_of(parent)
    lease = await claim_next(db, worker_id='m3')
    operation = await value('select operation_id from app_private.assignments where child_run_id = %s', waiting_child)

    async def waits(_: Any, child_lease: Any) -> LoopResult:
        return LoopResult('waiting', 'approval_pending', 'waiting_approval', None, (), (), (), {})

    tool = assign_tool(Delegation(waits, RootLimits(), 30, asyncio.sleep))
    context = ToolContext(db, ToolScope(WORKSPACE, parent, lease.generation, {DELEGATION_TOOL: 1}, root_run_id=parent), operation)
    try:
        await tool.handler(AssignSpecialist(expert_id=str(expert.id), goal='Part'), context)
        raised = 'closed'
    except ToolFailed as error:
        raised = str(error)
    state = await value('select status from app_private.assignments where child_run_id = %s', waiting_child)
    check('a child waiting for a person pauses its parent, and stays assigned', 'assignment_paused, open', (raised, state), raised == 'assignment_paused' and state == 'open')
    drives = 0

    async def counts(_: Any, child_lease: Any) -> LoopResult:
        nonlocal drives
        drives += 1
        return LoopResult('waiting', 'approval_pending', 'waiting_approval', None, (), (), (), {})

    await db.execute("update public.runs set status = 'waiting_approval' where id = %s", (waiting_child,))
    try:
        await assign_tool(Delegation(counts, RootLimits(), 30, asyncio.sleep)).handler(AssignSpecialist(expert_id=str(expert.id), goal='Part'), context)
        raised = 'closed'
    except ToolFailed as error:
        raised = str(error)
    check('a replay does not spin on a child still waiting', 'assignment_paused, no drive', (raised, drives), raised == 'assignment_paused' and drives == 0)

    # M7: a live model has to be told what it can reach.
    goal = await load_goal(db, parent)
    guidance = await _scope_guidance(db, parent, goal)
    check('a coordinator is told which Experts it can assign', 'the name and id', guidance[:160], str(expert.id) in guidance and expert.name in guidance)
    goal = await load_goal(db, waiting_child)
    guidance = await _scope_guidance(db, waiting_child, goal)
    check('a child is told where it may write', 'its namespace', guidance[:120], 'outputs/child-1' in guidance)
    await clear()
    _ = json


class Down:
    async def remove(self, path: str) -> None:
        raise RuntimeError('storage is down')

    async def ping(self) -> None:
        raise RuntimeError('storage is down')


async def retention_and_readiness(db: Any, cases: Cases) -> None:
    check = cases.check

    async def value(sql: str, *values: object) -> Any:
        return (await (await db.execute(sql, values)).fetchone())[0]

    async def terminal(status: str = 'succeeded', days: int = 90) -> UUID:
        run = uuid4()
        await db.execute("insert into public.runs (id, workspace_id, limit_micro_usd, status, updated_at) values (%s, %s, 1, %s, now() - make_interval(days => %s))", (run, WORKSPACE, status, days))
        return run

    other_workspace = UUID(sys.argv[2])
    await write_policy(db, other_workspace, ACTOR, RetentionPolicy(run_days=30, receipt_days=30))

    # M9: on a connection like the API's, rows are durable before bytes are touched.
    run = uuid4()
    await db.execute("insert into public.runs (id, workspace_id, limit_micro_usd, status, updated_at) values (%s, %s, 1, 'succeeded', now() - interval '90 days')", (run, other_workspace))
    artifact = uuid4()
    await db.execute("insert into public.artifacts (id, workspace_id, run_id, operation_id, name, object_path, media_type, size_bytes, sha256, status) values (%s, %s, %s, %s, 'a', %s, 'text/plain', 1, %s, 'published')", (artifact, other_workspace, run, str(uuid4()), f'{other_workspace}/{run}/a', '0' * 64))
    async with await psycopg.AsyncConnection.connect(URL) as pooled_like:
        check('the arrangement matches the API connection', 'not autocommit', pooled_like.autocommit, not pooled_like.autocommit)

        class CrashesOnRemove:
            async def remove(self, path: str) -> None:
                raise SystemExit('crashed while removing bytes')

        try:
            await apply_retention(pooled_like, CrashesOnRemove(), other_workspace)
        except SystemExit:
            await pooled_like.rollback()
    state = await value('select status from public.artifacts where id = %s', artifact)
    purged = await value('select content_purged_at is not null from public.runs where id = %s', run)
    check('a crash removing bytes keeps the purge on record', 'expired, purged', (state, purged), state == 'expired' and purged is True)

    # M10: a key lasts as long as its run's content, and through anything unresolved.
    run = await terminal(days=10)
    finished_late = str(uuid4())
    await db.execute("insert into app_private.idempotency_receipts (workspace_id, actor_id, operation, target, idempotency_key, request_hash, result, created_at) values (%s, %s, 'run.admit', %s, %s, 'x', '{}', now() - interval '100 days')", (WORKSPACE, ACTOR, str(run), finished_late))
    unresolved = await terminal()
    await db.execute("insert into app_private.tool_receipts (operation_id, run_id, workspace_id, tool_id, tool_version, argument_hash, status, generation) values (%s, %s, %s, 't', 1, 'x', 'unknown', 0)", (f'm10-{unresolved}', unresolved, WORKSPACE))
    held_key = str(uuid4())
    await db.execute("insert into app_private.idempotency_receipts (workspace_id, actor_id, operation, target, idempotency_key, request_hash, result, created_at) values (%s, %s, 'run.admit', %s, %s, 'x', '{}', now() - interval '100 days')", (WORKSPACE, ACTOR, str(unresolved), held_key))
    removed = await value("select app_private.expire_idempotency_receipts(%s, now() - interval '30 days')", WORKSPACE)
    kept = await value('select count(*) from app_private.idempotency_receipts where idempotency_key = any(%s)', [finished_late, held_key])
    check('a key outlives a recently finished run, and an unresolved effect', 'both kept', (removed, kept), kept == 2)
    try:
        RetentionSettings(receipt_days=1)
        accepted = 'accepted'
    except ValueError:
        accepted = 'refused'
    check('keys can\'t expire while content is kept for good', 'refused', accepted, accepted == 'refused')

    # M11: cancelling closes what the run was waiting on, and refused runs don't block the rest.
    run = (await admit_run(db, workspace_id=WORKSPACE, actor_id=ACTOR, idempotency_key=str(uuid4()), goal_text='Waits', limit_micro_usd=1_000_000, policy=resolve_role_policy())).run_id
    await db.execute("update app_private.run_jobs set status = 'done' where run_id = %s", (run,))
    await db.execute("insert into app_private.run_obligations (id, run_id, kind, detail) values (%s, %s, 'input', 'x')", (uuid4(), run))
    version = await value('select version from public.runs where id = %s', run)
    await apply_command(db, workspace_id=WORKSPACE, run_id=run, command=RunCommand.CANCEL, actor=Actor.USER, expected_version=version)
    open_left = await value("select count(*) from app_private.run_obligations where run_id = %s and status = 'open'", run)
    check('cancelling closes what the run was waiting on', '0', open_left, open_left == 0)
    crowd = 'deadbeef'
    await db.execute("insert into public.runs (id, workspace_id, limit_micro_usd, status, updated_at) select gen_random_uuid(), %s, 1, 'succeeded', now() - interval '400 days' from generate_series(1, 105)", (other_workspace,))
    await db.execute("insert into app_private.tool_receipts (operation_id, run_id, workspace_id, tool_id, tool_version, argument_hash, status, generation) select %s || r.id, r.id, r.workspace_id, 't', 1, 'x', 'unknown', 0 from public.runs r where r.workspace_id = %s and r.updated_at < now() - interval '399 days'", (crowd, other_workspace))
    behind = uuid4()
    await db.execute("insert into public.runs (id, workspace_id, limit_micro_usd, status, updated_at) values (%s, %s, 1, 'succeeded', now() - interval '200 days')", (behind, other_workspace))
    report = await apply_retention(db, None, other_workspace)
    reached = await value('select content_purged_at is not null from public.runs where id = %s', behind)
    check('105 refused runs at the head do not stop a later purge', 'refused 105, the later run purged', (report.refused.get('unresolved_effect'), reached), report.refused.get('unresolved_effect') == 105 and reached is True)


class Answers(Down):
    """Storage that answers its ping and removes nothing, so only the arranged condition refuses."""

    async def ping(self) -> None:
        return None


class Held:
    """Arranged: the hold a restore leaves (scripts/local_backup.py). The runtime role may only read
    app_private.installation_holds, so this connection answers the hold's one query with a row and sends
    every other statement to the database."""

    HOLD = 'select 1 from app_private.installation_holds limit 1'

    def __init__(self, connection: Any) -> None:
        self.connection = connection

    async def execute(self, sql: str, *values: Any) -> Any:
        return await self.connection.execute('select 1' if sql == self.HOLD else sql, *values)


class Said(logging.Handler):
    """The codes the worker logged while routines wait."""

    def __init__(self) -> None:
        super().__init__(logging.DEBUG)
        self.codes: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        if record.getMessage() == 'worker.routines_waiting':
            self.codes.append(str(getattr(record, 'fields', {}).get('reason')))


# A column a newer release relies on and this database lacks, so the code is newer than the database.
NEWER_COLUMN = ('public.runs', 'column_a_newer_release_adds')
# The disk can't refuse with no minimum, so only the arranged condition does.
GATE = ReadinessSettings(data_root=Path('.'), min_free_bytes=0)


async def routines_wait_on_readiness(db: Db) -> None:
    """A due routine is admission, so the worker refuses it on the gate a person's run passes, logs the
    refusing code and keeps declared retention (LM-07, Decision 0023 E2, refactor plan R-24). Routine
    evaluation is counted instead of run, so nothing here admits a run."""
    cases = db.cases
    evaluated: list[int] = []
    real = worker_module.evaluate_routines

    async def counted(*_: Any, **__: Any) -> int:
        evaluated.append(1)
        return 0

    async def maintain(connection: Any, store: Any, settings: ReadinessSettings = GATE) -> tuple[bool, int, list[str]]:
        """One maintenance pass: what it returned, how many routine evaluations it made and the codes it logged."""
        said, logger = Said(), logging.getLogger('autobots.worker')
        evaluated.clear()
        logger.addHandler(said)
        worker_module.evaluate_routines = counted
        try:
            worked = await worker_module.maintenance_step(worker_module.no_credential, store, settings)(connection)
        finally:
            worker_module.evaluate_routines = real
            logger.removeHandler(said)
        return worked, len(evaluated), said.codes

    async def refusal(connection: Any, store: Any) -> str | None:
        """What a person's run is refused with, through the gate require_ready applies."""
        blocking = first_blocking(await installation_conditions(OnePool(connection), store, GATE))
        return None if blocking is None else blocking.code

    @contextlib.asynccontextmanager
    async def declared_window() -> AsyncIterator[UUID]:
        """A run that finished 90 days ago, under a 30-day window that ends with the block."""
        run = uuid4()
        await db.connection.execute("insert into public.runs (id, workspace_id, limit_micro_usd, status, updated_at) values (%s, %s, 1, 'succeeded', now() - interval '90 days')", (run, db.workspace))
        await write_policy(db.connection, db.workspace, db.actor, RetentionPolicy(run_days=30))
        try:
            yield run
        finally:
            await write_policy(db.connection, db.workspace, db.actor, RetentionPolicy())

    async def purged(run: UUID) -> bool:
        return bool(await db.value('select content_purged_at is not null from public.runs where id = %s', run))

    with cases.scenario('a ready install'):
        cases.check('with everything ready, the worker evaluates due routines', 'one evaluation, nothing logged',
                    await maintain(db.connection, Answers()), lambda seen: seen[1:] == (1, []))

    with cases.scenario('Storage down'):
        async with declared_window() as run:
            down = await maintain(db.connection, Down())
        cases.check('with Storage down, no routine is evaluated', 'False, 0 evaluations', down[:2], lambda seen: seen == (False, 0))
        cases.check('but declared retention still runs', 'purged', await purged(run), lambda swept: swept is True)
        cases.check('and it says why', "['storage_unreachable']", down[2], lambda codes: codes == ['storage_unreachable'])

    with cases.scenario('a held install'):
        held = Held(db.connection)
        cases.check('arranged: the hold reads as held, to the worker and to readiness', 'True, restore_hold',
                    (await is_held(held), (await database_conditions(OnePool(held)))[2].code), lambda seen: seen == (True, 'restore_hold'))
        async with declared_window() as run:
            stopped = await maintain(held, Answers())
        cases.check('with the install held, no routine is evaluated and nothing is purged', 'False, 0 evaluations, nothing logged, not purged',
                    (*stopped, await purged(run)), lambda seen: seen == (False, 0, [], False))
        cases.check("and a person's run is refused with restore_hold", 'restore_hold', await refusal(held, Answers()),
                    lambda code: code == 'restore_hold')

    with cases.scenario('the schema behind'):
        required = operations_module.REQUIRED_COLUMNS
        async with declared_window() as run:
            operations_module.REQUIRED_COLUMNS = (*required, NEWER_COLUMN)
            try:
                behind = await maintain(db.connection, Answers())
                refused = await refusal(db.connection, Answers())
            finally:
                operations_module.REQUIRED_COLUMNS = required
        cases.check('with the schema behind, no routine is evaluated', 'False, 0 evaluations', behind[:2], lambda seen: seen == (False, 0))
        cases.check('and the worker logs schema_behind', "['schema_behind']", behind[2], lambda codes: codes == ['schema_behind'])
        cases.check('but declared retention still runs with the schema behind', 'purged', await purged(run), lambda swept: swept is True)
        cases.check("and a person's run is refused with the same code", 'schema_behind', refused, lambda code: code == 'schema_behind')

    with cases.scenario('low disk'):
        low = await maintain(db.connection, Answers(), ReadinessSettings(data_root=Path('.'), min_free_bytes=2**62))
        cases.check('with low disk, no routine is evaluated, and the worker says why', "False, 0 evaluations, ['disk_low']", low,
                    lambda seen: seen == (False, 0, ['disk_low']))


async def workflows_routines_memory(db: Any, cases: Cases) -> None:
    check = cases.check

    async def value(sql: str, *values: object) -> Any:
        return (await (await db.execute(sql, values)).fetchone())[0]

    async def clear() -> None:
        await db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null where status <> 'done'")

    graph = {
        'nodes': [{'id': 'in', 'block': 'input', 'version': 1, 'config': {'type': 'string'}}, {'id': 'out', 'block': 'output', 'version': 1, 'config': {}}],
        'links': [{'source': 'in', 'source_port': 'value', 'target': 'out', 'target_port': 'value'}],
    }
    flow = await create_workflow(db, workspace_id=WORKSPACE, actor_id=ACTOR, idempotency_key=str(uuid4()), name=f'Major {uuid4().hex[:6]}')
    await publish_version(db, workspace_id=WORKSPACE, actor_id=ACTOR, workflow_id=flow.id, idempotency_key=str(uuid4()), expected_version=0, graph=WorkflowGraph.model_validate(graph), source='user')

    # M20: an execution gets the workspace's chosen model.
    # In a workspace of its own, so the browser suite's versioned settings start clean.
    chooser = uuid4()
    await db.execute("insert into public.workspaces (id, name) values (%s, 'Chooses Terra')", (chooser,))
    theirs = await create_workflow(db, workspace_id=chooser, actor_id=ACTOR, idempotency_key=str(uuid4()), name=f'Major {uuid4().hex[:6]}')
    await publish_version(db, workspace_id=chooser, actor_id=ACTOR, workflow_id=theirs.id, idempotency_key=str(uuid4()), expected_version=0, graph=WorkflowGraph.model_validate(graph), source='user')
    await db.execute("insert into app_private.model_policies (workspace_id, version, default_profile, role_overrides) values (%s, 1, 'openrouter_terra', '{}')", (chooser,))
    await clear()
    bound = await create_execution(db, workspace_id=chooser, actor_id=ACTOR, workflow_id=theirs.id, idempotency_key=str(uuid4()), version=1, inputs={'in': 'x'})
    chosen = await value("select policy_snapshot -> 'bindings' ->> 'executor' from public.runs where id = %s", bound.run_id)
    check("a workflow's run gets the workspace's model", 'openrouter_terra', chosen, chosen == 'openrouter_terra')

    # M22: a routine's limit and tools reach its workflow's run.
    await clear()
    config = RoutineConfig(target=RoutineTarget(kind='workflow', id=flow.id, version=1), trigger={'kind': 'interval', 'minutes': 60}, limit_micro_usd=500, tools=['calculate'], inputs={'in': 'x'})
    routine_id = uuid4()
    run = await routine_admit(db, WORKSPACE, routine_id, 1, config, datetime(2026, 1, 1, tzinfo=UTC))
    limit = await value('select limit_micro_usd from public.runs where id = %s', run)
    goal = await load_goal(db, run)
    check("a routine's limit and tools reach its workflow's run", '500, no save or publish tools', (limit, sorted(goal.allowed_tools)), limit == 500 and 'calculate' in goal.allowed_tools and 'save_artifact' not in goal.allowed_tools)

    # M21: the monitor reads a run that never got there as not run.
    await clear()
    idle = await create_execution(db, workspace_id=WORKSPACE, actor_id=ACTOR, workflow_id=flow.id, idempotency_key=str(uuid4()), version=1, inputs={'in': 'x'})
    version = await value('select version from public.runs where id = %s', idle.run_id)
    await apply_command(db, workspace_id=WORKSPACE, run_id=idle.run_id, command=RunCommand.CANCEL, actor=Actor.USER, expected_version=version)
    view = await read_execution(db, WORKSPACE, idle.id)
    states = {item.node_id: item.status for item in view.instances}
    check("a cancelled workflow's unreached nodes say they didn't run", 'not_run', states, set(states.values()) == {'not_run'})
    await db.execute('update public.workflow_executions set current_instance = %s where id = %s', ('in', idle.id))
    await db.execute("update public.runs set status = 'running' where id = %s", (idle.run_id,))
    states = {item.node_id: item.status for item in (await read_execution(db, WORKSPACE, idle.id)).instances}
    check('and the node in progress says so', 'in running, out waiting', states, states == {'in': 'running', 'out': 'waiting'})
    await db.execute("update public.runs set status = 'cancelled' where id = %s", (idle.run_id,))

    # M24 and M25: time only moves forward, and one bad routine doesn't stop the rest.
    await clear()
    good = await create_routine(db, workspace_id=WORKSPACE, actor_id=ACTOR, idempotency_key=str(uuid4()), name=f'Good {uuid4().hex[:6]}', config=config)
    bad_config = config.model_copy(update={'trigger': {'kind': 'interval', 'minutes': 61}})
    bad = await create_routine(db, workspace_id=WORKSPACE, actor_id=ACTOR, idempotency_key=str(uuid4()), name=f'Bad {uuid4().hex[:6]}', config=bad_config)
    await db.execute("update public.routines set evaluated_until = clock_timestamp() - interval '3 hours' where id in (%s, %s)", (good.id, bad.id))

    async def ready(_: UUID) -> str:
        return 'ready'

    real_occurrences = routines_module.occurrences

    def raises_for_one(trigger: Any, *rest: Any) -> Any:
        # Arranged: what a routine stored before the bound existed could still raise.
        if trigger['minutes'] == 61:
            raise OverflowError
        return real_occurrences(trigger, *rest)

    routines_module.occurrences = raises_for_one
    try:
        admitted = await evaluate_routines(db, ready)
    finally:
        routines_module.occurrences = real_occurrences
    moved = await value('select evaluated_until > clock_timestamp() - interval \'1 minute\' from public.routines where id = %s', good.id)
    check('a routine that raises leaves the others running', 'the good one admitted', (admitted, moved), admitted >= 1 and moved is True)
    await db.execute('update public.routines set enabled = false where id = %s', (bad.id,))
    until = await value('select evaluated_until from public.routines where id = %s', good.id)
    await evaluate_routines(db, ready, until - timedelta(hours=1))
    kept = await value('select evaluated_until from public.routines where id = %s', good.id)
    check('a slower worker cannot move a routine back in time', 'unchanged', kept == until, kept == until)
    await db.execute('update public.routines set enabled = false where id = %s', (good.id,))
    await clear()

    # M27: a run finds its own files, and memory bound to another Expert stays hidden.
    mine = (await admit_run(db, workspace_id=WORKSPACE, actor_id=ACTOR, idempotency_key=str(uuid4()), goal_text='Mine', limit_micro_usd=1_000_000, policy=resolve_role_policy())).run_id
    other = (await admit_run(db, workspace_id=WORKSPACE, actor_id=ACTOR, idempotency_key=str(uuid4()), goal_text='Other', limit_micro_usd=1_000_000, policy=resolve_role_policy())).run_id
    word = f'zebra{uuid4().hex[:8]}'
    await db.execute("insert into app_private.run_files (run_id, path, version, content, sha256, media_type, operation_id) values (%s, 'outputs/secret.md', 1, %s, 'x', 'text/markdown', %s)", (other, f'{word} in another run', str(uuid4())))
    await db.execute("insert into app_private.run_files (run_id, path, version, content, sha256, media_type, operation_id) values (%s, 'outputs/mine.md', 1, %s, 'x', 'text/markdown', %s)", (mine, f'{word} in my run', str(uuid4())))
    lease = await claim_next(db, worker_id='m27')
    gateway = ToolGateway(ToolRegistry())
    gateway.registry.register(SEARCH_MEMORY)
    expert = await create_expert(db, workspace_id=WORKSPACE, actor_id=ACTOR, idempotency_key=str(uuid4()), name=f'Other {uuid4().hex[:6]}', config=ExpertConfig(tools=['calculate'], instructions='x'))
    await store_memory(db, workspace_id=WORKSPACE, actor_id=ACTOR, title=word, content=f'{word} belongs to another Expert', source={'kind': 'test'}, expert_id=expert.id)
    await store_memory(db, workspace_id=WORKSPACE, actor_id=ACTOR, title=word, content=f'{word} is shared', source={'kind': 'test'})
    reply = await gateway.execute(db, ToolScope(WORKSPACE, lease.run_id, lease.generation, {'search_memory': 1}), 'search_memory', {'query': word})
    hits = reply.output['hits']
    paths = [hit['source'].get('path') for hit in hits if hit['kind'] == 'evidence']
    memories = [hit['snippet'] for hit in hits if hit['kind'] == 'memory']
    check("a run's search stays in its own files", 'only its own path', (lease.run_id == mine, paths), set(paths) <= {'outputs/mine.md'} and 'outputs/secret.md' not in paths)
    with_foreign_expert = 'stored'
    try:
        await store_memory(db, workspace_id=WORKSPACE, actor_id=ACTOR, title='x', content='x', source={'kind': 'test'}, expert_id=uuid4())
    except MemoryRefused as error:
        with_foreign_expert = error.code
    check('memory can only name an Expert in its own workspace', 'expert_not_found', with_foreign_expert, with_foreign_expert == 'expert_not_found')
    check("and another Expert's memory stays hidden", 'the shared item only', memories, len(memories) == 1 and 'shared' in memories[0])
    wide = await search(db, WORKSPACE, word)
    check("an owner's own search still sees everything in the workspace", 'both files and both items', len(wide), len(wide) == 4)
    await clear()


async def main(cases: Cases) -> None:
    async with Db.connect(URL, cases, WORKSPACE, ACTOR) as db:
        await workflows_routines_memory(db.connection, cases)
        await effects_and_assignments(db.connection, cases)
        await retention_and_readiness(db.connection, cases)
        await routines_wait_on_readiness(db)


run_check(main)
