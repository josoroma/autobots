"""The public view of a run, SP-011. Graph state is never read: the inspector takes checkpoint
ids, steps and sources only."""

import base64
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import ValidationError

from autobots.application.artifacts import list_artifacts
from autobots.application.plans import GoalMissing, latest_plan, load_goal
from autobots.application.reconciliation import unknown_operations
from autobots.application.recovery import outstanding
from autobots.application.runs import RunNotFound
from autobots.application.tool_uses import METERED_TOOL_CALLS
from autobots.contracts.adapters import run_from_row, run_summary_from_domain
from autobots.contracts.artifacts import ArtifactSummary
from autobots.contracts.run_workspace import (
    AssignmentView,
    CheckpointView,
    CriterionView,
    EventPage,
    EvidenceView,
    ExpertBinding,
    FrozenBinding,
    ModelCallView,
    OutstandingSummary,
    PlanSummary,
    RunBudgets,
    RunGroupCounts,
    RunInspector,
    RunList,
    RunListGroup,
    RunListItem,
    RunWorkspace,
    TaskView,
    ToolAttemptView,
    UnknownEffect,
    UsageSummary,
    VerificationSummary,
)
from autobots.contracts.runs import RunEvent, RunSummary
from autobots.domain.errors import FixedRefusal, RefusalKind
from autobots.domain.models import (
    CONTEXT_TOKENS,
    MAX_OUTPUT_TOKENS,
    PROFILES,
    BindingSource,
    UnknownModelProfile,
    approved_profile,
)
from autobots.domain.runs import IN_PROGRESS, NEEDS_YOU, TERMINAL
from autobots.domain.secret_patterns import redact_shown
from autobots.domain.tools import PLAN_TOOLS

PAGE_SIZE = 200
RUN_LIST_SIZE = 100
INSPECTOR_CHECKPOINTS = 500
MAX_TEXT = 500
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
    "from app_private.model_invocations i where i.root_run_id = r.id or i.run_id = r.id), "
    "(select coalesce(sum(i.reserved_micro_usd) filter (where i.status in "
    "('reserved', 'dispatched', 'uncertain') and i.reconciled_at is null), 0)::bigint "
    "from app_private.model_invocations i where i.root_run_id = r.id or i.run_id = r.id), "
    "r.limit_micro_usd, r.lease_generation, r.checkpoint_thread_id, r.version, r.event_sequence "
    "from public.runs r where r.id = %s and r.workspace_id = %s"
)


def public_text(text: str, *, limit: int = MAX_TEXT) -> str:
    """Plans and summaries are written by a model, so a key it was shown must not be displayed."""
    return redact_shown(text)[:limit]


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
    return run_summary_from_domain(run_from_row(dict(zip(_NAMES, row[:-1], strict=True))))  # type: ignore[arg-type]  # a str that pydantic validates against the field's Literal


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


def _utc(value: Any) -> datetime | None:
    return value.astimezone(UTC) if value is not None else None


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
    # RN-05's times, with the wall time measured by the database's own clock.
    cursor = await connection.execute(
        "select task_id, started_at, finished_at, "
        "round(extract(epoch from coalesce(finished_at, now()) - started_at))::bigint "
        "from app_private.plan_task_times where run_id = %s",
        (run_id,),
    )
    times = {row[0]: row[1:] for row in await cursor.fetchall()}
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
    current = min(started_open, key=lambda name: (times[name][0], order[name]), default=None)

    def marker(name: str) -> Literal["done", "current", "to_do"]:
        if name in evidence:
            return "done"
        return "current" if name == current else "to_do"

    def wall(name: str) -> int | None:
        if name not in times or (name not in evidence and name != current):
            return None
        return max(int(times[name][2]), 0)

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
                started_at=_utc(times[task.id][0]) if task.id in times else None,
                finished_at=_utc(times[task.id][1]) if task.id in times else None,
                wall_seconds=wall(task.id),
                tools=used.get(task.id, []),
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
        "select e.name, r.expert_version, g.spec -> 'allowed_tools', v.config -> 'role_bindings', "
        "r.policy_snapshot -> 'bindings' "
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
        # What this run froze for the roles the Expert names. A child inherits its parent's.
        role_bindings={
            role: (row[4] or {}).get(role, profile) for role, profile in (row[3] or {}).items()
        },
    )


