"""Explicit routines and their occurrences, PRD 10.4 and SP-016.

Only a routine someone created and left enabled can start work. A saved key starts nothing. Each
occurrence takes its version's frozen configuration, so an edit can't reach a run already admitted.
"""

import json
import logging
import os
from datetime import datetime
from types import MappingProxyType
from typing import Any
from uuid import UUID, uuid4

from autobots.application.experts import ExpertRefused, saved_version
from autobots.application.improvements import active_skill_text
from autobots.application.run_admission import (
    CredentialCheck,
    ModelNotReady,
    expert_overrides,
    require_model_ready,
    require_tools_available,
    workspace_role_policy,
)
from autobots.application.runs import (
    Fresh,
    IdempotencyConflict,
    RunAdmission,
    RunGrant,
    admit,
    existing_receipt,
    request_hash,
    store_receipt,
)
from autobots.application.tool_catalog import Catalog, ToolsUnavailable
from autobots.application.workflows import WorkflowRefused, create_execution
from autobots.contracts.persisted import RoutineCreatedReceipt, RoutineVersionReceipt
from autobots.contracts.primitives import MAX_SAFE_INTEGER
from autobots.contracts.routines import (
    OccurrenceView,
    RoutineConfig,
    RoutineConfigView,
    RoutineScheduleView,
    RoutineTarget,
    RoutineView,
)
from autobots.domain.errors import Refusal, RefusalKind
from autobots.domain.models import ProfileNotOffered
from autobots.domain.routines import (
    IntervalTrigger,
    SavedTrigger,
    TriggerInvalid,
    UnscheduledTrigger,
    occurrences,
    occurrences_dropped,
    validate_trigger,
    wall_clock,
)
from autobots.domain.runs import TERMINAL
from autobots.domain.tools import EXPERT_TOOLS, PLAN_TOOLS
from autobots.logs import log_event
from autobots.persistence.records import (
    ExpertConfigRecord,
    RoutineConfigRecord,
    RoutineTargetRecord,
    read_routine_config,
)

logger = logging.getLogger("autobots.routines")


class RoutineRefused(Refusal):
    """A typed reason, and nothing changes. A routine its target or trigger can't have is
    invalid, and so is a refusal it carries over from admitting an occurrence."""

    kind = RefusalKind.INVALID
    kinds = MappingProxyType(
        {
            "routine_not_found": RefusalKind.NOT_FOUND,
            "routine_target_not_found": RefusalKind.NOT_FOUND,
            "routine_name_taken": RefusalKind.CONFLICT,
            "routine_version_conflict": RefusalKind.CONFLICT,
        }
    )


async def _expert_config(
    connection: Any, workspace_id: UUID, config: RoutineConfigRecord
) -> ExpertConfigRecord:
    target = config.target
    expert = await saved_version(connection, workspace_id, target.id, target.version)
    if expert is None:
        raise RoutineRefused("routine_target_not_found")
    return expert


def pinned_version(config: RoutineConfig) -> int:
    """A routine binds a published version only, never a workflow's draft (PRD-Studio WF-02)."""
    if config.target.version == "draft":
        raise RoutineRefused("draft_not_runnable")
    return config.target.version


def routine_record(config: RoutineConfig) -> RoutineConfigRecord:
    """What a version stores, with its trigger and timezone checked. The trigger keeps the shape
    triggers were always stored in, its kind and the one field that kind uses, so stored bytes and
    receipt fingerprints don't change (refactor plan R-52)."""
    version = pinned_version(config)
    try:
        trigger = validate_trigger(config.trigger.model_dump(exclude_none=True), config.timezone)
    except TriggerInvalid as invalid:
        raise RoutineRefused(invalid.code) from None
    return RoutineConfigRecord(
        target=RoutineTargetRecord(kind=config.target.kind, id=config.target.id, version=version),
        trigger=trigger,
        timezone=config.timezone,
        goal=config.goal,
        inputs=config.inputs,
        tools=tuple(config.tools) if config.tools is not None else None,
        limit_micro_usd=config.limit_micro_usd,
        overlap=config.overlap,
    )


def _schedule_view(trigger: SavedTrigger) -> RoutineScheduleView:
    """Daily at the wall-clock time its occurrences use, so a view never misstates when it runs,
    and with no time for one that never runs."""
    if isinstance(trigger, IntervalTrigger):
        return RoutineScheduleView(kind="interval", minutes=trigger.minutes, time=None)
    if isinstance(trigger, UnscheduledTrigger):
        return RoutineScheduleView(kind="daily", minutes=None, time=None)
    return RoutineScheduleView(kind="daily", minutes=None, time=wall_clock(trigger))


