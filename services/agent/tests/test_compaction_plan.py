"""US-16.9, Decision 0034 C1: a compacted call's state block pins the run's plan, so the run
continues it instead of proposing one the plan guard refuses. The second live deep research run
lost its plan at its first compaction and failed at its repair limit."""

from uuid import uuid4

import pytest

from autobots.application.compaction import state_block
from autobots.application.plans import plan_task_record
from autobots.contracts.plans import GoalSpec, PlanTask
from sql_fakes import RuledConnection

GOAL = GoalSpec(
    objective="langchain for deep agents",
    original_request="langchain for deep agents",
    criteria={"c1": "langchain for deep agents"},
    allowed_tools={"google_search": 1, "save_artifact": 1},
    allowed_paths=["inputs", "outputs"],
)
TASKS = [
    PlanTask(id="search", title="Search Google", criteria=["c1"], expected_evidence="results"),
    PlanTask(id="collect", title="Collect sources", criteria=["c1"], expected_evidence="a file"),
    PlanTask(id="write", title="Write the document", criteria=["c1"], expected_evidence="a file"),
]


def connection(plan: list[object] | None, done: list[str]) -> RuledConnection:
    stored = [plan_task_record(task).document() for task in TASKS] if plan is None else plan
    return RuledConnection(
        ("app_private.run_obligations", []),
        ("public.approval_requests", []),
        ("app_private.plan_versions", [(1, stored)] if stored else []),
        ("app_private.plan_evidence", [(task,) for task in done]),
    )


@pytest.mark.asyncio
async def test_a_compacted_call_sees_the_runs_plan() -> None:
    block = await state_block(connection(None, ["search"]), uuid4(), GOAL)
    assert "Plan version 1, still in force:" in block
    assert "- search (done): Search Google [criteria: c1]" in block
    assert "- collect (open): Collect sources [criteria: c1]" in block
    assert "- write (open): Write the document [criteria: c1]" in block
    assert "complete each open task with complete_task" in block
    assert "revision_reason" in block and "keep completed tasks unchanged" in block
    # The pinned state is still there, ahead of the plan.
    assert block.index("Goal: langchain for deep agents") < block.index("Plan version 1")


@pytest.mark.asyncio
async def test_a_run_without_a_plan_says_so() -> None:
    block = await state_block(connection([], []), uuid4(), GOAL)
    assert "Plan: none yet. Propose one with propose_plan." in block
    for line in (
        "Goal: langchain for deep agents",
        "- c1: langchain for deep agents",
        "Allowed tools: google_search, save_artifact",
        "Allowed paths: inputs, outputs",
    ):
        assert line in block
