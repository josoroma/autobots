"""The gate for model-backed work, and where its callers differ on purpose (refactor plan R-31,
PAPI-04, PPRD-09 and XDUP-08).

Every path to a model call uses `application/run_admission.py`'s gate: the key check, the workspace
policy resolved for new work with its offered check, the chosen limit and tool availability. A
resume, a held-out replay, a workflow execution, a routine's occurrence and the two previews each
pass it differently, and each difference is pinned here. No socket, database or model is used.
"""

import asyncio
import json
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime
from uuid import UUID

import pytest

from autobots.adapters.tool_registry import catalog
from autobots.api.dependencies import model_key_check, require_ready
from autobots.api.resources import resources_of
from autobots.application.experts import expert_record
from autobots.application.routines import run_routine_now
from autobots.application.run_admission import (
    ModelNotReady,
    PolicyNotOffered,
    WorkspacePolicy,
    chosen_limit,
    expert_overrides,
    require_model_ready,
    require_tools_available,
    saved_workspace_policy,
    workspace_role_policy,
)
from autobots.application.runs import Inheritance, Inherited, RunAdmission, admit
from autobots.application.tool_catalog import ToolsUnavailable
from autobots.application.workflow_executions import create_execution
from autobots.application.workflow_overview import preview_steps
from autobots.contracts.experts import ExpertConfig
from autobots.contracts.routines import CronjobSchedule, RoutineConfig, RoutineTarget
from autobots.domain.budgets import BudgetRefused
from autobots.domain.models import (
    PROFILES,
    ModelProfileId,
    ModelRole,
    ProfileNotOffered,
    RolePolicy,
)
from fake_api import OWNER, WORKSPACE, ApiClient, FakeConnection, FakeDatabase
from fake_openrouter import provider_context

EXPERT = UUID("0b000000-0000-4000-8000-0000000000e1")
SECOND_EXPERT = UUID("0b000000-0000-4000-8000-0000000000e2")
RUN = UUID("0b000000-0000-4000-8000-0000000000f1")
CANDIDATE = UUID("0b000000-0000-4000-8000-0000000000c1")
FLOW = UUID("0b000000-0000-4000-8000-0000000000d1")
ROUTINE = UUID("0b000000-0000-4000-8000-0000000000b1")
DEEPSEEK = ModelProfileId.DEEPSEEK_FLASH
DEEPSEEK_REASON = "DeepSeek isn't offered for new runs until it's qualified."
POLICY_READ = (
    "select default_profile, role_overrides from app_private.model_policies where workspace_id = %s"
)


def run[T](work: Awaitable[T]) -> T:
    async def awaited() -> T:
        return await work

    return asyncio.run(awaited())


def connection_of(database: FakeDatabase) -> FakeConnection:
    async def opened() -> FakeConnection:
        async with database.connection() as connection:
            return connection

    return run(opened())


def fresh() -> tuple[FakeDatabase, FakeConnection]:
    database = FakeDatabase([])
    return database, connection_of(database)


def checks(answer: str) -> tuple[Callable[[UUID], Awaitable[str]], list[UUID]]:
    asked: list[UUID] = []

    async def check(workspace_id: UUID) -> str:
        asked.append(workspace_id)
        return answer

    return check, asked


# The key check


def test_the_key_is_asked_only_when_the_work_needs_a_model() -> None:
    check, asked = checks("credentials_required")
    run(require_model_ready(check, WORKSPACE, needed=False))
    assert asked == []
    with pytest.raises(ModelNotReady) as refused:
        run(require_model_ready(check, WORKSPACE, needed=True))
    assert (refused.value.code, asked) == ("credentials_required", [WORKSPACE])


def test_a_ready_key_passes() -> None:
    check, asked = checks("ready")
    run(require_model_ready(check, WORKSPACE, needed=True))
    assert asked == [WORKSPACE]


# The workspace policy, resolved for new work