def routine_view_config(record: RoutineConfigRecord) -> RoutineConfigView:
    """A saved version as the Routines API shows it. A limit beyond what a JavaScript client can
    hold shows as that maximum, while admission uses the stored value, which the workspace's run
    limit caps (Decision 0029 F2)."""
    target = record.target
    return RoutineConfigView(
        target=RoutineTarget(kind=target.kind, id=target.id, version=target.version),
        trigger=_schedule_view(record.trigger),
        timezone=record.timezone,
        goal=record.goal,
        inputs=dict(record.inputs),
        tools=list(record.tools) if record.tools is not None else None,
        limit_micro_usd=min(record.limit_micro_usd, MAX_SAFE_INTEGER),
        overlap=record.overlap,
    )


async def _validate(
    connection: Any, workspace_id: UUID, config: RoutineConfig, budget_cap: int | None
) -> RoutineConfigRecord:
    """A routine can only narrow what its pinned target has, and a capped caller's routine can't
    spend more than its cap a run (Decision 0029 F2)."""
    record = routine_record(config)
    if budget_cap is not None and record.limit_micro_usd > budget_cap:
        raise RoutineRefused("routine_limit_too_high")
    if record.target.kind == "expert":
        expert = await _expert_config(connection, workspace_id, record)
        if not record.goal.strip():
            raise RoutineRefused("routine_goal_required")
        if record.tools is not None and not set(record.tools) <= set(expert.tools):
            raise RoutineRefused("routine_scope_widened")
        return record
    cursor = await connection.execute(
        "select 1 from public.workflow_versions v join public.workflows w on w.id = v.workflow_id "
        "where v.workflow_id = %s and v.version = %s and w.workspace_id = %s",
        (record.target.id, record.target.version, workspace_id),
    )
    if await cursor.fetchone() is None:
        raise RoutineRefused("routine_target_not_found")
    return record


async def _stored_config(connection: Any, routine_id: UUID, version: int) -> RoutineConfigRecord:
    cursor = await connection.execute(
        "select config from public.routine_versions where routine_id = %s and version = %s",
        (routine_id, version),
    )
    return read_routine_config((await cursor.fetchone())[0])


async def _view(connection: Any, row: Any) -> RoutineView:
    routine_id, name, enabled, latest = row
    config = routine_view_config(await _stored_config(connection, routine_id, latest))
    cursor = await connection.execute(
        "select occurrence_time, routine_version, status, reason, run_id "
        "from public.routine_occurrences where routine_id = %s "
        "order by occurrence_time desc limit 100",
        (routine_id,),
    )
    history = [
        OccurrenceView(
            occurrence_time=item[0].isoformat(),
            routine_version=item[1],
            status=item[2],
            reason=item[3],
            run_id=item[4],
        )
        for item in await cursor.fetchall()
    ]
    return RoutineView(
        schema_version=1,
        id=routine_id,
        name=name,
        enabled=enabled,
        latest_version=latest,
        config=config,
        occurrences=history,
    )


_COLUMNS = "id, name, enabled, latest_version"


async def get_routine(connection: Any, workspace_id: UUID, routine_id: UUID) -> RoutineView:
    cursor = await connection.execute(
        f"select {_COLUMNS} from public.routines "
        "where id = %s and workspace_id = %s and removed_at is null",
        (routine_id, workspace_id),
    )
    row = await cursor.fetchone()
    if row is None:
        raise RoutineRefused("routine_not_found")
    return await _view(connection, row)


async def list_routines(connection: Any, workspace_id: UUID) -> list[RoutineView]:
    cursor = await connection.execute(
        f"select {_COLUMNS} from public.routines where workspace_id = %s and removed_at is null "
        "order by name",
        (workspace_id,),
    )
    return [await _view(connection, row) for row in await cursor.fetchall()]


