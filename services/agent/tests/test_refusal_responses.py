"""Every refusal a route answers with: its status, code and fixed wording, route by route (refactor
plan R-41, PAPI-05 and XERR-07).

Each case makes one application call a route depends on raise one refusal, through the app in
process over fakes (fake_api.py), and reads the reply. Where the refusal comes from pure rules, such
as a profile that isn't offered, the real rule raises it. The cases hold the answers each route gave
before api/errors.py became the one place that maps refusals, so none can change unnoticed. Each
family's codes are the ones its routes can raise today, read from their raise sites. No socket,
database or model is used.
"""

from collections.abc import AsyncIterator, Awaitable, Callable, Iterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import NoReturn, Self
from uuid import UUID

import pytest

from autobots.api import (
    approval_routes,
    artifact_routes,
    event_routes,
    expert_routes,
    improvement_routes,
    memory_routes,
    routine_routes,
    run_command_routes,
    run_reconcile_routes,
    run_routes,
    workflow_routes,
)
from autobots.api.dependencies import (
    keys_and_vars_settings,
    model_key_check,
    provider_settings,
    require_ready,
)
from autobots.api.errors import STATUS, refusal_message
from autobots.application import reconciliation
from autobots.application.approvals import ApprovalRefused
from autobots.application.artifacts import ArtifactUnavailable
from autobots.application.credentials.store import CredentialMissing, CredentialStorageUnavailable
from autobots.application.experts import ExpertRefused
from autobots.application.improvements import ImprovementRefused
from autobots.application.memory import MemoryRefused
from autobots.application.provider_settings import (
    EnvironmentManaged,
    InvalidKey,
    StaleVersion,
    ValidationUnavailable,
)
from autobots.application.reconciliation import ReconciliationRefused
from autobots.application.recovery import Outstanding
from autobots.application.routines import RoutineRefused
from autobots.application.run_admission import AdmissionRefused, ModelNotReady, PolicyNotOffered
from autobots.application.run_projection import InvalidCursor
from autobots.application.runs import IdempotencyConflict, LinkRefused, RunNotFound, VersionConflict
from autobots.application.tool_catalog import ToolsUnavailable
from autobots.application.workflows import WorkflowRefused
from autobots.domain.budgets import BudgetRefused
from autobots.domain.models import NOT_OFFERED_MESSAGE
from autobots.domain.runs import CommandRefused
from autobots.domain.workflows import GraphError
from fake_api import ApiClient

RUN = UUID("0b000000-0000-4000-8000-0000000000c1")
WORKFLOW = UUID("0b000000-0000-4000-8000-0000000000c2")
EXECUTION = UUID("0b000000-0000-4000-8000-0000000000c3")
EXPERT = UUID("0b000000-0000-4000-8000-0000000000c4")
SESSION = UUID("0b000000-0000-4000-8000-0000000000c5")
ROUTINE = UUID("0b000000-0000-4000-8000-0000000000c6")
CANDIDATE = UUID("0b000000-0000-4000-8000-0000000000c7")
APPROVAL = UUID("0b000000-0000-4000-8000-0000000000c8")
ARTIFACT = UUID("0b000000-0000-4000-8000-0000000000c9")

KEY_NEEDED = "Model-backed work needs a usable OpenRouter key."
KEY_REUSED = "This key was already used with different content."
ROUTING = "That routing isn't available."
SAVED_CONFLICT = "That conflicts with what is saved. Reload and try again."
DEEPSEEK = "DeepSeek isn't offered for new runs until it's qualified."
TOOL_MISSING = (
    "A tool this Expert grants is unavailable in this install. See Tools for what it needs."
)
BUDGET = {
    "budget_out_of_range": (422, "Choose a budget from US$0.25 to US$5.00."),
    "budget_off_step": (422, "Choose a budget in steps of US$0.25."),
    "budget_above_daily_cap": (
        409,
        "That budget is more than what's left of today's spending cap.",
    ),
}

GRAPH: dict[str, list[object]] = {"nodes": [], "links": []}
ROUTINE_CONFIG = {
    "target": {"kind": "expert", "id": str(EXPERT), "version": 1},
    "trigger": {"kind": "interval", "minutes": 60},
    "goal": "Check the inbox",
}
Body = Mapping[str, object] | None
Reply = tuple[int, str, str]


@dataclass(frozen=True)
class Case:
    """One request whose `patched` call, `module.name`, raises `refusal`, and today's reply."""

    request: str
    patched: str
    refusal: Exception
    expected: Reply
    body: Body = None

    @property
    def id(self) -> str:
        return f"{self.request} {type(self.refusal).__name__} {self.expected[1]}"