def test_the_saved_policy_is_read_with_one_statement_and_none_saved_is_empty() -> None:
    database, connection = fresh()
    assert run(saved_workspace_policy(connection, WORKSPACE)) == WorkspacePolicy()
    database.answer(
        "app_private.model_policies", ("openrouter_sol", {"executor": "openrouter_terra"})
    )
    saved = run(saved_workspace_policy(connection, WORKSPACE))
    assert saved == WorkspacePolicy("openrouter_sol", {"executor": "openrouter_terra"})
    assert database.statements == [(POLICY_READ, (WORKSPACE,))] * 2


def test_mp01_order_run_role_then_run_wide_then_saved_role_then_saved_default() -> None:
    saved = WorkspacePolicy("openrouter_sol", {"reviewer": "openrouter_terra"})
    policy = saved.for_new_work(
        run_role_overrides={"executor": "openrouter_terra"},
        run_profile=None,
        require_offer=True,
    )
    assert policy.bindings[ModelRole.EXECUTOR] is ModelProfileId.TERRA
    assert policy.bindings[ModelRole.REVIEWER] is ModelProfileId.TERRA
    assert policy.bindings[ModelRole.COORDINATOR] is ModelProfileId.SOL
    run_wide = saved.for_new_work(run_profile=ModelProfileId.TERRA, require_offer=True)
    assert set(run_wide.bindings.values()) == {ModelProfileId.TERRA}


@pytest.mark.parametrize(
    ("saved", "overrides", "named", "is_named"),
    [
        (WorkspacePolicy(), None, DEEPSEEK, True),
        (WorkspacePolicy(DEEPSEEK.value), None, None, False),
        (WorkspacePolicy(None, {"executor": DEEPSEEK.value}), None, None, False),
        (WorkspacePolicy(), {"executor": DEEPSEEK.value}, ModelProfileId.TERRA, False),
    ],
    ids=["named here", "saved default", "saved role", "Expert binding beside an offered name"],
)
def test_a_profile_not_offered_refuses_and_says_whether_this_request_named_it(
    saved: WorkspacePolicy,
    overrides: dict[str, str] | None,
    named: ModelProfileId | None,
    is_named: bool,
) -> None:
    with pytest.raises(PolicyNotOffered) as refused:
        saved.for_new_work(run_role_overrides=overrides, run_profile=named, require_offer=True)
    assert isinstance(refused.value, ProfileNotOffered)
    assert (refused.value.code, str(refused.value), refused.value.named) == (
        "model_not_offered",
        DEEPSEEK_REASON,
        is_named,
    )


def test_without_the_offered_check_a_profile_not_offered_is_resolved_as_admission_would() -> None:
    policy = WorkspacePolicy(DEEPSEEK.value).for_new_work(require_offer=False)
    assert set(policy.bindings.values()) == {DEEPSEEK}


def test_workspace_role_policy_reads_then_resolves() -> None:
    database, connection = fresh()
    database.answer("app_private.model_policies", (DEEPSEEK.value, {}))
    with pytest.raises(PolicyNotOffered):
        run(workspace_role_policy(connection, WORKSPACE, require_offer=True))
    shown = run(workspace_role_policy(connection, WORKSPACE, require_offer=False))
    assert isinstance(shown, RolePolicy)


def test_an_experts_role_bindings_become_run_role_overrides() -> None:
    config = ExpertConfig(role_bindings={"executor": DEEPSEEK, "researcher": ModelProfileId.SOL})
    assert expert_overrides(expert_record(config)) == {
        "executor": "openrouter_deepseek_flash",
        "researcher": "openrouter_sol",
    }
    assert expert_overrides(expert_record(ExpertConfig())) == {}


# The chosen limit


def test_with_no_budget_the_limit_is_the_callers_and_nothing_is_read() -> None:
    database, connection = fresh()
    assert run(chosen_limit(connection, WORKSPACE, None, otherwise=40_000)) == 40_000
    assert database.statements == []


def test_a_budget_is_checked_against_what_is_left_today() -> None:
    database, connection = fresh()
    database.answer("app_private.model_spend_limits", (1_000_000,))
    database.answer("app_private.model_invocations", (500_000,))
    assert run(chosen_limit(connection, WORKSPACE, 500_000, otherwise=1)) == 500_000
    with pytest.raises(BudgetRefused) as refused:
        run(chosen_limit(connection, WORKSPACE, 750_000, otherwise=1))
    assert refused.value.code == "budget_above_daily_cap"


