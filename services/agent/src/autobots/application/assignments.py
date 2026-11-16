"""Synchronous specialist assignments with narrowed scope and shared budgets, PRD 8.2 and 8.3."""

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from autobots.application.experts import ExpertRefused, resolve_binding
from autobots.application.plans import load_goal, plan_view
from autobots.application.recovery import outstanding
from autobots.application.run_usage import LimitReached, RootLimits, consume, ensure_usage
from autobots.application.runs import (
    Inheritance,
    Inherited,
    RunAdmission,
    admit,
    cascade_command,
    current_status,
)
from autobots.application.sql import SqlConnection, one, optional_row, required_row
from autobots.application.tool_definitions import RuntimeUnbound, ToolContext, ToolFailed
from autobots.application.tool_gateway import hold_lease
from autobots.application.worker_leases import Lease, claim_run
from autobots.contracts.assignments import AssignmentResult, AssignSpecialist
from autobots.domain.runs import RunCommand, RunStatus
from autobots.domain.stops import GatewayCode, PassOutcome, StopCode
from autobots.domain.tools import DELEGATION_TOOL, PLAN_TOOLS
from autobots.persistence.rows import AssignmentRecordRow, DelegatingRunRow

if TYPE_CHECKING:
    # run_lifecycle imports Delegation from here, so its result type is named for the checker only.
    from autobots.application.run_lifecycle import LoopResult

# How a child is driven once claimed: the goal loop's pass, passed in by its caller (PPRD-02).
Driver = Callable[[SqlConnection, Lease], Awaitable["LoopResult"]]

TERMINAL_STATUSES = frozenset(
    {RunStatus.SUCCEEDED.value, RunStatus.FAILED.value, RunStatus.CANCELLED.value}
)
# A dead parent's child may still look owned until its lease runs out, so a claim retries this
# often, for the lease and about a second more.
CLAIM_POLL_SECONDS = 0.2
_EXTRA_CLAIM_POLLS = 5


@dataclass(frozen=True)
class Delegation:
    drive: Driver
    limits: RootLimits
    lease_seconds: float
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep


def narrowed_tools(
    parent: dict[str, int],
    offered: dict[str, int],
    requested: list[str] | None,
    depth: int,
    levels: int,
) -> dict[str, int]:
    """Intersects the Expert with the parent. A child can't receive what its parent lacks."""
    available = {
        tool: version
        for tool, version in offered.items()
        if tool in parent and tool not in PLAN_TOOLS and tool != DELEGATION_TOOL
    }
    if requested is not None:
        named = [tool for tool in requested if tool != DELEGATION_TOOL]
        if any(tool not in available for tool in named):
            raise ToolFailed(GatewayCode.SCOPE_EXPANSION_DENIED)
        available = {tool: available[tool] for tool in named}
    # N-4: a narrowed request that doesn't name delegation doesn't get it.
    wants_delegation = requested is None or DELEGATION_TOOL in requested
    can_delegate = DELEGATION_TOOL in parent and depth < levels
    if requested is not None and DELEGATION_TOOL in requested and not can_delegate:
        raise ToolFailed(GatewayCode.SCOPE_EXPANSION_DENIED)
    if can_delegate and wants_delegation:
        available[DELEGATION_TOOL] = parent[DELEGATION_TOOL]
    return {**PLAN_TOOLS, **available}


