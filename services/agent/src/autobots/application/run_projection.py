"""The public view of a run, SP-011. Nothing here reads checkpoints or graph state."""

import re
from typing import Any
from uuid import UUID

from pydantic import ValidationError

from autobots.application.artifacts import list_artifacts
from autobots.application.plans import latest_plan, load_goal
from autobots.application.runs import RunNotFound
from autobots.contracts.adapters import run_from_row, run_summary_from_domain
from autobots.contracts.artifacts import ArtifactSummary
from autobots.contracts.run_workspace import (
    CriterionView,
    EventPage,
    PlanSummary,
    RunWorkspace,
    TaskView,
    UsageSummary,
)
from autobots.contracts.runs import RunEvent

PAGE_SIZE = 200
MAX_TEXT = 500
# Plans and summaries are written by a model, so a key it was shown must not be displayed.
_SECRETS = re.compile(r"(sk-[A-Za-z0-9_-]{4,}|Bearer\s+[A-Za-z0-9._-]{8,}|eyJ[A-Za-z0-9_-]{10,})")
RUN_COLUMNS = (
    "id, workspace_id, parent_run_id, status, created_at, updated_at, spent_micro_usd, "
    "reserved_micro_usd, limit_micro_usd, lease_generation, checkpoint_thread_id, version"
)


def public_text(text: str) -> str:
    return _SECRETS.sub("[redacted]", text)[:MAX_TEXT]


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
    cursor = await connection.execute(
        f"select {RUN_COLUMNS}, event_sequence from public.runs "
        "where id = %s and workspace_id = %s",
        (run_id, workspace_id),
    )
    row = await cursor.fetchone()
    if row is None:
        raise RunNotFound("that run is not available")
    return row


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


async def read_workspace(connection: Any, workspace_id: UUID, run_id: UUID) -> RunWorkspace:
    row = await _require_run(connection, workspace_id, run_id)
    names = [column.strip() for column in RUN_COLUMNS.split(",")]
    summary = run_summary_from_domain(run_from_row(dict(zip(names, row[:-1], strict=True))))  # type: ignore[arg-type]
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
        cursor=row[-1],
    )
