"""Explicit routines and their occurrences, PRD 10.4 and SP-016.

Only a routine someone created and left enabled can start work. A saved key starts nothing. Each
occurrence takes its version's frozen configuration, so an edit can't reach a run already admitted.
"""

from collections.abc import Awaitable, Callable
from datetime import datetime
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

from autobots.application.experts import ExpertRefused, get_expert
from autobots.application.runs import admit_run, existing_receipt, request_hash, store_receipt
from autobots.application.workflows import WorkflowRefused, create_execution
from autobots.contracts.experts import ExpertConfig
from autobots.contracts.routines import OccurrenceView, RoutineConfig, RoutineView
from autobots.domain.models import resolve_role_policy
from autobots.domain.routines import TriggerInvalid, occurrences, validate_trigger
from autobots.domain.tools import EXPERT_TOOLS, PLAN_TOOLS

# Says whether a workspace can make model calls now. It reports, and never starts anything.
CredentialCheck = Callable[[UUID], Awaitable[str]]


class RoutineRefused(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


async def _expert_config(
    connection: Any, workspace_id: UUID, config: RoutineConfig
) -> ExpertConfig:
    try:
        expert = await get_expert(connection, workspace_id, config.target.id)
    except ExpertRefused:
        raise RoutineRefused("routine_target_not_found") from None
    version = next((v for v in expert.versions if v.version == config.target.version), None)
    if version is None:
        raise RoutineRefused("routine_target_not_found")
    return version.config


async def _validate(connection: Any, workspace_id: UUID, config: RoutineConfig) -> None:
    """A routine can only narrow what its pinned target has."""
    try:
        validate_trigger(config.trigger, config.timezone)
    except TriggerInvalid as invalid:
        raise RoutineRefused(str(invalid)) from None
    if config.target.kind == "expert":
        expert = await _expert_config(connection, workspace_id, config)
        if not config.goal.strip():
            raise RoutineRefused("routine_goal_required")
        if config.tools is not None and not set(config.tools) <= set(expert.tools):
            raise RoutineRefused("routine_scope_widened")
        return
    cursor = await connection.execute(
        "select 1 from public.workflow_versions v join public.workflows w on w.id = v.workflow_id "
        "where v.workflow_id = %s and v.version = %s and w.workspace_id = %s",
        (config.target.id, config.target.version, workspace_id),
    )
    if await cursor.fetchone() is None:
        raise RoutineRefused("routine_target_not_found")


async def _view(connection: Any, row: Any) -> RoutineView:
    routine_id, name, enabled, latest = row
    cursor = await connection.execute(
        "select config from public.routine_versions where routine_id = %s and version = %s",
        (routine_id, latest),
    )
    config = RoutineConfig.model_validate((await cursor.fetchone())[0])
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
        f"select {_COLUMNS} from public.routines where id = %s and workspace_id = %s",
        (routine_id, workspace_id),
    )
    row = await cursor.fetchone()
    if row is None:
        raise RoutineRefused("routine_not_found")
    return await _view(connection, row)


async def list_routines(connection: Any, workspace_id: UUID) -> list[RoutineView]:
    cursor = await connection.execute(
        f"select {_COLUMNS} from public.routines where workspace_id = %s order by name",
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
    now: datetime | None = None,
) -> RoutineView:
    """It starts counting from now, so creating one never reaches back into the past."""
    await _validate(connection, workspace_id, config)
    fingerprint = request_hash({"name": name, "config": config.model_dump(mode="json")})
    scope = (workspace_id, actor_id, "create_routine", str(workspace_id), idempotency_key)
    async with connection.transaction():
        existing = await existing_receipt(connection, scope, fingerprint)
        if existing is not None:
            return await get_routine(connection, workspace_id, UUID(existing["routine_id"]))
        cursor = await connection.execute(
            "select 1 from public.routines where workspace_id = %s and name = %s",
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
            (routine_id, config.model_dump_json(), actor_id),
        )
        await store_receipt(connection, scope, fingerprint, {"routine_id": str(routine_id)})
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
) -> RoutineView:
    await _validate(connection, workspace_id, config)
    fingerprint = request_hash(
        {"expected": expected_version, "config": config.model_dump(mode="json")}
    )
    scope = (workspace_id, actor_id, "edit_routine", str(routine_id), idempotency_key)
    async with connection.transaction():
        existing = await existing_receipt(connection, scope, fingerprint)
        if existing is not None:
            return await get_routine(connection, workspace_id, routine_id)
        cursor = await connection.execute(
            "select latest_version from public.routines "
            "where id = %s and workspace_id = %s for update",
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
            (routine_id, version, config.model_dump_json(), actor_id),
        )
        await connection.execute(
            "update public.routines set latest_version = %s where id = %s", (version, routine_id)
        )
        await store_receipt(connection, scope, fingerprint, {"version": version})
    return await get_routine(connection, workspace_id, routine_id)


