"""The workspace's YOLO setting for browsing and what each run froze of it, Decision 0035 Y1 to Y4.

Kept in `app_private.browsing_settings` (migration 65): no row means on, at version 0, and every
change carries the expected version, like the tool switches. Admission freezes the workspace's
value in `runs.browsing_yolo` (`runs._insert_run_and_job`). A call is YOLO only while both the
run's frozen value and the workspace's current one are on, so turning it off applies at the next
call and turning it on reaches only runs admitted afterwards (Y4).
"""

import json
from dataclasses import dataclass
from uuid import UUID
from zoneinfo import ZoneInfo

from autobots.application.provider_settings import StaleVersion
from autobots.application.sql import SqlConnection, one, optional_row
from autobots.domain.browsing import BrowserKind


@dataclass(frozen=True)
class BrowsingSetting:
    yolo: bool
    version: int
    # Whether the owner has seen Home's one-time notice that YOLO is on (Y1).
    notice_seen: bool


@dataclass(frozen=True)
class _Row:
    yolo: bool
    version: int
    notice_seen: bool


@dataclass(frozen=True)
class _Domains:
    domains: str | None


@dataclass(frozen=True)
class _Browser:
    browser: str | None
    timezone: str | None


async def load(connection: SqlConnection, workspace_id: UUID) -> BrowsingSetting:
    row = await optional_row(
        connection,
        _Row,
        "select yolo, version, notice_seen_at is not null as notice_seen "
        "from app_private.browsing_settings where workspace_id = %s",
        (workspace_id,),
    )
    if row is None:
        return BrowsingSetting(yolo=True, version=0, notice_seen=False)
    return BrowsingSetting(row.yolo, row.version, row.notice_seen)


async def change(
    connection: SqlConnection, workspace_id: UUID, yolo: bool, expected: int
) -> BrowsingSetting:
    """Sets YOLO at its expected version. A stale version changes nothing."""
    async with connection.transaction():
        found = await optional_row(
            connection,
            _Row,
            "select yolo, version, notice_seen_at is not null as notice_seen "
            "from app_private.browsing_settings where workspace_id = %s for update",
            (workspace_id,),
        )
        current = found.version if found is not None else 0
        if current != expected:
            raise StaleVersion("the browsing setting changed; read it again")
        if found is None:
            await connection.execute(
                "insert into app_private.browsing_settings (workspace_id, yolo) values (%s, %s)",
                (workspace_id, yolo),
            )
        else:
            await connection.execute(
                "update app_private.browsing_settings set yolo = %s, version = version + 1, "
                "updated_at = now() where workspace_id = %s",
                (yolo, workspace_id),
            )
    return await load(connection, workspace_id)


async def notice_seen(connection: SqlConnection, workspace_id: UUID) -> BrowsingSetting:
    """Records that the owner saw Home's notice. Seeing it again changes nothing, and neither the
    setting nor its version moves, so a Settings page read before it still saves."""
    await connection.execute(
        "insert into app_private.browsing_settings (workspace_id, version, notice_seen_at) "
        "values (%s, 1, now()) on conflict (workspace_id) do update set notice_seen_at = "
        "coalesce(app_private.browsing_settings.notice_seen_at, excluded.notice_seen_at)",
        (workspace_id,),
    )
    return await load(connection, workspace_id)


async def call_is_yolo(connection: SqlConnection, run_id: UUID) -> bool:
    """Whether a call of this run is YOLO now: the run froze it on and the workspace has it on."""
    (yolo,) = await one(
        connection,
        "select r.browsing_yolo and coalesce((select s.yolo from app_private.browsing_settings s "
        "where s.workspace_id = r.workspace_id), true) from public.runs r where r.id = %s",
        (run_id,),
    )
    return bool(yolo)


async def expert_browse_domains(connection: SqlConnection, run_id: UUID) -> tuple[str, ...]:
    """The browse domains of the Expert version this run was admitted with, or none (Y3). A run
    with no Expert, or an Expert saved before the list existed, has none."""
    row = await optional_row(
        connection,
        _Domains,
        "select (v.config -> 'browse_domains')::text as domains from public.runs r "
        "join public.expert_versions v on v.expert_id = r.expert_id "
        "and v.version = r.expert_version where r.id = %s",
        (run_id,),
    )
    if row is None or row.domains is None:
        return ()
    listed = json.loads(row.domains)
    return tuple(str(domain) for domain in listed) if isinstance(listed, list) else ()


@dataclass(frozen=True)
class ExpertBrowser:
    """The browser a run's Expert names, and its workspace's time zone (Decision 0038 Z1, Z3)."""

    kind: BrowserKind
    timezone: str


async def expert_browser(connection: SqlConnection, run_id: UUID) -> ExpertBrowser:
    """The browser of the Expert version this run was admitted with. A run with no Expert, or an
    Expert saved before the choice existed, has the box. An unknown time zone reads as UTC."""
    row = await optional_row(
        connection,
        _Browser,
        "select v.config ->> 'browser' as browser, w.timezone from public.runs r "
        "join public.workspaces w on w.id = r.workspace_id "
        "left join public.expert_versions v on v.expert_id = r.expert_id "
        "and v.version = r.expert_version where r.id = %s",
        (run_id,),
    )
    if row is None:
        return ExpertBrowser("box", "UTC")
    zone = row.timezone or "UTC"
    try:
        ZoneInfo(zone)
    except (KeyError, ValueError, OSError):
        zone = "UTC"
    return ExpertBrowser("stealth" if row.browser == "stealth" else "box", zone)
