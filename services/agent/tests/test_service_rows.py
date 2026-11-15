"""The service's other rows map field by field (refactor plan R-54, XTYP-04, PDOM-08, PPRD-12,
PTOL-13, POPS-17).

Each mapper takes every field from the row field of its own meaning, so these give every field a
different value and a swap fails. An unknown stored status or kind raises instead of reaching a
client, and a value the page shows from a model or a file is redacted.
"""

from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

import pytest

from autobots.application.artifacts import artifact_summary
from autobots.application.improvements import candidate_view
from autobots.application.job_activity import delayed_view
from autobots.application.memory import file_hit, memory_hit
from autobots.application.operations import queue_counts_of
from autobots.application.run_files import RunFile, run_file_of
from autobots.application.run_usage import usage_counts
from autobots.application.sql import UnknownStoredValue
from autobots.application.tool_uses import tool_use_view
from autobots.application.workflow_overview import execution_summary
from autobots.persistence.rows import (
    ArtifactRow,
    CandidateRow,
    DelayedOccurrenceRow,
    ExecutionSummaryRow,
    FileHitRow,
    MemoryHitRow,
    QueueCountRow,
    RunFileRow,
    ToolUseRow,
    UsageCountRow,
)

FIRST = UUID(int=1)
SECOND = UUID(int=2)
LOCAL = timezone(timedelta(hours=-6))
EARLIER = datetime(2026, 11, 15, 3, tzinfo=LOCAL)
LATER = datetime(2026, 11, 15, 3, 1, 40, tzinfo=LOCAL)
PLANTED = "sk-or-v1-abc123def456ghi789"


def test_an_artifact_takes_its_own_columns_and_its_listed_status() -> None:
    row = ArtifactRow(
        id=FIRST,
        run_id=SECOND,
        name="report.md",
        media_type="text/markdown",
        size_bytes=12,
        sha256="a" * 64,
        status="missing",
    )
    view = artifact_summary(row)
    assert (view.id, view.run_id, view.name, view.media_type) == (
        FIRST,
        SECOND,
        "report.md",
        "text/markdown",
    )
    assert (view.size_bytes, view.sha256, view.status) == (12, "a" * 64, "missing")
    with pytest.raises(UnknownStoredValue, match="staged"):
        artifact_summary(replace(row, status="staged"))


def test_a_candidate_takes_its_own_columns_and_its_vocabularies() -> None:
    row = CandidateRow(
        id=FIRST,
        kind="skill",
        key="figures",
        content="Read the table first.",
        status="regression_passed",
        regression_results={"failures": []},
    )
    view = candidate_view(row, None)
    assert (view.id, view.kind, view.key, view.content) == (
        FIRST,
        "skill",
        "figures",
        "Read the table first.",
    )
    assert (view.status, view.regression_results, view.replay) == (
        "regression_passed",
        {"failures": []},
        None,
    )
    with pytest.raises(UnknownStoredValue, match="habit"):
        candidate_view(replace(row, kind="habit"), None)
    with pytest.raises(UnknownStoredValue, match="archived"):
        candidate_view(replace(row, status="archived"), None)


TOOL_USE = ToolUseRow(
    id=7,
    run_id=FIRST,
    sequence_in_run=3,
    tool_id="web_search",
    tool_version=2,
    tool_group="web",
    provider="tavily",
    plan_version=4,
    task_id="t1",
    task_title="Find the rates",
    requested_at=EARLIER,
    finished_at=LATER,
    duration_ms=100_000,
    outcome="succeeded",
    code=None,
    input_public={"query": "rates"},
    output_public={"results": 5},
    input_digest="d" * 64,
    output_bytes=900,
    operation_id="op-1",
    provider_units=Decimal("1.5"),
    instance_key=None,
)


def test_a_tool_use_takes_each_field_from_its_own_column() -> None:
    view = tool_use_view(TOOL_USE)
    assert (view.id, view.run_id, view.sequence_in_run, view.tool_id, view.tool_version) == (
        7,
        FIRST,
        3,
        "web_search",
        2,
    )
    assert (view.group, view.provider, view.plan_version, view.task_id, view.task_title) == (
        "web",
        "tavily",
        4,
        "t1",
        "Find the rates",
    )
    assert (view.requested_at, view.finished_at, view.duration_ms) == (
        EARLIER.astimezone(UTC),
        LATER.astimezone(UTC),
        100_000,
    )
    assert (view.outcome, view.code, view.input_public, view.output_public) == (
        "succeeded",
        None,
        {"query": "rates"},
        {"results": 5},
    )
    assert (view.input_digest, view.output_bytes, view.operation_id, view.provider_units) == (
        "d" * 64,
        900,
        "op-1",
        1.5,
    )