def raising(error: Exception) -> Callable[..., Awaitable[NoReturn]]:
    async def refuse(*_args: object, **_kwargs: object) -> NoReturn:
        raise error

    return refuse


class Settings:
    """Provider and Keys & vars settings: each write raises `error`, and the key check answers
    `intent`."""

    def __init__(self, error: Exception | None = None, intent: str = "ready") -> None:
        self.error = error
        self.intent = intent

    async def _refuse(self, *_args: object) -> None:
        if self.error is not None:
            raise self.error

    save_credential = disconnect = revalidate = save = remove = _refuse

    async def run_intent(self, _workspace_id: UUID) -> str:
        return self.intent

    @asynccontextmanager
    async def opened(self) -> AsyncIterator[Self]:
        """As a handler opens the settings it was given, on no connection at all."""
        yield self


def answer(client: ApiClient, request: str, body: Body = None) -> Reply:
    method, path = request.split(" ", 1)
    reply = client.http.request(
        method,
        path,
        json=body,
        headers={**client.headers(), "Idempotency-Key": "fixture-key"},
    )
    payload = reply.json()
    return reply.status_code, payload["code"], payload["message"]


async def nothing_outstanding(*_args: object) -> Outstanding:
    return Outstanding(0, 0, 0)


async def none(*_args: object) -> None:
    return None


async def no_effect(*_args: object) -> bool:
    return False


@pytest.fixture
def client(api_client: ApiClient, monkeypatch: pytest.MonkeyPatch) -> Iterator[ApiClient]:
    """Readiness passes, keys are ready, the run exists with nothing to reconcile, and artifact
    storage is configured."""
    api_client.app.dependency_overrides[require_ready] = lambda: None
    api_client.app.dependency_overrides[provider_settings] = lambda: Settings()
    api_client.app.dependency_overrides[model_key_check] = lambda: Settings().run_intent
    api_client.database.answer("select 1 from public.runs where id", (1,))
    api_client.app.state.object_store = object()
    monkeypatch.setattr(reconciliation, "outstanding", nothing_outstanding)
    monkeypatch.setattr(reconciliation, "has_unresolvable_effect", no_effect)
    monkeypatch.setattr(reconciliation, "execution_block", none)
    yield api_client


MODULES = {
    "approval_routes": approval_routes,
    "artifact_routes": artifact_routes,
    "event_routes": event_routes,
    "expert_routes": expert_routes,
    "improvement_routes": improvement_routes,
    "memory_routes": memory_routes,
    "routine_routes": routine_routes,
    "run_command_routes": run_command_routes,
    "run_reconcile_routes": run_reconcile_routes,
    "run_routes": run_routes,
    "workflow_routes": workflow_routes,
}


def _patched(monkeypatch: pytest.MonkeyPatch, case: Case) -> None:
    module, name = case.patched.split(".")
    monkeypatch.setattr(MODULES[module], name, raising(case.refusal))


def admission(refusal: Exception, expected: Reply) -> Case:
    return Case(
        "POST /v1/runs",
        "run_routes.admit_from_request",
        refusal,
        expected,
        {"goal_text": "Write the report"},
    )


# Run admission: each refusal admit_from_request raises (run_admission.py's nine steps).
ADMISSION = [
    admission(
        AdmissionRefused("session_required"),
        (422, "session_required", "An Expert is chosen through a session."),
    ),
    admission(
        AdmissionRefused("budget_conflict"),
        (422, "budget_conflict", "Choose a budget or a limit, not both."),
    ),
    admission(
        AdmissionRefused("owner_required"),
        (403, "owner_required", "Only an owner can choose an Expert version."),
    ),
    *(
        admission(BudgetRefused(code), (status, code, text))
        for code, (status, text) in BUDGET.items()
    ),
    *(
        admission(ModelNotReady(code), (409, code, KEY_NEEDED))
        for code in ("credentials_required", "credential_invalid", "credential_unavailable")
    ),
    # Only resolve_binding raises an ExpertRefused here.
    *(
        admission(ExpertRefused(code), (status, code, ROUTING))
        for code, status in (
            ("session_not_found", 404),
            ("expert_version_not_found", 404),
            ("route_needs_expert", 409),
            ("route_not_granted", 409),
        )
    ),
    admission(ToolsUnavailable(["web_search"]), (409, "tool_unavailable", TOOL_MISSING)),
    admission(PolicyNotOffered(DEEPSEEK, named=True), (422, "model_not_offered", DEEPSEEK)),
    admission(PolicyNotOffered(DEEPSEEK, named=False), (409, "model_not_offered", DEEPSEEK)),
    admission(IdempotencyConflict("arranged"), (409, "idempotency_conflict", KEY_REUSED)),
    admission(
        LinkRefused("arranged"),
        (
            409,
            "run_not_continuable",
            "Only a finished goal run of its own, in this workspace, can be continued.",
        ),
    ),
]

