"""What a specialist's pass leaves its assignment, with plain values (PRD 8.2, PPRD-05).

A child that paused, is waiting on a person, or was lost leaves the assignment open, so the parent
stops and the same assignment continues later. Anything else closes it with the child's outcome,
code, status and tasks, each in its own named field.
"""

from typing import Any

import pytest

from autobots.application.assignments import ChildOutcome, outcome_of
from autobots.application.run_lifecycle import LoopResult
from autobots.application.tool_definitions import ToolFailed
from autobots.domain.runs import RunStatus
from autobots.domain.stops import GatewayCode, PassOutcome, StopCode


def result(outcome: PassOutcome, **changes: object) -> LoopResult:
    fields: dict[str, Any] = {
        "outcome": outcome,
        "code": None,
        "run_status": RunStatus.SUCCEEDED,
        "plan_version": 1,
        "completed": ("t1",),
        "remaining": ("t2",),
        "uncovered_criteria": (),
        "usage": {},
    }
    return LoopResult(**{**fields, **changes})


@pytest.mark.parametrize(
    ("finished", "code"),
    [
        (result(PassOutcome.STOPPED, run_status=RunStatus.PAUSED), GatewayCode.ASSIGNMENT_PAUSED),
        (result(PassOutcome.LOST, run_status=None), GatewayCode.ASSIGNMENT_LOST),
        (
            result(PassOutcome.STOPPED, code=StopCode.CHILDREN_SETTLING),
            GatewayCode.ASSIGNMENT_LOST,
        ),
        (
            result(PassOutcome.WAITING, run_status=RunStatus.WAITING_APPROVAL),
            GatewayCode.ASSIGNMENT_PAUSED,
        ),
        # A pause wins over a lost lease, as the run's own status says where it is.
        (result(PassOutcome.LOST, run_status=RunStatus.PAUSED), GatewayCode.ASSIGNMENT_PAUSED),
    ],
)
def test_a_child_that_has_not_finished_leaves_its_assignment_open(
    finished: LoopResult, code: GatewayCode
) -> None:
    with pytest.raises(ToolFailed) as refused:
        outcome_of(finished)
    assert refused.value.args == (code,)


def test_a_finished_child_closes_its_assignment_with_each_field_named() -> None:
    stopped = result(
        PassOutcome.STOPPED, code="budget_exhausted", run_status=RunStatus.FAILED, completed=()
    )
    assert outcome_of(stopped) == ChildOutcome(
        outcome=PassOutcome.STOPPED,
        code="budget_exhausted",
        run_status=RunStatus.FAILED,
        completed=[],
        remaining=["t2"],
    )
    assert outcome_of(result(PassOutcome.SUCCEEDED)) == ChildOutcome(
        outcome=PassOutcome.SUCCEEDED,
        code=None,
        run_status=RunStatus.SUCCEEDED,
        completed=["t1"],
        remaining=["t2"],
    )
