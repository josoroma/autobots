"""A run's workspace view: its goal, plan, usage, verification, Expert, assignments and the roles
it froze, read from one snapshot (SP-011, PRUN-11)."""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from autobots.application.artifacts import artifact_summary, list_artifacts
from autobots.application.plans import GoalMissing, latest_plan, load_goal
from autobots.application.reconciliation import unknown_operations
from autobots.application.recovery import outstanding
from autobots.application.run_projection.shown import canonical_id, public_text
from autobots.application.run_projection.summary import require_run, summary_of
from autobots.application.runs import frozen_snapshot
from autobots.application.sql import (
    SqlConnection,
    all_rows,
    one,
    optional_row,
    snapshot,
    stored,
)
from autobots.application.tool_uses import METERED_TOOL_CALLS
from autobots.contracts.persisted import PolicySnapshot
from autobots.contracts.run_workspace import (
    ASSIGNMENT_STATUSES,
    AssignmentView,
    CriterionView,
    ExpertBinding,
    FrozenBinding,
    OutstandingSummary,
    PlanSummary,
    RunBudgets,
    RunWorkspace,
    TaskView,
    UnknownEffect,
    UsageSummary,
    UserRunCommand,
    VerificationSummary,
)
from autobots.domain.models import CONTEXT_TOKENS, MAX_OUTPUT_TOKENS, UnknownModelProfile
from autobots.domain.runs import TERMINAL, Actor, CommandRefused, RunCommand, RunStatus, next_status
from autobots.domain.tools import PLAN_TOOLS
from autobots.persistence.rows import (
    AssignmentViewRow,
    ExpertBindingRow,
    RunUsageRow,
    TaskTimeRow,
    VerificationRow,
)

# A run with no usage row yet has counted nothing.
_NO_USAGE = RunUsageRow(
    model_calls=0, tool_dispatches=0, repairs=0, plan_revisions=0, stop_reason=None
)


def _utc(value: datetime | None) -> datetime | None:
    return value.astimezone(UTC) if value is not None else None


async def plan_summary(connection: SqlConnection, run_id: UUID) -> PlanSummary | None:
    plan = await latest_plan(connection, run_id)
    if plan is None:
        return None
    version, tasks = plan
    (reason,) = await one(
        connection,
        "select revision_reason from app_private.plan_versions where run_id = %s and version = %s",
        (run_id, version),
    )
    cursor = await connection.execute(
        "select task_id, summary from app_private.plan_evidence where run_id = %s", (run_id,)
    )
    evidence: dict[str, str] = {task_id: text for task_id, text in await cursor.fetchall()}
    # RN-05's times, with the wall time measured by the database's own clock.
    times = {
        row.task_id: row
        for row in await all_rows(
            connection,
            TaskTimeRow,
            "select task_id, started_at, finished_at, "
            "round(extract(epoch from coalesce(finished_at, now()) - started_at))::bigint "
            "as wall_seconds "
            "from app_private.plan_task_times where run_id = %s",
            (run_id,),
        )
    }
    cursor = await connection.execute(
        "select task_id, tool_id from app_private.tool_uses where run_id = %s "
        "and task_id is not null and tool_id <> all(%s) order by id",
        (run_id, sorted(PLAN_TOOLS)),
    )
    used: dict[str, list[str]] = {}
    for task_id, tool_id in await cursor.fetchall():
        if tool_id not in used.setdefault(task_id, []):
            used[task_id].append(tool_id)
    order = {task.id: index for index, task in enumerate(tasks)}
    started_open = [task.id for task in tasks if task.id not in evidence and task.id in times]
    # The earliest open task that has started, by start time and then plan order.
    current = min(
        started_open, key=lambda name: (times[name].started_at, order[name]), default=None
    )

    def marker(name: str) -> Literal["done", "current", "to_do"]:
        if name in evidence:
            return "done"
        return "current" if name == current else "to_do"

    def wall(name: str) -> int | None:
        if name not in times or (name not in evidence and name != current):
            return None
        return max(int(times[name].wall_seconds), 0)

    return PlanSummary(
        version=version,
        revision_reason=public_text(reason) if reason else None,
        current_task_id=current,
        tasks=[
            TaskView(
                id=task.id,
                title=public_text(task.title),
                status="complete" if task.id in evidence else "open",
                marker=marker(task.id),
                criteria=task.criteria,
                evidence_summary=public_text(evidence[task.id]) if task.id in evidence else None,
                started_at=_utc(times[task.id].started_at) if task.id in times else None,
                finished_at=_utc(times[task.id].finished_at) if task.id in times else None,
                wall_seconds=wall(task.id),
                tools=used.get(task.id, []),
            )
            for task in tasks
        ],
    )


