"""Synchronous specialist assignments with narrowed scope and shared budgets, PRD 8.2 and 8.3."""

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from autobots.application.experts import ExpertRefused, resolve_binding
from autobots.application.plans import load_goal, plan_view
from autobots.application.recovery import outstanding
from autobots.application.run_usage import LimitReached, RootLimits, consume, ensure_usage
from autobots.application.runs import Inheritance, admit_run, apply_command
from autobots.application.tool_gateway import (
    ToolContext,
    ToolDefinition,
    ToolFailed,
    hold_lease,
)
from autobots.application.worker_leases import Lease, claim_run
from autobots.contracts.assignments import AssignmentResult, AssignSpecialist
from autobots.domain.runs import Actor, RunCommand, RunStatus
from autobots.domain.tool_catalog import ToolGroup
from autobots.domain.tools import DELEGATION_TOOL, PLAN_TOOLS, OperationClass

Driver = Callable[[Any, Lease], Awaitable[Any]]

TERMINAL_STATUSES = frozenset(
    {RunStatus.SUCCEEDED.value, RunStatus.FAILED.value, RunStatus.CANCELLED.value}
)


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
            raise ToolFailed("scope_expansion_denied")
        available = {tool: available[tool] for tool in named}
    # N-4: a narrowed request that doesn't name delegation doesn't get it.
    wants_delegation = requested is None or DELEGATION_TOOL in requested
    can_delegate = DELEGATION_TOOL in parent and depth < levels
    if requested is not None and DELEGATION_TOOL in requested and not can_delegate:
        raise ToolFailed("scope_expansion_denied")
    if can_delegate and wants_delegation:
        available[DELEGATION_TOOL] = parent[DELEGATION_TOOL]
    return {**PLAN_TOOLS, **available}


