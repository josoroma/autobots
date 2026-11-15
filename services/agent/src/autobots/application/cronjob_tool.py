"""`cronjob` v1: the workspace's routines as an Automation tool, Decision 0026 and PRD-Tool-Catalog
CJ-01 to CJ-04.

One tool with seven actions, through the routine service the Routines API uses, so there is no
second scheduler and no second set of rules. `list` reads. Every other action can start or change
paid work, so the gateway holds it for a person's approval first, bound to its arguments. The tool
is granted only through an Expert, and each action stays in the run's workspace.
"""

from collections.abc import Awaitable, Callable
from typing import Any, assert_never
from uuid import UUID

from autobots.application.routines import (
    RoutineRefused,
    add_routine_version,
    create_routine,
    list_routines,
    remove_routine,
    run_routine_now,
    set_enabled,
)
from autobots.application.tool_catalog import Catalog
from autobots.application.tool_definitions import (
    ApprovalPolicy,
    ToolContext,
    ToolDefinition,
    ToolFailed,
)
from autobots.application.workflows import WorkflowRefused
from autobots.contracts.cronjob import (
    MAX_LIMIT_MICRO_USD,
    CronjobInput,
    CronjobOutput,
    CronjobRoutine,
    CronjobTask,
)
from autobots.contracts.routines import RoutineConfig, RoutineTarget
from autobots.domain.tool_catalog import ToolGroup
from autobots.domain.tools import OperationClass

CredentialCheck = Callable[[Any, UUID], Awaitable[str]]


async def _environment_check(connection: Any, workspace_id: UUID) -> str:
    """The worker's own readiness answer, so a scheduled and an asked-for occurrence agree."""
    from autobots.operations.worker import credential_check_from_environment

    return await credential_check_from_environment()(connection, workspace_id)


def routine_config(task: CronjobTask) -> RoutineConfig:
    """The Routines API's configuration, whose schedule is the task's own (Decision 0026 C5)."""
    return RoutineConfig(
        target=RoutineTarget(kind=task.target_kind, id=task.target_id, version=task.target_version),
        trigger=task.schedule,
        timezone=task.timezone,
        goal=task.goal,
        inputs=dict(task.inputs),
        tools=list(task.tools) if task.tools is not None else None,
        limit_micro_usd=task.limit_micro_usd,
    )


async def _creator(connection: Any, context: ToolContext) -> UUID:
    """C5: the person who started the run, else the workspace's owner for unattended runs."""
    cursor = await connection.execute(
        "select coalesce(r.started_by, (select m.user_id from public.workspace_members m "
        "where m.workspace_id = r.workspace_id and m.role = 'owner' order by m.user_id limit 1)) "
        "from public.runs r where r.id = %s and r.workspace_id = %s",
        (context.scope.run_id, context.scope.workspace_id),
    )
    row = await cursor.fetchone()
    if row is None or row[0] is None:
        raise ToolFailed("routine_creator_unknown")
    return UUID(str(row[0]))


def _required[T](value: T | None) -> T:
    """Each action's fields, which CronjobInput's validator already requires, narrowed for the
    type checker. A missing one is refused rather than asserted (R-11)."""
    if value is None:
        raise ToolFailed("cronjob_arguments_invalid")
    return value


def _target(arguments: CronjobInput) -> str:
    """What the approval names: the action and the routine. The schedule is in the arguments."""
    subject = arguments.name or (str(arguments.routine_id) if arguments.routine_id else "")
    return f"Routine {subject}: {arguments.action}"


def cronjob_tool(
    catalog: Catalog, credential_check: CredentialCheck | None = None
) -> ToolDefinition:
    """`catalog` is the composition's, so a run started now refuses an unavailable tool as a
    person's would (PK-02)."""
    check = credential_check or _environment_check

    async def handle(arguments: CronjobInput, context: ToolContext) -> CronjobOutput:
        connection, workspace = context.connection, context.scope.workspace_id
        # The operation id is the call's identity, so an interrupted save repeats nothing.
        key = context.operation_id or f"cronjob:{context.scope.run_id}"
        action = arguments.action
        try:
            match action:
                case "list":
                    listed = await list_routines(connection, workspace)
                    return CronjobOutput(
                        action=action,
                        status="listed",
                        routines=[
                            CronjobRoutine(
                                routine_id=item.id,
                                name=item.name,
                                enabled=item.enabled,
                                latest_version=item.latest_version,
                            )
                            for item in listed
                        ],
                    )
                case "create":
                    view = await create_routine(
                        connection,
                        workspace_id=workspace,
                        actor_id=await _creator(connection, context),
                        idempotency_key=key,
                        name=_required(arguments.name),
                        config=routine_config(_required(arguments.task)),
                        budget_cap=MAX_LIMIT_MICRO_USD,
                    )
                    return CronjobOutput(
                        action=action,
                        status="saved",
                        routine_id=view.id,
                        version=view.latest_version,
                    )
                case "update":
                    view = await add_routine_version(
                        connection,
                        workspace_id=workspace,
                        actor_id=await _creator(connection, context),
                        routine_id=_required(arguments.routine_id),
                        idempotency_key=key,
                        expected_version=_required(arguments.expected_version),
                        config=routine_config(_required(arguments.task)),
                        budget_cap=MAX_LIMIT_MICRO_USD,
                    )
                    return CronjobOutput(
                        action=action,
                        status="saved",
                        routine_id=view.id,
                        version=view.latest_version,
                    )
                case "pause" | "resume":
                    routine = _required(arguments.routine_id)
                    view = await set_enabled(connection, workspace, routine, action == "resume")
                    status = "resumed" if view.enabled else "paused"
                    return CronjobOutput(action=action, status=status, routine_id=routine)
                case "remove":
                    routine = _required(arguments.routine_id)
                    await remove_routine(connection, workspace, routine)
                    return CronjobOutput(action=action, status="removed", routine_id=routine)
                case "run":
                    routine = _required(arguments.routine_id)

                    async def ready(workspace_id: UUID) -> str:
                        return await check(connection, workspace_id)

                    status, reason, run_id = await run_routine_now(
                        connection, workspace, routine, ready, catalog=catalog
                    )
                    return CronjobOutput(
                        action=action,
                        status=status,
                        routine_id=routine,
                        run_id=run_id,
                        reason=reason,
                    )
                case _:
                    assert_never(action)
        except (RoutineRefused, WorkflowRefused) as refused:
            raise ToolFailed(refused.code) from None

    return ToolDefinition(
        tool_id="cronjob",
        version=1,
        title="Cron job",
        description=(
            "Manage this workspace's scheduled tasks (routines): list, create, update, pause, "
            "resume, run now or remove one. A task starts an Expert's goal or a published workflow "
            "version on an interval or daily at a time. Every action but list waits for a "
            "person's approval."
        ),
        input_model=CronjobInput,
        output_model=CronjobOutput,
        operation_class=OperationClass.REVERSIBLE_INTERNAL_WRITE,
        handler=handle,
        group=ToolGroup.AUTOMATION,
        approval=ApprovalPolicy(
            when=lambda arguments: arguments.action != "list",
            reason=(
                "This action can start or change scheduled work, which may spend money, so policy "
                "holds it for a person."
            ),
            resource_target=_target,
        ),
        expert_only=True,
        public_input_fields=("action", "routine_id", "name"),
        public_output_fields=("routine_id", "status", "run_id"),
        timeout_seconds=30.0,
    )