async def create_routine(
    connection: Any,
    *,
    workspace_id: UUID,
    actor_id: UUID,
    idempotency_key: str,
    name: str,
    config: RoutineConfig,
    budget_cap: int | None,
    now: datetime | None = None,
) -> RoutineView:
    """It starts counting from now, so creating one never reaches back into the past. Every caller
    states `budget_cap`: None for a person's routine, whose runs the workspace's run limit caps,
    and the cronjob tool's own cap for the model's (Decision 0029 F2)."""
    stored = (await _validate(connection, workspace_id, config, budget_cap)).stored()
    # Over the stored record, so a trigger sent with an explicit null hashes as its normalized
    # form, and such a retry across R-52 is refused as a conflict (refactor plan R-52).
    fingerprint = request_hash({"name": name, "config": json.loads(stored)})
    scope = (workspace_id, actor_id, "create_routine", str(workspace_id), idempotency_key)
    async with connection.transaction():
        existing = await existing_receipt(connection, scope, fingerprint, RoutineCreatedReceipt)
        if existing is not None:
            return await get_routine(connection, workspace_id, existing.routine_id)
        cursor = await connection.execute(
            "select 1 from public.routines where workspace_id = %s and name = %s "
            "and removed_at is null",
            (workspace_id, name),
        )
        if await cursor.fetchone() is not None:
            raise RoutineRefused("routine_name_taken")
        routine_id = uuid4()
        await connection.execute(
            "insert into public.routines (id, workspace_id, name, evaluated_until) "
            "values (%s, %s, %s, coalesce(%s, clock_timestamp()))",
            (routine_id, workspace_id, name, now),
        )
        await connection.execute(
            "insert into public.routine_versions (routine_id, version, config, created_by) "
            "values (%s, 1, %s, %s)",
            (routine_id, stored, actor_id),
        )
        await store_receipt(
            connection, scope, fingerprint, RoutineCreatedReceipt(routine_id=routine_id)
        )
    return await get_routine(connection, workspace_id, routine_id)


async def add_routine_version(
    connection: Any,
    *,
    workspace_id: UUID,
    actor_id: UUID,
    routine_id: UUID,
    idempotency_key: str,
    expected_version: int,
    config: RoutineConfig,
    budget_cap: int | None,
) -> RoutineView:
    """A new version, under `budget_cap` as for `create_routine`."""
    stored = (await _validate(connection, workspace_id, config, budget_cap)).stored()
    # Over the stored record, as for `create_routine`.
    fingerprint = request_hash({"expected": expected_version, "config": json.loads(stored)})
    scope = (workspace_id, actor_id, "edit_routine", str(routine_id), idempotency_key)
    async with connection.transaction():
        existing = await existing_receipt(connection, scope, fingerprint, RoutineVersionReceipt)
        if existing is not None:
            return await get_routine(connection, workspace_id, routine_id)
        cursor = await connection.execute(
            "select latest_version from public.routines "
            "where id = %s and workspace_id = %s and removed_at is null for update",
            (routine_id, workspace_id),
        )
        row = await cursor.fetchone()
        if row is None:
            raise RoutineRefused("routine_not_found")
        if row[0] != expected_version:
            raise RoutineRefused("routine_version_conflict")
        version = row[0] + 1
        await connection.execute(
            "insert into public.routine_versions (routine_id, version, config, created_by) "
            "values (%s, %s, %s, %s)",
            (routine_id, version, stored, actor_id),
        )
        await connection.execute(
            "update public.routines set latest_version = %s where id = %s", (version, routine_id)
        )
        await store_receipt(connection, scope, fingerprint, RoutineVersionReceipt(version=version))
    return await get_routine(connection, workspace_id, routine_id)


async def set_enabled(
    connection: Any, workspace_id: UUID, routine_id: UUID, enabled: bool
) -> RoutineView:
    """Turning one back on doesn't catch up on the time it was off."""
    cursor = await connection.execute(
        "update public.routines set enabled = %s, evaluated_until = case when %s and not enabled "
        "then clock_timestamp() else evaluated_until end "
        "where id = %s and workspace_id = %s and removed_at is null returning id",
        (enabled, enabled, routine_id, workspace_id),
    )
    if await cursor.fetchone() is None:
        raise RoutineRefused("routine_not_found")
    return await get_routine(connection, workspace_id, routine_id)


async def remove_routine(connection: Any, workspace_id: UUID, routine_id: UUID) -> None:
    """Decision 0026 C7: disabled, hidden and never evaluated again, with nothing deleted. Its
    versions, occurrences and runs stay, and its name is free for a new routine."""
    cursor = await connection.execute(
        "update public.routines set removed_at = clock_timestamp(), enabled = false "
        "where id = %s and workspace_id = %s and removed_at is null returning id",
        (routine_id, workspace_id),
    )
    if await cursor.fetchone() is None:
        raise RoutineRefused("routine_not_found")