async def set_enabled(
    connection: Any, workspace_id: UUID, routine_id: UUID, enabled: bool
) -> RoutineView:
    """Turning one back on doesn't catch up on the time it was off."""
    cursor = await connection.execute(
        "update public.routines set enabled = %s, evaluated_until = case when %s and not enabled "
        "then clock_timestamp() else evaluated_until end "
        "where id = %s and workspace_id = %s returning id",
        (enabled, enabled, routine_id, workspace_id),
    )
    if await cursor.fetchone() is None:
        raise RoutineRefused("routine_not_found")
    return await get_routine(connection, workspace_id, routine_id)


async def _has_active_run(connection: Any, routine_id: UUID) -> bool:
    cursor = await connection.execute(
        "select exists (select 1 from public.routine_occurrences o join public.runs r "
        "on r.id = o.run_id where o.routine_id = %s and r.status not in "
        "('succeeded', 'failed', 'cancelled'))",
        (routine_id,),
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


async def _admit(
    connection: Any,
    workspace_id: UUID,
    routine_id: UUID,
    version: int,
    config: RoutineConfig,
    moment: datetime,
) -> UUID:
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
            inputs=config.inputs,
        )
        return binding.run_id
    expert = await _expert_config(connection, workspace_id, config)
    tools = config.tools if config.tools is not None else expert.tools
    cursor = await connection.execute(
        "select default_profile, role_overrides from app_private.model_policies "
        "where workspace_id = %s",
        (workspace_id,),
    )
    policy_row = await cursor.fetchone()
    admitted = await admit_run(
        connection,
        workspace_id=workspace_id,
        actor_id=actor,
        idempotency_key=key,
        goal_text=config.goal,
        limit_micro_usd=config.limit_micro_usd,
        policy=resolve_role_policy(
            run_role_overrides={r: p.value for r, p in expert.role_bindings.items()},
            workspace_default=policy_row[0] if policy_row else None,
            workspace_role_overrides=policy_row[1] if policy_row else None,
        ),
        binding=SimpleNamespace(
            session_id=None,
            expert_id=config.target.id,
            version=config.target.version,
            instructions=expert.instructions,
            tools={**PLAN_TOOLS, **{tool: EXPERT_TOOLS[tool] for tool in tools}},
        ),
    )
    return admitted.run_id


async def _needs_model(config: RoutineConfig, connection: Any) -> bool:
    if config.target.kind == "expert":
        return True
    cursor = await connection.execute(
        "select graph from public.workflow_versions where workflow_id = %s and version = %s",
        (config.target.id, config.target.version),
    )
    graph = (await cursor.fetchone())[0]
    return any(node["block"] == "agent" for node in graph["nodes"])


async def evaluate_routines(
    connection: Any, credential_check: CredentialCheck, now: datetime | None = None
) -> int:
    """Admits what's due. Run from any number of workers: a row lock and a unique key keep it once.

    After time away, everything but the latest due occurrence is recorded as missed, and only the
    latest catches up. While an earlier run is active, an occurrence is skipped, and says so.
    """
    cursor = await connection.execute("select clock_timestamp()")
    moment_now = now or (await cursor.fetchone())[0]
    cursor = await connection.execute("select id from public.routines where enabled")
    admitted = 0
    for (routine_id,) in await cursor.fetchall():
        async with connection.transaction():
            row = await (
                await connection.execute(
                    "select workspace_id, latest_version, evaluated_until from public.routines "
                    "where id = %s and enabled for update skip locked",
                    (routine_id,),
                )
            ).fetchone()
            if row is None:
                continue
            workspace_id, version, until = row
            cursor = await connection.execute(
                "select config from public.routine_versions where routine_id = %s and version = %s",
                (routine_id, version),
            )
            config = RoutineConfig.model_validate((await cursor.fetchone())[0])
            due = occurrences(config.trigger, config.timezone, until, moment_now)
            await connection.execute(
                "update public.routines set evaluated_until = %s where id = %s",
                (moment_now, routine_id),
            )
            if not due:
                continue
            for missed in due[:-1]:
                await _record(connection, routine_id, missed, version, "missed", "host_away")
            latest = due[-1]
            if await _has_active_run(connection, routine_id):
                await _record(
                    connection, routine_id, latest, version, "skipped_overlap", "run_active"
                )
                continue
            if await _needs_model(config, connection):
                code = await credential_check(workspace_id)
                if code != "ready":
                    await _record(connection, routine_id, latest, version, "blocked", code)
                    continue
            try:
                run_id = await _admit(connection, workspace_id, routine_id, version, config, latest)
            except (RoutineRefused, WorkflowRefused) as refused:
                await _record(connection, routine_id, latest, version, "blocked", refused.code)
                continue
            await _record(connection, routine_id, latest, version, "admitted", None, run_id)
            admitted += 1
    return admitted
