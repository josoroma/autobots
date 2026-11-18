"""The tools a child's assignment narrows to (application/assignments.py). Found by US-11.12's
independent review (docs/engineering/evidence/US-11.12/), and filed in test_final_review.py until
refactor plan R-66 filed tests by module (PTST-05).
"""

import pytest

from autobots.application.assignments import narrowed_tools
from autobots.application.tool_definitions import ToolFailed
from autobots.domain.tools import DELEGATION_TOOL


def test_asking_for_delegation_the_parent_cant_give_is_refused() -> None:
    with pytest.raises(ToolFailed):
        narrowed_tools({"calculate": 1}, {"calculate": 1}, [DELEGATION_TOOL], 1, 2)
    assert DELEGATION_TOOL not in narrowed_tools(
        {"calculate": 1, DELEGATION_TOOL: 1}, {"calculate": 1}, ["calculate"], 1, 2
    )
