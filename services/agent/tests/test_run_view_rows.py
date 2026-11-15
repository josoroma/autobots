"""Each run view maps its rows field by field (refactor plan R-54, XTYP-04, PRUN-12).

A row is built by column name, so these hold the other half: each view field takes the row field
of its own meaning, such as `tasks_complete` from `tasks_complete` and not from `tasks_total`. Every
value differs, so a swap fails. An unknown stored status raises instead of reaching a client.
"""

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

import pytest

from autobots.application.run_projection.inspector import (
    checkpoint_of,
    evidence_of,
    model_call_of,
    tool_attempt_of,
)
from autobots.application.run_projection.run_list import group_counts, run_list_item
from autobots.application.run_projection.summary import summary_of
from autobots.application.run_projection.workspace import (
    assignment_of,
    expert_binding_of,
    usage_summary,
    verification_of,
)
from autobots.application.sql import UnknownStoredValue
from autobots.persistence.rows import (
    AssignmentViewRow,
    CheckpointRow,
    ExpertBindingRow,
    ModelCallRow,
    PlanEvidenceRow,
    RunGroupCountRow,
    RunListRow,
    RunRow,
    RunUsageRow,
    ToolAttemptRow,
    VerificationRow,
)

RUN = UUID(int=1)
PARENT = UUID(int=2)
WORKSPACE = UUID(int=3)
CREATED = datetime(2026, 11, 15, 9, tzinfo=UTC)
UPDATED = datetime(2026, 11, 15, 10, tzinfo=UTC)


def test_a_runs_summary_takes_the_ledgers_figures_as_its_spend() -> None:
    summary = summary_of(
        RunRow(
            id=RUN,
            workspace_id=WORKSPACE,
            parent_run_id=PARENT,
            status="paused",
            created_at=CREATED,
            updated_at=UPDATED,
            charged_micro_usd=11,
            reserved_micro_usd=12,
            limit_micro_usd=13,
            lease_generation=14,
            checkpoint_thread_id="private",
            version=15,
            event_sequence=16,
        )
    )
    assert (summary.id, summary.workspace_id, summary.parent_run_id) == (RUN, WORKSPACE, PARENT)
    assert (summary.status, summary.created_at, summary.updated_at) == ("paused", CREATED, UPDATED)
    assert summary.version == 15
    budget = summary.budget
    assert (budget.spent_micro_usd, budget.reserved_micro_usd, budget.limit_micro_usd) == (
        11,
        12,
        13,
    )


LISTED = RunListRow(
    id=RUN,
    parent_run_id=PARENT,
    status="running",
    goal_summary="Compare the rates",
    created_at=CREATED,
    updated_at=UPDATED,
    label_kind="expert",
    label="Writer",
    stop_reason="budget_exhausted",
    tasks_total=7,
    tasks_complete=3,
    profiles=["openrouter_terra"],
    charged_micro_usd=21,
    reserved_micro_usd=22,
    unreported=True,
    limit_micro_usd=23,
)


def test_a_listed_run_takes_each_field_from_its_own_column() -> None:
    item = run_list_item(LISTED)
    assert (item.id, item.parent_run_id, item.status) == (RUN, PARENT, "running")
    assert (item.goal_summary, item.label_kind, item.label) == (
        "Compare the rates",
        "expert",
        "Writer",
    )
    assert (item.created_at, item.updated_at, item.stop_reason) == (
        CREATED,
        UPDATED,
        "budget_exhausted",
    )
    assert (item.tasks_complete, item.tasks_total, item.profiles) == (3, 7, ["openrouter_terra"])
    assert (item.charged_micro_usd, item.reserved_micro_usd, item.limit_micro_usd) == (21, 22, 23)
    assert item.unreported is True


def test_a_listed_run_shows_no_label_for_an_empty_one() -> None:
    assert run_list_item(replace(LISTED, label=None)).label is None


def test_a_listed_run_with_an_unknown_stored_value_raises() -> None:
    with pytest.raises(ValueError, match="archived"):
        run_list_item(replace(LISTED, status="archived"))
    with pytest.raises(UnknownStoredValue, match="routine"):
        run_list_item(replace(LISTED, label_kind="routine"))


def test_the_group_counts_take_the_total_as_all() -> None:
    counts = group_counts(RunGroupCountRow(total=9, active=4, needs_you=3, finished=2))
    assert (counts.all, counts.active, counts.needs_you, counts.finished) == (9, 4, 3, 2)


def test_usage_and_verification_take_their_own_columns() -> None:
    usage = usage_summary(
        RunUsageRow(
            model_calls=1, tool_dispatches=2, repairs=3, plan_revisions=4, stop_reason=None
        ),
        input_tokens=5,
        output_tokens=6,
    )
    assert (usage.model_calls, usage.tool_dispatches, usage.repairs, usage.plan_revisions) == (
        1,
        2,
        3,
        4,
    )
    assert (usage.input_tokens, usage.output_tokens) == (5, 6)
    verified = verification_of(VerificationRow(passed=False, unmet=["c2"], checks=3))
    assert (verified.passed, verified.unmet, verified.checks) == (False, ["c2"], 3)


