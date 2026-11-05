"""Occurrence times from a trigger and an IANA timezone, stored as UTC instants, PRD 10.4."""

from collections.abc import Mapping
from datetime import UTC, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_TIMEZONE = "America/Costa_Rica"
MAX_OCCURRENCES = 1000


class TriggerInvalid(ValueError):
    pass


def validate_trigger(trigger: Mapping[str, Any], timezone: str) -> None:
    try:
        ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise TriggerInvalid("timezone_unknown") from None
    kind = trigger.get("kind")
    if kind == "interval":
        minutes = trigger.get("minutes")
        if not isinstance(minutes, int) or isinstance(minutes, bool) or minutes < 1:
            raise TriggerInvalid("interval_invalid")
    elif kind == "daily":
        try:
            time.fromisoformat(str(trigger.get("time")))
        except ValueError:
            raise TriggerInvalid("daily_time_invalid") from None
    else:
        raise TriggerInvalid("trigger_unknown")


def occurrences(
    trigger: Mapping[str, Any], timezone: str, after: datetime, until: datetime
) -> list[datetime]:
    """UTC instants in (after, until], oldest first.

    A daily time means that wall-clock time where the routine lives, including across a daylight
    saving change. A time skipped by a change runs at the shifted instant, and a repeated one once.
    """
    found: list[datetime] = []
    if trigger["kind"] == "interval":
        step = timedelta(minutes=trigger["minutes"])
        epoch = datetime(2000, 1, 1, tzinfo=UTC)
        count = (after - epoch) // step + 1
        moment = epoch + count * step
        while moment <= until and len(found) < MAX_OCCURRENCES:
            found.append(moment)
            moment += step
        return found
    zone = ZoneInfo(timezone)
    wall = time.fromisoformat(trigger["time"])
    day = after.astimezone(zone).date()
    last = until.astimezone(zone).date()
    while day <= last and len(found) < MAX_OCCURRENCES:
        moment = datetime.combine(day, wall, tzinfo=zone).astimezone(UTC)
        if after < moment <= until:
            found.append(moment)
        day += timedelta(days=1)
    return found