def verification_of(row: VerificationRow) -> VerificationSummary:
    return VerificationSummary(passed=row.passed, unmet=row.unmet, checks=row.checks)


async def verification(connection: SqlConnection, run_id: UUID) -> VerificationSummary | None:
    row = await optional_row(
        connection,
        VerificationRow,
        "select passed, unmet, checks from app_private.run_verifications where run_id = %s "
        "order by created_at desc limit 1",
        (run_id,),
    )
    return None if row is None else verification_of(row)


def assignment_of(row: AssignmentViewRow) -> AssignmentView:
    return AssignmentView(
        id=row.id,
        child_run_id=row.child_run_id,
        expert=row.expert,
        status=stored(ASSIGNMENT_STATUSES, row.status),
        outcome=row.outcome,
    )


async def assignments(connection: SqlConnection, run_id: UUID) -> list[AssignmentView]:
    rows = await all_rows(
        connection,
        AssignmentViewRow,
        "select a.id, a.child_run_id, e.name as expert, a.status, a.outcome "
        "from app_private.assignments a join public.experts e on e.id = a.expert_id "
        "where a.parent_run_id = %s order by a.created_at",
        (run_id,),
    )
    return [assignment_of(row) for row in rows]


def expert_binding_of(row: ExpertBindingRow) -> ExpertBinding:
    return ExpertBinding(
        name=row.name,
        version=row.version,
        tools=sorted(tool for tool in row.allowed_tools if tool not in PLAN_TOOLS),
        # What this run froze for the roles the Expert names. A child inherits its parent's.
        role_bindings={
            role: (row.frozen_bindings or {}).get(role, profile)
            for role, profile in (row.role_bindings or {}).items()
        },
    )


async def expert(connection: SqlConnection, run_id: UUID) -> ExpertBinding | None:
    row = await optional_row(
        connection,
        ExpertBindingRow,
        "select e.name, r.expert_version as version, g.spec -> 'allowed_tools' as allowed_tools, "
        "v.config -> 'role_bindings' as role_bindings, "
        "r.policy_snapshot -> 'bindings' as frozen_bindings "
        "from public.runs r join public.experts e on e.id = r.expert_id "
        "join app_private.goal_specs g on g.run_id = r.id "
        "join public.expert_versions v on v.expert_id = r.expert_id "
        "and v.version = r.expert_version where r.id = %s",
        (run_id,),
    )
    return None if row is None else expert_binding_of(row)


async def role_map(connection: SqlConnection, run_id: UUID) -> list[FrozenBinding]:
    """Each role as the run froze it, older snapshots included (PolicySnapshot): a profile frozen
    before routes were shows what it means now, and one since retired shows only its name."""
    try:
        frozen = await frozen_snapshot(connection, run_id)
    except UnknownModelProfile:
        # Shown as nothing bound, as `shown_snapshot` shows one.
        frozen = PolicySnapshot()
    shown: list[FrozenBinding] = []
    for role, profile in sorted(frozen.bindings.items()):
        route = frozen.routes.get(profile)
        source = frozen.source(role)
        shown.append(
            FrozenBinding(
                role=role,
                profile=profile,
                canonical_id=canonical_id(profile, frozen.routes),
                wire_id=(route.wire_id if route else "") or "unknown",
                source=None if source is None else source.value,
            )
        )
    return shown


async def metered_calls(connection: SqlConnection, run_id: UUID) -> int:
    """Counted over the run's whole root tree, as admission counts them (Decision 0017 Q4)."""
    (count,) = await one(
        connection,
        "select count(*) from app_private.tool_uses u where u.metered and u.root_run_id = "
        "(select coalesce(r.root_run_id, r.id) from public.runs r where r.id = %s)",
        (run_id,),
    )
    return int(count)


