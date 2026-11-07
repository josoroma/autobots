"""What an operator can see, LM-07: conditions and counts, never an address, path or secret."""

import asyncio
import json
import logging
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from autobots.adapters.checkpoints import adapter_qualified
from autobots.operations.logs import log_event

logger = logging.getLogger("autobots.operations")
DB_SECONDS = 3.0
STORAGE_SECONDS = 3.0
HEARTBEAT_FRESH_SECONDS = 60
DEFAULT_MIN_FREE_BYTES = 2 * 1024**3
# The relations a release can't run without. Add the one a required new migration creates.
REQUIRED_RELATIONS = (
    "public.runs",
    "public.artifacts",
    "app_private.run_jobs",
    "app_private.tool_receipts",
    "agent_runtime.checkpoints",
    "app_private.workspace_retention",
    "app_private.worker_heartbeats",
    "app_private.installation_holds",
    "app_private.improvement_replays",
    "app_private.improvement_replay_runs",
    "agent_runtime.adapter_qualifications",
    "agent_runtime.route_qualifications",
)
# A migration can add only columns, which a relation check can't see. The newest code relies on.
REQUIRED_COLUMNS = (
    ("public.approval_requests", "policy_reason"),
    ("public.approval_requests", "resource_target"),
    ("public.approval_requests", "requested_by_agent"),
    ("public.approval_requests", "scope_snapshot"),
    ("public.approval_requests", "policy_version"),
    ("public.runs", "started_by"),
    ("app_private.tool_receipts", "failure_code"),
    ("app_private.model_invocations", "finish_reason"),
    ("app_private.model_invocations", "charge_source"),
)
RESTORES_SHOWN = 5
RESTORE_FIELDS = {"at", "result", "checks_passed", "checks_total"}
DELAYED_SHOWN = 10
CATALOG_CHECK_SECONDS = 3.0
# Admission stops on these. A missing worker only means a job waits.
BLOCKING = frozenset({"database", "schema", "storage", "disk", "hold", "adapter"})


@dataclass(frozen=True)
class Condition:
    name: str
    state: str  # ok, degraded or unavailable
    code: str


@dataclass(frozen=True)
class QueueCounts:
    queued: int
    claimed: int
    expired_leases: int
    oldest_queued_seconds: int


async def database_conditions(pool: Any) -> tuple[Condition, Condition, Condition, Condition]:
    if pool is None:
        return (
            Condition("database", "unavailable", "database_not_configured"),
            Condition("schema", "unavailable", "schema_unknown"),
            Condition("hold", "unavailable", "hold_unknown"),
            Condition("adapter", "unavailable", "adapter_unknown"),
        )
    try:
        async with asyncio.timeout(DB_SECONDS), pool.connection() as connection:
            cursor = await connection.execute(
                "select count(*) from unnest(%s::text[]) r where to_regclass(r) is null",
                (list(REQUIRED_RELATIONS),),
            )
            row = await cursor.fetchone()
            cursor = await connection.execute(
                "select count(*) from unnest(%s::text[], %s::text[]) c(rel, col) where not exists "
                "(select 1 from pg_attribute a where a.attrelid = to_regclass(c.rel) "
                "and a.attname = c.col and not a.attisdropped)",
                ([item[0] for item in REQUIRED_COLUMNS], [item[1] for item in REQUIRED_COLUMNS]),
            )
            missing_columns = int((await cursor.fetchone())[0])
            held = False
            qualified = False
            if int(row[0]) == 0:
                cursor = await connection.execute(
                    "select 1 from app_private.installation_holds limit 1"
                )
                held = await cursor.fetchone() is not None
                qualified = await adapter_qualified(connection)
    except Exception as error:
        # Whatever it was, the database didn't answer. The type is logged, never its message.
        log_event(logger, "database.unavailable", logging.WARNING, error=type(error).__name__)
        return (
            Condition("database", "unavailable", "database_unreachable"),
            Condition("schema", "unavailable", "schema_unknown"),
            Condition("hold", "unavailable", "hold_unknown"),
            Condition("adapter", "unavailable", "adapter_unknown"),
        )
    missing = int(row[0]) + missing_columns
    return (
        Condition("database", "ok", "database_ready"),
        Condition("schema", "ok", "schema_ready")
        if missing == 0
        else Condition("schema", "unavailable", "schema_behind"),
        Condition("hold", "unavailable", "restore_hold")
        if held
        else Condition("hold", "ok", "no_hold"),
        Condition("adapter", "ok", "adapter_qualified")
        if qualified
        else Condition("adapter", "unavailable", "adapter_unqualified"),
    )


