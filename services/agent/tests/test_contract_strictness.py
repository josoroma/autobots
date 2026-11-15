"""Strictness per value, and response fields typed by their vocabularies (refactor plan R-61,
PDOM-04, PDOM-05, XTYP-10).

FastAPI validates a request body as Python values, so these validate the same way: money, counts,
versions and flags refuse a string, a float or a boolean even in a lax model, which still reads a
UUID from its string. The shared boundary fixtures cover the cases JSON can tell apart in both
languages (contracts/fixtures/boundary-cases.json).
"""

from datetime import UTC, datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError

from autobots.contracts.experts import SessionCreate
from autobots.contracts.improvements import ReplayRequest, RollbackRequest
from autobots.contracts.operations import RetentionSettings
from autobots.contracts.primitives import MAX_SAFE_INTEGER, Count, Flag, MicroUsd, Version
from autobots.contracts.routines import OccurrenceView, RoutineEnabled
from autobots.contracts.run_commands import ModelCallReconciliation, RunRequest
from autobots.contracts.run_workspace import ModelCallView, RunListItem
from autobots.contracts.settings import ModelList, ModelPolicyUpdate
from autobots.contracts.workflows import ExecutionCreate, WorkflowExecutionSummary, WorkflowPublish
from autobots.domain.stops import StopCode

RUN = "11111111-1111-4111-8111-111111111111"
NOW = datetime(2026, 11, 5, tzinfo=UTC)


def refused(model: type[BaseModel], value: dict[str, Any]) -> bool:
    try:
        model.model_validate(value)
    except ValidationError:
        return True
    return False


@pytest.mark.parametrize(
    ("alias", "schema"),
    [
        (MicroUsd, {"type": "integer", "minimum": 0, "maximum": MAX_SAFE_INTEGER}),
        (Count, {"type": "integer", "minimum": 0}),
        (Version, {"type": "integer", "minimum": 1}),
        (Flag, {"type": "boolean"}),
    ],
)
def test_strictness_leaves_the_published_schema_as_it_was(
    alias: Any,  # noqa: ANN401 - an Annotated alias, which has no static type
    schema: dict[str, object],
) -> None:
    assert TypeAdapter(alias).json_schema() == schema


@pytest.mark.parametrize("amount", ["5000000", 5000000.0, True])
def test_a_run_request_refuses_money_that_isnt_an_integer(amount: object) -> None:
    assert refused(RunRequest, {"goal_text": "Report", "limit_micro_usd": amount})
    assert refused(RunRequest, {"goal_text": "Report", "budget_micro_usd": amount})


def test_a_lax_request_still_reads_identifiers_and_integers() -> None:
    request = RunRequest.model_validate(
        {"continues_run_id": RUN, "limit_micro_usd": 5_000_000, "expert_version": 2}
    )
    assert request.continues_run_id == UUID(RUN)
    assert request.limit_micro_usd == 5_000_000


@pytest.mark.parametrize(
    ("model", "value"),
    [
        (RunRequest, {"goal_text": "Report", "expert_version": "2"}),
        (RunRequest, {"goal_text": "Report", "budget_micro_usd": MAX_SAFE_INTEGER + 1}),
        (ReplayRequest, {"tasks": [{"goal_text": "g", "criteria": ["c"]}], "limit_micro_usd": "1"}),
        (RoutineEnabled, {"enabled": "no"}),
        (RoutineEnabled, {"enabled": "off"}),
        (RoutineEnabled, {"enabled": 0}),
        (
            ModelPolicyUpdate,
            {"expected_version": "3", "default_profile": None, "role_overrides": {}},
        ),
        (WorkflowPublish, {"expected_version": 1.0, "graph": {}}),
        (RollbackRequest, {"kind": "memory", "key": "k", "to_version": "1"}),
        (ExecutionCreate, {"version": "2"}),
        (ExecutionCreate, {"version": 1, "budget_micro_usd": "250000"}),
        (SessionCreate, {"kind": "direct", "experts": [{"expert_id": RUN, "version": "1"}]}),
        (RetentionSettings, {"run_days": "30"}),
        (ModelCallReconciliation, {"charged_micro_usd": MAX_SAFE_INTEGER + 1}),
    ],
)
def test_a_request_refuses_a_value_of_the_wrong_json_type(
    model: type[BaseModel], value: dict[str, Any]
) -> None:
    assert refused(model, value)


def test_the_same_requests_take_json_integers_and_booleans() -> None:
    assert RoutineEnabled.model_validate({"enabled": False}).enabled is False
    assert ExecutionCreate.model_validate({"version": "draft"}).version == "draft"
    assert ExecutionCreate.model_validate({"version": 2, "budget_micro_usd": 250_000}).version == 2
    assert RetentionSettings.model_validate({"run_days": 30}).run_days == 30


