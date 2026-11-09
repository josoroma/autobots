"""Experts, immutable revisions, sessions and bounded routing, PRD 8.2 and 8.3."""

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from autobots.application.improvements import active_skill_text
from autobots.application.runs import existing_receipt, request_hash, store_receipt
from autobots.contracts.experts import (
    ExpertConfig,
    ExpertVersionView,
    ExpertView,
    RouteOption,
    SessionExpert,
    SessionView,
)
from autobots.domain.models import approved_role
from autobots.domain.tools import DELEGATION_TOOL, EXPERT_TOOLS, PLAN_TOOLS


class ExpertRefused(Exception):
    """A typed reason, and nothing changes."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def expand_groups(config: ExpertConfig, environ: Mapping[str, str] = os.environ) -> ExpertConfig:
    """Groups become explicit tools when a version is saved, so a tool added to a group later
    never changes a saved version (TC-06). A tool an editor didn't name stays out."""
    if not config.tool_groups:
        return config
    from autobots.application.tool_catalog import expert_tools_by_group

    if len(set(config.tool_groups)) != len(config.tool_groups):
        raise ExpertRefused("expert_tool_group_duplicated")
    by_group = expert_tools_by_group(environ)
    tools = list(config.tools)
    for group in config.tool_groups:
        members = by_group.get(group, [])
        if not members:
            raise ExpertRefused("expert_tool_group_empty")
        tools += [tool for tool in members if tool not in tools]
    return config.model_copy(update={"tools": tools})


async def _workspace_keys(connection: Any, workspace_id: UUID) -> Mapping[str, str]:
    """PK-04: a tool's key may be saved for this workspace, so availability is the workspace's."""
    from autobots.application.tool_keys import key_sources

    return await key_sources(connection, workspace_id, os.environ)


def validate_config(config: ExpertConfig, environ: Mapping[str, str] = os.environ) -> None:
    """A revision can only name what exists and is available. Anything else is refused, not
    dropped."""
    if any(tool not in EXPERT_TOOLS for tool in config.tools):
        raise ExpertRefused("expert_tool_not_available")
    if len(set(config.tools)) != len(config.tools):
        raise ExpertRefused("expert_tool_duplicated")
    from autobots.application.tool_catalog import unavailable_tools

    if unavailable_tools(config.tools, environ):
        raise ExpertRefused("expert_tool_unavailable")
    try:
        for role in config.role_bindings:
            approved_role(role)
    except Exception:
        raise ExpertRefused("expert_role_unknown") from None


async def _view(connection: Any, expert_id: UUID, name: str, latest: int) -> ExpertView:
    cursor = await connection.execute(
        "select version, config from public.expert_versions where expert_id = %s order by version",
        (expert_id,),
    )
    versions = [
        ExpertVersionView(version=row[0], config=ExpertConfig.model_validate(row[1]))
        for row in await cursor.fetchall()
    ]
    cursor = await connection.execute(
        "select count(*), max(created_at) from public.runs where expert_id = %s", (expert_id,)
    )
    runs = await cursor.fetchone()
    return ExpertView(
        schema_version=1,
        id=expert_id,
        name=name,
        latest_version=latest,
        versions=versions,
        run_count=int(runs[0]),
        last_run_at=runs[1],
    )


async def list_experts(connection: Any, workspace_id: UUID) -> list[ExpertView]:
    cursor = await connection.execute(
        "select id, name, latest_version from public.experts where workspace_id = %s order by name",
        (workspace_id,),
    )
    return [await _view(connection, *row) for row in await cursor.fetchall()]


async def get_expert(connection: Any, workspace_id: UUID, expert_id: UUID) -> ExpertView:
    cursor = await connection.execute(
        "select id, name, latest_version from public.experts where id = %s and workspace_id = %s",
        (expert_id, workspace_id),
    )
    row = await cursor.fetchone()
    if row is None:
        raise ExpertRefused("expert_not_found")
    return await _view(connection, *row)


