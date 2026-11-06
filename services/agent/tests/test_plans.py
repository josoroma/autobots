"""What a proposed plan may not do. No database and no model."""

import pytest

from autobots.application.goal_loop import _opening
from autobots.application.plans import PlanRejected, validate_proposal
from autobots.contracts.plans import GoalSpec, PlanProposal, PlanTask, RequiredArtifact

GOAL = GoalSpec(
    objective="Report",
    original_request="Write the report",
    criteria={"c1": "Has a summary", "c2": "Has figures"},
    allowed_tools={"save_artifact": 1},
    allowed_paths=["outputs"],
)


def task(name: str, **fields: object) -> PlanTask:
    return PlanTask.model_validate(
        {"id": name, "title": name, "expected_evidence": "a file", "criteria": ["c1", "c2"]}
        | fields
    )


def proposal(*tasks: PlanTask, reason: str | None = None) -> PlanProposal:
    return PlanProposal(tasks=list(tasks), revision_reason=reason)


def rejected(*arguments: object) -> str:
    with pytest.raises(PlanRejected) as caught:
        validate_proposal(*arguments)  # type: ignore[arg-type]
    return caught.value.code


def test_a_covering_plan_is_valid() -> None:
    validate_proposal(GOAL, proposal(task("a")), None, frozenset())


def test_duplicate_tasks_are_refused() -> None:
    assert (
        rejected(GOAL, proposal(task("a"), task("a")), None, frozenset()) == "plan_duplicate_task"
    )


def test_unknown_dependencies_are_refused() -> None:
    plan = proposal(task("a", depends_on=["ghost"]))
    assert rejected(GOAL, plan, None, frozenset()) == "plan_unknown_dependency"


def test_cycles_are_refused() -> None:
    plan = proposal(task("a", depends_on=["b"]), task("b", depends_on=["a"]))
    assert rejected(GOAL, plan, None, frozenset()) == "plan_cycle"


def test_a_new_criterion_widens_scope() -> None:
    plan = proposal(task("a", criteria=["c1", "c2", "c3"]))
    assert rejected(GOAL, plan, None, frozenset()) == "plan_out_of_scope"


def test_a_tool_outside_the_goal_widens_scope() -> None:
    plan = proposal(task("a", tools=["send_email"]))
    assert rejected(GOAL, plan, None, frozenset()) == "plan_out_of_scope"


def test_a_plan_cannot_drop_a_criterion() -> None:
    plan = proposal(task("a", criteria=["c1"]))
    assert rejected(GOAL, plan, None, frozenset()) == "plan_uncovered_criteria"


def test_a_revision_needs_a_reason() -> None:
    previous = [task("a")]
    assert rejected(GOAL, proposal(task("a")), previous, frozenset()) == "plan_reason_required"
    assert (
        rejected(GOAL, proposal(task("a"), reason="  "), previous, frozenset())
        == "plan_reason_required"
    )


def test_a_revision_keeps_completed_work() -> None:
    previous = [task("a"), task("b")]
    done = frozenset({"a"})
    assert (
        rejected(GOAL, proposal(task("b"), reason="simpler"), previous, done)
        == "plan_drops_completed"
    )
    changed = task("a", title="something else")
    assert (
        rejected(GOAL, proposal(changed, task("b"), reason="reworded"), previous, done)
        == "plan_changes_completed"
    )
    validate_proposal(GOAL, proposal(task("a"), task("c"), reason="better"), previous, done)


def test_an_open_task_may_be_replaced() -> None:
    validate_proposal(GOAL, proposal(task("c"), reason="better"), [task("a")], frozenset())


def test_the_opening_says_a_goal_is_delivered_by_publishing() -> None:
    """Verification accepts only published files. A live model, not told so, saved and stopped."""
    required = RequiredArtifact(name="report.md", must_contain=["Trade-offs covered: 3"])
    goal = GOAL.model_copy(
        update={
            "allowed_tools": {"save_artifact": 1, "publish_artifact": 1},
            "required_artifacts": [required],
        }
    )
    opening = _opening(goal)
    assert "publish_artifact" in opening
    assert "named report.md" in opening
    assert '"Trade-offs covered: 3"' in opening
    assert "c1: Has a summary" in opening


def test_the_opening_names_no_tool_the_run_cannot_call() -> None:
    assert "publish" not in _opening(GOAL).lower()