COMMAND_REFUSALS: list[tuple[Exception, Reply]] = [
    (IdempotencyConflict("arranged"), (409, "idempotency_conflict", KEY_REUSED)),
    (
        VersionConflict("arranged"),
        (409, "version_conflict", "The run changed. Reload and try again."),
    ),
    (RunNotFound("arranged"), (404, "run_not_found", "That run is not available.")),
    (
        CommandRefused("arranged"),
        (409, "transition_refused", "That is not allowed in the run's current state."),
    ),
]
COMMANDS = [
    Case(f"POST /v1/runs/{RUN}/{command}", "run_command_routes.apply_command", refusal, reply, body)
    for command, body in (
        ("input", {"expected_version": 1, "value": "yes"}),
        ("pause", {"expected_version": 1}),
        ("resume", {"expected_version": 1}),
        ("cancel", {"expected_version": 1}),
    )
    for refusal, reply in COMMAND_REFUSALS
]

EVIDENCE = {"outcome": "delivered", "evidence": "Seen in the destination", "generation": 1}
RECONCILIATION = [
    *(
        Case(
            f"POST /v1/runs/{RUN}/effects/op-1/reconcile",
            "run_reconcile_routes.record_evidence",
            ReconciliationRefused(code),
            (status, code, "That can't be recorded."),
            EVIDENCE,
        )
        for code, status in (
            ("operation_not_found", 404),
            ("operation_not_unknown", 409),
            ("operation_attempt_changed", 409),
        )
    ),
    Case(
        f"POST /v1/runs/{RUN}/effects/op-1/reconcile",
        "run_reconcile_routes.record_evidence",
        IdempotencyConflict("arranged"),
        (409, "idempotency_conflict", KEY_REUSED),
        EVIDENCE,
    ),
    Case(
        f"POST /v1/runs/{RUN}/model-calls/reconcile",
        "run_reconcile_routes.reconcile_oldest_uncertain_call",
        IdempotencyConflict("arranged"),
        (409, "idempotency_conflict", KEY_REUSED),
        {"charged_micro_usd": 10},
    ),
]

