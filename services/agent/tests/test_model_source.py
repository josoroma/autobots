"""US-23.3, Decision 0041 A1, A7, A8 and A10 to A13: a workspace's Model source. Settings and Home
through the API over the fake pool, admission's resolution on each source, the worker's refusal
after a switch, each route's limits, and browsing on a local researcher route. A fake llama-server
answers on an httpx transport, and OpenRouter's catalog and client fail a test if they're used."""

import asyncio
import json
import os
from datetime import date
from pathlib import Path
from typing import Any, NoReturn
from uuid import UUID, uuid4

import httpx
import pytest
from langchain_core.messages import HumanMessage

from autobots.adapters.model_endpoint import EndpointRefused, Reply, admitted_answer
from autobots.adapters.models.local_health import Digests, runtime_health
from autobots.adapters.models.local_server import LoopbackClient
from autobots.api import operation_routes
from autobots.api.resources import resources_of
from autobots.application.credentials.store import ProviderCredentialStore
from autobots.application.goal_loop import UNBOUND
from autobots.application.model_attempts import FailureClass, ProviderFailure
from autobots.application.model_source import (
    SourceRolesUncovered,
    roles_needed,
    switch_model_source,
)
from autobots.application.operations import Condition
from autobots.application.provider_settings import ProviderSettings, SourceIsLocal
from autobots.application.run_admission import PolicyNotOffered, WorkspacePolicy
from autobots.application.run_lifecycle import LoopConfig
from autobots.application.run_projection.workspace import run_budgets
from autobots.application.run_usage import RootLimits
from autobots.application.worker_inference import (
    AttemptModel,
    InferenceSource,
    frozen_policy,
)
from autobots.contracts.persisted import PolicySnapshot
from autobots.contracts.run_workspace import FrozenBinding
from autobots.contracts.settings import ModelList
from autobots.domain.models import (
    PROFILES,
    ModelProfile,
    ModelProfileId,
    ModelRole,
    ModelRoute,
    ModelSource,
    limits_for,
)
from autobots.domain.stops import DISPOSITION, Disposition, StopCode
from fake_api import MEMBER, OWNER, WORKSPACE, ApiClient, FakeConnection, FakeDatabase
from fake_openrouter import provider_context
from test_local_model_route import (
    BONSAI,
    FakeLlamaServer,
    admitting,
    local_model,
    on,
    untouched_catalog,
)
from test_loop_middleware import Ledger, Usage

TERRA = PROFILES[ModelProfileId.TERRA]
READY = (
    Condition("database", "ok", "database_ready"),
    Condition("schema", "ok", "schema_ready"),
)
POLICY_READ = "select version, default_profile, role_overrides, model_source, local_profile"
QUALIFICATIONS = "from agent_runtime.route_qualifications"
BROWSING = "select exists (select 1 from public.experts"
SWITCH_LOCK = "select version, local_profile from app_private.model_policies"
SOURCE = "select model_source from app_private.model_policies"
BONSAI_QUALIFIED = {
    "profile": BONSAI.id.value,
    "canonical_id": BONSAI.canonical_id,
    "status": "qualified_with_limits",
    "qualified_on": date(2026, 11, 27),
    "configuration": "Served as bonsai-2.5-27b-q2_0.",
    "limits": "Not passed in every trial, so disabled: schema_nested passed 0 of 3.",
}


def policy_row(
    version: int, source: str = "openrouter", local: str | None = None
) -> dict[str, Any]:
    return {
        "version": version,
        "default_profile": "openrouter_sol",
        "role_overrides": {"coder": "openrouter_terra"},
        "model_source": source,
        "local_profile": local,
    }


class Runtime:
    """The owner's llama-server for Settings and Home: `/v1/models` and `/props`, or nothing."""

    def __init__(self, served: str | None, model_path: str | None = None) -> None:
        self.served = served
        self.model_path = model_path
        self.paths: list[str] = []
        self.transport = httpx.MockTransport(self.handle)

    def handle(self, request: httpx.Request) -> httpx.Response:
        if self.served is None:
            raise httpx.ConnectError("connection refused", request=request)
        self.paths.append(request.url.path)
        assert request.url.host == "127.0.0.1"
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": self.served}]})
        return httpx.Response(200, json={"model_path": self.model_path})


