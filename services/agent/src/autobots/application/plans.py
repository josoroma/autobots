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
from autobots.domain.tools import OperationClass

# What the model can fix. Each one spends the root's single repair.
PLAN_REJECTIONS = frozenset(
    {
        "plan_duplicate_task",
        "plan_unknown_dependency",
        "plan_cycle",
        "plan_out_of_scope",
        "plan_uncovered_criteria",
        "plan_drops_completed",
        "plan_changes_completed",
        "plan_reason_required",
        "plan_missing",
        "task_unknown",
        "task_dependencies_open",
        "evidence_invalid",
    }
)


class PlanRejected(Exception):
    def __init__(self, code: str, detail: str | None = None) -> None:
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
        raise PlanRejected("plan_duplicate_task")
    if any(need not in names for task in proposal.tasks for need in task.depends_on):
        raise PlanRejected("plan_unknown_dependency")
    if _has_cycle(proposal.tasks):
        raise PlanRejected("plan_cycle")
    for task in proposal.tasks:
        if any(criterion not in goal.criteria for criterion in task.criteria):
            raise PlanRejected("plan_out_of_scope", "criterion")
        if any(tool not in goal.allowed_tools for tool in task.tools):
            raise PlanRejected("plan_out_of_scope", "tool")
    covered = {criterion for task in proposal.tasks for criterion in task.criteria}
    if covered != set(goal.criteria):
        raise PlanRejected("plan_uncovered_criteria")
    if previous is None:
        return
    if not (proposal.revision_reason or "").strip():
        raise PlanRejected("plan_reason_required")
    proposed = {task.id: task for task in proposal.tasks}
    for task in previous:
        if task.id not in completed:
            continue
        if task.id not in proposed:
            raise PlanRejected("plan_drops_completed")
        if proposed[task.id] != task:
            raise PlanRejected("plan_changes_completed")


async def load_goal(connection: Any, run_id: UUID) -> GoalSpec:
    cursor = await connection.execute(
        "select spec from app_private.goal_specs where run_id = %s", (run_id,)
    )
    row = await cursor.fetchone()
    if row is None:
        raise LookupError("this run has no goal")
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


async def _evidence_exists(connection: Any, run_id: UUID, kind: str, reference: str) -> bool:
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
        except LimitReached as reached:
            raise ToolFailed(reached.code) from None
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
            raise ToolFailed("plan_missing")
        tasks = {task.id: task for task in plan[1]}
        task = tasks.get(arguments.task_id)
        if task is None:
            raise ToolFailed("task_unknown")
        done = await completed_tasks(context.connection, run_id)
        if not set(task.depends_on) <= done:
            raise ToolFailed("task_dependencies_open")
        for item in arguments.evidence:
            if not await _evidence_exists(context.connection, run_id, item.kind, item.reference):
                detail = f"{item.kind}:{reference_shape(item.reference)}"
                raise ToolFailed("evidence_invalid", detail=detail)
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
        return TaskCompleted(
            task_id=arguments.task_id,
            remaining=sorted(set(tasks) - done - {arguments.task_id}),
        )

    return (
        ToolDefinition(
            tool_id="propose_plan",
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
