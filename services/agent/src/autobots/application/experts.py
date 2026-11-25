"""Experts, immutable revisions, sessions and bounded routing, PRD 8.2 and 8.3."""

import json
import os
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any
from uuid import UUID, uuid4

from autobots.application.idempotency import (
    ExpectedVersionStale,
    VersionedRowMissing,
    next_version,
    receipted,
    set_latest,
)
from autobots.application.knowledge import active_skill_text
from autobots.application.runs import CommandKey, Idempotent
from autobots.application.sql import SqlConnection, all_rows, optional_row
from autobots.application.tool_catalog import Catalog
from autobots.application.tool_keys import key_sources
from autobots.contracts.experts import (
    ExpertConfig,
    ExpertConfigView,
    ExpertVersionView,
    ExpertView,
    RouteOption,
    SessionExpert,
    SessionView,
)
from autobots.contracts.persisted import (
    ExpertCreatedReceipt,
    ExpertVersionReceipt,
    SessionCreatedReceipt,
)
from autobots.domain.errors import Refusal, RefusalKind
from autobots.domain.models import UnknownModelProfile, approved_role
from autobots.domain.tools import DELEGATION_TOOL, EXPERT_TOOLS, PLAN_TOOLS, without_retired
from autobots.persistence.records import ExpertConfigRecord, read_expert_config
from autobots.persistence.rows import ExpertRow, ExpertRunsRow, ExpertVersionRow, RouteOptionRow


def expert_overrides(config: ExpertConfigRecord) -> dict[str, str]:
    """A saved version's role bindings as run role overrides, the first step of MP-01's order
    (PRD-Model-Providers MP-01)."""
    return dict(config.role_bindings)


def expert_record(config: ExpertConfig) -> ExpertConfigRecord:
    """What a saved version stores, in the shape versions always had (refactor plan R-52)."""
    return ExpertConfigRecord(
        purpose=config.purpose,
        instructions=config.instructions,
        tools=tuple(config.tools),
        tool_groups=tuple(config.tool_groups),
        skills=tuple(config.skills),
        role_bindings={role: profile.value for role, profile in config.role_bindings.items()},
        browse_domains=tuple(config.browse_domains),
        browser=config.browser,
    )


def expert_view_config(record: ExpertConfigRecord) -> ExpertConfigView:
    """A saved version as the Experts API shows it, with no request bounds."""
    return ExpertConfigView.model_validate(
        {
            "purpose": record.purpose,
            "instructions": record.instructions,
            "tools": list(record.tools),
            "tool_groups": list(record.tool_groups),
            "skills": list(record.skills),
            "role_bindings": dict(record.role_bindings),
            "browse_domains": list(record.browse_domains),
            "browser": record.browser,
        }
    )


class ExpertRefused(Refusal):
    """A typed reason, and nothing changes. A configuration an Expert can't have is invalid."""

    kind = RefusalKind.INVALID
    kinds = MappingProxyType(
        {
            "expert_not_found": RefusalKind.NOT_FOUND,
            "session_not_found": RefusalKind.NOT_FOUND,
            "expert_version_not_found": RefusalKind.NOT_FOUND,
            "expert_name_taken": RefusalKind.CONFLICT,
            "expert_version_conflict": RefusalKind.CONFLICT,
            "route_needs_expert": RefusalKind.CONFLICT,
            "route_not_granted": RefusalKind.CONFLICT,
        }
    )


def expand_groups(
    config: ExpertConfig, catalog: Catalog, environ: Mapping[str, str]
) -> ExpertConfig:
    """Groups become explicit tools when a version is saved, so a tool added to a group later
    never changes a saved version (TC-06). A tool an editor didn't name stays out."""
    if not config.tool_groups:
        return config
    if len(set(config.tool_groups)) != len(config.tool_groups):
        raise ExpertRefused("expert_tool_group_duplicated")
    by_group = catalog.expert_groups(environ)
    tools = list(config.tools)
    for group in config.tool_groups:
        members = by_group.get(group, [])
        if not members:
            raise ExpertRefused("expert_tool_group_empty")
        tools += [tool for tool in members if tool not in tools]
    return config.model_copy(update={"tools": tools})