async def run_routine_now(
    connection: Any,
    workspace_id: UUID,
    routine_id: UUID,
    credential_check: CredentialCheck,
    *,
    catalog: Catalog,
) -> tuple[str, str | None, UUID | None]:
    """Decision 0026 C6: one occurrence now, by the scheduled path's own checks, in order.

    Returns `(status, reason, run_id)`: `admitted` with its run, `skipped_overlap` while an earlier
    run is active, or `blocked` with why. A paused routine is refused, so a person resumes it first.
    """
    async with connection.transaction():
        cursor = await connection.execute(
            "select latest_version, enabled from public.routines "
            "where id = %s and workspace_id = %s and removed_at is null for update",
            (routine_id, workspace_id),
        )
        row = await cursor.fetchone()
        if row is None:
            raise RoutineRefused("routine_not_found")
        version, enabled = row
        if not enabled:
            raise RoutineRefused("routine_paused")
        moment = (await (await connection.execute("select clock_timestamp()")).fetchone())[0]
        config = await _stored_config(connection, routine_id, version)
        if await _has_active_run(connection, routine_id):
            await _record(connection, routine_id, moment, version, "skipped_overlap", "run_active")
            return "skipped_overlap", "run_active", None
        try:
            await require_model_ready(
                credential_check, workspace_id, needed=await _needs_model(config, connection)
            )
        except ModelNotReady as refused:
            await _record(connection, routine_id, moment, version, "blocked", refused.code)
            return "blocked", refused.code, None
        try:
            run_id = await admit_occurrence(
                connection, workspace_id, routine_id, version, config, moment, catalog=catalog
            )
        except (RoutineRefused, WorkflowRefused, IdempotencyConflict, ExpertRefused) as refused:
            await _record(connection, routine_id, moment, version, "blocked", refused.code)
            return "blocked", refused.code, None
        await _record(connection, routine_id, moment, version, "admitted", None, run_id)
        return "admitted", None, run_id


async def _has_active_run(connection: Any, routine_id: UUID) -> bool:
    cursor = await connection.execute(
        "select exists (select 1 from public.routine_occurrences o join public.runs r "
        "on r.id = o.run_id where o.routine_id = %s and r.status <> all(%s))",
        (routine_id, sorted(TERMINAL)),
    )
    return bool((await cursor.fetchone())[0])


async def _record(
    connection: Any,
    routine_id: UUID,
    moment: datetime,
    version: int,
    status: str,
    reason: str | None = None,
    run_id: UUID | None = None,
) -> None:
    await connection.execute(
        "insert into public.routine_occurrences (routine_id, occurrence_time, routine_version, "
        "status, reason, run_id) values (%s, %s, %s, %s, %s, %s) "
        "on conflict (routine_id, occurrence_time) do nothing",
        (routine_id, moment, version, status, reason, run_id),
    )


async def admit_occurrence(
    connection: Any,
    workspace_id: UUID,
    routine_id: UUID,
    version: int,
    config: RoutineConfigRecord,
    moment: datetime,
    *,
    catalog: Catalog,
) -> UUID:
    """Admits the run one occurrence starts: the workflow's execution, or the Expert's run under its
    pinned version's bindings and tools. Its key is the routine and the occurrence time, so
    admitting the same occurrence again returns that run (SP-014). `catalog` decides whether its
    tools are available (PK-02)."""
    key = f"routine:{routine_id}:{moment.isoformat()}"
    actor = routine_id
    if config.target.kind == "workflow":
        binding = await create_execution(
            connection,
            workspace_id=workspace_id,
            actor_id=actor,
            workflow_id=config.target.id,
            idempotency_key=key,
            version=config.target.version,
            inputs=dict(config.inputs),
            limit_micro_usd=config.limit_micro_usd,
            tools=list(config.tools) if config.tools is not None else None,
        )
        return binding.run_id
    expert = await _expert_config(connection, workspace_id, config)
    tools = config.tools if config.tools is not None else expert.tools
    try:
        # The pinned version's role bindings, and no run-wide profile, which a routine can't name.
        policy = await workspace_role_policy(
            connection,
            workspace_id,
            run_role_overrides=expert_overrides(expert),
            require_offer=True,
        )
    except ProfileNotOffered as refused:
        raise RoutineRefused(refused.code) from None
    try:
        # PK-02: a missing key refuses this occurrence, before a run exists. Its keys come from
        # this process's environment as it is now, where POST /v1/runs reads the one its entry
        # point read at start.
        await require_tools_available(connection, workspace_id, tools, os.environ, catalog)
    except ToolsUnavailable as refused:
        raise RoutineRefused(refused.code) from None
    grant = RunGrant(
        expert_id=config.target.id,
        version=config.target.version,
        instructions=expert.instructions
        + await active_skill_text(connection, workspace_id, list(expert.skills)),
        tools={**PLAN_TOOLS, **{tool: EXPERT_TOOLS[tool] for tool in tools}},
    )
    # No started_by: a routine's run has none, Decision 0015.
    admitted = await admit(
        connection,
        RunAdmission(
            workspace_id=workspace_id,
            actor_id=actor,
            idempotency_key=key,
            goal_text=config.goal,
            limit_micro_usd=config.limit_micro_usd,
            origin=Fresh(policy, grant),
        ),
    )
    return admitted.run_id