# WorkflowRefused's codes, each through one route; every workflow route follows below.
WORKFLOW_CODES: list[tuple[WorkflowRefused, Reply]] = [
    (
        WorkflowRefused("workflow_not_found"),
        (404, "workflow_not_found", "That workflow is not available."),
    ),
    (
        WorkflowRefused("workflow_draft_not_found"),
        (404, "workflow_draft_not_found", "This workflow has no saved draft."),
    ),
    (
        WorkflowRefused("workflow_version_not_found"),
        (404, "workflow_version_not_found", "That workflow is not available."),
    ),
    (
        WorkflowRefused("execution_not_found"),
        (404, "execution_not_found", "That workflow is not available."),
    ),
    (
        WorkflowRefused("workflow_version_conflict"),
        (409, "workflow_version_conflict", "A newer version was published. Reload and try again."),
    ),
    (WorkflowRefused("workflow_name_taken"), (409, "workflow_name_taken", SAVED_CONFLICT)),
    (
        WorkflowRefused(
            "workflow_invalid",
            [GraphError("node_unknown", "a"), GraphError("cycle", "b"), GraphError("cycle", "c")],
        ),
        (422, "workflow_invalid", "That isn't valid: cycle, node_unknown."),
    ),
    (
        WorkflowRefused("workflow_inputs_invalid", [GraphError("input_missing", "a")]),
        (422, "workflow_inputs_invalid", "That isn't valid: input_missing."),
    ),
    (
        WorkflowRefused("model_not_offered", reason=DEEPSEEK),
        (409, "model_not_offered", DEEPSEEK),
    ),
    (WorkflowRefused("model_not_offered"), (409, "model_not_offered", NOT_OFFERED_MESSAGE)),
]
WORKFLOW_ROUTES: list[tuple[str, str, Body]] = [
    (f"GET /v1/workflow-executions/{EXECUTION}", "read_execution", None),
    ("POST /v1/workflows", "create_workflow", {"name": "Fixture"}),
    (f"GET /v1/workflows/{WORKFLOW}/executions", "get_workflow", None),
    (f"GET /v1/workflows/{WORKFLOW}/preview?version=1", "get_workflow", None),
    (f"PUT /v1/workflows/{WORKFLOW}/draft", "save_draft", {"graph": GRAPH}),
    (f"DELETE /v1/workflows/{WORKFLOW}/draft", "discard_draft", None),
    (f"POST /v1/workflows/{WORKFLOW}/draft/publish", "publish_draft", {"expected_version": 0}),
    (f"PUT /v1/workflows/{WORKFLOW}/description", "set_description", {"description": "About"}),
    (f"GET /v1/workflows/{WORKFLOW}", "get_workflow", None),
    (
        f"POST /v1/workflows/{WORKFLOW}/versions",
        "publish_version",
        {"expected_version": 0, "graph": GRAPH},
    ),
    (f"POST /v1/workflows/{WORKFLOW}/executions", "create_execution", {"version": 1}),
]
WORKFLOWS = [
    *(
        Case(f"GET /v1/workflows/{WORKFLOW}", "workflow_routes.get_workflow", refusal, reply)
        for refusal, reply in WORKFLOW_CODES
    ),
    *(
        Case(request, f"workflow_routes.{name}", WorkflowRefused("workflow_not_found"), reply, body)
        for request, name, body in WORKFLOW_ROUTES
        for reply in [(404, "workflow_not_found", "That workflow is not available.")]
    ),
    *(
        Case(request, f"workflow_routes.{name}", IdempotencyConflict("arranged"), reply, body)
        for request, name, body in WORKFLOW_ROUTES
        if name in {"create_workflow", "publish_draft", "publish_version", "create_execution"}
        for reply in [(409, "idempotency_conflict", KEY_REUSED)]
    ),
    *(
        Case(
            f"POST /v1/workflows/{WORKFLOW}/executions",
            "workflow_routes.chosen_limit",
            BudgetRefused(code),
            (status, code, text),
            {"version": 1, "budget_micro_usd": 1_000_000},
        )
        for code, (status, text) in BUDGET.items()
    ),
]

IMPROVEMENT_CODES = [
    ("candidate_not_found", 404),
    ("version_not_found", 404),
    ("candidate_not_open", 409),
    ("candidate_already_decided", 409),
    ("regression_required", 409),
    ("replay_required", 409),
    ("replay_running", 409),
    ("task_drawn_from_proposal", 409),
]
REPLAY = {"tasks": [{"goal_text": "Do it", "criteria": ["Done"]}], "limit_micro_usd": 1000}
IMPROVEMENT_ROUTES: list[tuple[str, str, Body]] = [
    (f"POST /v1/improvements/{CANDIDATE}/regression", "run_regression", {"cases": []}),
    (f"POST /v1/improvements/{CANDIDATE}/replay", "request_replay", REPLAY),
    (f"POST /v1/improvements/{CANDIDATE}/decision", "decide", {"decision": "promote"}),
    ("POST /v1/knowledge/rollback", "rollback", {"kind": "skill", "key": "k", "to_version": 1}),
]
IMPROVEMENTS = [
    *(
        Case(
            request,
            f"improvement_routes.{name}",
            ImprovementRefused(code),
            (status, code, "That can't be done to this proposal."),
            body,
        )
        for request, name, body in IMPROVEMENT_ROUTES
        for code, status in IMPROVEMENT_CODES
    ),
    Case(
        f"POST /v1/improvements/{CANDIDATE}/replay",
        "improvement_routes.request_replay",
        IdempotencyConflict("arranged"),
        (409, "idempotency_conflict", "That key was used for a different replay."),
        REPLAY,
    ),
]

APPROVALS = [
    *(
        Case(
            f"POST /v1/approvals/{APPROVAL}/decision",
            "approval_routes.decide",
            ApprovalRefused(code),
            (status, code, "That decision can't be applied."),
            {"decision": "approve", "argument_hash": "a" * 64},
        )
        for code, status in (
            ("approval_not_found", 404),
            ("approval_mismatch", 409),
            ("approval_too_large", 409),
            ("approval_already_decided", 409),
            ("approval_run_not_waiting", 409),
            ("approval_expired", 409),
        )
    ),
    Case(
        f"POST /v1/approvals/{APPROVAL}/decision",
        "approval_routes.decide",
        IdempotencyConflict("arranged"),
        (409, "idempotency_conflict", "This key was used with a different decision."),
        {"decision": "approve", "argument_hash": "a" * 64},
    ),
]