# The order the page shows them in.
_PAGE_COMMANDS: tuple[UserRunCommand, ...] = ("pause", "resume", "cancel")


def user_commands(status: RunStatus) -> list[UserRunCommand]:
    """What a person may send a run in this status: each command SP-010's next_status moves it
    with (WRUN-12). A repeated cancellation changes nothing, so it isn't offered. The command routes
    admit any member, so no role narrows this, and the writes check the status again."""
    offered: list[UserRunCommand] = []
    for command in _PAGE_COMMANDS:
        try:
            moves = next_status(status, RunCommand(command), Actor.USER) is not None
        except CommandRefused:
            moves = False
        if moves:
            offered.append(command)
    return offered


def usage_summary(usage: RunUsageRow, input_tokens: int, output_tokens: int) -> UsageSummary:
    return UsageSummary(
        model_calls=usage.model_calls,
        tool_dispatches=usage.tool_dispatches,
        repairs=usage.repairs,
        plan_revisions=usage.plan_revisions,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


async def read_workspace(
    connection: SqlConnection, workspace_id: UUID, run_id: UUID
) -> RunWorkspace:
    """Every statement reads the same snapshot, so the status and cursor agree with the plan,
    verification and counts (PRUN-11). The reads run in the order the page lists them."""
    async with snapshot(connection):
        row = await require_run(connection, workspace_id, run_id)
        try:
            goal = await load_goal(connection, run_id)
            objective: str | None = public_text(goal.objective)
            criteria = [
                CriterionView(id=name, text=public_text(text))
                for name, text in sorted(goal.criteria.items())
            ]
        except GoalMissing:
            objective, criteria = None, []
        usage = (
            await optional_row(
                connection,
                RunUsageRow,
                "select model_calls, tool_dispatches, repairs, plan_revisions, stop_reason "
                "from app_private.run_usage where run_id = %s",
                (run_id,),
            )
            or _NO_USAGE
        )
        input_tokens, output_tokens = await one(
            connection,
            "select coalesce(sum(input_tokens), 0)::bigint, "
            "coalesce(sum(output_tokens), 0)::bigint "
            "from app_private.model_invocations where run_id = %s or root_run_id = %s",
            (run_id, run_id),
        )
        artifacts = await list_artifacts(connection, workspace_id, run_id)
        left = await outstanding(connection, run_id)
        (is_workflow,) = await one(
            connection,
            "select exists (select 1 from public.workflow_executions where run_id = %s)",
            (run_id,),
        )
        plan = await plan_summary(connection, run_id)
        verified = await verification(connection, run_id)
        bound = await expert(connection, run_id)
        children = await assignments(connection, run_id)
        unknown = await unknown_operations(connection, run_id)
        roles = await role_map(connection, run_id)
        metered = await metered_calls(connection, run_id)
    summary = summary_of(row)
    return RunWorkspace(
        schema_version=1,
        run=summary,
        can_continue=(
            summary.status in TERMINAL and summary.parent_run_id is None and not is_workflow
        ),
        allowed_commands=user_commands(summary.status),
        objective=objective,
        criteria=criteria,
        plan=plan,
        artifacts=[artifact_summary(item) for item in artifacts],
        usage=usage_summary(usage, input_tokens, output_tokens),
        stop_reason=usage.stop_reason,
        verification=verified,
        expert=bound,
        assignments=children,
        unknown_operations=[
            UnknownEffect(
                operation_id=item.operation_id,
                tool_id=item.tool_id,
                tool_version=item.tool_version,
                generation=item.generation,
            )
            for item in unknown
        ],
        outstanding=OutstandingSummary(
            uncertain_calls=left.uncertain_calls,
            unknown_effects=left.unknown_effects,
            unreported_charges=left.unreported_charges,
        ),
        cursor=row.event_sequence,
        role_map=roles,
        metered_tool_calls=metered,
        metered_tool_call_limit=METERED_TOOL_CALLS,
        budgets=RunBudgets(
            context_tokens=CONTEXT_TOKENS, max_output_tokens_per_call=MAX_OUTPUT_TOKENS
        ),
    )