async def _create(
    connection: Any,
    context: ToolContext,
    arguments: AssignSpecialist,
    delegation: Delegation,
) -> tuple[UUID, UUID]:
    """The record is committed with the child and before any dispatch."""
    scope = context.scope
    limits = delegation.limits
    root = scope.budget_run_id
    cursor = await connection.execute(
        "select r.session_id, r.policy_snapshot, r.limit_micro_usd, "
        "coalesce((select a.depth from app_private.assignments a where a.child_run_id = r.id), 0) "
        "from public.runs r where r.id = %s",
        (scope.run_id,),
    )
    session_id, snapshot, limit, parent_depth = await cursor.fetchone()
    depth = parent_depth + 1
    if depth > limits.child_levels:
        raise ToolFailed("assignment_depth_limit")
    if session_id is None:
        raise ToolFailed("route_not_granted")
    try:
        binding = await resolve_binding(
            connection, scope.workspace_id, session_id, expert_id=UUID(arguments.expert_id)
        )
    except (ExpertRefused, ValueError):
        raise ToolFailed("route_not_granted") from None
    goal = await load_goal(connection, scope.run_id)
    tools = narrowed_tools(
        goal.allowed_tools, binding.tools, arguments.tools, depth, limits.child_levels
    )
    async with connection.transaction():
        await hold_lease(connection, scope)
        # Under the lease, so a cancel can't land between this and the child's admission unseen.
        cursor = await connection.execute(
            "select status from public.runs where id = %s for share", (scope.run_id,)
        )
        if (await cursor.fetchone())[0] != RunStatus.RUNNING.value:
            raise ToolFailed("parent_not_running")
        cursor = await connection.execute(
            "select count(*) filter (where status = 'open'), count(*) "
            "from app_private.assignments where root_run_id = %s",
            (root,),
        )
        open_count, total = await cursor.fetchone()
        if open_count >= limits.outstanding_assignments:
            raise ToolFailed("outstanding_assignments_limit")
        try:
            await consume(connection, root, "children", limits.children)
        except LimitReached as reached:
            raise ToolFailed(reached.code) from None
        namespace = f"outputs/child-{total + 1}"
        paths = (*[path for path in goal.allowed_paths if path == "inputs"], namespace)
        admitted = await admit_run(
            connection,
            workspace_id=scope.workspace_id,
            actor_id=scope.run_id,
            idempotency_key=str(context.operation_id),
            goal_text=arguments.goal,
            limit_micro_usd=limit,
            acceptance_criteria=tuple(arguments.criteria),
            inherit=Inheritance(
                parent_run_id=scope.run_id,
                root_run_id=root,
                snapshot=snapshot,
                tools=tools,
                paths=paths,
                instructions=binding.instructions,
                session_id=session_id,
                expert_id=binding.expert_id,
                version=binding.version,
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


async def _claim_child(connection: Any, child: UUID, delegation: Delegation) -> Lease:
    """A dead parent's child may still look owned for a moment, so this waits out its lease."""
    for _ in range(int(delegation.lease_seconds * 5) + 5):
        lease = await claim_run(
            connection, child, worker_id="assignment", lease_seconds=delegation.lease_seconds
        )
        if lease is not None:
            return lease
        await delegation.sleep(0.2)
    raise ToolFailed("assignment_busy")


def assign_tool(delegation: Delegation) -> ToolDefinition:
    async def run(arguments: AssignSpecialist, context: ToolContext) -> AssignmentResult:
        connection = context.connection
        cursor = await connection.execute(
            "select id, child_run_id, status, result from app_private.assignments "
            "where operation_id = %s",
            (context.operation_id,),
        )
        row = await cursor.fetchone()
        if row is not None and row[2] == "finished":
            # A replayed request reads the existing result. No second specialist starts.
            return AssignmentResult.model_validate(row[3])
        if row is None:
            assignment_id, child = await _create(connection, context, arguments, delegation)
        else:
            assignment_id, child = row[0], row[1]
            finished = await _finished_child(connection, child)
            if finished is not None:
                # The parent died before writing this down. Its job is done, so nothing to claim.
                return await _close(connection, assignment_id, child, *finished)
            await _resume_if_paused(connection, context, child)
            await _refuse_if_waiting(connection, child)
        lease = await _claim_child(connection, child, delegation)
        result = await delegation.drive(connection, lease)
        if result.run_status == RunStatus.PAUSED.value:
            raise ToolFailed("assignment_paused")
        if result.outcome == "lost" or result.code == "children_settling":
            raise ToolFailed("assignment_lost")
        if result.outcome == "waiting":
            raise ToolFailed("assignment_paused")
        return await _close(
            connection,
            assignment_id,
            child,
            result.outcome,
            result.code,
            result.run_status,
            list(result.completed),
            list(result.remaining),
        )

    async def _refuse_if_waiting(connection: Any, child: UUID) -> None:
        """Its job is done until a person answers, so there's nothing to claim yet."""
        cursor = await connection.execute("select status from public.runs where id = %s", (child,))
        if (await cursor.fetchone())[0] in {
            RunStatus.WAITING_INPUT.value,
            RunStatus.WAITING_APPROVAL.value,
        }:
            raise ToolFailed("assignment_paused")

    async def _finished_child(
        connection: Any, child: UUID
    ) -> tuple[str, str | None, str, list[str], list[str]] | None:
        cursor = await connection.execute(
            "select r.status, u.stop_reason from public.runs r "
            "left join app_private.run_usage u on u.run_id = r.id where r.id = %s",
            (child,),
        )
        status, code = await cursor.fetchone()
        if status not in TERMINAL_STATUSES:
            return None
        view = await plan_view(connection, child, await load_goal(connection, child))
        if status == RunStatus.CANCELLED.value and not str(code).startswith("cancelled"):
            code = "cancelled"
        outcome = "succeeded" if status == RunStatus.SUCCEEDED.value else "stopped"
        return outcome, code, status, list(view.completed), list(view.remaining)

    async def _close(
        connection: Any,
        assignment_id: UUID,
        child: UUID,
        outcome: str,
        code: str | None,
        run_status: str | None,
        completed: list[Any],
        remaining: list[Any],
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
            outcome=outcome,
            code=code,
            run_status=run_status,
            completed=completed,
            remaining=remaining,
            artifact_ids=artifacts,
        )
        await connection.execute(
            "update app_private.assignments set status = 'finished', outcome = %s, result = %s, "
            "finished_at = now() where id = %s",
            (outcome, json.dumps(output.model_dump()), assignment_id),
        )
        return output

    async def _resume_if_paused(connection: Any, context: ToolContext, child: UUID) -> None:
        """Resuming a parent continues its child, unless the child's own wait is still open."""
        cursor = await connection.execute(
            "select status, version from public.runs where id = %s", (child,)
        )
        status, version = await cursor.fetchone()
        if status != RunStatus.PAUSED.value:
            return
        if (await outstanding(connection, child)).uncertain_calls:
            raise ToolFailed("assignment_paused")
        await apply_command(
            connection,
            workspace_id=context.scope.workspace_id,
            run_id=child,
            command=RunCommand.RESUME,
            actor=Actor.USER,
            expected_version=version,
        )

    return ToolDefinition(
        tool_id=DELEGATION_TOOL,
        title="Assign specialist",
        group=ToolGroup.DELEGATION,
        public_input_fields=("expert_id",),
        public_output_fields=("assignment_id", "child_run_id", "outcome", "code"),
        version=1,
        description="Give a bounded task to an Expert in this session, and wait for its result.",
        input_model=AssignSpecialist,
        output_model=AssignmentResult,
        operation_class=OperationClass.REVERSIBLE_INTERNAL_WRITE,
        handler=run,
        timeout_seconds=delegation.limits.active_seconds,
        safe_to_repeat=True,
    )