async def create_expert(
    connection: Any,
    *,
    workspace_id: UUID,
    actor_id: UUID,
    idempotency_key: str,
    name: str,
    config: ExpertConfig,
) -> ExpertView:
    fingerprint = request_hash({"name": name, "config": config.model_dump(mode="json")})
    keys = await _workspace_keys(connection, workspace_id)
    config = expand_groups(config, keys)
    validate_config(config, keys)
    scope = (workspace_id, actor_id, "create_expert", str(workspace_id), idempotency_key)
    async with connection.transaction():
        existing = await existing_receipt(connection, scope, fingerprint)
        if existing is not None:
            return await get_expert(connection, workspace_id, UUID(existing["expert_id"]))
        cursor = await connection.execute(
            "select 1 from public.experts where workspace_id = %s and name = %s",
            (workspace_id, name),
        )
        if await cursor.fetchone() is not None:
            raise ExpertRefused("expert_name_taken")
        expert_id = uuid4()
        await connection.execute(
            "insert into public.experts (id, workspace_id, name) values (%s, %s, %s)",
            (expert_id, workspace_id, name),
        )
        await connection.execute(
            "insert into public.expert_versions (expert_id, version, config, created_by) "
            "values (%s, 1, %s, %s)",
            (expert_id, config.model_dump_json(), actor_id),
        )
        await store_receipt(connection, scope, fingerprint, {"expert_id": str(expert_id)})
    return await get_expert(connection, workspace_id, expert_id)


async def add_version(
    connection: Any,
    *,
    workspace_id: UUID,
    actor_id: UUID,
    expert_id: UUID,
    idempotency_key: str,
    expected_version: int,
    config: ExpertConfig,
) -> ExpertView:
    """A new revision. Earlier ones never change, so work holding them is unaffected."""
    fingerprint = request_hash(
        {"expected": expected_version, "config": config.model_dump(mode="json")}
    )
    keys = await _workspace_keys(connection, workspace_id)
    config = expand_groups(config, keys)
    validate_config(config, keys)
    scope = (workspace_id, actor_id, "add_expert_version", str(expert_id), idempotency_key)
    async with connection.transaction():
        existing = await existing_receipt(connection, scope, fingerprint)
        if existing is not None:
            return await get_expert(connection, workspace_id, expert_id)
        cursor = await connection.execute(
            "select latest_version from public.experts "
            "where id = %s and workspace_id = %s for update",
            (expert_id, workspace_id),
        )
        row = await cursor.fetchone()
        if row is None:
            raise ExpertRefused("expert_not_found")
        if row[0] != expected_version:
            raise ExpertRefused("expert_version_conflict")
        version = row[0] + 1
        await connection.execute(
            "insert into public.expert_versions (expert_id, version, config, created_by) "
            "values (%s, %s, %s, %s)",
            (expert_id, version, config.model_dump_json(), actor_id),
        )
        await connection.execute(
            "update public.experts set latest_version = %s where id = %s", (version, expert_id)
        )
        await store_receipt(connection, scope, fingerprint, {"version": version})
    return await get_expert(connection, workspace_id, expert_id)


async def _option(
    connection: Any, workspace_id: UUID, expert_id: UUID, version: int
) -> RouteOption:
    cursor = await connection.execute(
        "select e.name, v.config from public.experts e join public.expert_versions v "
        "on v.expert_id = e.id where e.id = %s and e.workspace_id = %s and v.version = %s",
        (expert_id, workspace_id, version),
    )
    row = await cursor.fetchone()
    if row is None:
        raise ExpertRefused("expert_not_found")
    config = ExpertConfig.model_validate(row[1])
    return RouteOption(
        expert_id=expert_id,
        name=row[0],
        version=version,
        purpose=config.purpose,
        tools=config.tools,
        role_bindings={role: profile.value for role, profile in config.role_bindings.items()},
    )