# The codes the Expert routes can raise: validate_config, expand_groups, the name and version
# checks, get_expert, create_session and get_session (experts.py).
EXPERT_CODES = [
    ("expert_not_found", 404, "That is not available."),
    ("session_not_found", 404, "That is not available."),
    ("expert_name_taken", 409, SAVED_CONFLICT),
    ("expert_version_conflict", 409, SAVED_CONFLICT),
    *(
        (code, 422, "That configuration is not allowed.")
        for code in (
            "expert_tool_group_duplicated",
            "expert_tool_group_empty",
            "expert_tool_not_available",
            "expert_tool_duplicated",
            "expert_tool_unavailable",
            "expert_role_unknown",
            "session_needs_one_expert",
        )
    ),
]
EXPERT_ROUTES: list[tuple[str, str, Body]] = [
    ("POST /v1/experts", "create_expert", {"name": "Fixture", "config": {}}),
    (f"GET /v1/experts/{EXPERT}", "get_expert", None),
    (f"POST /v1/experts/{EXPERT}/versions", "add_version", {"expected_version": 1, "config": {}}),
    (
        "POST /v1/sessions",
        "create_session",
        {"kind": "direct", "experts": [{"expert_id": str(EXPERT)}]},
    ),
    (f"GET /v1/sessions/{SESSION}", "get_session", None),
]
EXPERTS = [
    *(
        Case(
            "POST /v1/experts",
            "expert_routes.create_expert",
            ExpertRefused(code),
            (status, code, text),
            body,
        )
        for code, status, text in EXPERT_CODES
        for body in [{"name": "Fixture", "config": {}}]
    ),
    *(
        Case(request, f"expert_routes.{name}", ExpertRefused("expert_not_found"), reply, body)
        for request, name, body in EXPERT_ROUTES
        for reply in [(404, "expert_not_found", "That is not available.")]
    ),
    *(
        Case(request, f"expert_routes.{name}", IdempotencyConflict("arranged"), reply, body)
        for request, name, body in EXPERT_ROUTES
        if request.startswith("POST")
        for reply in [(409, "idempotency_conflict", KEY_REUSED)]
    ),
]

# The codes the routine routes can raise: _validate, the name and version checks, get_routine and
# set_enabled (routines.py). Of the domain's trigger codes (domain/routines.py), only
# timezone_unknown reaches a route. A malformed trigger is a malformed body, refused as
# invalid_request before the service (Decision 0029 F9), and every caller of the service, these
# routes and the cronjob tool, sends a typed schedule, which always parses. So no caller today gets
# interval_invalid, daily_time_invalid or trigger_unknown as a reply. validate_trigger still raises
# them for a trigger mapping, and the scheduler raises daily_time_invalid, which it logs, for a
# stored daily time that isn't text. Their wording stays here.
ROUTINE_CODES = [
    ("routine_not_found", 404, "That is not available."),
    ("routine_target_not_found", 404, "That is not available."),
    ("draft_not_runnable", 422, "A routine binds a published version, not a draft."),
    ("routine_name_taken", 409, SAVED_CONFLICT),
    ("routine_version_conflict", 409, SAVED_CONFLICT),
    *(
        (code, 422, "That routine isn't valid.")
        for code in (
            "routine_goal_required",
            "routine_scope_widened",
            "timezone_unknown",
            "interval_invalid",
            "daily_time_invalid",
            "trigger_unknown",
        )
    ),
]
ROUTINE_ROUTES: list[tuple[str, str, Body]] = [
    ("POST /v1/routines", "create_routine", {"name": "Fixture", "config": ROUTINE_CONFIG}),
    (f"GET /v1/routines/{ROUTINE}", "get_routine", None),
    (
        f"POST /v1/routines/{ROUTINE}/versions",
        "add_routine_version",
        {"expected_version": 1, "config": ROUTINE_CONFIG},
    ),
    (f"POST /v1/routines/{ROUTINE}/enabled", "set_enabled", {"enabled": False}),
]
ROUTINES = [
    *(
        Case(
            "POST /v1/routines",
            "routine_routes.create_routine",
            RoutineRefused(code),
            (status, code, text),
            {"name": "Fixture", "config": ROUTINE_CONFIG},
        )
        for code, status, text in ROUTINE_CODES
    ),
    *(
        Case(request, f"routine_routes.{name}", RoutineRefused("routine_not_found"), reply, body)
        for request, name, body in ROUTINE_ROUTES
        for reply in [(404, "routine_not_found", "That is not available.")]
    ),
    *(
        Case(request, f"routine_routes.{name}", IdempotencyConflict("arranged"), reply, body)
        for request, name, body in ROUTINE_ROUTES
        if name in {"create_routine", "add_routine_version"}
        for reply in [(409, "idempotency_conflict", KEY_REUSED)]
    ),
]

