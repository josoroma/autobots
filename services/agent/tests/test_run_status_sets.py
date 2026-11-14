"""R-11: each run-status set derives from RunStatus and TERMINAL, and equals the old literal."""

from autobots.domain.runs import IN_PROGRESS, INTERRUPTING, NEEDS_YOU, TERMINAL, RunStatus


def test_derived_sets_equal_the_literals_they_replaced() -> None:
    assert {status.value for status in TERMINAL} == {"succeeded", "failed", "cancelled"}
    assert {status.value for status in IN_PROGRESS} == {
        "queued",
        "running",
        "verifying",
        "paused",
        "cancelling",
    }
    assert {status.value for status in NEEDS_YOU} == {"waiting_approval", "waiting_input"}
    assert {status.value for status in INTERRUPTING} == {
        "cancelling",
        "cancelled",
        "failed",
        "succeeded",
    }


def test_the_list_groups_cover_every_status_once() -> None:
    assert IN_PROGRESS | NEEDS_YOU | TERMINAL == frozenset(RunStatus)
    assert not (IN_PROGRESS & NEEDS_YOU or IN_PROGRESS & TERMINAL or NEEDS_YOU & TERMINAL)


def test_a_status_read_from_the_database_matches_as_text() -> None:
    assert "cancelling" in INTERRUPTING and "queued" not in INTERRUPTING
