"""The public view of a run, SP-011. Nothing here reads checkpoints or graph state."""

import re
from typing import Any
from uuid import UUID

from pydantic import ValidationError

from autobots.application.artifacts import list_artifacts
from autobots.application.plans import latest_plan, load_goal
from autobots.application.reconciliation import unknown_operations
from autobots.application.recovery import outstanding
from autobots.application.runs import RunNotFound
from autobots.contracts.adapters import run_from_row, run_summary_from_domain
from autobots.contracts.artifacts import ArtifactSummary
from autobots.contracts.run_workspace import (
    AssignmentView,
    CheckpointView,
    CriterionView,
    EventPage,
    ExpertBinding,
    ModelCallView,
    OutstandingSummary,
    PlanSummary,
    RunInspector,
    RunList,
    RunListItem,
    RunWorkspace,
    TaskView,
    ToolAttemptView,
    UnknownEffect,
    UsageSummary,
    VerificationSummary,
)
from autobots.contracts.runs import RunEvent, RunSummary
from autobots.domain.models import PROFILES, UnknownModelProfile, approved_profile
from autobots.domain.tools import PLAN_TOOLS

PAGE_SIZE = 200
RUN_LIST_SIZE = 100
INSPECTOR_CHECKPOINTS = 500
MAX_TEXT = 500
# Plans and summaries are written by a model, so a key it was shown must not be displayed.
_SECRETS = re.compile(
    r"((?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{4,}|Bearer\s+[A-Za-z0-9._-]{8,}|eyJ[A-Za-z0-9_-]{10,})"
)
# Spend comes from the ledger, so the public figures can't drift from what admission counted.
_NAMES = (
    "id",
    "workspace_id",
    "parent_run_id",
    "status",
    "created_at",
    "updated_at",
    "spent_micro_usd",
    "reserved_micro_usd",
    "limit_micro_usd",
    "lease_generation",
    "checkpoint_thread_id",
    "version",
)
_SELECT_RUN = (
    "select r.id, r.workspace_id, r.parent_run_id, r.status, r.created_at, r.updated_at, "
    "(select coalesce(sum(coalesce(i.charged_micro_usd, 0)), 0)::bigint "
    "from app_private.model_invocations i where i.root_run_id = r.id), "
    "(select coalesce(sum(i.reserved_micro_usd) filter (where i.status in "
    "('reserved', 'dispatched', 'uncertain') and i.reconciled_at is null), 0)::bigint "
    "from app_private.model_invocations i where i.root_run_id = r.id), "
    "r.limit_micro_usd, r.lease_generation, r.checkpoint_thread_id, r.version, r.event_sequence "
    "from public.runs r where r.id = %s and r.workspace_id = %s"
)


def public_text(text: str, *, limit: int = MAX_TEXT) -> str:
    return _SECRETS.sub("[redacted]", text)[:limit]


def project_event(run_id: UUID, sequence: int, payload: Any, occurred_at: Any) -> RunEvent | None:
    """Only what the public contract accepts. Anything else stays out, and the cursor moves on."""
    try:
        return RunEvent.model_validate(
            {
                "schema_version": 1,
                "run_id": str(run_id),
                "sequence": sequence,
                "causal_ids": [],
                "occurred_at": occurred_at.isoformat(),
                "payload": payload,
            },
            strict=False,
        )
    except ValidationError:
        return None


async def _require_run(connection: Any, workspace_id: UUID, run_id: UUID) -> Any:
    cursor = await connection.execute(_SELECT_RUN, (run_id, workspace_id))
    row = await cursor.fetchone()
    if row is None:
        raise RunNotFound("that run is not available")
    return row


def _summary(row: Any) -> RunSummary:
    return run_summary_from_domain(run_from_row(dict(zip(_NAMES, row[:-1], strict=True))))  # type: ignore[arg-type]


async def read_summary(connection: Any, workspace_id: UUID, run_id: UUID) -> RunSummary | None:
    cursor = await connection.execute(_SELECT_RUN, (run_id, workspace_id))
    row = await cursor.fetchone()
    return None if row is None else _summary(row)