async def _workspace_keys(connection: SqlConnection, workspace_id: UUID) -> Mapping[str, str]:
    """PK-04: a tool's key may be saved for this workspace, so availability is the workspace's."""
    return await key_sources(connection, workspace_id, os.environ)


def drop_retired(config: ExpertConfig) -> ExpertConfig:
    """A retired tool, which a revision made from an earlier version may still name, is left out
    rather than refused (Decision 0036 R4)."""
    kept = without_retired(config.tools)
    return config if len(kept) == len(config.tools) else config.model_copy(update={"tools": kept})


def validate_config(config: ExpertConfig, catalog: Catalog, environ: Mapping[str, str]) -> None:
    """A revision can only name what exists and is available, by the catalog the composition edge
    passes (PK-02). Anything else is refused, not dropped, once `drop_retired` has run."""
    if any(tool not in EXPERT_TOOLS for tool in config.tools):
        raise ExpertRefused("expert_tool_not_available")
    if len(set(config.tools)) != len(config.tools):
        raise ExpertRefused("expert_tool_duplicated")
    if catalog.unavailable(config.tools, environ):
        raise ExpertRefused("expert_tool_unavailable")
    try:
        for role in config.role_bindings:
            approved_role(role)
    except UnknownModelProfile:
        raise ExpertRefused("expert_role_unknown") from None


async def _views(connection: SqlConnection, experts: list[ExpertRow]) -> list[ExpertView]:
    """Each Expert's view, from one read of its versions and one of its runs for all of them
    (PPRD-11)."""
    if not experts:
        return []
    ids = [expert.id for expert in experts]
    rows = await all_rows(
        connection,
        ExpertVersionRow,
        "select expert_id, version, config from public.expert_versions "
        "where expert_id = any(%s) order by expert_id, version",
        (ids,),
    )
    versions: dict[UUID, list[ExpertVersionView]] = defaultdict(list)
    for row in rows:
        versions[row.expert_id].append(
            ExpertVersionView(
                version=row.version, config=expert_view_config(read_expert_config(row.config))
            )
        )
    runs = await all_rows(
        connection,
        ExpertRunsRow,
        "select expert_id, count(*) as run_count, max(created_at) as last_run_at "
        "from public.runs where expert_id = any(%s) group by expert_id",
        (ids,),
    )
    ran = {row.expert_id: row for row in runs}
    return [
        ExpertView(
            schema_version=1,
            id=expert.id,
            name=expert.name,
            latest_version=expert.latest_version,
            versions=versions[expert.id],
            run_count=int(ran[expert.id].run_count) if expert.id in ran else 0,
            last_run_at=ran[expert.id].last_run_at if expert.id in ran else None,
        )
        for expert in experts
    ]


async def list_experts(connection: SqlConnection, workspace_id: UUID) -> list[ExpertView]:
    rows = await all_rows(
        connection,
        ExpertRow,
        "select id, name, latest_version from public.experts where workspace_id = %s order by name",
        (workspace_id,),
    )
    return await _views(connection, rows)


async def get_expert(connection: SqlConnection, workspace_id: UUID, expert_id: UUID) -> ExpertView:
    row = await optional_row(
        connection,
        ExpertRow,
        "select id, name, latest_version from public.experts where id = %s and workspace_id = %s",
        (expert_id, workspace_id),
    )
    if row is None:
        raise ExpertRefused("expert_not_found")
    (view,) = await _views(connection, [row])
    return view


async def create_expert(
    connection: SqlConnection,
    *,
    workspace_id: UUID,
    actor_id: UUID,
    idempotency_key: str,
    name: str,
    config: ExpertConfig,
    catalog: Catalog,
) -> ExpertView:
    # Over the request as sent, before its groups expand.
    command = Idempotent.of(
        CommandKey(workspace_id, actor_id, idempotency_key),
        "create_expert",
        str(workspace_id),
        {"name": name, "config": config.model_dump(mode="json")},
    )
    keys = await _workspace_keys(connection, workspace_id)
    config = expand_groups(drop_retired(config), catalog, keys)
    validate_config(config, catalog, keys)
    async with receipted(connection, command, ExpertCreatedReceipt) as receipt:
        if receipt.prior is not None:
            return await get_expert(connection, workspace_id, receipt.prior.expert_id)
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
            (expert_id, expert_record(config).stored(), actor_id),
        )
        await receipt.store(ExpertCreatedReceipt(expert_id=expert_id))
    return await get_expert(connection, workspace_id, expert_id)