BINDING_SOURCES = frozenset(source.value for source in BindingSource)


async def _role_map(connection: Any, run_id: UUID) -> list[FrozenBinding]:
    cursor = await connection.execute(
        "select policy_snapshot from public.runs where id = %s", (run_id,)
    )
    row = await cursor.fetchone()
    snapshot = (row[0] if row else None) or {}
    routes = snapshot.get("routes") or {}
    sources = snapshot.get("sources") or {}
    return [
        FrozenBinding(
            role=role,
            profile=profile,
            canonical_id=_canonical_id(profile, routes),
            wire_id=str((routes.get(profile) or {}).get("wire_id") or "unknown"),
            source=sources.get(role) if sources.get(role) in BINDING_SOURCES else None,
        )
        for role, profile in sorted((snapshot.get("bindings") or {}).items())
    ]


async def _metered_calls(connection: Any, run_id: UUID) -> int:
    """Counted over the run's whole root tree, as admission counts them (Decision 0017 Q4)."""
    cursor = await connection.execute(
        "select count(*) from app_private.tool_uses u where u.metered and u.root_run_id = "
        "(select coalesce(r.root_run_id, r.id) from public.runs r where r.id = %s)",
        (run_id,),
    )
    return int((await cursor.fetchone())[0])


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
    except GoalMissing:
        objective, criteria = None, []
    cursor = await connection.execute(
        "select model_calls, tool_dispatches, repairs, plan_revisions, stop_reason "
        "from app_private.run_usage where run_id = %s",
        (run_id,),
    )
    usage = await cursor.fetchone() or (0, 0, 0, 0, None)
    cursor = await connection.execute(
        "select coalesce(sum(input_tokens), 0)::bigint, coalesce(sum(output_tokens), 0)::bigint "
        "from app_private.model_invocations where run_id = %s or root_run_id = %s",
        (run_id, run_id),
    )
    tokens = await cursor.fetchone()
    artifacts = await list_artifacts(connection, workspace_id, run_id)
    left = await outstanding(connection, run_id)
    cursor = await connection.execute(
        "select exists (select 1 from public.workflow_executions where run_id = %s)", (run_id,)
    )
    is_workflow = (await cursor.fetchone())[0]
    return RunWorkspace(
        schema_version=1,
        run=summary,
        can_continue=(
            summary.status in TERMINAL and summary.parent_run_id is None and not is_workflow
        ),
        objective=objective,
        criteria=criteria,
        plan=await _plan_summary(connection, run_id),
        artifacts=[ArtifactSummary.model_validate(item) for item in artifacts],
        usage=UsageSummary(
            model_calls=usage[0],
            tool_dispatches=usage[1],
            repairs=usage[2],
            plan_revisions=usage[3],
            input_tokens=tokens[0],
            output_tokens=tokens[1],
        ),
        stop_reason=usage[4],
        verification=await _verification(connection, run_id),
        expert=await _expert(connection, run_id),
        assignments=await _assignments(connection, run_id),
        unknown_operations=[
            UnknownEffect(
                operation_id=item.operation_id,
                tool_id=item.tool_id,
                tool_version=item.tool_version,
                generation=item.generation,
            )
            for item in await unknown_operations(connection, run_id)
        ],
        outstanding=OutstandingSummary(
            uncertain_calls=left.uncertain_calls,
            unknown_effects=left.unknown_effects,
            unreported_charges=left.unreported_charges,
        ),
        cursor=row[-1],
        role_map=await _role_map(connection, run_id),
        metered_tool_calls=await _metered_calls(connection, run_id),
        metered_tool_call_limit=METERED_TOOL_CALLS,
        budgets=RunBudgets(
            context_tokens=CONTEXT_TOKENS, max_output_tokens_per_call=MAX_OUTPUT_TOKENS
        ),
    )