async def storage_condition(store: Any) -> Condition:
    if store is None:
        return Condition("storage", "unavailable", "storage_not_configured")
    try:
        async with asyncio.timeout(STORAGE_SECONDS):
            await store.ping()
    except Exception as error:
        log_event(logger, "storage.unavailable", logging.WARNING, error=type(error).__name__)
        return Condition("storage", "unavailable", "storage_unreachable")
    return Condition("storage", "ok", "storage_ready")


def disk_condition(path: Path, minimum_free: int) -> Condition:
    """The host disk under the app's data. Docker's disk sits in its VM, with its own limit."""
    try:
        free = shutil.disk_usage(path).free
    except OSError:
        return Condition("disk", "unavailable", "disk_unreadable")
    if free < minimum_free:
        return Condition("disk", "degraded", "disk_low")
    return Condition("disk", "ok", "disk_ready")


def backup_age_hours(directory: str, now: datetime) -> int | None:
    """The newest manifest under the backup directory: when it was taken, and nothing else."""
    newest: datetime | None = None
    for path in Path(directory).glob("*/manifest.json") if directory else ():
        try:
            created = datetime.fromisoformat(json.loads(path.read_text())["created_at"])
        except (OSError, ValueError, KeyError):
            continue
        newest = created if newest is None or created > newest else newest
    return None if newest is None else max(int((now - newest).total_seconds() // 3600), 0)


def restore_history(directory: str, limit: int = RESTORES_SHOWN) -> list[dict[str, Any]]:
    """What `local_backup.py` wrote beside each backup, newest first. A bad line is skipped."""
    found: list[dict[str, Any]] = []
    for path in Path(directory).glob("*/restores.jsonl") if directory else ():
        try:
            lines = path.read_text().splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for line in lines:
            try:
                item = json.loads(line)
            except ValueError:
                continue
            if isinstance(item, dict) and set(item) == RESTORE_FIELDS:
                found.append(item)
    return sorted(found, key=lambda item: str(item.get("at")), reverse=True)[:limit]


async def delayed_occurrences(
    connection: Any, workspace_id: UUID, limit: int = DELAYED_SHOWN
) -> list[tuple[Any, ...]]:
    """Occurrences of this workspace's routines that didn't run at their time, newest first."""
    cursor = await connection.execute(
        "select r.name, o.occurrence_time, o.status, o.reason from public.routine_occurrences o "
        "join public.routines r on r.id = o.routine_id where r.workspace_id = %s "
        "and o.status in ('missed', 'skipped_overlap', 'blocked') "
        "order by o.occurrence_time desc limit %s",
        (workspace_id, limit),
    )
    return list(await cursor.fetchall())


async def openrouter_availability(
    fetch_catalog: Any, seconds: float = CATALOG_CHECK_SECONDS
) -> str:
    """The public catalog only, as a page load must not make a model call or wait long."""
    if fetch_catalog is None:
        return "unknown"
    try:
        payload = await asyncio.wait_for(fetch_catalog(), seconds)
    except (TimeoutError, OSError, ValueError):
        return "unavailable"
    return "available" if payload is not None else "unavailable"


async def queue_counts(connection: Any, workspace_id: UUID) -> QueueCounts:
    """Only this workspace's jobs."""
    cursor = await connection.execute(
        "select count(*) filter (where status = 'queued'), "
        "count(*) filter (where status = 'claimed' and lease_expires_at >= clock_timestamp()), "
        "count(*) filter (where status = 'claimed' and lease_expires_at < clock_timestamp()), "
        "coalesce(extract(epoch from clock_timestamp() - "
        "min(available_at) filter (where status = 'queued'))::bigint, 0) "
        "from app_private.run_jobs where workspace_id = %s",
        (workspace_id,),
    )
    row = await cursor.fetchone()
    return QueueCounts(int(row[0]), int(row[1]), int(row[2]), max(int(row[3]), 0))


def queue_condition(counts: QueueCounts) -> Condition:
    if counts.expired_leases:
        return Condition("queue", "degraded", "leases_expired")
    return Condition("queue", "ok", "queue_ready")


async def worker_condition(connection: Any, counts: QueueCounts) -> Condition:
    cursor = await connection.execute(
        "select count(*), count(*) filter (where claims_inference) "
        "from app_private.worker_heartbeats where state <> 'stopped' "
        "and beat_at >= clock_timestamp() - make_interval(secs => %s)",
        (HEARTBEAT_FRESH_SECONDS,),
    )
    row = await cursor.fetchone()
    live, claiming = int(row[0]), int(row[1])
    if live == 0:
        return Condition("worker", "degraded", "worker_absent")
    if counts.queued and claiming == 0:
        return Condition("worker", "degraded", "no_inference_worker")
    return Condition("worker", "ok", "worker_ready")


def is_ready(conditions: tuple[Condition, ...] | list[Condition]) -> bool:
    return all(item.state == "ok" for item in conditions if item.name in BLOCKING)