def on_runtime(client: ApiClient, runtime: Runtime, digests: Digests | None = None) -> None:
    resources = resources_of(client.app)
    resources.local_transport = runtime.transport
    resources.local_port = 9931
    if digests is not None:
        resources.local_digests = digests


def arrange(client: ApiClient, *, offered: bool, browsing: bool = False) -> None:
    """Bonsai 2.5's stored qualification or none, whether an Expert grants browse_goal, and the
    owner's server stopped unless a test starts its own."""
    client.database.answer(QUALIFICATIONS, *([BONSAI_QUALIFIED] if offered else []))
    client.database.answer(BROWSING, (browsing,))
    on_runtime(client, Runtime(None))


def get_source(client: ApiClient, user: UUID = OWNER) -> tuple[int, Any]:
    reply = client.http.get("/v1/settings/model-source", headers=client.headers(user))
    return reply.status_code, reply.json()


def put_source(client: ApiClient, body: dict[str, Any], user: UUID = OWNER) -> tuple[int, Any]:
    reply = client.http.put("/v1/settings/model-source", headers=client.headers(user), json=body)
    return reply.status_code, reply.json()


# OpenRouter is the default, as today


def test_a_new_workspace_and_an_existing_one_are_on_openrouter(api_client: ApiClient) -> None:
    arrange(api_client, offered=True)
    status, body = get_source(api_client)
    assert status == 200 and (body["source"], body["version"]) == ("openrouter", 0)
    api_client.database.answer(POLICY_READ, policy_row(4))
    status, body = get_source(api_client)
    assert (body["source"], body["version"], body["local_profile"]) == ("openrouter", 4, None)
    # Admission resolves MP-01's order, with researcher on Sol and the saved choices as they were.
    policy = WorkspacePolicy("openrouter_sol", {"coder": "openrouter_terra"}).for_new_work(
        require_offer=True
    )
    assert policy.bindings[ModelRole.CODER] == ModelProfileId.TERRA
    assert policy.bindings[ModelRole.RESEARCHER] == ModelProfileId.SOL
    assert not any(PROFILES[profile].is_local for profile in policy.bindings.values())


# Switching: who, when and what it needs


@pytest.mark.parametrize(
    ("browsing", "roles"), [(True, ["executor", "researcher"]), (False, ["executor"])]
)
def test_local_is_refused_until_offered_profiles_cover_the_roles(
    api_client: ApiClient, browsing: bool, roles: list[str]
) -> None:
    arrange(api_client, offered=False, browsing=browsing)
    status, body = put_source(api_client, {"expected_version": 0, "source": "local"})
    assert status == 409 and body["code"] == "model_source_roles_uncovered"
    assert all(role in body["message"] for role in roles)
    assert ("researcher" in body["message"]) is browsing
    assert api_client.database.changes() == []


def test_only_the_owner_switches_and_a_stale_version_is_a_conflict(api_client: ApiClient) -> None:
    arrange(api_client, offered=True)
    status, body = put_source(api_client, {"expected_version": 0, "source": "local"}, MEMBER)
    assert status == 403 and body["code"] == "owner_required"
    api_client.database.answer(SWITCH_LOCK, (3, None))
    status, body = put_source(api_client, {"expected_version": 2, "source": "local"})
    assert status == 409 and body["code"] == "stale_version"
    assert api_client.database.changes() == []


def test_a_switch_keeps_openrouters_choices_and_back_again(api_client: ApiClient) -> None:
    """The upsert writes only the source and the Local default, so OpenRouter's saved default and
    overrides are kept for a switch back (Decision 0041 A1)."""
    arrange(api_client, offered=True)
    api_client.database.answer(SWITCH_LOCK, (4, None))
    status, _ = put_source(api_client, {"expected_version": 4, "source": "local"})
    assert status == 200
    api_client.database.answer(SWITCH_LOCK, (5, BONSAI.id.value))
    status, _ = put_source(api_client, {"expected_version": 5, "source": "openrouter"})
    assert status == 200
    writes = [
        (text, values)
        for text, values in api_client.database.statements
        if text.startswith("insert into app_private.model_policies")
    ]
    assert [values for _, values in writes] == [
        (WORKSPACE, 5, "local", BONSAI.id.value),
        (WORKSPACE, 6, "openrouter", BONSAI.id.value),
    ]
    for text, _ in writes:
        update = text.split("do update set", 1)[1]
        assert "default_profile" not in update and "role_overrides" not in update


