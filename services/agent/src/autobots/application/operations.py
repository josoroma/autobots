"""The installation's readiness conditions, LM-07: states and codes, never an address, path or
secret.

`readiness.installation_conditions` gathers the admission gate's conditions from here, and the API
adds the queue and worker conditions for Local Operations. Backups are read in `backups.py`, the
jobs chart and delayed routines in `job_activity.py`, and the other values Operations shows in
`operation_values.py` (POPS-04).
"""

import asyncio
import logging
import math
import shutil
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from autobots.adapters.checkpoints import adapter_identity, adapter_qualified
from autobots.application.schema_release import SHIPPED_MIGRATIONS
from autobots.logs import log_event

logger = logging.getLogger("autobots.operations")
DB_SECONDS = 3.0
STORAGE_SECONDS = 3.0
HEARTBEAT_FRESH_SECONDS = 60
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
    # Migrations 38 to 49 by Decision 0023 E2, and those added since, for a database with no
    # readable history.
    "app_private.tool_uses",
    "public.user_profiles",
    "public.workflow_drafts",
    "app_private.plan_task_times",
    "app_private.tool_key_settings",
)
# A migration can add only columns, which a relation check can't see. These are the ones the newest
# code relies on.
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
    ("app_private.tool_uses", "instance_key"),
    ("public.workflows", "description"),
    ("app_private.tool_key_settings", "value"),
    ("app_private.run_jobs", "failed_attempts"),
    ("app_private.run_jobs", "last_failure_type"),
    ("public.routines", "removed_at"),
    ("public.approval_requests", "review_detail"),
    ("public.approval_requests", "consumed_at"),
)
# Decision 0023 E2: the one function that counts the applied history, migration 49.
COUNT_FUNCTION = "app_private.applied_migration_count()"
# Admission stops on these. A missing worker only means a job waits.
BLOCKING = frozenset({"database", "schema", "storage", "disk", "hold", "adapter"})


@dataclass(frozen=True)
class Condition:
    name: str
    state: str  # ok, degraded or unavailable
    code: str


# Decision 0023 E2: a newer database than this code is shown, and doesn't stop admission.
NOT_BLOCKING = frozenset({"schema_ahead"})


def stops_admission(condition: Condition) -> bool:
    """A blocking check that isn't ok stops admission (LM-07), unless it only degrades by Decision
    0023 E2. The one rule behind `is_ready` and `readiness.first_blocking`."""
    return (
        condition.name in BLOCKING
        and condition.state != "ok"
        and condition.code not in NOT_BLOCKING
    )


def is_ready(conditions: tuple[Condition, ...] | list[Condition]) -> bool:
    return not any(stops_admission(item) for item in conditions)


# Decision 0022 D5: the database answer time is the p95 of the last 20 readiness probes.
PROBES_KEPT = 20


class ProbeTimes:
    """The last readiness probes' database answer times, in this process only. Nothing is traced
    or sent anywhere, and a restart starts the window again."""

    def __init__(self, kept: int = PROBES_KEPT) -> None:
        self._times: deque[float] = deque(maxlen=kept)

    def record(self, milliseconds: float) -> None:
        self._times.append(milliseconds)

    def count(self) -> int:
        return len(self._times)

    def p95(self) -> int | None:
        """Nearest rank, in whole milliseconds, rounded up so it never reads faster."""
        if not self._times:
            return None
        ordered = sorted(self._times)
        return math.ceil(ordered[math.ceil(0.95 * len(ordered)) - 1])


@dataclass(frozen=True)
class QueueCounts:
    queued: int
    claimed: int
    expired_leases: int
    oldest_queued_seconds: int