OTHERS = [
    Case(
        "POST /v1/memory",
        "memory_routes.store_memory",
        MemoryRefused("expert_not_found"),
        (404, "expert_not_found", "That Expert isn't in this workspace."),
        {"title": "A note", "content": "Text"},
    ),
    *(
        Case(
            f"GET /v1/artifacts/{ARTIFACT}/download",
            "artifact_routes.read_artifact",
            ArtifactUnavailable(code),
            (status, code, "That artifact is not available."),
        )
        for code, status in (("artifact_not_found", 404), ("artifact_missing", 409))
    ),
    *(
        Case(request, f"event_routes.{name}", RunNotFound("arranged"), reply)
        for request, name in (
            (f"GET /v1/runs/{RUN}/events", "read_events"),
            (f"GET /v1/runs/{RUN}/workspace", "read_workspace"),
            (f"GET /v1/runs/{RUN}/inspector", "read_inspector"),
            (f"GET /v1/runs/{RUN}/events/stream", "read_events"),
        )
        for reply in [(404, "run_not_found", "That run is not available.")]
    ),
    Case(
        "GET /v1/runs?cursor=bad",
        "event_routes.read_run_list",
        InvalidCursor("arranged"),
        (422, "invalid_cursor", "That page cursor is not valid."),
    ),
]

CASES = [
    *ADMISSION,
    *COMMANDS,
    *RECONCILIATION,
    *WORKFLOWS,
    *IMPROVEMENTS,
    *APPROVALS,
    *EXPERTS,
    *ROUTINES,
    *OTHERS,
]


@pytest.mark.parametrize("case", CASES, ids=[case.id for case in CASES])
def test_each_route_answers_a_refusal_as_it_always_has(
    client: ApiClient, monkeypatch: pytest.MonkeyPatch, case: Case
) -> None:
    _patched(monkeypatch, case)
    assert answer(client, case.request, case.body) == case.expected


@pytest.mark.parametrize(
    "trigger",
    [
        {"kind": "cron"},
        {"kind": "interval", "minutes": 0},
        {"kind": "interval", "minutes": True},
        {"kind": "interval", "minutes": "15"},
        {"kind": "interval", "minutes": 60, "note": "x"},
        {"kind": "daily"},
        {"kind": "daily", "time": "25:00"},
        {"kind": "daily", "time": "07:30:45"},
        {"kind": "daily", "time": "09:00", "minutes": 5},
    ],
)
def test_a_malformed_trigger_is_a_malformed_request_body(
    client: ApiClient, monkeypatch: pytest.MonkeyPatch, trigger: dict[str, object]
) -> None:
    """Decision 0029 F9: the trigger is typed, so a person's malformed one is refused like any other
    strict field, before the routine service runs."""
    for name in ("create_routine", "add_routine_version"):
        monkeypatch.setattr(routine_routes, name, raising(AssertionError("reached the service")))
    config = {**ROUTINE_CONFIG, "trigger": trigger}
    for request, body in (
        ("POST /v1/routines", {"name": "Fixture", "config": config}),
        (f"POST /v1/routines/{ROUTINE}/versions", {"expected_version": 1, "config": config}),
    ):
        reply = answer(client, request, body)
        assert reply == (422, "invalid_request", "The request is not valid.")


# Settings: each write's refusals, the same for every operation that can raise them.
SETTINGS_REFUSALS: list[tuple[Exception, Reply]] = [
    (
        StaleVersion("arranged"),
        (409, "stale_version", "The settings changed. Reload and try again."),
    ),
    (
        EnvironmentManaged("arranged"),
        (409, "environment_managed", "The environment supplies this key. Change it there."),
    ),
    (
        InvalidKey("arranged"),
        (422, "invalid_key", "That key was not accepted. The previous key is unchanged."),
    ),
    (
        ValidationUnavailable("arranged"),
        (503, "validation_unavailable", "The key could not be checked right now. Nothing changed."),
    ),
    (
        CredentialStorageUnavailable("arranged"),
        (503, "credential_storage_unavailable", "Credential storage is unavailable."),
    ),
    (CredentialMissing("arranged"), (409, "credential_missing", "No credential is configured.")),
]
PROVIDER_WRITES: list[tuple[str, Body]] = [
    (
        "PUT /v1/settings/model-providers/openrouter/credential",
        {"draft_key": "k", "expected_version": 0},
    ),
    ("DELETE /v1/settings/model-providers/openrouter/credential", {"expected_version": 0}),
    ("POST /v1/settings/model-providers/openrouter/validate", None),
]