# On Local, one local profile answers every role


def test_on_local_every_role_is_on_the_local_default() -> None:
    saved = WorkspacePolicy(
        "openrouter_sol",
        {"coder": "openrouter_terra"},
        ModelSource.LOCAL,
        BONSAI.id.value,
        frozenset({BONSAI.id}),
    )
    policy = saved.for_new_work(require_offer=True)
    assert set(policy.bindings.values()) == {BONSAI.id} and len(policy.bindings) == len(ModelRole)
    frozen = PolicySnapshot.of(policy).routes
    assert list(frozen) == [BONSAI.id.value]
    assert (frozen[BONSAI.id.value].wire_id, frozen[BONSAI.id.value].canonical_id) == (
        BONSAI.wire_id,
        BONSAI.canonical_id,
    )
    with pytest.raises(PolicyNotOffered) as refused:
        saved.for_new_work(run_role_overrides={"researcher": BONSAI.id.value}, require_offer=True)
    assert refused.value.code == "model_not_offered" and refused.value.named
    with pytest.raises(PolicyNotOffered):
        saved.for_new_work(run_profile=ModelProfileId.TERRA, require_offer=True)
    unoffered = WorkspacePolicy(None, None, ModelSource.LOCAL, BONSAI.id.value, frozenset())
    with pytest.raises(PolicyNotOffered):
        unoffered.for_new_work(require_offer=True)


def test_on_local_the_pickers_list_offered_local_profiles_and_a_role_override_is_refused(
    api_client: ApiClient,
) -> None:
    arrange(api_client, offered=True)
    api_client.database.answer(SOURCE, ("local",))
    api_client.database.answer(POLICY_READ, policy_row(5, "local", BONSAI.id.value))
    models = asyncio.run(listed(api_client.database))
    assert [item.profile for item in models.models] == [BONSAI.id]
    assert (models.catalog_status, models.fetched_at) == ("unknown", None)
    shown = api_client.http.get("/v1/settings/model-policy", headers=api_client.headers()).json()
    assert shown["default_profile"] == BONSAI.id.value and shown["role_overrides"] == {}
    assert {item["profile"] for item in shown["policy"]["bindings"]} == {BONSAI.id.value}
    reply = api_client.http.put(
        "/v1/settings/model-policy",
        headers=api_client.headers(),
        json={
            "expected_version": 5,
            "default_profile": BONSAI.id.value,
            "role_overrides": {"researcher": BONSAI.id.value},
        },
    )
    assert reply.status_code == 422 and reply.json()["code"] == "model_not_offered"
    assert api_client.database.changes() == []


async def listed(database: FakeDatabase) -> ModelList:
    """`GET /v1/models`'s list, with a catalog fetch that fails the test if it's made."""

    async def fetch() -> dict[str, Any]:
        raise AssertionError("OpenRouter's catalog was fetched on Local")

    async with database.connection() as connection:
        return await ProviderSettings(connection, provider_context(fetch)).models(WORKSPACE)


# Limits follow the route


def test_a_runs_limits_follow_its_frozen_route() -> None:
    def frozen(profile: ModelProfileId) -> list[FrozenBinding]:
        p = PROFILES[profile]
        return [
            FrozenBinding(
                role="executor",
                profile=p.id.value,
                canonical_id=p.canonical_id,
                wire_id=p.wire_id,
                source=None,
            )
        ]

    local, remote = run_budgets(frozen(BONSAI.id)), run_budgets(frozen(TERRA.id))
    assert (local.context_tokens, local.max_output_tokens_per_call) == (64_000, 4_096)
    assert (local.call_seconds, local.active_seconds / 60) == (1_800.0, 240.0)
    assert (local.model_calls, local.tool_dispatches) == (64, 96)
    assert (remote.call_seconds, remote.active_seconds / 60) == (300.0, 45.0)
    assert limits_for(PROFILES[ModelProfileId.LOCAL_INKLING_2_MINI]).output_tokens == 8_192
    assert BONSAI.local is not None and BONSAI.local.thinking == {"enable_thinking": False}