async def read_events(
    connection: Any, workspace_id: UUID, run_id: UUID, *, after: int, limit: int = PAGE_SIZE
) -> EventPage:
    await _require_run(connection, workspace_id, run_id)
    cursor = await connection.execute(
        "select sequence, payload, occurred_at from public.run_events "
        "where run_id = %s and sequence > %s order by sequence limit %s",
        (run_id, after, limit),
    )
    rows = await cursor.fetchall()
    events = [
        event
        for event in (project_event(run_id, row[0], row[1], row[2]) for row in rows)
        if event is not None
    ]
    return EventPage(
        schema_version=1,
        run_id=run_id,
        events=events,
        next_cursor=rows[-1][0] if rows else after,
        gap=bool(rows) and rows[0][0] > after + 1,
    )


async def _plan_summary(connection: Any, run_id: UUID) -> PlanSummary | None:
    plan = await latest_plan(connection, run_id)
    if plan is None:
        return None
    version, tasks = plan
    cursor = await connection.execute(
        "select revision_reason from app_private.plan_versions where run_id = %s and version = %s",
        (run_id, version),
    )
    reason = (await cursor.fetchone())[0]
    cursor = await connection.execute(
        "select task_id, summary from app_private.plan_evidence where run_id = %s", (run_id,)
    )
    evidence = dict(await cursor.fetchall())
    return PlanSummary(
        version=version,
        revision_reason=public_text(reason) if reason else None,
        tasks=[
            TaskView(
                id=task.id,
                title=public_text(task.title),
                status="complete" if task.id in evidence else "open",
                criteria=task.criteria,
                evidence_summary=public_text(evidence[task.id]) if task.id in evidence else None,
            )
            for task in tasks
        ],
    )


async def _verification(connection: Any, run_id: UUID) -> VerificationSummary | None:
    cursor = await connection.execute(
        "select passed, unmet, checks from app_private.run_verifications where run_id = %s "
        "order by created_at desc limit 1",
        (run_id,),
    )
    row = await cursor.fetchone()
    return VerificationSummary(passed=row[0], unmet=row[1], checks=row[2]) if row else None


async def _assignments(connection: Any, run_id: UUID) -> list[AssignmentView]:
    cursor = await connection.execute(
        "select a.id, a.child_run_id, e.name, a.status, a.outcome "
        "from app_private.assignments a join public.experts e on e.id = a.expert_id "
        "where a.parent_run_id = %s order by a.created_at",
        (run_id,),
    )
    return [
        AssignmentView(id=row[0], child_run_id=row[1], expert=row[2], status=row[3], outcome=row[4])
        for row in await cursor.fetchall()
    ]