@pytest.mark.parametrize(
    ("request_line", "body", "refusal", "expected"),
    [
        (request, body, refusal, reply)
        for request, body in PROVIDER_WRITES
        for refusal, reply in SETTINGS_REFUSALS
    ],
    ids=[
        f"{request} {reply[1]}"
        for request, _body in PROVIDER_WRITES
        for _refusal, reply in SETTINGS_REFUSALS
    ],
)
def test_each_provider_settings_write_answers_its_refusals(
    client: ApiClient, request_line: str, body: Body, refusal: Exception, expected: Reply
) -> None:
    client.app.dependency_overrides[provider_settings] = lambda: Settings(refusal)
    assert answer(client, request_line, body) == expected


KEYS_AND_VARS: list[tuple[str, Reply]] = [
    *(
        (name, (422, "invalid_key", "That key was not accepted. The previous key is unchanged."))
        for name in ("tavily", "jina", "github_token")
    ),
    (
        "github_repository",
        (422, "invalid_value", "Use owner/name. The previous value is unchanged."),
    ),
    (
        "browser_executor",
        (422, "invalid_value", "Use enabled or disabled. The previous value is unchanged."),
    ),
]


@pytest.mark.parametrize(
    ("name", "expected"), KEYS_AND_VARS, ids=[name for name, _ in KEYS_AND_VARS]
)
def test_a_refused_item_value_names_the_item_never_the_value(
    client: ApiClient, name: str, expected: Reply
) -> None:
    client.app.dependency_overrides[keys_and_vars_settings] = lambda: Settings(
        InvalidKey("arranged")
    )
    body = {"value": "submitted-value", "expected_version": 0}
    assert answer(client, f"PUT /v1/settings/keys-and-vars/{name}", body) == expected


@pytest.mark.parametrize(
    ("request_line", "refusal", "expected"),
    [
        (request, refusal, reply)
        for request in (
            "PUT /v1/settings/keys-and-vars/tavily",
            "DELETE /v1/settings/keys-and-vars/tavily",
        )
        for refusal, reply in SETTINGS_REFUSALS
        if not isinstance(refusal, InvalidKey)
    ],
    ids=[
        f"{request} {reply[1]}"
        for request in ("PUT", "DELETE")
        for refusal, reply in SETTINGS_REFUSALS
        if not isinstance(refusal, InvalidKey)
    ],
)
def test_each_keys_and_vars_write_answers_its_refusals(
    client: ApiClient, request_line: str, refusal: Exception, expected: Reply
) -> None:
    client.app.dependency_overrides[keys_and_vars_settings] = lambda: Settings(refusal)
    body = {"value": "v"} if request_line.startswith("PUT") else {}
    assert answer(client, request_line, {**body, "expected_version": 0}) == expected


POLICY_REFUSALS: list[tuple[dict[str, object], Reply]] = [
    (
        {"default_profile": "openrouter_deepseek_flash", "role_overrides": {}},
        (422, "model_not_offered", DEEPSEEK),
    ),
    (
        {"default_profile": None, "role_overrides": {"not_a_role": "openrouter_terra"}},
        (422, "unknown_model", "Choose an approved model and role."),
    ),
    # An unknown role is found before a profile that isn't offered.
    (
        {"default_profile": None, "role_overrides": {"not_a_role": "openrouter_deepseek_flash"}},
        (422, "unknown_model", "Choose an approved model and role."),
    ),
]


@pytest.mark.parametrize(("choice", "expected"), POLICY_REFUSALS)
def test_a_model_policy_names_what_it_refuses(
    client: ApiClient, choice: dict[str, object], expected: Reply
) -> None:
    body = {"expected_version": 0, **choice}
    assert answer(client, "PUT /v1/settings/model-policy", body) == expected


def test_an_expert_binding_a_profile_not_offered_is_a_bad_request(client: ApiClient) -> None:
    config = {"role_bindings": {"executor": "openrouter_deepseek_flash"}}
    for request, body in (
        ("POST /v1/experts", {"name": "Fixture", "config": config}),
        (f"POST /v1/experts/{EXPERT}/versions", {"expected_version": 1, "config": config}),
    ):
        assert answer(client, request, body) == (422, "model_not_offered", DEEPSEEK)