async def add_version(
    connection: SqlConnection,
    *,
    workspace_id: UUID,
    actor_id: UUID,
    expert_id: UUID,
    idempotency_key: str,
    expected_version: int,
    config: ExpertConfig,
    catalog: Catalog,
) -> ExpertView:
    """A new revision. Earlier ones never change, so work holding them is unaffected."""
    command = Idempotent.of(
        CommandKey(workspace_id, actor_id, idempotency_key),
        "add_expert_version",
        str(expert_id),
        {"expected": expected_version, "config": config.model_dump(mode="json")},
    )
    keys = await _workspace_keys(connection, workspace_id)
    config = expand_groups(drop_retired(config), catalog, keys)
    validate_config(config, catalog, keys)
    async with receipted(connection, command, ExpertVersionReceipt) as receipt:
        if receipt.prior is not None:
            return await get_expert(connection, workspace_id, expert_id)
        try:
            version = await next_version(
                connection, "experts", expert_id, workspace_id, expected_version
            )
        except VersionedRowMissing:
            raise ExpertRefused("expert_not_found") from None
        except ExpectedVersionStale:
            raise ExpertRefused("expert_version_conflict") from None
        await connection.execute(
            "insert into public.expert_versions (expert_id, version, config, created_by) "
            "values (%s, %s, %s, %s)",
            (expert_id, version, expert_record(config).stored(), actor_id),
        )
        await set_latest(connection, "experts", expert_id, version)
        await receipt.store(ExpertVersionReceipt(version=version))
    return await get_expert(connection, workspace_id, expert_id)


def _route_option(row: RouteOptionRow) -> RouteOption:
    config = read_expert_config(row.config)
    return RouteOption(
        expert_id=row.expert_id,
        name=row.name,
        version=row.version,
        purpose=config.purpose,
        tools=list(config.tools),
        role_bindings=expert_overrides(config),
    )


async def _options(
    connection: SqlConnection, workspace_id: UUID, pinned: list[tuple[UUID, int]]
) -> list[RouteOption]:
    """Each pinned Expert version as a route option, in the order pinned, from one read. One this
    workspace doesn't have is refused as not found (PPRD-11)."""
    if not pinned:
        return []
    rows = await all_rows(
        connection,
        RouteOptionRow,
        "select e.id as expert_id, v.version, e.name, v.config from public.experts e "
        "join public.expert_versions v on v.expert_id = e.id "
        "join unnest(%s::uuid[], %s::int[]) as p(expert_id, version) "
        "on p.expert_id = e.id and p.version = v.version where e.workspace_id = %s",
        ([expert for expert, _ in pinned], [version for _, version in pinned], workspace_id),
    )
    found = {(row.expert_id, row.version): row for row in rows}
    missing = [item for item in pinned if item not in found]
    if missing:
        raise ExpertRefused("expert_not_found")
    return [_route_option(found[item]) for item in pinned]


async def latest_version_config(
    connection: SqlConnection, workspace_id: UUID, expert_id: UUID
) -> ExpertConfigRecord | None:
    """The Expert's latest saved version's configuration, if this workspace has that Expert."""
    cursor = await connection.execute(
        "select v.config from public.experts e join public.expert_versions v "
        "on v.expert_id = e.id and v.version = e.latest_version "
        "where e.id = %s and e.workspace_id = %s",
        (expert_id, workspace_id),
    )
    row = await cursor.fetchone()
    return None if row is None else read_expert_config(row[0])


async def saved_version(
    connection: SqlConnection, workspace_id: UUID, expert_id: UUID, version: int
) -> ExpertConfigRecord | None:
    """One saved version's configuration, if this workspace has that Expert and version."""
    cursor = await connection.execute(
        "select v.config from public.experts e join public.expert_versions v "
        "on v.expert_id = e.id where e.id = %s and e.workspace_id = %s and v.version = %s",
        (expert_id, workspace_id, version),
    )
    row = await cursor.fetchone()
    return None if row is None else read_expert_config(row[0])


