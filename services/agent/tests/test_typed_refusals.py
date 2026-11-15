"""Refusals and missing rows by name (refactor plan R-41: PDOM-13, PRUN-13, PPRD-17, XERR-07 and
XERR-15).

Every refusal whose code reaches a response has one shape: a stable code, from its class or its
raise, a kind that api/errors.py turns into a status, and an internal detail no response shows. A
run without a goal and a defect while approving a role are told apart from the conditions they used
to be caught as. test_refusal_responses.py holds what each route answers.
"""

import asyncio
from uuid import uuid4

import pytest

from autobots.adapters.tool_registry import catalog
from autobots.api.errors import STATUS
from autobots.application import experts, run_projection
from autobots.application.approvals import ApprovalRefused
from autobots.application.credentials.store import CredentialStorageUnavailable
from autobots.application.experts import ExpertRefused, validate_config
from autobots.application.improvements import ImprovementRefused
from autobots.application.memory import MemoryRefused
from autobots.application.plans import GoalMissing, load_goal
from autobots.application.provider_settings import StaleVersion, ValidationUnavailable
from autobots.application.routines import RoutineRefused
from autobots.application.run_admission import AdmissionRefused, ModelNotReady, PolicyNotOffered
from autobots.application.run_projection import InvalidCursor
from autobots.application.runs import IdempotencyConflict, RunNotFound
from autobots.application.tool_catalog import ToolsUnavailable
from autobots.application.workflows import WorkflowRefused
from autobots.contracts.experts import ExpertConfig
from autobots.domain.budgets import BudgetRefused
from autobots.domain.errors import Refusal, RefusalKind
from autobots.domain.models import ProfileNotOffered
from autobots.domain.routines import TriggerInvalid
from autobots.domain.runs import CommandRefused

CATALOG = catalog()


def test_every_kind_has_a_status() -> None:
    assert set(STATUS) == set(RefusalKind)


def test_a_code_comes_from_the_class_or_from_the_raise() -> None:
    fixed = IdempotencyConflict("this key was used with different content")
    assert (fixed.code, fixed.detail, str(fixed)) == (
        "idempotency_conflict",
        "this key was used with different content",
        "this key was used with different content",
    )
    raised = ApprovalRefused("approval_expired")
    assert (raised.code, raised.detail, str(raised)) == (
        "approval_expired",
        None,
        "approval_expired",
    )


def test_a_refused_transition_has_a_code_and_keeps_its_reason_internal() -> None:
    refused = CommandRefused("only a user cancels a run")
    assert (refused.code, refused.kind) == ("transition_refused", RefusalKind.CONFLICT)
    assert refused.detail == "only a user cancels a run"


def test_a_tool_list_stays_detail_beside_the_code() -> None:
    refused = ToolsUnavailable(["web_search", "fetch_url"])
    assert (refused.code, refused.tools, refused.detail) == (
        "tool_unavailable",
        ["web_search", "fetch_url"],
        "web_search, fetch_url",
    )


