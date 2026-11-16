"""Which due occurrences a routine admits, and what each records, with plain values (SP-016,
Decision 0026 C6, PPRD-07, PPRD-16).

After time away, every due occurrence but the latest is recorded as missed, the first noting how
many earlier ones weren't listed, and only the latest catches up. Its outcome is admitted with a
run, skipped while an earlier run is active, or blocked with why.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from autobots.domain.routines import CatchUp, OccurrenceOutcome, catch_up

START = datetime(2026, 11, 15, 9, 0, tzinfo=UTC)
RUN = UUID("0e000000-0000-4000-8000-000000000001")


def hours(count: int) -> list[datetime]:
    return [START + timedelta(hours=index) for index in range(count)]


def test_nothing_due_catches_up_nothing() -> None:
    assert catch_up([], 0) is None


def test_one_due_occurrence_is_the_latest_and_misses_nothing() -> None:
    assert catch_up(hours(1), 0) == CatchUp(missed=(), latest=START)


def test_every_earlier_occurrence_is_missed_and_only_the_latest_catches_up() -> None:
    due = hours(3)
    assert catch_up(due, 0) == CatchUp(
        missed=((due[0], "host_away"), (due[1], "host_away")), latest=due[2]
    )


def test_the_first_missed_occurrence_says_how_many_earlier_were_not_listed() -> None:
    due = hours(3)
    found = catch_up(due, 7)
    assert found is not None
    assert found.missed == (
        (due[0], "host_away, 7 earlier not listed"),
        (due[1], "host_away"),
    )


def test_dropped_occurrences_with_nothing_missed_are_not_noted() -> None:
    assert catch_up(hours(1), 7) == CatchUp(missed=(), latest=START)


def test_an_outcome_unpacks_as_status_reason_and_run() -> None:
    status, reason, run_id = OccurrenceOutcome.admitted(RUN)
    assert (status, reason, run_id) == ("admitted", None, RUN)
    assert tuple(OccurrenceOutcome.skipped()) == ("skipped_overlap", "run_active", None)
    assert tuple(OccurrenceOutcome.blocked("missing_key")) == ("blocked", "missing_key", None)