async def _expert(connection: Any, run_id: UUID) -> ExpertBinding | None:
    cursor = await connection.execute(
        "select e.name, r.expert_version, g.spec -> 'allowed_tools', v.config -> 'role_bindings' "
        "from public.runs r join public.experts e on e.id = r.expert_id "
        "join app_private.goal_specs g on g.run_id = r.id "
        "join public.expert_versions v on v.expert_id = r.expert_id "
        "and v.version = r.expert_version where r.id = %s",
        (run_id,),
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    return ExpertBinding(
        name=row[0],
        version=row[1],
        tools=sorted(tool for tool in row[2] if tool not in PLAN_TOOLS),
        role_bindings=row[3] or {},
    )


async def read_workspace(connection: Any, workspace_id: UUID, run_id: UUID) -> RunWorkspace:
    row = await _require_run(connection, workspace_id, run_id)
    summary = _summary(row)
    try:
        goal = await load_goal(connection, run_id)
        objective: str | None = public_text(goal.objective)
        criteria = [
            CriterionView(id=name, text=public_text(text))
            for name, text in sorted(goal.criteria.items())
        ]
    except LookupError:
        objective, criteria = None, []
    cursor = await connection.execute(
        "select model_calls, tool_dispatches, repairs, plan_revisions, stop_reason "
        "from app_private.run_usage where run_id = %s",
        (run_id,),
    )
    usage = await cursor.fetchone() or (0, 0, 0, 0, None)
    artifacts = await list_artifacts(connection, workspace_id, run_id)
    left = await outstanding(connection, run_id)
    return RunWorkspace(
        schema_version=1,
        run=summary,
        objective=objective,
        criteria=criteria,
        plan=await _plan_summary(connection, run_id),
        artifacts=[ArtifactSummary.model_validate(item) for item in artifacts],
        usage=UsageSummary(
            model_calls=usage[0],
            tool_dispatches=usage[1],
            repairs=usage[2],
            plan_revisions=usage[3],
        ),
        stop_reason=usage[4],
        verification=await _verification(connection, run_id),
        expert=await _expert(connection, run_id),
        assignments=await _assignments(connection, run_id),
        unknown_operations=[
            UnknownEffect(
                operation_id=item.operation_id, tool_id=item.tool_id, tool_version=item.tool_version
            )
            for item in await unknown_operations(connection, run_id)
        ],
        outstanding=OutstandingSummary(
            uncertain_calls=left.uncertain_calls,
            unknown_effects=left.unknown_effects,
            unreported_charges=left.unreported_charges,
        ),
        cursor=row[-1],
    )


async def read_run_list(connection: Any, workspace_id: UUID, limit: int = RUN_LIST_SIZE) -> RunList:
    """Only this workspace's, newest first. A read, so it starts nothing and needs no key."""
    cursor = await connection.execute(
        "select id, parent_run_id, status, goal_summary, created_at from public.runs "
        "where workspace_id = %s order by created_at desc, id desc limit %s",
        (workspace_id, limit + 1),
    )
    rows = await cursor.fetchall()
    return RunList(
        schema_version=1,
        runs=[
            RunListItem(
                id=row[0],
                parent_run_id=row[1],
                status=row[2],
                goal_summary=public_text(row[3]),
                created_at=row[4],
            )
            for row in rows[:limit]
        ],
        has_more=len(rows) > limit,
    )


def _canonical_id(profile: str, routes: dict[str, Any]) -> str:
    """What this run froze, then what the profile means now. A retired one keeps only its name."""
    frozen = routes.get(profile)
    if isinstance(frozen, dict) and frozen.get("canonical_id"):
        return str(frozen["canonical_id"])
    try:
        return PROFILES[approved_profile(profile)].canonical_id
    except UnknownModelProfile:
        return "unknown"


async def read_inspector(connection: Any, workspace_id: UUID, run_id: UUID) -> RunInspector:
    """Typed columns only. No checkpoint content, tool arguments or partial model output is read."""
    row = await _require_run(connection, workspace_id, run_id)
    summary = _summary(row)
    cursor = await connection.execute(
        "select goal_summary, policy_snapshot, coalesce(checkpoint_thread_id, id::text) "
        "from public.runs where id = %s",
        (run_id,),
    )
    goal_summary, snapshot, thread = await cursor.fetchone()
    routes = (snapshot or {}).get("routes") or {}
    cursor = await connection.execute(
        "select id, run_id, role, attempt, status, profile, wire_id, upstream_provider, "
        "input_tokens, output_tokens, reasoning_tokens, created_at "
        "from app_private.model_invocations where run_id = %s or root_run_id = %s "
        "order by created_at, attempt",
        (run_id, run_id),
    )
    calls = [
        ModelCallView(
            id=item[0],
            run_id=item[1],
            role=item[2],
            attempt=item[3],
            status=item[4],
            provider="openrouter",
            profile=item[5],
            canonical_id=_canonical_id(item[5], routes),
            wire_id=item[6],
            upstream_provider=item[7] or "unknown",
            input_tokens=item[8],
            output_tokens=item[9],
            reasoning_tokens=item[10],
            created_at=item[11],
        )
        for item in await cursor.fetchall()
    ]
    cursor = await connection.execute(
        "select operation_id, tool_id, tool_version, status, failure_code, created_at "
        "from app_private.tool_receipts where run_id = %s order by created_at",
        (run_id,),
    )
    attempts = [
        ToolAttemptView(
            operation_id=item[0],
            tool_id=item[1],
            tool_version=item[2],
            status=item[3],
            failure_code=item[4],
            created_at=item[5],
        )
        for item in await cursor.fetchall()
    ]
    cursor = await connection.execute(
        "select checkpoint_id, parent_checkpoint_id, (metadata ->> 'step')::integer, "
        "metadata ->> 'source' from agent_runtime.checkpoints where thread_id = %s "
        "order by checkpoint_id limit %s",
        (thread, INSPECTOR_CHECKPOINTS + 1),
    )
    rows = await cursor.fetchall()
    return RunInspector(
        schema_version=1,
        run=summary,
        goal_summary=public_text(goal_summary),
        model_calls=calls,
        tool_attempts=attempts,
        checkpoints=[
            CheckpointView(
                checkpoint_id=item[0],
                parent_checkpoint_id=item[1],
                step=item[2],
                source=item[3],
            )
            for item in rows[:INSPECTOR_CHECKPOINTS]
        ],
        checkpoints_truncated=len(rows) > INSPECTOR_CHECKPOINTS,
    )