# Tool availability


def test_tool_availability_reads_the_environment_it_is_given(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-live")
    _, connection = fresh()
    with pytest.raises(ToolsUnavailable) as refused:
        run(require_tools_available(connection, WORKSPACE, ["tavily_search"], {}, catalog()))
    assert (refused.value.code, refused.value.tools) == ("tool_unavailable", ["tavily_search"])
    given = {"TAVILY_API_KEY": "tvly-given"}
    run(
        require_tools_available(
            connection, WORKSPACE, ["tavily_search", "calculate"], given, catalog()
        )
    )


def test_a_key_saved_for_the_workspace_makes_its_tool_available() -> None:
    database, connection = fresh()
    database.answer("from app_private.provider_credentials", ("tavily",))
    run(require_tools_available(connection, WORKSPACE, ["tavily_search"], {}, catalog()))


# Where the API's handlers differ


class KeyCheck:
    def __init__(self, code: str, log: list[str]) -> None:
        self.code = code
        self.log = log

    async def run_intent(self, workspace_id: UUID) -> str:
        assert workspace_id == WORKSPACE
        self.log.append("run_intent")
        return self.code


def overridden(client: ApiClient, key: str) -> None:
    resources_of(client.app).provider_context = provider_context()
    client.app.dependency_overrides[require_ready] = lambda: None
    client.app.dependency_overrides[model_key_check] = lambda: KeyCheck(key, client.log).run_intent


def reads_policy(client: ApiClient) -> bool:
    return any("app_private.model_policies" in entry for entry in client.log)


def test_a_resume_checks_the_key_with_the_goal_runs_wording(api_client: ApiClient) -> None:
    overridden(api_client, "credential_invalid")
    reply = api_client.http.post(
        f"/v1/runs/{RUN}/resume",
        headers=api_client.headers(OWNER, **{"Idempotency-Key": "k"}),
        json={"expected_version": 1},
    )
    assert (reply.status_code, reply.json()) == (
        409,
        {
            "code": "credential_invalid",
            "message": "Model-backed work needs a usable OpenRouter key.",
        },
    )
    assert api_client.log == ["run_intent"]


def test_a_resume_keeps_its_frozen_policy_so_offering_isnt_checked(api_client: ApiClient) -> None:
    overridden(api_client, "ready")
    api_client.database.answer("app_private.model_policies", (DEEPSEEK.value, {}))
    reply = api_client.http.post(
        f"/v1/runs/{RUN}/resume",
        headers=api_client.headers(OWNER, **{"Idempotency-Key": "k"}),
        json={"expected_version": 1},
    )
    assert (reply.status_code, reply.json()["code"]) == (404, "run_not_found")
    assert not reads_policy(api_client)


def replay(client: ApiClient) -> tuple[int, dict[str, str]]:
    reply = client.http.post(
        f"/v1/improvements/{CANDIDATE}/replay",
        headers=client.headers(OWNER, **{"Idempotency-Key": "k"}),
        json={
            "tasks": [{"goal_text": "Find the figure", "criteria": ["States it"]}],
            "limit_micro_usd": 1,
        },
    )
    return reply.status_code, reply.json()


def test_a_replay_checks_the_key_with_its_own_wording(api_client: ApiClient) -> None:
    overridden(api_client, "credentials_required")
    assert replay(api_client) == (
        409,
        {"code": "credentials_required", "message": "A replay needs a usable OpenRouter key."},
    )
    assert not reads_policy(api_client)


def test_a_replay_refuses_a_saved_profile_not_offered_as_a_conflict(api_client: ApiClient) -> None:
    overridden(api_client, "ready")
    api_client.database.answer("app_private.model_policies", (DEEPSEEK.value, {}))
    assert replay(api_client) == (409, {"code": "model_not_offered", "message": DEEPSEEK_REASON})


def test_a_replay_past_the_gate_reaches_its_candidate(api_client: ApiClient) -> None:
    overridden(api_client, "ready")
    assert replay(api_client)[1]["code"] == "candidate_not_found"
    assert reads_policy(api_client)


AGENT_GRAPH = {
    "nodes": [
        {"id": "in", "block": "input", "version": 1, "config": {"type": "string"}},
        {"id": "ask", "block": "agent", "version": 1, "config": {"expert_id": str(EXPERT)}},
        {"id": "out", "block": "output", "version": 1, "config": {}},
    ],
    "links": [
        {"source": "in", "source_port": "value", "target": "ask", "target_port": "goal"},
        {"source": "ask", "source_port": "result", "target": "out", "target_port": "value"},
    ],
}
PLAIN_GRAPH = {
    "nodes": [
        {"id": "in", "block": "input", "version": 1, "config": {"type": "string"}},
        {"id": "out", "block": "output", "version": 1, "config": {}},
    ],
    "links": [{"source": "in", "source_port": "value", "target": "out", "target_port": "value"}],
}


def execute(client: ApiClient, body: Mapping[str, object]) -> tuple[int, dict[str, str]]:
    reply = client.http.post(
        f"/v1/workflows/{FLOW}/executions",
        headers=client.headers(OWNER, **{"Idempotency-Key": "k"}),
        json=dict(body),
    )
    return reply.status_code, reply.json()


def test_a_workflow_with_an_agent_step_needs_the_key(api_client: ApiClient) -> None:
    overridden(api_client, "credentials_required")
    api_client.database.answer("select v.graph from public.workflow_versions", (AGENT_GRAPH,))
    assert execute(api_client, {"version": 1, "inputs": {"in": "x"}}) == (
        409,
        {"code": "credentials_required", "message": "An agent step needs a usable OpenRouter key."},
    )
    assert "run_intent" in api_client.log


def test_a_workflow_without_an_agent_step_never_asks_for_the_key(api_client: ApiClient) -> None:
    overridden(api_client, "credentials_required")
    api_client.database.answer("select v.graph from public.workflow_versions", (PLAIN_GRAPH,))
    status, body = execute(api_client, {"version": 1, "inputs": {"in": "x"}})
    assert (status, body["code"]) == (404, "workflow_version_not_found")
    assert "run_intent" not in api_client.log


def test_a_workflow_budget_follows_the_goal_runs_rules_before_the_key(
    api_client: ApiClient,
) -> None:
    overridden(api_client, "credentials_required")
    api_client.database.answer("select v.graph from public.workflow_versions", (AGENT_GRAPH,))
    status, body = execute(api_client, {"version": 1, "budget_micro_usd": 300_000})
    assert (status, body["code"]) == (422, "budget_off_step")
    assert "run_intent" not in api_client.log


def test_a_draft_is_refused_before_any_check(api_client: ApiClient) -> None:
    overridden(api_client, "credentials_required")
    assert execute(api_client, {"version": "draft"})[1]["code"] == "draft_not_runnable"
    assert api_client.log == []


def test_the_run_preview_shows_a_profile_not_offered_instead_of_refusing(
    api_client: ApiClient,
) -> None:
    api_client.database.answer(
        "from public.experts e join public.expert_versions v",
        ({"tools": ["calculate"], "role_bindings": {"executor": DEEPSEEK.value}},),
    )
    reply = api_client.http.get(
        "/v1/run-preview",
        params={"expert_id": str(EXPERT), "run_profile": "openrouter_terra"},
        headers=api_client.headers(),
    )
    assert reply.status_code == 200
    roles = {item["profile"]: item["roles"] for item in reply.json()["profiles"]}
    assert roles[DEEPSEEK.value] == ["executor"]
    assert "executor" not in roles["openrouter_terra"]


# The workflow preview


def test_every_agent_step_shows_the_workflow_runs_executor_from_one_policy_read() -> None:
    """Decision 0028 E6: an Expert's own binding isn't applied, and a step whose Expert isn't in
    this workspace shows no model."""
    database, connection = fresh()
    second = {"expert_id": str(SECOND_EXPERT)}
    graph = {
        "nodes": [
            {"id": "in", "block": "input", "version": 1, "config": {"type": "string"}},
            {"id": "ask", "block": "agent", "version": 1, "config": {"expert_id": str(EXPERT)}},
            {"id": "again", "block": "agent", "version": 1, "config": second},
            {"id": "out", "block": "output", "version": 1, "config": {}},
        ],
        "links": [
            {"source": "in", "source_port": "value", "target": "ask", "target_port": "goal"},
            {"source": "ask", "source_port": "result", "target": "again", "target_port": "goal"},
            {"source": "again", "source_port": "result", "target": "out", "target_port": "value"},
        ],
    }
    database.answer(
        "from public.experts e",
        {
            "id": str(EXPERT),
            "name": "Researcher",
            "config": {"tools": [], "role_bindings": {"executor": DEEPSEEK.value}},
        },
        {"id": str(SECOND_EXPERT), "name": "Writer", "config": {"tools": ["calculate"]}},
    )
    database.answer("app_private.model_policies", ("openrouter_sol", {}))
    steps = {step.id: step for step in run(preview_steps(connection, WORKSPACE, graph))}
    sol = PROFILES[ModelProfileId.SOL].canonical_id
    assert (steps["ask"].model, steps["again"].model, steps["in"].model) == (sol, sol, None)
    assert [text for text, _ in database.statements].count(POLICY_READ) == 1
    database.answers.clear()
    gone = {step.id: step for step in run(preview_steps(connection, WORKSPACE, graph))}
    assert (gone["ask"].expert_name, gone["ask"].model) == (None, None)


def test_a_draft_preview_reads_only_its_agent_steps_configuration() -> None:
    """A draft can hold any JSON in another step's configuration, such as a list for an input's
    type, and its preview still shows every step (refactor plan R-52)."""
    database, connection = fresh()
    database.answer(
        "select e.id::text as id, e.name, v.config from public.experts e",
        {"id": str(EXPERT), "name": "Researcher", "config": {"tools": ["calculate"]}},
    )
    draft = {
        "nodes": [
            {"id": "in", "block": "input", "version": 1, "config": {"type": ["string"]}},
            {"id": "ask", "block": "agent", "version": 1, "config": {"expert_id": str(EXPERT)}},
            {"id": "out", "block": "output", "version": 1, "config": "not an object"},
        ],
        "links": [],
    }
    steps = {step.id: step for step in run(preview_steps(connection, WORKSPACE, draft))}
    assert list(steps) == ["in", "ask", "out"]
    assert (steps["ask"].expert_name, steps["ask"].tools, steps["in"].expert_id) == (
        "Researcher",
        ["calculate"],
        None,
    )


def test_the_workflow_preview_names_the_model_its_agent_steps_child_will_use() -> None:
    """Decision 0028 E6: an agent step's child inherits the workflow run's frozen policy, which is
    resolved without the step Expert's role bindings, so the preview shows that policy's executor
    even when the Expert binds another model."""
    database, connection = fresh()
    expert = {"tools": ["calculate"], "role_bindings": {"executor": "openrouter_sol"}}
    database.answer(
        "select e.id::text as id, e.name, v.config from public.experts e",
        {"id": str(EXPERT), "name": "Researcher", "config": expert},
    )
    (step,) = [s for s in run(preview_steps(connection, WORKSPACE, AGENT_GRAPH)) if s.id == "ask"]
    # The workflow run, as creating an execution freezes it.
    database.answer("event_sequence = event_sequence + 1", (1,))
    database.answer(
        "select v.graph, v.graph_hash",
        {
            "graph": AGENT_GRAPH,
            "graph_hash": "digest",
            "block_versions": {},
            "name": "Weekly digest",
        },
    )
    database.answer("select v.graph from public.workflow_versions", (AGENT_GRAPH,))
    database.answer(
        "select id, name, latest_version from public.experts",
        {"id": EXPERT, "name": "Researcher", "latest_version": 1},
    )
    database.answer(
        "from public.expert_versions where expert_id",
        {"expert_id": EXPERT, "version": 1, "config": expert},
    )
    database.answer(
        "select e.id as expert_id, v.version, e.name, v.config from public.experts e",
        {"expert_id": EXPERT, "version": 1, "name": "Researcher", "config": expert},
    )
    database.answer(
        "select kind, experts from public.sessions",
        ("coordinator", [{"expert_id": str(EXPERT), "version": 1}]),
    )
    binding = run(
        create_execution(
            connection,
            workspace_id=WORKSPACE,
            actor_id=OWNER,
            workflow_id=FLOW,
            idempotency_key="k",
            version=1,
            inputs={"in": "x"},
        )
    )
    (workflow_run,) = database.written("public.runs")
    assert isinstance(workflow_run, tuple) and workflow_run[0] == binding.run_id
    snapshot = json.loads(workflow_run[6])
    # The child, admitted as assignments.py admits one: with the parent's snapshot as it is.
    child = FakeDatabase([])
    child.answer("event_sequence = event_sequence + 1", (1,))
    inheritance = Inheritance(
        parent_run_id=binding.run_id,
        root_run_id=binding.run_id,
        snapshot=snapshot,
        tools={"calculate": 1},
        paths=("inputs", "outputs/child-1"),
        instructions="",
        session_id=FLOW,
        expert_id=EXPERT,
        version=1,
    )
    admission = RunAdmission(
        workspace_id=WORKSPACE,
        actor_id=binding.run_id,
        idempotency_key="child",
        goal_text="Summarize",
        limit_micro_usd=1_000,
        origin=Inherited(inheritance),
    )
    run(admit(connection_of(child), admission))
    (child_run,) = child.written("public.runs")
    assert isinstance(child_run, tuple)
    inherited = json.loads(child_run[6])
    executor = inherited["bindings"]["executor"]
    assert executor == "openrouter_terra", "the child doesn't apply the step Expert's binding"
    assert step.model == inherited["routes"][executor]["canonical_id"]
    assert step.model == PROFILES[ModelProfileId.TERRA].canonical_id


# The run intent check: it reports the gate's answer instead of refusing


FULL_BUDGET = {
    "min_micro_usd": 250_000,
    "max_micro_usd": 5_000_000,
    "step_micro_usd": 250_000,
    "default_micro_usd": 1_000_000,
    "remaining_daily_micro_usd": 5_000_000,
}
NAMES = {
    "app_private.model_policies": "workspace policy",
    "app_private.model_spend_limits": "daily cap",
    "app_private.model_invocations": "spent today",
}


def intent(client: ApiClient, key: str) -> dict[str, object]:
    overridden(client, key)
    reply = client.http.post("/v1/runs/intent", headers=client.headers(OWNER))
    assert reply.status_code == 200
    body: dict[str, object] = reply.json()
    return body


def consulted(client: ApiClient) -> list[str]:
    return [next((name for part, name in NAMES.items() if part in e), e) for e in client.log]


AFTER_THE_POLICY = ["connect", "daily cap", "spent today", "release"]


@pytest.mark.parametrize(
    "code", ["credentials_required", "credential_invalid", "credential_unavailable"]
)
def test_without_a_usable_key_the_intent_check_reports_it_and_reads_no_policy(
    api_client: ApiClient, code: str
) -> None:
    api_client.database.answer("app_private.model_policies", (DEEPSEEK.value, {}))
    reported = intent(api_client, code)
    assert reported == {"schema_version": 1, "ready": False, "code": code, "budget": FULL_BUDGET}
    assert consulted(api_client) == ["run_intent", *AFTER_THE_POLICY]


def test_with_a_usable_key_and_offered_profiles_the_intent_check_is_ready(
    api_client: ApiClient,
) -> None:
    reported = intent(api_client, "ready")
    assert reported == {"schema_version": 1, "ready": True, "code": "ready", "budget": FULL_BUDGET}
    assert consulted(api_client) == [
        "run_intent",
        "connect",
        "workspace policy",
        "release",
        *AFTER_THE_POLICY,
    ]


@pytest.mark.parametrize(
    ("saved", "ready"),
    [
        ((DEEPSEEK.value, {}), False),
        ((None, {"executor": DEEPSEEK.value}), False),
        (("openrouter_sol", {"executor": "openrouter_terra"}), True),
    ],
    ids=["saved default not offered", "saved role not offered", "saved choices offered"],
)
def test_the_intent_check_reports_a_saved_profile_not_offered(
    api_client: ApiClient, saved: tuple[str | None, dict[str, str]], ready: bool
) -> None:
    api_client.database.answer("app_private.model_policies", saved)
    reported = intent(api_client, "ready")
    assert (reported["ready"], reported["code"]) == (
        ready,
        "ready" if ready else "model_not_offered",
    )
    assert consulted(api_client)[:4] == ["run_intent", "connect", "workspace policy", "release"]


def test_the_intent_check_reports_whats_left_today_whatever_the_key(api_client: ApiClient) -> None:
    api_client.database.answer("app_private.model_spend_limits", (1_000_000,))
    api_client.database.answer("app_private.model_invocations", (250_000,))
    assert intent(api_client, "credentials_required")["budget"] == {
        "min_micro_usd": 250_000,
        "max_micro_usd": 750_000,
        "step_micro_usd": 250_000,
        "default_micro_usd": 750_000,
        "remaining_daily_micro_usd": 750_000,
    }


# A routine's occurrence


MOMENT = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)


