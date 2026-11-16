"""A held-out replay's verdict, from its runs alone (Decision 0016). Pure, so it is tested alone."""

from collections.abc import Iterable
from typing import Literal

from autobots.domain.runs import TERMINAL, RunStatus

ReplayState = Literal["running", "passed", "failed"]


def replay_verdict(statuses: Iterable[RunStatus]) -> ReplayState:
    """Passed only when every run succeeded, failed as soon as any run ended otherwise, even while
    others still run, and running until then (PPRD-16). A replay always has at least one run, so
    its reader never asks about none."""
    found = list(statuses)
    if all(status is RunStatus.SUCCEEDED for status in found):
        return "passed"
    if any(status in TERMINAL and status is not RunStatus.SUCCEEDED for status in found):
        return "failed"
    return "running"