async def _create(
    connection: SqlConnection,
    context: ToolContext,
    arguments: AssignSpecialist,
    delegation: Delegation,
) -> tuple[UUID, UUID]:
    """The record is committed with the child and before any dispatch."""
    scope = context.scope
    limits = delegation.limits
    root = scope.budget_run_id
    parent = await required_row(
        connection,
        DelegatingRunRow,
        "select r.session_id, r.policy_snapshot, r.limit_micro_usd, "
        "coalesce((select a.depth from app_private.assignments a where a.child_run_id = r.id), 0) "
        "as parent_depth from public.runs r where r.id = %s",
        (scope.run_id,),
    )
    session_id, snapshot, limit, parent_depth = (
        parent.session_id,
        parent.policy_snapshot,
        parent.limit_micro_usd,
        parent.parent_depth,
    )
    depth = parent_depth + 1
    if depth > limits.child_levels:
        raise ToolFailed(GatewayCode.ASSIGNMENT_DEPTH_LIMIT)
    if session_id is None:
        raise ToolFailed(GatewayCode.ROUTE_NOT_GRANTED)
    try:
        binding = await resolve_binding(
            connection, scope.workspace_id, session_id, expert_id=UUID(arguments.expert_id)
        )
    except (ExpertRefused, ValueError):
        raise ToolFailed(GatewayCode.ROUTE_NOT_GRANTED) from None
    goal = await load_goal(connection, scope.run_id)
    tools = narrowed_tools(
        goal.allowed_tools, binding.tools, arguments.tools, depth, limits.child_levels
    )
    async with connection.transaction():
        await hold_lease(connection, scope)
        # Under the lease, so a cancel can't land between this and the child's admission unseen.
        (status,) = await one(
            connection, "select status from public.runs where id = %s for share", (scope.run_id,)
        )
        if status != RunStatus.RUNNING.value:
            raise ToolFailed(GatewayCode.PARENT_NOT_RUNNING)
        open_count, total = await one(
            connection,
            "select count(*) filter (where status = 'open'), count(*) "
            "from app_private.assignments where root_run_id = %s",
            (root,),
        )
        if open_count >= limits.outstanding_assignments:
            raise ToolFailed(GatewayCode.OUTSTANDING_ASSIGNMENTS_LIMIT)
        try:
            await consume(connection, root, "children", limits.children)
        except LimitReached:
            raise ToolFailed(GatewayCode.CHILDREN_LIMIT) from None
        namespace = f"outputs/child-{total + 1}"
        paths = (*[path for path in goal.allowed_paths if path == "inputs"], namespace)
        admitted = await admit(
            connection,
            RunAdmission(
                workspace_id=scope.workspace_id,
                actor_id=scope.run_id,
                idempotency_key=str(context.operation_id),
                goal_text=arguments.goal,
                limit_micro_usd=limit,
                origin=Inherited(
                    Inheritance(
                        parent_run_id=scope.run_id,
                        root_run_id=root,
                        snapshot=snapshot,
                        tools=tools,
                        paths=paths,
                        instructions=binding.instructions,
                        session_id=session_id,
                        expert_id=binding.expert_id,
                        version=binding.version,
                    )
                ),
                acceptance_criteria=tuple(arguments.criteria),
            ),
        )
        assignment_id = uuid4()
        await connection.execute(
            "insert into app_private.assignments (id, workspace_id, parent_run_id, child_run_id, "
            "root_run_id, operation_id, depth, expert_id, expert_version) "
            "values (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                assignment_id,
                scope.workspace_id,
                scope.run_id,
                admitted.run_id,
                root,
                context.operation_id,
                depth,
                binding.expert_id,
                binding.version,
            ),
        )
    await ensure_usage(connection, admitted.run_id)
    return assignment_id, admitted.run_id


async def _claim_child(connection: SqlConnection, child: UUID, delegation: Delegation) -> Lease:
    """A dead parent's child may still look owned for a moment, so this waits out its lease."""
    polls = int(delegation.lease_seconds * round(1 / CLAIM_POLL_SECONDS)) + _EXTRA_CLAIM_POLLS
    for _ in range(polls):
        lease = await claim_run(
            connection, child, worker_id="assignment", lease_seconds=delegation.lease_seconds
        )
        if lease is not None:
            return lease
        await delegation.sleep(CLAIM_POLL_SECONDS)
    raise ToolFailed(GatewayCode.ASSIGNMENT_BUSY)


@dataclass(frozen=True)
class ChildOutcome:
    """What a finished child leaves its assignment, each field named so none can swap with
    another (PPRD-05)."""

    outcome: str
    code: str | None
    run_status: str | None
    completed: list[str]
    remaining: list[str]


def outcome_of(result: "LoopResult") -> ChildOutcome:
    """A child's pass as its assignment's outcome. One that paused, waits on a person or was lost
    leaves the assignment open: the parent stops, and the same assignment continues later."""
    if result.run_status == RunStatus.PAUSED.value:
        raise ToolFailed(GatewayCode.ASSIGNMENT_PAUSED)
    if result.outcome == PassOutcome.LOST or result.code == StopCode.CHILDREN_SETTLING:
        raise ToolFailed(GatewayCode.ASSIGNMENT_LOST)
    if result.outcome == PassOutcome.WAITING:
        raise ToolFailed(GatewayCode.ASSIGNMENT_PAUSED)
    return ChildOutcome(
        outcome=result.outcome,
        code=result.code,
        run_status=result.run_status,
        completed=list(result.completed),
        remaining=list(result.remaining),
    )