# The worker: nothing to OpenRouter on Local, and a run on a switched-off source waits


class Snapshot:
    """A connection that answers every statement with the run's frozen snapshot."""

    def __init__(self, snapshot: dict[str, Any]) -> None:
        self.snapshot = snapshot

    async def execute(self, *_: object) -> "Snapshot":
        return self

    async def fetchone(self) -> tuple[Any]:
        return (self.snapshot,)


def worker(server: FakeLlamaServer, source: ModelSource) -> InferenceSource:
    def no_openrouter(_key: str) -> NoReturn:
        raise AssertionError("an OpenRouter client was built")

    def loopback(profile: ModelProfile, port: int) -> LoopbackClient:
        return LoopbackClient(
            profile, port, 30.0, transport=server.transport, async_transport=server.transport
        )

    return InferenceSource(
        "postgresql://never",
        provider_context(),
        untouched_catalog(),
        client_factory=no_openrouter,
        local_client=loopback,
        local_transport=server.transport,
        source_check=on(source),
    )


def bound(source: InferenceSource, profile: ModelProfileId) -> LoopConfig:
    from test_worker_inference import lease

    snapshot = {"version": 1, "bindings": {"executor": profile.value}}
    _, config = asyncio.run(source.bind(Snapshot(snapshot), lease(), LoopConfig(route=UNBOUND)))  # type: ignore[arg-type]  # a fake connection
    return config


def test_a_run_on_a_switched_off_source_is_refused_before_anything_is_sent() -> None:
    server = FakeLlamaServer(BONSAI.wire_id)
    # A run frozen on OpenRouter, after the switch to Local: refused at bind, with no catalog,
    # key or client touched.
    assert bound(worker(server, ModelSource.LOCAL), TERRA.id).refusal == "model_source_disabled"
    # A run frozen on Local, after a switch back to OpenRouter: refused at bind too.
    assert (
        bound(worker(server, ModelSource.OPENROUTER), BONSAI.id).refusal == "model_source_disabled"
    )
    # On each attempt as well, so a switch mid-run stops the next call.
    policy = frozen_policy({"version": 1, "bindings": {"executor": BONSAI.id.value}})
    model = AttemptModel(worker(server, ModelSource.OPENROUTER), uuid4(), policy)
    with pytest.raises(ProviderFailure) as refused:
        asyncio.run(model.ainvoke([HumanMessage("hello")]))
    assert refused.value.failure == FailureClass.MODEL_SOURCE_DISABLED
    assert server.requests == []
    assert DISPOSITION[StopCode.MODEL_SOURCE_DISABLED] is Disposition.SUSPEND


def test_after_the_switch_back_the_run_binds_on_its_frozen_route_with_its_limits() -> None:
    server = FakeLlamaServer(BONSAI.wire_id)
    config = bound(worker(server, ModelSource.LOCAL), BONSAI.id)
    assert config.refusal is None and config.route.profile == BONSAI.id.value
    assert (config.model_call_seconds, config.limits.active_seconds) == (1_800.0, 14_400.0)
    assert (config.limits.model_calls, config.limits.tool_dispatches) == (64, 96)
    assert config.limits.repairs == RootLimits().repairs


def test_a_local_run_sends_everything_to_the_loopback_and_nothing_to_openrouter() -> None:
    server = FakeLlamaServer(BONSAI.wire_id)
    policy = frozen_policy({"version": 1, "bindings": {"executor": BONSAI.id.value}})
    model = AttemptModel(worker(server, ModelSource.LOCAL), uuid4(), policy)
    message = asyncio.run(model.ainvoke([HumanMessage("hello")]))
    assert message.content == "ready"
    assert all(
        r.url.host == "127.0.0.1" and "authorization" not in r.headers for r in server.requests
    )
    (sent,) = server.chats()
    assert sent["max_tokens"] == 4_096 and sent["chat_template_kwargs"] == {
        "enable_thinking": False
    }


# Browsing follows the source