async def create_session(
    connection: Any,
    *,
    workspace_id: UUID,
    actor_id: UUID,
    idempotency_key: str,
    kind: str,
    experts: list[SessionExpert],
) -> SessionView:
    """Pins the revisions, and for a coordinator, the only Experts it may route to."""
    if kind == "direct" and len(experts) != 1:
        raise ExpertRefused("session_needs_one_expert")
    pinned: list[dict[str, Any]] = []
    for item in experts:
        expert = await get_expert(connection, workspace_id, item.expert_id)
        version = item.version if item.version is not None else expert.latest_version
        await _option(connection, workspace_id, item.expert_id, version)
        pinned.append({"expert_id": str(item.expert_id), "version": version})
    fingerprint = request_hash({"kind": kind, "experts": pinned})
    scope = (workspace_id, actor_id, "create_session", str(workspace_id), idempotency_key)
    async with connection.transaction():
        existing = await existing_receipt(connection, scope, fingerprint)
        if existing is not None:
            return await get_session(connection, workspace_id, UUID(existing["session_id"]))
        session_id = uuid4()
        await connection.execute(
            "insert into public.sessions (id, workspace_id, kind, experts, created_by) "
            "values (%s, %s, %s, %s, %s)",
            (session_id, workspace_id, kind, json.dumps(pinned), actor_id),
        )
        await store_receipt(connection, scope, fingerprint, {"session_id": str(session_id)})
    return await get_session(connection, workspace_id, session_id)


async def get_session(connection: Any, workspace_id: UUID, session_id: UUID) -> SessionView:
    cursor = await connection.execute(
        "select kind, experts from public.sessions where id = %s and workspace_id = %s",
        (session_id, workspace_id),
    )
    row = await cursor.fetchone()
    if row is None:
        raise ExpertRefused("session_not_found")
    options = [
        await _option(connection, workspace_id, UUID(item["expert_id"]), item["version"])
        for item in row[1]
    ]
    return SessionView(schema_version=1, id=session_id, kind=row[0], options=options)


@dataclass(frozen=True)
class RunBinding:
    """What a run freezes at admission. Later revisions and grants don't reach it."""

    session_id: UUID
    expert_id: UUID
    version: int
    instructions: str
    tools: dict[str, int]
    role_bindings: dict[str, str]


async def resolve_binding(
    connection: Any,
    workspace_id: UUID,
    session_id: UUID,
    *,
    expert_id: UUID | None = None,
    version: int | None = None,
) -> RunBinding:
    """A coordinator picks only among its own list. No model or tool is added by being routed."""
    cursor = await connection.execute(
        "select kind, experts from public.sessions where id = %s and workspace_id = %s",
        (session_id, workspace_id),
    )
    row = await cursor.fetchone()
    if row is None:
        raise ExpertRefused("session_not_found")
    kind, pinned = row
    if expert_id is None:
        if kind != "direct":
            raise ExpertRefused("route_needs_expert")
        entry = pinned[0]
    else:
        entry = next((item for item in pinned if item["expert_id"] == str(expert_id)), None)
        if entry is None:
            raise ExpertRefused("route_not_granted")
    chosen = version if version is not None else entry["version"]
    cursor = await connection.execute(
        "select v.config from public.expert_versions v join public.experts e on e.id = v.expert_id "
        "where v.expert_id = %s and v.version = %s and e.workspace_id = %s",
        (entry["expert_id"], chosen, workspace_id),
    )
    found = await cursor.fetchone()
    if found is None:
        raise ExpertRefused("expert_version_not_found")
    config = ExpertConfig.model_validate(found[0])
    references = await active_skill_text(connection, workspace_id, config.skills)
    return RunBinding(
        session_id=session_id,
        expert_id=UUID(entry["expert_id"]),
        version=chosen,
        instructions=config.instructions + references,
        tools={
            **PLAN_TOOLS,
            **{tool: EXPERT_TOOLS[tool] for tool in config.tools},
            **({DELEGATION_TOOL: 1} if kind == "coordinator" else {}),
        },
        role_bindings={role: profile.value for role, profile in config.role_bindings.items()},
    )