@pytest.mark.parametrize(
    ("refusal", "kind"),
    [
        (WorkflowRefused("workflow_not_found"), RefusalKind.NOT_FOUND),
        (WorkflowRefused("workflow_draft_not_found"), RefusalKind.NOT_FOUND),
        (WorkflowRefused("execution_not_found"), RefusalKind.NOT_FOUND),
        (WorkflowRefused("workflow_invalid"), RefusalKind.INVALID),
        (WorkflowRefused("workflow_name_taken"), RefusalKind.CONFLICT),
        (RoutineRefused("routine_target_not_found"), RefusalKind.NOT_FOUND),
        (RoutineRefused("draft_not_runnable"), RefusalKind.INVALID),
        (RoutineRefused("routine_version_conflict"), RefusalKind.CONFLICT),
        (RoutineRefused("interval_invalid"), RefusalKind.INVALID),
        (ImprovementRefused("version_not_found"), RefusalKind.NOT_FOUND),
        (ImprovementRefused("replay_running"), RefusalKind.CONFLICT),
        (ExpertRefused("session_not_found"), RefusalKind.NOT_FOUND),
        (ExpertRefused("route_not_granted"), RefusalKind.CONFLICT),
        (ExpertRefused("expert_tool_duplicated"), RefusalKind.INVALID),
        (MemoryRefused("expert_not_found"), RefusalKind.NOT_FOUND),
        (ApprovalRefused("approval_not_found"), RefusalKind.NOT_FOUND),
        (ApprovalRefused("approval_expired"), RefusalKind.CONFLICT),
        (BudgetRefused("budget_above_daily_cap"), RefusalKind.CONFLICT),
        (BudgetRefused("budget_off_step"), RefusalKind.INVALID),
        (AdmissionRefused("owner_required"), RefusalKind.FORBIDDEN),
        (AdmissionRefused("budget_conflict"), RefusalKind.INVALID),
        (ModelNotReady("credentials_required"), RefusalKind.CONFLICT),
        (ProfileNotOffered("arranged"), RefusalKind.INVALID),
        (PolicyNotOffered("arranged", named=True), RefusalKind.INVALID),
        (PolicyNotOffered("arranged", named=False), RefusalKind.CONFLICT),
        (RunNotFound("arranged"), RefusalKind.NOT_FOUND),
        (StaleVersion("arranged"), RefusalKind.CONFLICT),
        (ValidationUnavailable("arranged"), RefusalKind.UNAVAILABLE),
        (CredentialStorageUnavailable("arranged"), RefusalKind.UNAVAILABLE),
        (InvalidCursor("arranged"), RefusalKind.INVALID),
    ],
    ids=lambda value: getattr(value, "code", None) or str(value),
)
def test_each_code_names_its_kind(refusal: Refusal, kind: RefusalKind) -> None:
    """A kind is declared per code, not read from a suffix such as `not_found` (PAPI-05)."""
    assert refusal.kind is kind


def test_a_refusal_that_was_a_value_error_still_is_one() -> None:
    for refusal in (BudgetRefused("budget_off_step"), TriggerInvalid("interval_invalid")):
        assert isinstance(refusal, Refusal) and isinstance(refusal, ValueError)
    assert InvalidCursor("arranged").code == "invalid_cursor"


def test_a_profile_not_offered_keeps_the_reason_it_shows() -> None:
    refused = PolicyNotOffered("Sol isn't offered for new runs.", named=False)
    assert (refused.code, refused.reason, str(refused)) == (
        "model_not_offered",
        "Sol isn't offered for new runs.",
        "Sol isn't offered for new runs.",
    )


def test_an_unknown_role_is_refused_but_a_defect_while_checking_one_is_not(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = ExpertConfig.model_validate({"role_bindings": {"not_a_role": "openrouter_terra"}})
    with pytest.raises(ExpertRefused) as refused:
        validate_config(config, CATALOG, {})
    assert refused.value.code == "expert_role_unknown"

    def defect(_role: object) -> None:
        raise RuntimeError("arranged defect")

    monkeypatch.setattr(experts, "approved_role", defect)
    with pytest.raises(RuntimeError, match="arranged defect"):
        validate_config(config, CATALOG, {})


class NoRows:
    async def execute(self, *_: object) -> "NoRows":
        return self

    async def fetchone(self) -> None:
        return None


def test_a_run_without_a_goal_is_named_as_such() -> None:
    with pytest.raises(GoalMissing) as caught:
        asyncio.run(load_goal(NoRows(), uuid4()))
    assert isinstance(caught.value, LookupError)


def test_a_defect_reading_a_goal_is_not_shown_as_a_run_without_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only a missing goal leaves the objective empty. A KeyError is a defect, and surfaces."""

    async def found(*_args: object) -> tuple[object, ...]:
        return ()

    async def defect(*_args: object) -> None:
        raise KeyError("arranged defect")

    monkeypatch.setattr(run_projection, "_require_run", found)
    monkeypatch.setattr(run_projection, "_summary", lambda _row: None)
    monkeypatch.setattr(run_projection, "load_goal", defect)
    with pytest.raises(KeyError, match="arranged defect"):
        asyncio.run(run_projection.read_workspace(NoRows(), uuid4(), uuid4()))
