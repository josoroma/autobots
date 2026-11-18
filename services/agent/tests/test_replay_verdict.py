"""A held-out replay's verdict from its runs' statuses, with plain values (Decision 0016, PPRD-16).

It passes only when every run succeeded, fails as soon as any run ended otherwise, even while others
still run, and is running until then. tests/db/checks/improvement_check.py checks it against
stored runs.
"""

import pytest

from autobots.domain.improvements import replay_verdict
from autobots.domain.runs import RunStatus

S, F, C, R = RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED, RunStatus.RUNNING


@pytest.mark.parametrize(
    ("statuses", "verdict"),
    [
        ([S], "passed"),
        ([S, S, S], "passed"),
        ([F], "failed"),
        ([S, C], "failed"),
        ([R, F, S], "failed"),
        ([R], "running"),
        ([S, RunStatus.QUEUED], "running"),
        ([S, RunStatus.WAITING_APPROVAL, RunStatus.PAUSED], "running"),
    ],
)
def test_a_replay_passes_only_when_every_run_succeeded(
    statuses: list[RunStatus], verdict: str
) -> None:
    assert replay_verdict(statuses) == verdict


@pytest.mark.parametrize("status", sorted(set(RunStatus) - {S, F, C}))
def test_a_run_that_has_not_ended_keeps_the_replay_running(status: RunStatus) -> None:
    assert replay_verdict([S, status]) == "running"
