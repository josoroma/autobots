"""Boundary validation from the shared fixtures, and the conversion boundaries around it."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from pydantic import BaseModel, ValidationError

from autobots.contracts.adapters import run_from_row, run_summary_from_domain
from autobots.contracts.export import openapi_document
from autobots.contracts.runs import ErrorResponse, RunEvent, RunSummary
from autobots.contracts.workflows import WorkflowGraph
from autobots.domain.runs import (
    NORMAL_EXITS,
    TERMINAL,
    Actor,
    CommandRefused,
    RunCommand,
    RunStatus,
    can_transition,
    next_status,
)
from autobots.persistence.rows import RunRow
from conftest import SocketBlockedError

REPOSITORY = Path(__file__).resolve().parents[3]
CASES = json.loads((REPOSITORY / "contracts/fixtures/boundary-cases.json").read_text())
MODELS: dict[str, type[BaseModel]] = {
    "RunSummary": RunSummary,
    "RunEvent": RunEvent,
    "ErrorResponse": ErrorResponse,
    "WorkflowGraph": WorkflowGraph,
}
RUN_ID = UUID("11111111-1111-4111-8111-111111111111")
WORKSPACE_ID = UUID("22222222-2222-4222-8222-222222222222")
NOW = datetime(2026, 11, 5, tzinfo=UTC)


def row(**overrides: Any) -> RunRow:
    data: RunRow = {
        "id": RUN_ID,
        "workspace_id": WORKSPACE_ID,
        "parent_run_id": None,
        "status": "running",
        "created_at": NOW,
        "updated_at": NOW,
        "spent_micro_usd": 5,
        "reserved_micro_usd": 6,
        "limit_micro_usd": 7,
        "lease_generation": 3,
        "checkpoint_thread_id": "private-thread",
        "version": 1,
    }
    data.update(overrides)  # type: ignore[typeddict-item]
    return data


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_shared_boundary_case(case: dict[str, Any]) -> None:
    model = MODELS[case["model"]]
    encoded = json.dumps(case["value"])
    if case["valid"]:
        model.model_validate_json(encoded)
    else:
        with pytest.raises(ValidationError):
            model.model_validate_json(encoded)


def test_the_fixtures_cover_each_required_kind() -> None:
    names = " ".join(case["name"] for case in CASES if not case["valid"])
    for kind in ("identifier", "money", "timestamp", "enum", "private field"):
        assert kind in names


def test_a_response_built_from_a_row_holds_no_private_field() -> None:
    summary = run_summary_from_domain(run_from_row(row()))
    encoded = summary.model_dump_json()
    assert "private-thread" not in encoded
    assert "lease" not in encoded
    assert json.loads(encoded)["budget"]["spent_micro_usd"] == 5


def test_an_unknown_stored_status_does_not_reach_a_client() -> None:
    with pytest.raises(ValueError, match="not_a_status"):
        run_from_row(row(status="not_a_status"))


@pytest.mark.parametrize(
    ("current", "command", "actor"),
    [
        (RunStatus.VERIFYING, RunCommand.COMPLETE, Actor.USER),
        (RunStatus.QUEUED, RunCommand.CLAIM, Actor.USER),
        (RunStatus.PAUSED, RunCommand.PAUSE, Actor.WORKER),
        (RunStatus.RUNNING, RunCommand.RESUME, Actor.USER),
        (RunStatus.SUCCEEDED, RunCommand.RESUME, Actor.USER),
        (RunStatus.FAILED, RunCommand.CANCEL, Actor.USER),
        (RunStatus.RUNNING, RunCommand.CANCEL, Actor.WORKER),
    ],
)
def test_commands_refuse_the_wrong_actor_or_state(
    current: RunStatus, command: RunCommand, actor: Actor
) -> None:
    with pytest.raises(CommandRefused):
        next_status(current, command, actor)


def test_a_raw_payload_never_projects() -> None:
    from datetime import UTC, datetime
    from uuid import uuid4

    from autobots.application.run_projection import project_event, public_text

    now = datetime.now(UTC)
    for payload in (
        {"type": "model.reasoning", "text": "private"},
        {"type": "run.status_changed", "previous": "queued", "current": "paused", "extra": "x"},
        {"type": "run.status_changed", "previous": "queued"},
        "just text",
    ):
        assert project_event(uuid4(), 1, payload, now) is None
    good = {"type": "run.status_changed", "previous": "queued", "current": "paused"}
    assert project_event(uuid4(), 1, good, now) is not None
    assert public_text("key sk-or-abcdefgh here") == "key [redacted] here"
    assert public_text("Bearer abcdefghijklmnop") == "[redacted]"
    assert len(public_text("x" * 900)) == 500


def test_cancelling_twice_is_idempotent() -> None:
    assert next_status(RunStatus.CANCELLING, RunCommand.CANCEL, Actor.USER) is None
    assert next_status(RunStatus.CANCELLED, RunCommand.CANCEL, Actor.USER) is None
    assert (
        next_status(RunStatus.RUNNING, RunCommand.CANCEL, Actor.USER, has_active_work=True)
        is RunStatus.CANCELLING
    )
    assert next_status(RunStatus.QUEUED, RunCommand.CANCEL, Actor.USER) is RunStatus.CANCELLED


def test_terminal_runs_never_move() -> None:
    for current in TERMINAL:
        for following in RunStatus:
            assert not can_transition(current, following)


def test_normal_exits_match_sp_010() -> None:
    assert can_transition(RunStatus.QUEUED, RunStatus.RUNNING)
    assert can_transition(RunStatus.VERIFYING, RunStatus.SUCCEEDED)
    assert not can_transition(RunStatus.RUNNING, RunStatus.SUCCEEDED)
    assert not can_transition(RunStatus.PAUSED, RunStatus.RUNNING)
    assert not can_transition(RunStatus.CANCELLING, RunStatus.RUNNING)
    assert set(NORMAL_EXITS) | TERMINAL == set(RunStatus)


def test_cancellation_is_valid_from_every_nonterminal_state() -> None:
    for current in set(RunStatus) - TERMINAL:
        assert can_transition(current, RunStatus.CANCELLED)
    assert not can_transition(RunStatus.CANCELLING, RunStatus.CANCELLING)


def test_generation_needs_no_service_or_credential() -> None:
    """The socket block and missing key are in force here, so any connection attempt would fail."""
    with pytest.raises(SocketBlockedError):
        __import__("socket").create_connection(("127.0.0.1", 9))
    schemas = openapi_document()["components"]["schemas"]
    assert {"RunSummary", "RunEvent", "RunStatus", "ErrorResponse"} <= set(schemas)
    assert schemas["RunSummary"]["additionalProperties"] is False