async def _pinned(
    connection: SqlConnection, workspace_id: UUID, experts: list[SessionExpert]
) -> list[dict[str, Any]]:
    """The version a session pins for each Expert: the one asked for, or its latest, checked to
    be this workspace's."""
    pinned: list[dict[str, Any]] = []
    for item in experts:
        expert = await get_expert(connection, workspace_id, item.expert_id)
        version = item.version if item.version is not None else expert.latest_version
        await _options(connection, workspace_id, [(item.expert_id, version)])
        pinned.append({"expert_id": str(item.expert_id), "version": version})
    return pinned


async def _insert_session(
    connection: SqlConnection,
    workspace_id: UUID,
    actor_id: UUID,
    kind: str,
    pinned: list[dict[str, Any]],
) -> UUID:
    session_id = uuid4()
    await connection.execute(
        "insert into public.sessions (id, workspace_id, kind, experts, created_by) "
        "values (%s, %s, %s, %s, %s)",
        (session_id, workspace_id, kind, json.dumps(pinned), actor_id),
    )
    return session_id


async def create_session(
    connection: SqlConnection,
    *,
    workspace_id: UUID,
    actor_id: UUID,
    idempotency_key: str,
    kind: str,
    experts: list[SessionExpert],
) -> SessionView:
    """Pins the revisions, and for a coordinator, the only Experts it may route to. Its receipt
    fingerprints the versions it pinned, as it always has, so stored receipts keep matching."""
    if kind == "direct" and len(experts) != 1:
        raise ExpertRefused("session_needs_one_expert")
    pinned = await _pinned(connection, workspace_id, experts)
    command = Idempotent.of(
        CommandKey(workspace_id, actor_id, idempotency_key),
        "create_session",
        str(workspace_id),
        {"kind": kind, "experts": pinned},
    )
    async with receipted(connection, command, SessionCreatedReceipt) as receipt:
        if receipt.prior is not None:
            return await get_session(connection, workspace_id, receipt.prior.session_id)
        session_id = await _insert_session(connection, workspace_id, actor_id, kind, pinned)
        await receipt.store(SessionCreatedReceipt(session_id=session_id))
    return await get_session(connection, workspace_id, session_id)


async def open_session(
    connection: SqlConnection,
    *,
    workspace_id: UUID,
    actor_id: UUID,
    kind: str,
    experts: list[SessionExpert],
) -> UUID:
    """A session no person asked for, such as a workflow execution's for its agent steps. It
    pins and checks its Experts as `create_session` does, and stores no receipt, since no retry
    can name it again (PPRD-04)."""
    pinned = await _pinned(connection, workspace_id, experts)
    return await _insert_session(connection, workspace_id, actor_id, kind, pinned)


async def get_session(
    connection: SqlConnection, workspace_id: UUID, session_id: UUID
) -> SessionView:
    cursor = await connection.execute(
        "select kind, experts from public.sessions where id = %s and workspace_id = %s",
        (session_id, workspace_id),
    )
    row = await cursor.fetchone()
    if row is None:
        raise ExpertRefused("session_not_found")
    pinned = [(UUID(item["expert_id"]), item["version"]) for item in row[1]]
    options = await _options(connection, workspace_id, pinned)
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
    connection: SqlConnection,
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
    config = read_expert_config(found[0])
    references = await active_skill_text(connection, workspace_id, list(config.skills))
    return RunBinding(
        session_id=session_id,
        expert_id=UUID(entry["expert_id"]),
        version=chosen,
        instructions=config.instructions + references,
        tools={
            **PLAN_TOOLS,
            # A retired tool the saved version names is left out (Decision 0036 R3).
            **{tool: EXPERT_TOOLS[tool] for tool in without_retired(config.tools)},
            **({DELEGATION_TOOL: 1} if kind == "coordinator" else {}),
        },
        role_bindings=expert_overrides(config),
    )
