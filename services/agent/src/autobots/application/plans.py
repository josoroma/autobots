"""The model proposes, and deterministic logic commits, SP-011 and PRD 8.1."""

import json
import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from autobots.application.run_usage import LimitReached, RootLimits, consume
from autobots.application.tool_gateway import ToolContext, ToolDefinition, ToolFailed, hold_lease
from autobots.contracts.plans import (
    CompleteTask,
    GoalSpec,
    PlanCommitted,
    PlanProposal,
    PlanTask,
    TaskCompleted,
)
from autobots.domain.stops import GatewayCode
from autobots.domain.tool_catalog import ToolGroup
from autobots.domain.tools import OperationClass


class PlanRejected(Exception):
    """What the model can fix. Each code spends the root's single repair (domain/stops.py)."""

    def __init__(self, code: GatewayCode, detail: str | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail


def _has_cycle(tasks: list[PlanTask]) -> bool:
    remaining = {task.id: set(task.depends_on) for task in tasks}
    while remaining:
        ready = [name for name, needs in remaining.items() if not needs]
        if not ready:
            return True
        for name in ready:
            del remaining[name]
        for needs in remaining.values():
            needs.difference_update(ready)
    return False


def validate_proposal(
    goal: GoalSpec,
    proposal: PlanProposal,
    previous: list[PlanTask] | None,
    completed: frozenset[str],
) -> None:
    """A plan can't widen scope, drop a criterion or rewrite what's already done."""
    names = [task.id for task in proposal.tasks]
    if len(names) != len(set(names)):
        raise PlanRejected(GatewayCode.PLAN_DUPLICATE_TASK)
    if any(need not in names for task in proposal.tasks for need in task.depends_on):
        raise PlanRejected(GatewayCode.PLAN_UNKNOWN_DEPENDENCY)
    if _has_cycle(proposal.tasks):
        raise PlanRejected(GatewayCode.PLAN_CYCLE)
    for task in proposal.tasks:
        if any(criterion not in goal.criteria for criterion in task.criteria):
            raise PlanRejected(GatewayCode.PLAN_OUT_OF_SCOPE, "criterion")
        if any(tool not in goal.allowed_tools for tool in task.tools):
            raise PlanRejected(GatewayCode.PLAN_OUT_OF_SCOPE, "tool")
    covered = {criterion for task in proposal.tasks for criterion in task.criteria}
    if covered != set(goal.criteria):
        raise PlanRejected(GatewayCode.PLAN_UNCOVERED_CRITERIA)
    if previous is None:
        return
    if not (proposal.revision_reason or "").strip():
        raise PlanRejected(GatewayCode.PLAN_REASON_REQUIRED)
    proposed = {task.id: task for task in proposal.tasks}
    for task in previous:
        if task.id not in completed:
            continue
        if task.id not in proposed:
            raise PlanRejected(GatewayCode.PLAN_DROPS_COMPLETED)
        if proposed[task.id] != task:
            raise PlanRejected(GatewayCode.PLAN_CHANGES_COMPLETED)


class GoalMissing(LookupError):
    """No goal is stored for this run. Named, so a defect while reading one isn't taken for this
    (refactor plan R-41, PRUN-13)."""


async def load_goal(connection: Any, run_id: UUID) -> GoalSpec:
    cursor = await connection.execute(
        "select spec from app_private.goal_specs where run_id = %s", (run_id,)
    )
    row = await cursor.fetchone()
    if row is None:
        raise GoalMissing("this run has no goal")
    return GoalSpec.model_validate(row[0])


async def latest_plan(connection: Any, run_id: UUID) -> tuple[int, list[PlanTask]] | None:
    cursor = await connection.execute(
        "select version, tasks from app_private.plan_versions where run_id = %s "
        "order by version desc limit 1",
        (run_id,),
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    return row[0], [PlanTask.model_validate(task) for task in row[1]]


async def completed_tasks(connection: Any, run_id: UUID) -> frozenset[str]:
    cursor = await connection.execute(
        "select task_id from app_private.plan_evidence where run_id = %s", (run_id,)
    )
    return frozenset(row[0] for row in await cursor.fetchall())


@dataclass(frozen=True)
class PlanView:
    version: int | None
    completed: tuple[str, ...]
    remaining: tuple[str, ...]
    uncovered_criteria: tuple[str, ...]

    @property
    def finished(self) -> bool:
        return self.version is not None and not self.remaining and not self.uncovered_criteria


async def plan_view(connection: Any, run_id: UUID, goal: GoalSpec) -> PlanView:
    """Decided from recorded evidence. A model saying it finished changes nothing here."""
    done = await completed_tasks(connection, run_id)
    plan = await latest_plan(connection, run_id)
    if plan is None:
        return PlanView(None, (), (), tuple(sorted(goal.criteria)))
    version, tasks = plan
    met = {criterion for task in tasks if task.id in done for criterion in task.criteria}
    return PlanView(
        version,
        tuple(task.id for task in tasks if task.id in done),
        tuple(task.id for task in tasks if task.id not in done),
        tuple(sorted(set(goal.criteria) - met)),
    )


def reference_shape(reference: str) -> str:
    """What a cited reference looks like, for diagnosis. Its form, never the model's text."""
    if reference.startswith(("outputs/", "inputs/")):
        return "run_path"
    if re.fullmatch(r"[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", reference):
        return "uuid"
    if re.fullmatch(r"[0-9a-fA-F]{64}", reference):
        return "sha256"
    return "other_path" if "/" in reference else "bare_name"


async def evidence_exists(connection: Any, run_id: UUID, kind: str, reference: str) -> bool:
    """Whether a task's evidence is on record for this run: an artifact as a file saved at that
    path, anything else as a succeeded receipt with that operation id."""
    if kind == "artifact":
        sql = "select 1 from app_private.run_files where run_id = %s and path = %s limit 1"
    else:
        sql = (
            "select 1 from app_private.tool_receipts where run_id = %s and operation_id = %s "
            "and status = 'succeeded'"
        )
    cursor = await connection.execute(sql, (run_id, reference))
    return await cursor.fetchone() is not None


def plan_tools(limits: RootLimits) -> tuple[ToolDefinition, ToolDefinition]:
    async def propose(arguments: PlanProposal, context: ToolContext) -> PlanCommitted:
        run_id = context.scope.run_id
        goal = await load_goal(context.connection, run_id)
        plan = await latest_plan(context.connection, run_id)
        done = await completed_tasks(context.connection, run_id)
        try:
            validate_proposal(goal, arguments, plan[1] if plan else None, done)
        except PlanRejected as rejected:
            raise ToolFailed(rejected.code, detail=rejected.detail) from None
        version = plan[0] + 1 if plan else 1
        try:
            async with context.connection.transaction():
                await hold_lease(context.connection, context.scope)
                if plan is not None:
                    await consume(
                        context.connection,
                        context.scope.budget_run_id,
                        "plan_revisions",
                        limits.plan_revisions,
                    )
                await context.connection.execute(
                    "insert into app_private.plan_versions (run_id, version, tasks, "
                    "revision_reason) values (%s, %s, %s, %s)",
                    (
                        run_id,
                        version,
                        json.dumps([task.model_dump() for task in arguments.tasks]),
                        arguments.revision_reason,
                    ),
                )
        except LimitReached:
            raise ToolFailed(GatewayCode.PLAN_REVISIONS_LIMIT) from None
        return PlanCommitted(version=version, tasks=[task.id for task in arguments.tasks])

    async def proposed_already(
        arguments: PlanProposal, context: ToolContext
    ) -> PlanCommitted | None:
        """A crash may have committed this exact plan. If not, the transaction left nothing."""
        plan = await latest_plan(context.connection, context.scope.run_id)
        if plan is None or plan[1] != arguments.tasks:
            return None
        return PlanCommitted(version=plan[0], tasks=[task.id for task in arguments.tasks])

    async def complete(arguments: CompleteTask, context: ToolContext) -> TaskCompleted:
        run_id = context.scope.run_id
        plan = await latest_plan(context.connection, run_id)
        if plan is None:
            raise ToolFailed(GatewayCode.PLAN_MISSING)
        tasks = {task.id: task for task in plan[1]}
        task = tasks.get(arguments.task_id)
        if task is None:
            raise ToolFailed(GatewayCode.TASK_UNKNOWN)
        done = await completed_tasks(context.connection, run_id)
        if not set(task.depends_on) <= done:
            raise ToolFailed(GatewayCode.TASK_DEPENDENCIES_OPEN)
        for item in arguments.evidence:
            if not await evidence_exists(context.connection, run_id, item.kind, item.reference):
                detail = f"{item.kind}:{reference_shape(item.reference)}"
                raise ToolFailed(GatewayCode.EVIDENCE_INVALID, detail=detail)
        async with context.connection.transaction():
            await hold_lease(context.connection, context.scope)
            await context.connection.execute(
                "insert into app_private.plan_evidence (run_id, task_id, evidence, summary) "
                "values (%s, %s, %s, %s) on conflict (run_id, task_id) do nothing",
                (
                    run_id,
                    arguments.task_id,
                    json.dumps([item.model_dump() for item in arguments.evidence]),
                    arguments.summary,
                ),
            )
            # RN-05: its finish, in database time. The first one stands, as a repeat changes
            # nothing. A task finished with no use that served it starts and finishes together.
            await context.connection.execute(
                "insert into app_private.plan_task_times "
                "(run_id, task_id, started_at, finished_at) values (%s, %s, now(), now()) "
                "on conflict (run_id, task_id) do update "
                "set finished_at = coalesce(plan_task_times.finished_at, excluded.finished_at)",
                (run_id, arguments.task_id),
            )
        return TaskCompleted(
            task_id=arguments.task_id,
            remaining=sorted(set(tasks) - done - {arguments.task_id}),
        )

    return (
        ToolDefinition(
            tool_id="propose_plan",
            title="Propose plan",
            group=ToolGroup.PLANNING,
            public_input_fields=("revision_reason",),
            public_output_fields=("version", "tasks"),
            version=1,
            description="Propose the plan for this goal, or revise it with a reason.",
            input_model=PlanProposal,
            output_model=PlanCommitted,
            operation_class=OperationClass.REVERSIBLE_INTERNAL_WRITE,
            handler=propose,
            reconcile=proposed_already,
            safe_to_repeat=True,
        ),
        ToolDefinition(
            tool_id="complete_task",
            title="Complete task",
            group=ToolGroup.PLANNING,
            public_input_fields=("task_id",),
            public_output_fields=("task_id", "remaining"),
            version=1,
            description=(
                "Mark a plan task complete, citing saved files by their exact path or tool "
                "effects by their operation_id. A reference matching neither is refused."
            ),
            input_model=CompleteTask,
            output_model=TaskCompleted,
            operation_class=OperationClass.REVERSIBLE_INTERNAL_WRITE,
            handler=complete,
            # Its insert ignores a repeat, so finishing an interrupted attempt can't double it.
            safe_to_repeat=True,
        ),
    )
