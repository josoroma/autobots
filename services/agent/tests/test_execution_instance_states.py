"""What an execution shows for each node instance, from its saved rows, its graph's nodes, the
instance in progress and its run's status, with plain values (PPRD-04, PPRD-16, refactor plan R-63).

A node with no saved row yet is waiting, or not run once the run has ended. The instance in progress
started, so on an ended run its effect may have happened: it shows where the run stopped, never
`not_run`. tests/db/major_check.py checks the same rule on a disposable database.
"""

import pytest

from autobots.domain.runs import RunStatus
from autobots.domain.workflow_execution import (
    InstanceState,
    UnsavedStatus,
    instance_key,
    instance_states,
    parse_instance_key,
    unsaved_status,
)

NODES = ("in", "each", "up", "all", "out")


def saved(key: str, status: str, error: str | None = None) -> InstanceState:
    node_id, iteration = parse_instance_key(key)
    return InstanceState(key, node_id, iteration, status, error)


@pytest.mark.parametrize(
    ("run_status", "pending", "expected"),
    [
        (RunStatus.RUNNING, False, UnsavedStatus.RUNNING),
        (RunStatus.QUEUED, False, UnsavedStatus.WAITING),
        (RunStatus.WAITING_APPROVAL, False, UnsavedStatus.WAITING_APPROVAL),
        # A pending request shows as the wait, whatever the run's status says.
        (RunStatus.RUNNING, True, UnsavedStatus.WAITING_APPROVAL),
        (RunStatus.CANCELLED, True, UnsavedStatus.WAITING_APPROVAL),
        (RunStatus.PAUSED, False, UnsavedStatus.STOPPED_HERE),
        (RunStatus.WAITING_INPUT, False, UnsavedStatus.STOPPED_HERE),
        (RunStatus.SUCCEEDED, False, UnsavedStatus.STOPPED_HERE),
        (RunStatus.FAILED, False, UnsavedStatus.STOPPED_HERE),
        (RunStatus.CANCELLED, False, UnsavedStatus.STOPPED_HERE),
    ],
)
def test_the_instance_in_progress_shows_where_its_run_is(
    run_status: RunStatus, pending: bool, expected: UnsavedStatus
) -> None:
    assert unsaved_status("up#1", "up#1", run_status, pending) is expected


@pytest.mark.parametrize("run_status", sorted(RunStatus))
def test_any_other_unsaved_instance_waits_until_its_run_ends(run_status: RunStatus) -> None:
    ended = run_status in {RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED}
    expected = UnsavedStatus.NOT_RUN if ended else UnsavedStatus.WAITING
    assert unsaved_status("out", "up#1", run_status, True) is expected
    assert unsaved_status("out", None, run_status, False) is expected


def test_saved_rows_unsaved_nodes_and_the_iteration_in_progress_in_graph_order() -> None:
    rows = [
        saved("up#0", "succeeded"),
        saved("in", "succeeded"),
        saved("each", "succeeded"),
    ]
    shown = instance_states(rows, NODES, "up#1", RunStatus.RUNNING, approval_pending=False)
    assert [(item.key, item.node_id, item.iteration, item.status) for item in shown] == [
        ("in", "in", None, "succeeded"),
        ("each", "each", None, "succeeded"),
        ("up#0", "up", 0, "succeeded"),
        ("up#1", "up", 1, UnsavedStatus.RUNNING),
        ("all", "all", None, UnsavedStatus.WAITING),
        ("out", "out", None, UnsavedStatus.WAITING),
    ]


def test_an_ended_run_shows_unstarted_nodes_as_not_run_and_keeps_saved_errors() -> None:
    rows = [saved("in", "succeeded"), saved("each", "failed", "foreach_over_bound")]
    shown = instance_states(rows, NODES, None, RunStatus.FAILED, approval_pending=False)
    assert [(item.key, item.status, item.error_code) for item in shown] == [
        ("in", "succeeded", None),
        ("each", "failed", "foreach_over_bound"),
        ("up", UnsavedStatus.NOT_RUN, None),
        ("all", UnsavedStatus.NOT_RUN, None),
        ("out", UnsavedStatus.NOT_RUN, None),
    ]


def test_a_node_in_progress_with_no_row_is_listed_once() -> None:
    rows = [saved("in", "succeeded")]
    shown = instance_states(rows, ("in", "ok", "out"), "ok", RunStatus.WAITING_APPROVAL, False)
    assert [(item.key, item.status) for item in shown] == [
        ("in", "succeeded"),
        ("ok", UnsavedStatus.WAITING_APPROVAL),
        ("out", UnsavedStatus.WAITING),
    ]


def test_a_saved_instance_in_progress_keeps_its_saved_status() -> None:
    rows = [saved("in", "succeeded"), saved("out", "running")]
    shown = instance_states(rows, ("in", "out"), "out", RunStatus.CANCELLED, False)
    assert [(item.key, item.status) for item in shown] == [("in", "succeeded"), ("out", "running")]


@pytest.mark.parametrize(("node_id", "iteration"), [("up", None), ("up", 0), ("up", 12)])
def test_an_instance_key_reads_back_as_its_node_and_iteration(
    node_id: str, iteration: int | None
) -> None:
    assert parse_instance_key(instance_key(node_id, iteration)) == (node_id, iteration)
