"""What a proposed plan may not do. No database and no model."""

import json

import pytest

from autobots.application.goal_loop import _opening
from autobots.application.plans import PlanRejected, reference_shape, validate_proposal
from autobots.application.tool_gateway import ToolResult
from autobots.contracts.plans import (
    CompleteTask,
    GoalSpec,
    PlanProposal,
    PlanTask,
    RequiredArtifact,
)
from autobots.domain.tools import ToolOutcome

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


@pytest.mark.parametrize(
    ("reference", "shape"),
    [
        ("outputs/report.md", "run_path"),
        ("inputs/brief.md", "run_path"),
        ("report.md", "bare_name"),
        ("anything a model wrote", "bare_name"),
        ("elsewhere/report.md", "other_path"),
        ("93380e77-e7a2-4a70-8d56-e103849a190f", "uuid"),
        ("6049275d483e43c3d2161a6e8f2fe6567568b1c454ba0801f4b76661a5b80a52", "sha256"),
    ],
)
def test_a_reference_is_recorded_by_its_form_and_never_its_text(reference: str, shape: str) -> None:
    assert reference_shape(reference) == shape


def test_a_rejection_says_which_part_widened_scope() -> None:
    with pytest.raises(PlanRejected) as criterion:
        validate_proposal(GOAL, proposal(task("a", criteria=["c1", "c2", "c3"])), None, frozenset())
    assert criterion.value.detail == "criterion"
    with pytest.raises(PlanRejected) as tool:
        validate_proposal(GOAL, proposal(task("a", tools=["send_email"])), None, frozenset())
    assert tool.value.detail == "tool"


def test_the_schema_a_model_sees_says_how_to_cite_evidence() -> None:
    reference = CompleteTask.model_json_schema()["$defs"]["Evidence"]["properties"]["reference"]
    assert "outputs/report.md" in reference["description"]
    assert "no version" in reference["description"]
    assert "operation_id" in reference["description"]


def test_a_reply_shows_the_operation_id_a_receipt_has_to_cite() -> None:
    effect = ToolResult(ToolOutcome.SUCCEEDED, output={}, operation_id="op-1")
    assert json.loads(effect.for_model())["operation_id"] == "op-1"
    assert "operation_id" not in json.loads(ToolResult(ToolOutcome.SUCCEEDED).for_model())


def test_the_opening_says_a_plan_cites_criteria_by_id() -> None:
    """Live, Sol cited a criterion by its text and turned a delivery step into a criterion, and
    the plan was refused as out of scope twice. The model is told the IDs, and that steps aren't
    criteria."""
    goal = GOAL.model_copy(update={"allowed_tools": {"save_artifact": 1, "publish_artifact": 1}})
    opening = _opening(goal)
    assert "criterion IDs from this list (c1, c2)" in opening
    assert "never their text, and no new criteria" in opening
    assert "These are steps, not criteria." in opening


def test_the_plan_schema_describes_criteria_as_ids() -> None:
    """What the model reads in propose_plan's own schema."""
    schema = PlanProposal.model_json_schema()
    described = schema["$defs"]["PlanTask"]["properties"]["criteria"]["description"]
    assert "IDs of the goal's criteria" in described and "such as c1" in described


def test_a_criterion_cited_by_its_text_is_still_refused() -> None:
    """The check itself is unchanged: only the listed IDs count."""
    cited = PlanTask(
        id="a",
        title="Write it",
        criteria=["c1: Has a summary", "c2"],
        expected_evidence="outputs/report.md",
    )
    with pytest.raises(PlanRejected) as refused:
        validate_proposal(GOAL, PlanProposal(tasks=[cited]), None, frozenset())
    assert (refused.value.code, refused.value.detail) == ("plan_out_of_scope", "criterion")