def test_an_assignment_reads_its_status_from_the_constraints_vocabulary() -> None:
    row = AssignmentViewRow(
        id=RUN, child_run_id=PARENT, expert="Writer", status="open", outcome=None
    )
    view = assignment_of(row)
    assert (view.id, view.child_run_id, view.expert, view.status, view.outcome) == (
        RUN,
        PARENT,
        "Writer",
        "open",
        None,
    )
    with pytest.raises(UnknownStoredValue):
        assignment_of(
            AssignmentViewRow(
                id=RUN, child_run_id=PARENT, expert="Writer", status="closed", outcome="done"
            )
        )


def test_an_experts_roles_show_what_the_run_froze_then_the_experts_own() -> None:
    binding = expert_binding_of(
        ExpertBindingRow(
            name="Writer",
            version=4,
            allowed_tools={"web_search": 3, "propose_plan": 1},
            role_bindings={"executor": "openrouter_terra", "researcher": "openrouter_sol"},
            frozen_bindings={"executor": "openrouter_deepseek_flash"},
        )
    )
    assert (binding.name, binding.version, binding.tools) == ("Writer", 4, ["web_search"])
    assert binding.role_bindings == {
        "executor": "openrouter_deepseek_flash",
        "researcher": "openrouter_sol",
    }


CALL = ModelCallRow(
    id=RUN,
    run_id=PARENT,
    role="executor",
    attempt=2,
    status="succeeded",
    profile="openrouter_terra",
    wire_id="fixture/wire",
    upstream_provider=None,
    input_tokens=31,
    output_tokens=32,
    reasoning_tokens=33,
    charged_micro_usd=34,
    reserved_micro_usd=35,
    finish_reason="stop",
    failure_class="charge_not_reported",
    created_at=CREATED,
    reconciled=True,
    charge_source_unknown=False,
)


def test_a_model_call_takes_each_field_from_its_own_column() -> None:
    view = model_call_of(CALL, {})
    assert (view.id, view.run_id, view.role, view.attempt, view.status) == (
        RUN,
        PARENT,
        "executor",
        2,
        "succeeded",
    )
    assert (view.profile, view.wire_id, view.upstream_provider) == (
        "openrouter_terra",
        "fixture/wire",
        "unknown",
    )
    assert (view.input_tokens, view.output_tokens, view.reasoning_tokens) == (31, 32, 33)
    assert (view.reported_micro_usd, view.estimated_micro_usd) == (34, 35)
    assert (view.finish_reason, view.failure_class, view.created_at) == (
        "stop",
        "charge_not_reported",
        CREATED,
    )
    # Reconciled with only its charge missing, so its outcome was never in doubt.
    assert (view.reconciled, view.outcome_unknown, view.charge_source_unknown) == (
        True,
        False,
        False,
    )


def test_a_reconciled_call_that_failed_otherwise_had_an_unknown_outcome() -> None:
    view = model_call_of(replace(CALL, failure_class="transport", charge_source_unknown=True), {})
    assert (view.outcome_unknown, view.charge_source_unknown) == (True, True)
    with pytest.raises(ValueError, match="paid"):
        model_call_of(replace(CALL, status="paid"), {})


def test_a_tool_attempt_and_a_checkpoint_take_their_own_columns() -> None:
    attempt = tool_attempt_of(
        ToolAttemptRow(
            operation_id="op-1",
            tool_id="web_search",
            tool_version=2,
            status="unknown",
            failure_code="timeout",
            created_at=CREATED,
        )
    )
    assert (attempt.operation_id, attempt.tool_id, attempt.tool_version) == (
        "op-1",
        "web_search",
        2,
    )
    assert (attempt.status, attempt.failure_code, attempt.created_at) == (
        "unknown",
        "timeout",
        CREATED,
    )
    with pytest.raises(ValueError, match="lost"):
        tool_attempt_of(
            ToolAttemptRow(
                operation_id="op-1",
                tool_id="web_search",
                tool_version=2,
                status="lost",
                failure_code=None,
                created_at=CREATED,
            )
        )
    checkpoint = checkpoint_of(
        CheckpointRow(checkpoint_id="c2", parent_checkpoint_id="c1", step=4, source="loop")
    )
    assert (checkpoint.checkpoint_id, checkpoint.parent_checkpoint_id) == ("c2", "c1")
    assert (checkpoint.step, checkpoint.source) == (4, "loop")


def test_evidence_names_the_published_artifact_an_item_refers_to() -> None:
    artifact = UUID(int=7)
    row = PlanEvidenceRow(
        task_id="t1",
        evidence=[
            {"kind": "artifact", "reference": "runs/x/report.md"},
            {"kind": "note", "reference": "report.md"},
        ],
        summary="Wrote the report",
    )
    first, second = evidence_of(row, {"report.md": artifact})
    assert (first.task_id, first.kind, first.reference, first.summary) == (
        "t1",
        "artifact",
        "runs/x/report.md",
        "Wrote the report",
    )
    assert (first.artifact_id, second.artifact_id) == (artifact, None)
    assert evidence_of(PlanEvidenceRow(task_id="t2", evidence=None, summary=""), {}) == []