def routine_database(
    target: RoutineTarget, expert: Mapping[str, object] | None = None
) -> FakeDatabase:
    database = FakeDatabase([])
    config = RoutineConfig(
        target=target,
        goal="Check the figures",
        trigger=CronjobSchedule(kind="interval", minutes=60),
    )
    database.answer("event_sequence = event_sequence + 1", (1,))
    database.answer("select latest_version, enabled from public.routines", (1, True))
    database.answer("select clock_timestamp()", (MOMENT,))
    database.answer("select config from public.routine_versions", (config.model_dump(mode="json"),))
    database.answer("from public.routine_occurrences o join public.runs", (False,))
    database.answer("select graph from public.workflow_versions", (PLAIN_GRAPH,))
    database.answer(
        "select v.config from public.experts e join public.expert_versions v",
        (dict(expert or {}),),
    )
    return database


def occurrence(
    database: FakeDatabase, key: str
) -> tuple[tuple[str, str | None, UUID | None], list[UUID]]:
    check, asked = checks(key)
    connection = connection_of(database)
    return run(run_routine_now(connection, WORKSPACE, ROUTINE, check, catalog=catalog())), asked


EXPERT_TARGET = RoutineTarget(kind="expert", id=EXPERT, version=1)
WORKFLOW_TARGET = RoutineTarget(kind="workflow", id=FLOW, version=1)