def test_an_open_tool_use_shows_no_end_and_an_unknown_outcome_raises() -> None:
    open_use = tool_use_view(
        replace(TOOL_USE, finished_at=None, duration_ms=None, outcome=None, input_public=None)
    )
    assert (open_use.finished_at, open_use.duration_ms, open_use.outcome) == (None, None, None)
    assert open_use.input_public == {}
    assert tool_use_view(replace(TOOL_USE, duration_ms=-5)).duration_ms == 0
    with pytest.raises(ValueError, match="skipped"):
        tool_use_view(replace(TOOL_USE, outcome="skipped"))


EXECUTION = ExecutionSummaryRow(
    id=FIRST,
    run_id=SECOND,
    workflow_version=3,
    status="succeeded",
    started_at=EARLIER,
    run_updated_at=LATER,
    run_created_at=EARLIER,
    charged_micro_usd=11,
    reserved_micro_usd=12,
    unreported=True,
)


def test_an_execution_takes_its_own_columns_and_times_a_finished_run() -> None:
    view = execution_summary(EXECUTION)
    assert (view.id, view.run_id, view.version, view.status) == (FIRST, SECOND, 3, "succeeded")
    assert (view.charged_micro_usd, view.reserved_micro_usd, view.unreported) == (11, 12, True)
    assert (view.started_at, view.duration_seconds) == (EARLIER.astimezone(UTC), 100)
    assert execution_summary(replace(EXECUTION, status="running")).duration_seconds is None
    with pytest.raises(ValueError, match="archived"):
        execution_summary(replace(EXECUTION, status="archived"))


def test_queue_counts_and_usage_counts_take_their_own_columns() -> None:
    counts = queue_counts_of(
        QueueCountRow(queued=4, claimed=3, expired_leases=2, oldest_queued_seconds=90)
    )
    assert (counts.queued, counts.claimed, counts.expired_leases) == (4, 3, 2)
    assert counts.oldest_queued_seconds == 90
    ahead = QueueCountRow(queued=1, claimed=0, expired_leases=0, oldest_queued_seconds=-3)
    assert queue_counts_of(ahead).oldest_queued_seconds == 0
    usage = UsageCountRow(
        model_calls=1,
        tool_dispatches=2,
        repairs=3,
        plan_revisions=4,
        children=5,
        stop_reason="budget_exhausted",
    )
    assert usage_counts(usage) == {
        "model_calls": 1,
        "tool_dispatches": 2,
        "repairs": 3,
        "plan_revisions": 4,
        "children": 5,
        "stop": "budget_exhausted",
    }
    assert usage_counts(None) == dict.fromkeys(
        ("model_calls", "tool_dispatches", "repairs", "plan_revisions", "children"), 0
    ) | {"stop": None}


def test_a_delayed_occurrence_takes_its_own_columns_and_status() -> None:
    moment = EARLIER.astimezone(UTC)
    row = DelayedOccurrenceRow(
        name="Morning digest", occurrence_time=moment, status="blocked", reason="key_missing"
    )
    view = delayed_view(row, "Morning digest")
    assert (view.routine, view.occurrence_time, view.status, view.reason) == (
        "Morning digest",
        moment,
        "blocked",
        "key_missing",
    )
    with pytest.raises(UnknownStoredValue, match="admitted"):
        delayed_view(replace(row, status="admitted"), "Morning digest")


def test_a_memory_hit_and_a_file_hit_redact_what_they_show() -> None:
    memory = memory_hit(
        MemoryHitRow(
            id=FIRST,
            title=f"Rates {PLANTED}",
            headline=f"use {PLANTED}",
            source={"kind": "run"},
            created_at=EARLIER,
        )
    )
    assert PLANTED not in memory.title + memory.snippet
    assert memory.source == {
        "kind": "run",
        "memory_id": str(FIRST),
        "stored_at": EARLIER.isoformat(),
    }
    evidence = file_hit(
        FileHitRow(
            run_id=SECOND,
            path="outputs/rates.md",
            version=2,
            sha256="b" * 64,
            headline=f"with {PLANTED}",
            created_at=LATER,
        )
    )
    assert (evidence.kind, evidence.title) == ("evidence", "outputs/rates.md")
    assert PLANTED not in evidence.snippet
    assert evidence.source == {
        "run_id": str(SECOND),
        "path": "outputs/rates.md",
        "version": 2,
        "sha256": "b" * 64,
        "stored_at": LATER.isoformat(),
    }


def test_a_run_file_takes_its_own_columns() -> None:
    row = RunFileRow(version=3, sha256="c" * 64, content="Total: 2", media_type="text/markdown")
    assert run_file_of(row) == RunFile(3, "c" * 64, "Total: 2", "text/markdown")