def occurrence(**overrides: object) -> dict[str, object]:
    return {
        "occurrence_time": NOW,
        "routine_version": 1,
        "status": "admitted",
        "reason": None,
        "run_id": None,
    } | overrides


def test_an_occurrence_has_a_utc_time_and_a_status_its_table_allows() -> None:
    view = OccurrenceView.model_validate(occurrence(occurrence_time=NOW.isoformat()))
    assert view.model_dump(mode="json")["occurrence_time"] == "2026-11-05T00:00:00Z"
    plus_two = datetime(2026, 11, 5, 2, tzinfo=timezone(timedelta(hours=2)))
    assert refused(OccurrenceView, occurrence(occurrence_time=plus_two))
    assert refused(OccurrenceView, occurrence(occurrence_time="2026-11-05T00:00:00"))
    assert refused(OccurrenceView, occurrence(status="queued"))


def run_row(**overrides: object) -> dict[str, object]:
    return {
        "id": RUN,
        "parent_run_id": None,
        "status": "failed",
        "goal_summary": "Report",
        "created_at": NOW,
        "updated_at": NOW,
        "label_kind": "goal",
        "label": None,
        "stop_reason": None,
        "tasks_complete": 0,
        "tasks_total": 0,
        "profiles": ["openrouter_retired_profile"],
        "charged_micro_usd": 0,
        "reserved_micro_usd": 0,
        "unreported": False,
        "limit_micro_usd": 1_000_000,
    } | overrides


@pytest.mark.parametrize("reason", ["budget_exceeded", "repair_limit:plan_cycle", "a_retired_code"])
def test_a_stop_reason_shows_any_stored_code(reason: str) -> None:
    item = RunListItem.model_validate(run_row(stop_reason=reason))
    assert item.model_dump(mode="json")["stop_reason"] == reason
    assert item.stop_reason == reason


def test_a_known_stop_code_is_one_of_the_published_codes() -> None:
    assert StopCode("budget_exceeded") is StopCode.BUDGET_EXCEEDED


def test_listed_money_is_exact_and_bounded() -> None:
    assert refused(RunListItem, run_row(charged_micro_usd=MAX_SAFE_INTEGER + 1))
    assert refused(RunListItem, run_row(limit_micro_usd=1.5))


def test_an_execution_summary_has_a_run_status_and_a_utc_start() -> None:
    summary = {
        "id": RUN,
        "run_id": RUN,
        "version": 1,
        "status": "succeeded",
        "charged_micro_usd": 0,
        "reserved_micro_usd": 0,
        "unreported": False,
        "started_at": NOW.isoformat(),
        "duration_seconds": 3,
    }
    assert WorkflowExecutionSummary.model_validate(summary).started_at == NOW
    assert refused(WorkflowExecutionSummary, summary | {"status": "done"})
    assert refused(WorkflowExecutionSummary, summary | {"started_at": "2026-11-05T02:00:00+02:00"})


def model_call(**overrides: object) -> dict[str, object]:
    return {
        "id": RUN,
        "run_id": RUN,
        "role": "a_retired_role",
        "attempt": 1,
        "status": "succeeded",
        "provider": "openrouter",
        "profile": "openrouter_retired_profile",
        "canonical_id": "unknown",
        "wire_id": "unknown",
        "upstream_provider": "unknown",
        "input_tokens": None,
        "output_tokens": None,
        "reasoning_tokens": None,
        "reported_micro_usd": None,
        "estimated_micro_usd": 10,
        "reconciled": False,
        "outcome_unknown": False,
        "charge_source_unknown": False,
        "finish_reason": None,
        "failure_class": None,
        "created_at": NOW,
    } | overrides


def test_a_model_call_keeps_retired_profiles_and_refuses_an_unknown_status() -> None:
    assert ModelCallView.model_validate(model_call()).profile == "openrouter_retired_profile"
    assert refused(ModelCallView, model_call(status="settled_reported"))
    assert refused(ModelCallView, model_call(estimated_micro_usd=-1))


def test_a_catalog_fetch_time_is_utc() -> None:
    listed = {"schema_version": 1, "catalog_status": "available", "models": []}
    assert ModelList.model_validate(listed | {"fetched_at": NOW}).fetched_at == NOW
    plus_two = datetime(2026, 11, 5, 2, tzinfo=timezone(timedelta(hours=2)))
    assert refused(ModelList, listed | {"fetched_at": plus_two})