def test_a_routine_on_an_expert_is_blocked_without_a_key() -> None:
    database = routine_database(EXPERT_TARGET, {"tools": ["calculate"]})
    (status, reason, run_id), asked = occurrence(database, "credentials_required")
    assert (status, reason, run_id, asked) == ("blocked", "credentials_required", None, [WORKSPACE])
    (recorded,) = database.written("public.routine_occurrences")
    assert isinstance(recorded, tuple) and recorded[3:5] == ("blocked", "credentials_required")


def test_a_routine_on_a_workflow_without_an_agent_step_never_asks_for_the_key() -> None:
    database = routine_database(WORKFLOW_TARGET)
    (status, reason, _), asked = occurrence(database, "credentials_required")
    assert (status, reason, asked) == ("blocked", "workflow_version_not_found", [])


def test_a_routine_on_an_expert_bound_to_a_profile_not_offered_is_blocked() -> None:
    expert = {"tools": ["calculate"], "role_bindings": {"executor": DEEPSEEK.value}}
    (status, reason, _), _ = occurrence(routine_database(EXPERT_TARGET, expert), "ready")
    assert (status, reason) == ("blocked", "model_not_offered")


def test_a_routines_tool_keys_come_from_the_workers_live_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expert = {"tools": ["tavily_search"]}
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    (status, reason, _), _ = occurrence(routine_database(EXPERT_TARGET, expert), "ready")
    assert (status, reason) == ("blocked", "tool_unavailable")
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-live")
    database = routine_database(EXPERT_TARGET, expert)
    (status, reason, run_id), _ = occurrence(database, "ready")
    assert (status, reason, run_id) == ("admitted", None, run_id)
    assert run_id is not None
    (row,) = database.written("public.runs")
    assert isinstance(row, tuple) and row[14] is None, "a routine's run has no started_by"