async def database_conditions(
    pool: Any, probes: ProbeTimes | None = None
) -> tuple[Condition, Condition, Condition, Condition]:
    """One readiness probe. When the database answers, its answer time joins `probes`."""
    if pool is None:
        return (
            Condition("database", "unavailable", "database_not_configured"),
            Condition("schema", "unavailable", "schema_unknown"),
            Condition("hold", "unavailable", "hold_unknown"),
            Condition("adapter", "unavailable", "adapter_unknown"),
        )
    started = time.monotonic()
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
            applied = await _applied_if_readable(connection)
            held = False
            qualified = False
            if int(row[0]) == 0:
                cursor = await connection.execute(
                    "select 1 from app_private.installation_holds limit 1"
                )
                held = await cursor.fetchone() is not None
                qualified = await adapter_qualified(connection)
    except Exception as error:  # noqa: BLE001 - any failure means the database didn't answer; the type is logged
        # Whatever it was, the database didn't answer. The type is logged, never its message.
        log_event(logger, "database.unavailable", logging.WARNING, error=error)
        return (
            Condition("database", "unavailable", "database_unreachable"),
            Condition("schema", "unavailable", "schema_unknown"),
            Condition("hold", "unavailable", "hold_unknown"),
            Condition("adapter", "unavailable", "adapter_unknown"),
        )
    if probes is not None:
        probes.record((time.monotonic() - started) * 1000)
    missing = int(row[0]) + missing_columns
    return (
        Condition("database", "ok", "database_ready"),
        schema_condition(missing, applied),
        Condition("hold", "unavailable", "restore_hold")
        if held
        else Condition("hold", "ok", "no_hold"),
        Condition("adapter", "ok", "adapter_qualified")
        if qualified
        else Condition("adapter", "unavailable", "adapter_unqualified"),
    )


def schema_condition(missing: int, applied: int | None) -> Condition:
    """Behind when a required object is missing or fewer migrations are applied than this release
    ships. Ahead, which only degrades, when more are: older code on a newer database. With no
    readable history, the required objects decide."""
    if missing or (applied is not None and applied < SHIPPED_MIGRATIONS):
        return Condition("schema", "unavailable", "schema_behind")
    if applied is not None and applied > SHIPPED_MIGRATIONS:
        return Condition("schema", "degraded", "schema_ahead")
    return Condition("schema", "ok", "schema_ready")


async def _applied_if_readable(connection: Any) -> int | None:
    """The applied count, when the counting function exists. Its absence is not an error here."""
    cursor = await connection.execute("select to_regprocedure(%s) is not null", (COUNT_FUNCTION,))
    present = await cursor.fetchone()
    if not present or not present[0]:
        return None
    cursor = await connection.execute(f"select {COUNT_FUNCTION}")
    row = await cursor.fetchone()
    return None if row is None or row[0] is None else int(row[0])


async def storage_condition(store: Any) -> Condition:
    if store is None:
        return Condition("storage", "unavailable", "storage_not_configured")
    try:
        async with asyncio.timeout(STORAGE_SECONDS):
            await store.ping()
    except Exception as error:  # noqa: BLE001 - any failure means Storage didn't answer; the type is logged
        log_event(logger, "storage.unavailable", logging.WARNING, error=error)
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


async def live_workers(connection: Any) -> int:
    """Workers with a fresh heartbeat that haven't stopped, as the worker check counts."""
    cursor = await connection.execute(
        "select count(*) from app_private.worker_heartbeats where state <> 'stopped' "
        "and beat_at >= clock_timestamp() - make_interval(secs => %s)",
        (HEARTBEAT_FRESH_SECONDS,),
    )
    return int((await cursor.fetchone())[0])


async def applied_migrations(connection: Any) -> int | None:
    """The count only, through the one function that may read the migration history."""
    try:
        cursor = await connection.execute("select app_private.applied_migration_count()")
        row = await cursor.fetchone()
    except Exception as error:  # noqa: BLE001 - an unreadable migration table is reported, not raised
        log_event(logger, "migrations.unreadable", logging.WARNING, error=error)
        return None
    return None if row is None or row[0] is None else int(row[0])


def checkpoint_adapter() -> str:
    """The installed checkpoint adapter's package and release."""
    return f"langgraph-checkpoint-postgres {adapter_identity()[0]}"