async def _refuse_if_waiting(connection: SqlConnection, child: UUID) -> None:
    """Its job is done until a person answers, so there's nothing to claim yet."""
    (status,) = await one(connection, "select status from public.runs where id = %s", (child,))
    if status in {
        RunStatus.WAITING_INPUT.value,
        RunStatus.WAITING_APPROVAL.value,
    }:
        raise ToolFailed(GatewayCode.ASSIGNMENT_PAUSED)


async def _finished_child(connection: SqlConnection, child: UUID) -> ChildOutcome | None:
    """The outcome of a child that already ended, or None while it hasn't."""
    status, code = await one(
        connection,
        "select r.status, u.stop_reason from public.runs r "
        "left join app_private.run_usage u on u.run_id = r.id where r.id = %s",
        (child,),
    )
    if status not in TERMINAL_STATUSES:
        return None
    view = await plan_view(connection, child, await load_goal(connection, child))
    if status == RunStatus.CANCELLED.value and not str(code).startswith(StopCode.CANCELLED):
        code = StopCode.CANCELLED
    outcome = PassOutcome.SUCCEEDED if status == RunStatus.SUCCEEDED.value else PassOutcome.STOPPED
    return ChildOutcome(
        outcome=outcome,
        code=code,
        run_status=status,
        completed=list(view.completed),
        remaining=list(view.remaining),
    )


async def _close(
    connection: SqlConnection, assignment_id: UUID, child: UUID, finished: ChildOutcome
) -> AssignmentResult:
    cursor = await connection.execute(
        "select id from public.artifacts where run_id = %s and status = 'published' "
        "order by created_at",
        (child,),
    )
    artifacts = [str(item[0]) for item in await cursor.fetchall()]
    output = AssignmentResult(
        assignment_id=str(assignment_id),
        child_run_id=str(child),
        outcome=finished.outcome,
        code=finished.code,
        run_status=finished.run_status,
        completed=finished.completed,
        remaining=finished.remaining,
        artifact_ids=artifacts,
    )
    await connection.execute(
        "update app_private.assignments set status = 'finished', outcome = %s, result = %s, "
        "finished_at = now() where id = %s",
        (finished.outcome, json.dumps(output.model_dump()), assignment_id),
    )
    return output


async def _resume_if_paused(connection: SqlConnection, context: ToolContext, child: UUID) -> None:
    """Resuming a parent continues its child, unless the child's own wait is still open. The
    system resumes it, as no person asked for it (Decision 0029 F5)."""
    if await current_status(connection, child) is not RunStatus.PAUSED:
        return
    if (await outstanding(connection, child)).uncertain_calls:
        raise ToolFailed(GatewayCode.ASSIGNMENT_PAUSED)
    await cascade_command(
        connection,
        workspace_id=context.scope.workspace_id,
        run_id=child,
        command=RunCommand.RESUME,
    )


async def run_assignment(
    delegation: Delegation | None, arguments: AssignSpecialist, context: ToolContext
) -> AssignmentResult:
    """One assignment, by its operation: a replay reads the finished result and never starts a
    second specialist, a dead parent's finished child is written down, and otherwise the child
    is created or resumed, claimed and driven. With no delegation, as the catalog describes the
    tool, it refuses before any assignment or child exists (XMOD-01)."""
    if delegation is None:
        raise RuntimeUnbound
    connection = context.connection
    row = await optional_row(
        connection,
        AssignmentRecordRow,
        "select id, child_run_id, status, result from app_private.assignments "
        "where operation_id = %s",
        (context.operation_id,),
    )
    if row is not None and row.status == "finished":
        # A replayed request reads the existing result. No second specialist starts.
        return AssignmentResult.model_validate(row.result)
    if row is None:
        assignment_id, child = await _create(connection, context, arguments, delegation)
    else:
        assignment_id, child = row.id, row.child_run_id
        finished = await _finished_child(connection, child)
        if finished is not None:
            # The parent died before writing this down. Its job is done, so nothing to claim.
            return await _close(connection, assignment_id, child, finished)
        await _resume_if_paused(connection, context, child)
        await _refuse_if_waiting(connection, child)
    lease = await _claim_child(connection, child, delegation)
    result = await delegation.drive(connection, lease)
    return await _close(connection, assignment_id, child, outcome_of(result))