# Plain values, since these go to SQL as parameters.
GROUPS: dict[str, tuple[str, ...]] = {
    "active": tuple(sorted(status.value for status in IN_PROGRESS)),
    "needs_you": tuple(sorted(status.value for status in NEEDS_YOU)),
    "finished": tuple(sorted(status.value for status in TERMINAL)),
}
MAX_QUERY = 200


class InvalidCursor(FixedRefusal, ValueError):
    """A cursor this API didn't issue."""

    code = "invalid_cursor"
    kind = RefusalKind.INVALID


def encode_cursor(created_at: datetime, run_id: UUID) -> str:
    raw = f"{created_at.isoformat()}|{run_id}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
        stamp, _, identifier = raw.partition("|")
        moment = datetime.fromisoformat(stamp)
        if moment.tzinfo is None:
            raise ValueError("naive")
        return moment, UUID(identifier)
    except (ValueError, UnicodeDecodeError) as error:
        raise InvalidCursor("invalid_cursor") from error


def _like(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


# One row per run (PRD-Studio RN-01). The joins only label a run; they never widen the workspace.
_LIST_FROM = (
    "from public.runs r "
    "left join public.experts e on e.id = r.expert_id and e.workspace_id = r.workspace_id "
    "left join public.sessions s on s.id = r.session_id and s.workspace_id = r.workspace_id "
    "left join public.workflow_executions x on x.run_id = r.id and x.workspace_id = r.workspace_id "
    "left join public.workflows w on w.id = x.workflow_id and w.workspace_id = r.workspace_id "
    "where r.workspace_id = %(workspace)s "
    "and (%(like)s::text is null or r.goal_summary ilike %(like)s or e.name ilike %(like)s "
    "or w.name ilike %(like)s) "
    "and (%(profile)s::text is null or exists (select 1 from "
    "jsonb_each_text(coalesce(r.policy_snapshot -> 'bindings', '{}'::jsonb)) b "
    "where b.value = %(profile)s)) "
)
_LIST_SELECT = (
    "select r.id, r.parent_run_id, r.status, r.goal_summary, r.created_at, r.updated_at, "
    "case when x.id is not null then 'workflow' when s.kind = 'coordinator' then 'session' "
    "when e.id is not null then 'expert' else 'goal' end, "
    "case when x.id is not null then w.name || ', version ' || x.workflow_version "
    "when s.kind = 'coordinator' then 'Coordinator session' else e.name end, "
    "(select u.stop_reason from app_private.run_usage u where u.run_id = r.id), "
    "coalesce((select jsonb_array_length(p.tasks) from app_private.plan_versions p "
    "where p.run_id = r.id order by p.version desc limit 1), 0), "
    "(select count(*) from app_private.plan_evidence v where v.run_id = r.id and v.task_id in "
    "(select t ->> 'id' from app_private.plan_versions p, jsonb_array_elements(p.tasks) t "
    "where p.run_id = r.id and p.version = (select max(version) from app_private.plan_versions q "
    "where q.run_id = r.id))), "
    "array(select distinct b.value from "
    "jsonb_each_text(coalesce(r.policy_snapshot -> 'bindings', '{}'::jsonb)) b order by 1), "
    "(select coalesce(sum(coalesce(i.charged_micro_usd, 0)), 0)::bigint "
    "from app_private.model_invocations i where i.root_run_id = r.id or i.run_id = r.id), "
    "(select coalesce(sum(i.reserved_micro_usd) filter (where i.status in "
    "('reserved', 'dispatched', 'uncertain') and i.reconciled_at is null), 0)::bigint "
    "from app_private.model_invocations i where i.root_run_id = r.id or i.run_id = r.id), "
    "exists (select 1 from app_private.model_invocations i where (i.root_run_id = r.id "
    "or i.run_id = r.id) and i.status = 'uncertain' and i.reconciled_at is null "
    "and i.failure_class = 'charge_not_reported'), "
    "r.limit_micro_usd "
)


async def read_run_list(
    connection: Any,
    workspace_id: UUID,
    limit: int = RUN_LIST_SIZE,
    *,
    group: RunListGroup = "all",
    query: str | None = None,
    profile: str | None = None,
    cursor: str | None = None,
) -> RunList:
    """Only this workspace's, newest first. A read, so it starts nothing and needs no key."""
    text = (query or "").strip()[:MAX_QUERY]
    params: dict[str, Any] = {
        "workspace": workspace_id,
        "like": _like(text) if text else None,
        "profile": profile,
    }
    counted = await connection.execute(
        "select count(*), "
        "count(*) filter (where r.status = any(%(active)s)), "
        "count(*) filter (where r.status = any(%(needs)s)), "
        "count(*) filter (where r.status = any(%(finished)s)) " + _LIST_FROM,
        {
            **params,
            "active": list(GROUPS["active"]),
            "needs": list(GROUPS["needs_you"]),
            "finished": list(GROUPS["finished"]),
        },
    )
    totals = await counted.fetchone()
    counts = RunGroupCounts(
        all=int(totals[0]), active=int(totals[1]), needs_you=int(totals[2]), finished=int(totals[3])
    )
    where = ""
    page_params = {**params, "limit": limit + 1}
    if group != "all":
        where += "and r.status = any(%(statuses)s) "
        page_params["statuses"] = list(GROUPS[group])
    if cursor is not None:
        moment, after = decode_cursor(cursor)
        where += "and (r.created_at, r.id) < (%(moment)s, %(after)s) "
        page_params["moment"], page_params["after"] = moment, after
    page = await connection.execute(
        _LIST_SELECT + _LIST_FROM + where + "order by r.created_at desc, r.id desc limit %(limit)s",
        page_params,
    )
    rows = await page.fetchall()
    shown = rows[:limit]
    return RunList(
        schema_version=1,
        runs=[
            RunListItem(
                id=row[0],
                parent_run_id=row[1],
                status=row[2],
                goal_summary=public_text(row[3]),
                created_at=row[4],
                updated_at=row[5],
                label_kind=row[6],
                label=public_text(row[7]) if row[7] else None,
                stop_reason=row[8],
                tasks_complete=int(row[10]),
                tasks_total=int(row[9]),
                profiles=list(row[11]),
                charged_micro_usd=int(row[12]),
                reserved_micro_usd=int(row[13]),
                unreported=bool(row[14]),
                limit_micro_usd=int(row[15]),
            )
            for row in shown
        ],
        has_more=len(rows) > limit,
        next_cursor=encode_cursor(shown[-1][4], shown[-1][0]) if len(rows) > limit else None,
        total=getattr(counts, group),
        counts=counts,
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


async def _evidence(connection: Any, run_id: UUID) -> list[EvidenceView]:
    cursor = await connection.execute(
        "select name, id from public.artifacts where run_id = %s and status = 'published'",
        (run_id,),
    )
    published = {row[0]: row[1] for row in await cursor.fetchall()}
    cursor = await connection.execute(
        "select task_id, evidence, summary from app_private.plan_evidence "
        "where run_id = %s order by completed_at",
        (run_id,),
    )
    found = []
    for task_id, items, summary in await cursor.fetchall():
        for item in items or []:
            reference = str(item.get("reference", ""))
            found.append(
                EvidenceView(
                    task_id=public_text(task_id),
                    kind=str(item.get("kind", "")),
                    reference=public_text(reference),
                    summary=public_text(summary),
                    artifact_id=published.get(reference.rsplit("/", 1)[-1])
                    if item.get("kind") == "artifact"
                    else None,
                )
            )
    return found


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
        "input_tokens, output_tokens, reasoning_tokens, charged_micro_usd, reserved_micro_usd, "
        "finish_reason, failure_class, created_at, "
        "charge_source is not distinct from 'owner', "
        "reconciled_at is not null and charge_source is null "
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
            reported_micro_usd=item[11],
            estimated_micro_usd=item[12],
            finish_reason=item[13],
            failure_class=item[14],
            created_at=item[15],
            reconciled=item[16],
            # The call worked and only its charge was missing, so its outcome was never in doubt.
            outcome_unknown=item[16] and item[14] != "charge_not_reported",
            charge_source_unknown=item[17],
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
        evidence=await _evidence(connection, run_id),
    )