@pytest.mark.parametrize(
    ("request_line", "body", "expected"),
    [
        (f"POST /v1/runs/{RUN}/resume", {"expected_version": 1}, KEY_NEEDED),
        (
            f"POST /v1/workflows/{WORKFLOW}/executions",
            {"version": 1},
            "An agent step needs a usable OpenRouter key.",
        ),
        (
            f"POST /v1/improvements/{CANDIDATE}/replay",
            REPLAY,
            "A replay needs a usable OpenRouter key.",
        ),
    ],
)
def test_each_route_words_a_missing_key_for_its_own_work(
    client: ApiClient, monkeypatch: pytest.MonkeyPatch, request_line: str, body: Body, expected: str
) -> None:
    async def needs(*_args: object) -> bool:
        return True

    monkeypatch.setattr(workflow_routes, "needs_model", needs)
    client.app.dependency_overrides[model_key_check] = lambda: (
        Settings(intent="credential_invalid").run_intent
    )
    assert answer(client, request_line, body) == (409, "credential_invalid", expected)


def test_a_replay_under_a_saved_profile_not_offered_is_a_conflict(client: ApiClient) -> None:
    client.database.answer("from app_private.model_policies", ("openrouter_deepseek_flash", {}))
    reply = answer(client, f"POST /v1/improvements/{CANDIDATE}/replay", REPLAY)
    assert reply == (409, "model_not_offered", DEEPSEEK)


def test_a_workflow_execution_checks_the_draft_then_the_budget_then_the_key(
    client: ApiClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each refusal holds while every later one would also apply."""
    monkeypatch.setattr(workflow_routes, "chosen_limit", raising(BudgetRefused("budget_off_step")))
    client.app.dependency_overrides[model_key_check] = lambda: (
        Settings(intent="credential_invalid").run_intent
    )
    path = f"POST /v1/workflows/{WORKFLOW}/executions"
    assert answer(client, path, {"version": "draft", "budget_micro_usd": 1}) == (
        409,
        "draft_not_runnable",
        "Only a published version can run.",
    )
    assert answer(client, path, {"version": 1, "budget_micro_usd": 1}) == (
        422,
        "budget_off_step",
        "Choose a budget in steps of US$0.25.",
    )


def test_a_resume_checks_the_key_then_the_run_then_what_needs_reconciling(
    client: ApiClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each refusal holds while every later one would also apply."""

    async def everything_outstanding(*_args: object) -> Outstanding:
        return Outstanding(1, 1, 0)

    async def effect(*_args: object) -> bool:
        return True

    async def incompatible(*_args: object) -> str:
        return "incompatible_version"

    monkeypatch.setattr(reconciliation, "outstanding", everything_outstanding)
    monkeypatch.setattr(reconciliation, "has_unresolvable_effect", effect)
    monkeypatch.setattr(reconciliation, "execution_block", incompatible)
    path, body = f"POST /v1/runs/{RUN}/resume", {"expected_version": 1}
    client.app.dependency_overrides[model_key_check] = lambda: (
        Settings(intent="credential_invalid").run_intent
    )
    assert answer(client, path, body) == (409, "credential_invalid", KEY_NEEDED)
    client.app.dependency_overrides[model_key_check] = lambda: Settings().run_intent
    client.database.answer("select 1 from public.runs where id")
    assert answer(client, path, body) == (404, "run_not_found", "That run is not available.")
    client.database.answer("select 1 from public.runs where id", (1,))
    assert answer(client, path, body) == (
        409,
        "incompatible_version",
        "This run can't continue on this release. Start a new one.",
    )
    monkeypatch.setattr(reconciliation, "execution_block", none)
    assert answer(client, path, body) == (
        409,
        "uncertain_model_call",
        "A model call's outcome must be reconciled first.",
    )
    monkeypatch.setattr(reconciliation, "outstanding", nothing_outstanding)
    assert answer(client, path, body) == (
        409,
        "unknown_effect",
        "An effect's outcome must be reconciled first.",
    )


def test_a_resume_block_without_wording_of_its_own_is_still_a_conflict() -> None:
    """A code `api/errors.py` doesn't word yet reads as its kind's wording, never a server error."""
    unworded = reconciliation.ResumeBlocked("arranged_new_block")
    assert (STATUS[unworded.kind], refusal_message(unworded)) == (
        409,
        "Conflicts with the current state.",
    )