def test_the_browser_boxs_calls_are_answered_on_the_local_researcher_route() -> None:
    server = FakeLlamaServer(BONSAI.wire_id)
    model = local_model(server)
    route = ModelRoute(ModelRole.RESEARCHER.value, BONSAI.id.value, BONSAI.wire_id, 0)
    usage, ledger = Usage(), Ledger()
    answer = admitted_answer(admitting(model, ledger, usage), model, route)
    body = {"model": "anything", "messages": [{"role": "user", "content": "Read the page."}]}

    async def sent(request: dict[str, Any]) -> Reply:
        return await answer(request)

    reply = asyncio.run(sent(body))
    assert reply.completion["model"] == BONSAI.wire_id
    assert ledger.asked[0].worst_case_micro_usd == 0 and ("settled", 0) in ledger.events
    assert all(r.url.host == "127.0.0.1" for r in server.requests)
    image = {
        "role": "user",
        "content": [{"type": "image_url", "image_url": {"url": "data:image/png;base64,AA=="}}],
    }
    before = len(server.requests)
    with pytest.raises(EndpointRefused) as refused:
        asyncio.run(sent({"model": "anything", "messages": [image]}))
    assert refused.value.code == "content_not_qualified" and len(server.requests) == before


# Settings → Models and Home


def test_the_panel_shows_each_local_profile_the_runtime_and_the_roles(
    api_client: ApiClient, tmp_path: Path
) -> None:
    weights = tmp_path / "bonsai.gguf"
    weights.write_bytes(b"weights")
    facts = os.stat(weights)
    assert BONSAI.local is not None
    digests = Digests()
    digests._known[(str(weights), facts.st_size, facts.st_mtime_ns)] = BONSAI.local.sha256
    arrange(api_client, offered=True, browsing=True)
    on_runtime(api_client, Runtime(BONSAI.wire_id, str(weights)), digests)
    status, body = get_source(api_client, MEMBER)
    assert status == 200
    shown = {item["profile"]: item for item in body["local_profiles"]}
    bonsai, inkling = shown[BONSAI.id.value], shown[ModelProfileId.LOCAL_INKLING_2_MINI.value]
    assert (bonsai["offered"], bonsai["name"], bonsai["matched_runs"]) == (True, "Bonsai 2.5", [])
    assert bonsai["qualified_on"] == "2026-11-27" and "schema_nested" in bonsai["limits"]
    assert inkling["offered"] is False and "Inkling 2 Mini isn't offered" in inkling["reason"]
    assert body["runtime"] == {
        "status": "ready",
        "port": 9931,
        "served_model_id": BONSAI.wire_id,
        "sha256_matches": True,
        "sha256_checking": False,
    }
    assert body["roles_needed"] == ["executor", "researcher"] and body["roles_uncovered"] == []


def test_a_served_file_is_hashed_once_off_the_event_loop_and_a_wrong_one_doesnt_match(
    tmp_path: Path,
) -> None:
    weights = tmp_path / "other.gguf"
    weights.write_bytes(b"not the pinned weights")
    hashed: list[str] = []

    def count(path: str) -> str:
        hashed.append(path)
        return "0" * 64

    digests = Digests(hash_file=count)
    runtime = Runtime(BONSAI.wire_id, str(weights))

    async def twice() -> tuple[Any, Any]:
        first = await runtime_health(
            BONSAI, 9931, with_digest=True, transport=runtime.transport, digests=digests
        )
        await digests.settled()
        second = await runtime_health(
            BONSAI, 9931, with_digest=True, transport=runtime.transport, digests=digests
        )
        return first, second

    first, second = asyncio.run(twice())
    assert (first.sha256_matches, first.sha256_checking) == (None, True)
    assert (second.status, second.sha256_matches) == ("ready", False)
    assert hashed == [str(weights)]


