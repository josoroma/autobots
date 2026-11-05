"""Occurrence times, including daylight saving changes, with no database."""

from datetime import UTC, datetime, timedelta

import pytest

from autobots.domain.routines import (
    MAX_OCCURRENCES,
    TriggerInvalid,
    occurrences,
    occurrences_dropped,
    validate_trigger,
)


def utc(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


def test_a_daily_time_is_local_to_the_routine() -> None:
    found = occurrences(
        {"kind": "daily", "time": "09:00"},
        "America/Costa_Rica",
        utc(2026, 11, 5, 0),
        utc(2026, 11, 7, 0),
    )
    assert found == [utc(2026, 11, 5, 15), utc(2026, 11, 6, 15)]


def test_an_instant_at_the_start_is_excluded_and_at_the_end_included() -> None:
    trigger = {"kind": "daily", "time": "09:00"}
    assert (
        occurrences(trigger, "America/Costa_Rica", utc(2026, 11, 5, 15), utc(2026, 11, 5, 16)) == []
    )
    assert occurrences(
        trigger, "America/Costa_Rica", utc(2026, 11, 5, 14), utc(2026, 11, 5, 15)
    ) == [utc(2026, 11, 5, 15)]


def test_a_daily_time_keeps_its_wall_clock_across_daylight_saving() -> None:
    found = occurrences(
        {"kind": "daily", "time": "09:00"},
        "America/New_York",
        utc(2026, 10, 31, 0),
        utc(2026, 11, 3, 0),
    )
    assert found == [utc(2026, 10, 31, 13), utc(2026, 11, 1, 14), utc(2026, 11, 2, 14)]


def test_a_time_skipped_by_daylight_saving_still_runs_once() -> None:
    found = occurrences(
        {"kind": "daily", "time": "02:30"},
        "America/New_York",
        utc(2026, 3, 8, 0),
        utc(2026, 3, 9, 0),
    )
    assert len(found) == 1


def test_a_time_repeated_by_daylight_saving_runs_once() -> None:
    found = occurrences(
        {"kind": "daily", "time": "01:30"},
        "America/New_York",
        utc(2026, 11, 1, 0),
        utc(2026, 11, 2, 0),
    )
    assert len(found) == 1


def test_intervals_land_on_a_fixed_grid() -> None:
    trigger = {"kind": "interval", "minutes": 60}
    first = occurrences(trigger, "UTC", utc(2026, 11, 5, 0), utc(2026, 11, 5, 3))
    assert first == [utc(2026, 11, 5, 1), utc(2026, 11, 5, 2), utc(2026, 11, 5, 3)]
    assert occurrences(trigger, "UTC", utc(2026, 11, 5, 0, 30), utc(2026, 11, 5, 1)) == [
        utc(2026, 11, 5, 1)
    ]


@pytest.mark.parametrize(
    ("trigger", "timezone", "code"),
    [
        ({"kind": "daily", "time": "09:00"}, "Mars/Olympus", "timezone_unknown"),
        ({"kind": "cron"}, "UTC", "trigger_unknown"),
        ({"kind": "interval", "minutes": 0}, "UTC", "interval_invalid"),
        ({"kind": "interval", "minutes": True}, "UTC", "interval_invalid"),
        ({"kind": "daily", "time": "25:00"}, "UTC", "daily_time_invalid"),
    ],
)
def test_invalid_triggers(trigger: dict[str, object], timezone: str, code: str) -> None:
    with pytest.raises(TriggerInvalid, match=code):
        validate_trigger(trigger, timezone)


def test_after_long_away_the_newest_occurrences_are_kept_and_the_rest_counted() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = start + timedelta(hours=20)
    trigger = {"kind": "interval", "minutes": 1}
    found = occurrences(trigger, "UTC", start, end)
    assert len(found) == MAX_OCCURRENCES
    assert found[-1] == end
    assert occurrences_dropped(trigger, start, end, len(found)) == 200


def test_an_interval_too_long_to_compute_is_refused() -> None:
    with pytest.raises(TriggerInvalid):
        validate_trigger({"kind": "interval", "minutes": 10**10}, "UTC")
