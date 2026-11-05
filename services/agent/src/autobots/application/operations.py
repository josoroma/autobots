"""What an operator can see, LM-07: conditions and counts, never an address, path or secret."""

import asyncio
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

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
)
# Admission stops on these. A missing worker only means a job waits.
BLOCKING = frozenset({"database", "schema", "storage", "disk"})


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


async def database_conditions(pool: Any) -> tuple[Condition, Condition]:
    if pool is None:
        return (
            Condition("database", "unavailable", "database_not_configured"),
            Condition("schema", "unavailable", "schema_unknown"),
        )
    try:
        async with asyncio.timeout(DB_SECONDS), pool.connection() as connection:
            cursor = await connection.execute(
                "select count(*) from unnest(%s::text[]) r where to_regclass(r) is null",
                (list(REQUIRED_RELATIONS),),
            )
            row = await cursor.fetchone()
    except Exception as error:
        # Whatever it was, the database didn't answer. The type is logged, never its message.
        log_event(logger, "database.unavailable", logging.WARNING, error=type(error).__name__)
        return (
            Condition("database", "unavailable", "database_unreachable"),
            Condition("schema", "unavailable", "schema_unknown"),
        )
    missing = int(row[0])
    return (
        Condition("database", "ok", "database_ready"),
        Condition("schema", "ok", "schema_ready")
        if missing == 0
        else Condition("schema", "unavailable", "schema_behind"),
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