def test_home_reads_the_local_model_from_its_health_check_and_nothing_from_openrouter(
    api_client: ApiClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def conditions(_pool: object, _probes: object = None) -> tuple[Condition, ...]:
        return READY

    async def worker_state(_connection: object, _counts: object) -> Condition:
        return Condition("worker", "ok", "worker_ready")

    async def no_key(*_: object) -> NoReturn:
        raise AssertionError("OpenRouter's key was read on Local")

    monkeypatch.setattr(operation_routes, "database_conditions", conditions)
    monkeypatch.setattr(operation_routes, "worker_condition", worker_state)
    monkeypatch.setattr(ProviderSettings, "auth_status", no_key)
    arrange(api_client, offered=True)
    api_client.database.answer(POLICY_READ, policy_row(5, "local", BONSAI.id.value))
    runtime = Runtime(BONSAI.wire_id)
    on_runtime(api_client, runtime)

    def services() -> dict[str, Any]:
        reply = api_client.http.get("/v1/readiness", headers=api_client.headers(MEMBER))
        return {item["name"]: item for item in reply.json()["services"]}

    ready = services()
    assert ready["local_model"] == {"name": "local_model", "state": "ready", "code": "local_ready"}
    assert "openrouter" not in ready
    # Only the model ID is asked, so Home never waits on a hash.
    assert runtime.paths == ["/v1/models"]
    runtime.served = None
    stopped = services()
    assert stopped["local_model"]["code"] == "local_not_running"
    assert stopped["local_model"]["state"] == "not_ready"


def test_on_local_settings_send_nothing_to_openrouter(api_client: ApiClient) -> None:
    api_client.database.answer(SOURCE, ("local",))
    reply = api_client.http.get("/v1/settings/model-providers", headers=api_client.headers())
    # No provider context is configured in the fake app, so a catalog fetch would read as
    # unavailable; on Local it isn't attempted, and reads as unknown.
    if reply.status_code == 200:
        assert reply.json()["catalog_status"] == "unknown"
    refused = api_client.http.post(
        "/v1/settings/model-providers/openrouter/validate", headers=api_client.headers()
    )
    assert refused.status_code in {409, 503}


@pytest.mark.asyncio
async def test_a_switch_writes_nothing_when_its_roles_arent_covered() -> None:
    database = FakeDatabase([])
    database.answer(SWITCH_LOCK, (0, None))
    database.answer(BROWSING, (False,))
    async with database.connection() as connection:
        with pytest.raises(SourceRolesUncovered) as refused:
            await switch_model_source(
                connection,
                WORKSPACE,
                expected_version=0,
                source=ModelSource.LOCAL,
                local_profile=None,
            )
    assert refused.value.roles == roles_needed(False)
    assert database.changes() == []
    assert json.dumps([ModelRole.EXECUTOR.value]) == json.dumps(
        [r.value for r in refused.value.roles]
    )


class Unread(ProviderCredentialStore):
    """A credential store that fails the test if any key is read."""

    def __init__(self) -> None:
        super().__init__(FakeConnection(FakeDatabase([])), Path("/nonexistent"))

    async def load_active(self, workspace_id: UUID) -> NoReturn:
        raise AssertionError("an OpenRouter key was read on Local")

    async def installation_key_allowed(self, workspace_id: UUID) -> NoReturn:
        raise AssertionError("the installation's key was considered on Local")


class NoRows:
    """The provider settings row, which a gate on Local never reads."""

    async def read(self, workspace_id: UUID, *, lock: bool = False) -> NoReturn:
        raise AssertionError("the OpenRouter settings row was read on Local")

    async def ensure(self, workspace_id: UUID) -> None:
        raise AssertionError("ensure on Local")

    async def record(self, workspace_id: UUID, status: object) -> None:
        raise AssertionError("record on Local")


@pytest.mark.asyncio
async def test_on_local_the_key_gate_answers_ready_without_reading_any_key() -> None:
    database = FakeDatabase([])
    database.answer(SOURCE, ("local",))
    environment = {"OPENROUTER_API_KEY": "sk-or-v1-" + "a" * 64}
    async with database.connection() as connection:
        settings = ProviderSettings(
            connection,
            provider_context(environment=environment),
            store=Unread(),
            rows=NoRows(),
        )
        assert await settings.run_intent(WORKSPACE) == "ready"
        with pytest.raises(SourceIsLocal):
            await settings.revalidate(WORKSPACE)
    assert [text for text, _ in database.statements] == [
        "select model_source from app_private.model_policies where workspace_id = %s"
    ] * 2
