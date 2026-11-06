"""The root envelope from SP-008, counted in the database so a replacement worker inherits it."""

from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

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


class LimitReached(Exception):
    def __init__(self, counter: str) -> None:
        super().__init__(counter)
        self.code = f"{counter}_limit"


async def ensure_usage(connection: Any, run_id: UUID) -> None:
    await connection.execute(
        "insert into app_private.run_usage (run_id) values (%s) on conflict (run_id) do nothing",
        (run_id,),
    )


async def consume(connection: Any, run_id: UUID, counter: Counter, limit: int) -> int:
    """Atomic, so concurrent callers can't pass the limit together."""
    cursor = await connection.execute(COUNTER_SQL[counter], (run_id, limit))
    row = await cursor.fetchone()
    if row is None:
        raise LimitReached(counter)
    used: int = row[0]
    return used


async def begin_segment(connection: Any, run_id: UUID) -> None:
    """A segment a dead worker left open is closed at its start, since its end is unknown."""
    await connection.execute(
        "update app_private.run_usage set segment_started_at = clock_timestamp() where run_id = %s",
        (run_id,),
    )


async def end_segment(connection: Any, run_id: UUID) -> None:
    await connection.execute(
        "update app_private.run_usage set active_seconds = active_seconds + "
        "extract(epoch from clock_timestamp() - segment_started_at), segment_started_at = null "
        "where run_id = %s and segment_started_at is not null",
        (run_id,),
    )


async def discount_sleep(connection: Any, run_id: UUID, seconds: float) -> None:
    """A Mac asleep isn't a run working, so an open segment doesn't count that time."""
    await connection.execute(
        "update app_private.run_usage "
        "set segment_started_at = segment_started_at + make_interval(secs => %s) "
        "where run_id = %s and segment_started_at is not null",
        (seconds, run_id),
    )


async def active_seconds_used(connection: Any, run_id: UUID) -> float:
    cursor = await connection.execute(
        "select active_seconds + coalesce(extract(epoch from clock_timestamp() - "
        "segment_started_at), 0) from app_private.run_usage where run_id = %s",
        (run_id,),
    )
    row = await cursor.fetchone()
    return float(row[0]) if row else 0.0


async def usage_view(connection: Any, run_id: UUID) -> dict[str, Any]:
    cursor = await connection.execute(
        "select model_calls, tool_dispatches, repairs, plan_revisions, children, stop_reason "
        "from app_private.run_usage where run_id = %s",
        (run_id,),
    )
    row = await cursor.fetchone()
    names = ("model_calls", "tool_dispatches", "repairs", "plan_revisions", "children", "stop")
    return dict(zip(names, row or (0, 0, 0, 0, 0, None), strict=True))
