"""The root envelope from SP-008, counted in the database so a replacement worker inherits it."""

from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

from autobots.application.sql import SqlConnection, one, optional_row
from autobots.application.worker_leases import LeaseHolder
from autobots.domain.stops import StopCode
from autobots.persistence.rows import UsageCountRow

Counter = Literal["model_calls", "tool_dispatches", "repairs", "plan_revisions", "children"]
COUNTER_SQL: dict[Counter, str] = {
    "model_calls": "update app_private.run_usage set model_calls = model_calls + 1 "
    "where run_id = %s and model_calls < %s returning model_calls",
    "tool_dispatches": "update app_private.run_usage set tool_dispatches = tool_dispatches + 1 "
    "where run_id = %s and tool_dispatches < %s returning tool_dispatches",
    "repairs": "update app_private.run_usage set repairs = repairs + 1 "
    "where run_id = %s and repairs < %s returning repairs",
    "plan_revisions": "update app_private.run_usage set plan_revisions = plan_revisions + 1 "
    "where run_id = %s and plan_revisions < %s returning plan_revisions",
    "children": "update app_private.run_usage set children = children + 1 "
    "where run_id = %s and children < %s returning children",
}


@dataclass(frozen=True)
class RootLimits:
    """Application limits, not measured adequacy for every task."""

    model_calls: int = 24
    tool_dispatches: int = 40
    repairs: int = 1
    plan_revisions: int = 2
    child_levels: int = 2
    children: int = 4
    outstanding_assignments: int = 2
    active_seconds: float = 900.0


# Each counter's stop code, named in the stop table so a search finds it (PRUN-02, R-29).
LIMIT_CODES: dict[Counter, StopCode] = {
    "model_calls": StopCode.MODEL_CALLS_LIMIT,
    "tool_dispatches": StopCode.TOOL_DISPATCHES_LIMIT,
    "repairs": StopCode.REPAIRS_LIMIT,
    "plan_revisions": StopCode.PLAN_REVISIONS_LIMIT,
    "children": StopCode.CHILDREN_LIMIT,
}


class LimitReached(Exception):
    def __init__(self, counter: Counter) -> None:
        super().__init__(counter)
        self.code = LIMIT_CODES[counter]


async def ensure_usage(connection: SqlConnection, run_id: UUID) -> None:
    await connection.execute(
        "insert into app_private.run_usage (run_id) values (%s) on conflict (run_id) do nothing",
        (run_id,),
    )


async def consume(connection: SqlConnection, run_id: UUID, counter: Counter, limit: int) -> int:
    """Atomic, so concurrent callers can't pass the limit together."""
    cursor = await connection.execute(COUNTER_SQL[counter], (run_id, limit))
    row = await cursor.fetchone()
    if row is None:
        raise LimitReached(counter)
    used: int = row[0]
    return used


# Only for the worker that still owns the run, so a lost one can't start, end or move a new owner's
# segment (PRUN-20). Its parameters are the run and the lease's generation.
_HELD = "exists (select 1 from app_private.run_jobs j where j.run_id = %s and j.generation = %s)"


async def begin_segment(connection: SqlConnection, lease: LeaseHolder) -> None:
    """A segment a dead worker left open is closed at its start, since its end is unknown."""
    await connection.execute(
        "update app_private.run_usage set segment_started_at = clock_timestamp() "
        f"where run_id = %s and {_HELD}",
        (lease.run_id, lease.run_id, lease.generation),
    )


async def end_segment(connection: SqlConnection, lease: LeaseHolder) -> None:
    """A worker that lost the run reaches its own end after the new owner began, so without the
    fence it would count the new owner's time and close their segment."""
    await connection.execute(
        "update app_private.run_usage set active_seconds = active_seconds + "
        "greatest(extract(epoch from clock_timestamp() - segment_started_at), 0), "
        "segment_started_at = null "
        f"where run_id = %s and segment_started_at is not null and {_HELD}",
        (lease.run_id, lease.run_id, lease.generation),
    )


async def discount_sleep(connection: SqlConnection, lease: LeaseHolder, seconds: float) -> None:
    """A Mac asleep isn't a run working, so an open segment doesn't count that time.

    This isn't capped at the database's now. Docker's clock can lag a wake by half a minute, then
    jump, so a cap here clamps the discount to nothing and the jump then counts the whole sleep as
    work, which a real sleep showed in US-12.5. Reads floor at zero until the clock catches up. A
    connection lost just after this commits applies it twice, which at worst leaves that segment's
    active time uncounted. The money limits don't depend on it.
    """
    await connection.execute(
        "update app_private.run_usage "
        "set segment_started_at = segment_started_at + make_interval(secs => %s) "
        f"where run_id = %s and segment_started_at is not null and {_HELD}",
        (seconds, lease.run_id, lease.run_id, lease.generation),
    )


async def model_calls_used(connection: SqlConnection, run_id: UUID) -> int:
    """The model calls the run tree whose root is `run_id` has counted so far."""
    (used,) = await one(
        connection, "select model_calls from app_private.run_usage where run_id = %s", (run_id,)
    )
    return int(used)


async def active_seconds_used(connection: SqlConnection, run_id: UUID) -> float:
    cursor = await connection.execute(
        "select active_seconds + greatest(coalesce(extract(epoch from clock_timestamp() - "
        "segment_started_at), 0), 0) from app_private.run_usage where run_id = %s",
        (run_id,),
    )
    row = await cursor.fetchone()
    return float(row[0]) if row else 0.0


async def usage_view(connection: SqlConnection, run_id: UUID) -> dict[str, Any]:
    """The run's counters as a pass reports them, all zero before its first segment."""
    row = await optional_row(
        connection,
        UsageCountRow,
        "select model_calls, tool_dispatches, repairs, plan_revisions, children, stop_reason "
        "from app_private.run_usage where run_id = %s",
        (run_id,),
    )
    return usage_counts(row)


def usage_counts(row: UsageCountRow | None) -> dict[str, Any]:
    if row is None:
        row = UsageCountRow(
            model_calls=0,
            tool_dispatches=0,
            repairs=0,
            plan_revisions=0,
            children=0,
            stop_reason=None,
        )
    return {
        "model_calls": row.model_calls,
        "tool_dispatches": row.tool_dispatches,
        "repairs": row.repairs,
        "plan_revisions": row.plan_revisions,
        "children": row.children,
        "stop": row.stop_reason,
    }
