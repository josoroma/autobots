"""Occurrence times, including daylight saving changes, with no database."""

from datetime import UTC, datetime, time, timedelta

import pytest

from autobots.domain.routines import (
    MAX_OCCURRENCES,
    DailyTrigger,
    IntervalTrigger,
    TriggerInvalid,
    UnscheduledTrigger,
    occurrences,
    occurrences_dropped,
    saved_trigger,
    validate_trigger,
)


def utc(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=UTC)


def test_a_daily_time_is_local_to_the_routine() -> None:
    found = occurrences(
        DailyTrigger(time(9, 0)),
        "America/Costa_Rica",
        utc(2026, 11, 5, 0),
        utc(2026, 11, 7, 0),
    )
    assert found == [utc(2026, 11, 5, 15), utc(2026, 11, 6, 15)]


def test_an_instant_at_the_start_is_excluded_and_at_the_end_included() -> None:
    trigger = DailyTrigger(time(9, 0))
    assert (
        occurrences(trigger, "America/Costa_Rica", utc(2026, 11, 5, 15), utc(2026, 11, 5, 16)) == []
    )
    assert occurrences(
        trigger, "America/Costa_Rica", utc(2026, 11, 5, 14), utc(2026, 11, 5, 15)
    ) == [utc(2026, 11, 5, 15)]


def test_a_daily_time_keeps_its_wall_clock_across_daylight_saving() -> None:
    found = occurrences(
        DailyTrigger(time(9, 0)),
        "America/New_York",
        utc(2026, 10, 31, 0),
        utc(2026, 11, 3, 0),
    )
    assert found == [utc(2026, 10, 31, 13), utc(2026, 11, 1, 14), utc(2026, 11, 2, 14)]


def test_a_time_skipped_by_daylight_saving_still_runs_once() -> None:
    found = occurrences(
        DailyTrigger(time(2, 30)),
        "America/New_York",
        utc(2026, 3, 8, 0),
        utc(2026, 3, 9, 0),
    )
    assert len(found) == 1


def test_a_time_repeated_by_daylight_saving_runs_once() -> None:
    found = occurrences(
        DailyTrigger(time(1, 30)),
        "America/New_York",
        utc(2026, 11, 1, 0),
        utc(2026, 11, 2, 0),
    )
    assert len(found) == 1


def test_intervals_land_on_a_fixed_grid() -> None:
    trigger = IntervalTrigger(60)
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
        ({"kind": "daily", "time": 12}, "UTC", "daily_time_invalid"),
        ({"kind": "daily", "time": 1230}, "UTC", "daily_time_invalid"),
    ],
)
def test_invalid_triggers(trigger: dict[str, object], timezone: str, code: str) -> None:
    with pytest.raises(TriggerInvalid, match=code):
        validate_trigger(trigger, timezone)


@pytest.mark.parametrize(
    ("trigger", "parsed"),
    [
        ({"kind": "interval", "minutes": 15}, IntervalTrigger(15)),
        ({"kind": "interval", "minutes": 15, "time": None, "note": "x"}, IntervalTrigger(15)),
        ({"kind": "daily", "time": "09:00"}, DailyTrigger(time(9, 0))),
        ({"kind": "daily", "time": "07:30:45"}, DailyTrigger(time(7, 30, 45))),
        ({"kind": "daily", "time": "0730"}, DailyTrigger(time(7, 30))),
        ({"kind": "daily", "time": "T07:30"}, DailyTrigger(time(7, 30))),
        ({"kind": "daily", "time": "07"}, DailyTrigger(time(7, 0))),
        ({"kind": "daily", "time": "07:30+05:00"}, DailyTrigger(time(7, 30))),
    ],
)
def test_a_trigger_parses_once_into_its_typed_schedule(
    trigger: dict[str, object], parsed: IntervalTrigger | DailyTrigger
) -> None:
    """Every form a saved routine holds still parses, so no routine a person has is refused
    (Decision 0029 F2). An offset is dropped because the routine's timezone always replaced it."""
    assert validate_trigger(trigger, "America/Costa_Rica") == parsed


def test_a_saved_daily_time_that_is_not_text_reads_and_is_never_scheduled() -> None:
    saved = saved_trigger({"kind": "daily", "time": 12})
    assert saved == UnscheduledTrigger(12)
    with pytest.raises(TriggerInvalid, match="daily_time_invalid"):
        occurrences(saved, "UTC", utc(2026, 11, 5), utc(2026, 11, 7))
    with pytest.raises(TriggerInvalid, match="daily_time_invalid"):
        occurrences_dropped(saved, utc(2026, 11, 5), utc(2026, 11, 7), 0)
    assert saved_trigger({"kind": "daily", "time": "12"}) == DailyTrigger(time(12, 0))


def test_after_long_away_the_newest_occurrences_are_kept_and_the_rest_counted() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    end = start + timedelta(hours=20)
    trigger = IntervalTrigger(1)
    found = occurrences(trigger, "UTC", start, end)
    assert len(found) == MAX_OCCURRENCES
    assert found[-1] == end
    assert occurrences_dropped(trigger, start, end, len(found)) == 200


def test_an_interval_too_long_to_compute_is_refused() -> None:
    with pytest.raises(TriggerInvalid):
        validate_trigger({"kind": "interval", "minutes": 10**10}, "UTC")