async def _needs_model(config: RoutineConfigRecord, connection: Any) -> bool:
    if config.target.kind == "expert":
        return True
    cursor = await connection.execute(
        "select graph from public.workflow_versions where workflow_id = %s and version = %s",
        (config.target.id, config.target.version),
    )
    graph = (await cursor.fetchone())[0]
    return any(node["block"] == "agent" for node in graph["nodes"])


async def _evaluate_one(
    connection: Any,
    routine_id: UUID,
    credential_check: CredentialCheck,
    now: datetime | None,
    catalog: Catalog,
) -> int:
    async with connection.transaction():
        row = await (
            await connection.execute(
                "select workspace_id, latest_version, evaluated_until from public.routines "
                "where id = %s and enabled and removed_at is null for update skip locked",
                (routine_id,),
            )
        ).fetchone()
        if row is None:
            return 0
        workspace_id, version, until = row
        # Read under the row's lock, so a slower worker can't carry an older time past a newer one.
        cursor = await connection.execute("select clock_timestamp()")
        moment_now = now or (await cursor.fetchone())[0]
        if moment_now <= until:
            return 0
        config = await _stored_config(connection, routine_id, version)
        due = occurrences(config.trigger, config.timezone, until, moment_now)
        await connection.execute(
            "update public.routines set evaluated_until = %s where id = %s",
            (moment_now, routine_id),
        )
        if not due:
            return 0
        dropped = occurrences_dropped(config.trigger, until, moment_now, len(due))
        for index, missed in enumerate(due[:-1]):
            note = f", {dropped} earlier not listed" if dropped and not index else ""
            reason = f"host_away{note}"
            await _record(connection, routine_id, missed, version, "missed", reason)
        latest = due[-1]
        if await _has_active_run(connection, routine_id):
            await _record(connection, routine_id, latest, version, "skipped_overlap", "run_active")
            return 0
        try:
            await require_model_ready(
                credential_check, workspace_id, needed=await _needs_model(config, connection)
            )
        except ModelNotReady as refused:
            await _record(connection, routine_id, latest, version, "blocked", refused.code)
            return 0
        try:
            run_id = await admit_occurrence(
                connection, workspace_id, routine_id, version, config, latest, catalog=catalog
            )
        except (RoutineRefused, WorkflowRefused, IdempotencyConflict, ExpertRefused) as refused:
            await _record(connection, routine_id, latest, version, "blocked", refused.code)
            return 0
        await _record(connection, routine_id, latest, version, "admitted", None, run_id)
        return 1


async def evaluate_routines(
    connection: Any,
    credential_check: CredentialCheck,
    now: datetime | None = None,
    *,
    catalog: Catalog,
) -> int:
    """Admits what's due. Run from any number of workers: a row lock and a unique key keep it once.

    After time away, everything but the latest due occurrence is recorded as missed, and only the
    latest catches up. While an earlier run is active, an occurrence is skipped, and says so.
    """
    cursor = await connection.execute(
        "select id from public.routines where enabled and removed_at is null"
    )
    admitted = 0
    for (routine_id,) in await cursor.fetchall():
        try:
            admitted += await _evaluate_one(connection, routine_id, credential_check, now, catalog)
        except Exception as error:  # noqa: BLE001 - one routine's failure leaves it due and never stops the others
            # Rolled back on its own. This one stays due, and every other routine still runs.
            log_event(
                logger,
                "routine.evaluation_failed",
                logging.ERROR,
                routine=routine_id,
                error=error,
            )
    return admitted
