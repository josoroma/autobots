"""Occurrence times from a trigger and an IANA timezone, stored as UTC instants, PRD 10.4.

A trigger is parsed once into a typed schedule, from a request or from what a saved version stores,
and occurrences are computed from that (refactor plan R-52, XTYP-08).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from autobots.domain.errors import Refusal, RefusalKind

DEFAULT_TIMEZONE = "America/Costa_Rica"
MAX_OCCURRENCES = 1000
MAX_INTERVAL_MINUTES = 366 * 24 * 60
# A run of a routine the model saves through `cronjob` spends at most US$1 (Decision 0026 C5). A
# person's routine has no cap of its own: admission caps each run at the workspace's run limit
# (Decision 0029 F2).
MODEL_ROUTINE_LIMIT_MICRO_USD = 1_000_000


class TriggerInvalid(Refusal, ValueError):
    """A trigger or timezone a routine can't use. Its code names which part."""

    kind = RefusalKind.INVALID


@dataclass(frozen=True)
class IntervalTrigger:
    """Every `minutes`, on a fixed grid counted from 2000-01-01 UTC."""

    minutes: int


@dataclass(frozen=True)
class DailyTrigger:
    """Each day at the wall-clock time `at` where the routine lives. It carries no offset: the
    routine's timezone always decided the instant, even for a stored time written with one."""

    at: time


@dataclass(frozen=True)
class UnscheduledTrigger:
    """A saved daily trigger whose time isn't text, such as 12 or 1230. The routine service once
    accepted one by reading it through `str`, but scheduling never could, so the routine never ran.
    It reads, and is never scheduled (refactor plan R-52)."""

    time: object


Trigger = IntervalTrigger | DailyTrigger
SavedTrigger = Trigger | UnscheduledTrigger


def known_timezone(timezone: str) -> ZoneInfo:
    """The zone a routine lives in, for the Routines API and `cronjob` alike (Decision 0026 C5)."""
    try:
        return ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise TriggerInvalid("timezone_unknown") from None


def parse_trigger(trigger: Mapping[str, Any]) -> Trigger:
    """The typed schedule of a trigger mapping. It reads every form a saved version holds: a daily
    time is any that `time.fromisoformat` reads, such as 07:30, 07:30:45, 0730 or 07:30+05:00, and
    keys a kind doesn't use are ignored."""
    kind = trigger.get("kind")
    if kind == "interval":
        minutes = trigger.get("minutes")
        if (
            not isinstance(minutes, int)
            or isinstance(minutes, bool)
            or not 1 <= minutes <= MAX_INTERVAL_MINUTES
        ):
            raise TriggerInvalid("interval_invalid")
        return IntervalTrigger(minutes)
    if kind == "daily":
        text = trigger.get("time")
        if not isinstance(text, str):
            raise TriggerInvalid("daily_time_invalid")
        try:
            at = time.fromisoformat(text)
        except ValueError:
            raise TriggerInvalid("daily_time_invalid") from None
        return DailyTrigger(at.replace(tzinfo=None))
    raise TriggerInvalid("trigger_unknown")


def saved_trigger(trigger: Mapping[str, Any]) -> SavedTrigger:
    """A saved version's trigger, as `parse_trigger` reads it, except that a daily time that isn't
    text reads as unscheduled rather than failing the routine's every read."""
    if trigger.get("kind") == "daily" and not isinstance(trigger.get("time"), str):
        return UnscheduledTrigger(trigger.get("time"))
    return parse_trigger(trigger)


def _scheduled(trigger: SavedTrigger) -> Trigger:
    """Refuses to schedule an unscheduled trigger. The scheduler's evaluation of that routine fails,
    and leaves it due with nothing admitted, as before R-52."""
    if isinstance(trigger, UnscheduledTrigger):
        raise TriggerInvalid("daily_time_invalid")
    return trigger


def validate_trigger(trigger: Mapping[str, Any], timezone: str) -> Trigger:
    """The timezone, then the trigger, each refused with its own code."""
    known_timezone(timezone)
    return parse_trigger(trigger)


def wall_clock(trigger: DailyTrigger) -> str:
    """The time it runs at as text: `HH:MM`, with seconds only when it runs on one."""
    if trigger.at.second or trigger.at.microsecond:
        return trigger.at.isoformat()
    return trigger.at.isoformat(timespec="minutes")


def occurrences(
    saved: SavedTrigger, timezone: str, after: datetime, until: datetime
) -> list[datetime]:
    """UTC instants in (after, until], oldest first.

    A daily time means that wall-clock time where the routine lives, including across a daylight
    saving change. A time skipped by a change runs at the shifted instant, and a repeated one once.
    """
    found: list[datetime] = []
    trigger = _scheduled(saved)
    if isinstance(trigger, IntervalTrigger):
        step = timedelta(minutes=trigger.minutes)
        epoch = datetime(2000, 1, 1, tzinfo=UTC)
        count = (after - epoch) // step + 1
        last_count = (until - epoch) // step
        # After long enough away, the newest are what matter. `occurrences_dropped` counts the rest.
        count = max(count, last_count - MAX_OCCURRENCES + 1)
        moment = epoch + count * step
        while moment <= until:
            found.append(moment)
            moment += step
        return found
    zone = ZoneInfo(timezone)
    day = after.astimezone(zone).date()
    last = until.astimezone(zone).date()
    day = max(day, last - timedelta(days=MAX_OCCURRENCES))
    while day <= last:
        moment = datetime.combine(day, trigger.at, tzinfo=zone).astimezone(UTC)
        if after < moment <= until:
            found.append(moment)
        day += timedelta(days=1)
    return found[-MAX_OCCURRENCES:]


def occurrences_dropped(saved: SavedTrigger, after: datetime, until: datetime, listed: int) -> int:
    """How many fell before the listed ones, so history can say so. Exact for intervals, and within
    a day for daily times, which can move with daylight saving."""
    trigger = _scheduled(saved)
    if isinstance(trigger, IntervalTrigger):
        step = timedelta(minutes=trigger.minutes)
        epoch = datetime(2000, 1, 1, tzinfo=UTC)
        return max(0, (until - epoch) // step - (after - epoch) // step - listed)
    return max(0, (until - after).days - listed)
