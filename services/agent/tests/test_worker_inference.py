"""The worker's route and attempt client, through the real adapter and SDK over a fake transport."""

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import openrouter
import psycopg
import pytest
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from pydantic import SecretStr

from autobots.adapters import model_replies
from autobots.adapters.loop_middleware import AdmittedModel
from autobots.adapters.models.catalog import (
    CatalogEntry,
    CatalogSnapshot,
    ModelUnavailable,
    parse_catalog,
)
from autobots.application.credentials.store import (
    CredentialBlocked,
    CredentialMissing,
    CredentialReference,
    CredentialStorageUnavailable,
    CredentialUnreadable,
)
from autobots.application.goal_loop import UNBOUND, LoopConfig
from autobots.application.loop_admission import admitted_scope
from autobots.application.model_attempts import (
    UNCERTAIN,
    FailureClass,
    ProviderFailure,
)
from autobots.application.provider_settings import (
    CredentialRefused,
    ProviderSettings,
)
from autobots.application.worker_inference import (
    CATALOG_REFRESH,
    ROLE,
    AttemptModel,
    CatalogCache,
    InferenceSource,
    frozen_policy,
    prepared,
)
from autobots.application.worker_leases import Lease
from autobots.domain.models import (
    MAX_OUTPUT_TOKENS,
    ModelRole,
    UnknownModelProfile,
)
from fake_openrouter import (
    ARRANGED_KEY,
    DEEPSEEK,
    DEEPSEEK_WIRE_ID,
    PRICE,
    TERRA,
    TERRA_WIRE_ID,
    RecordingOpenRouter,
    attempt_model,
    catalog_payload,
    invoke,
    provider_context,
    snapshot,
    source_with,
)
from sql_fakes import ScriptedConnection

NOW = datetime.now(UTC)


# The frozen route


def test_the_policy_is_read_from_the_snapshot_not_a_default() -> None:
    policy = frozen_policy(snapshot(TERRA.id.value))
    assert policy.profile_for(ROLE).wire_id == TERRA_WIRE_ID


@pytest.mark.parametrize(
    "bad",
    [
        None,
        {},
        {"bindings": {}},
        {"bindings": {"summarizer": DEEPSEEK.id.value}},
        {"bindings": {"executor": "openai/gpt-unapproved"}},
    ],
)
def test_a_snapshot_without_an_approved_binding_has_no_route(bad: Any) -> None:
    with pytest.raises(UnknownModelProfile):
        frozen_policy(bad)


def test_a_model_without_tools_is_unavailable_to_this_loop() -> None:
    catalog = parse_catalog(catalog_payload("tools"), retrieved_at=NOW, revision="fixture")
    with pytest.raises(ModelUnavailable):
        prepared(frozen_policy(snapshot()), catalog)


def test_a_model_without_the_output_limit_is_refused_not_sent_unbounded() -> None:
    catalog = parse_catalog(catalog_payload("max_tokens"), retrieved_at=NOW, revision="fixture")
    with pytest.raises(ModelUnavailable):
        prepared(frozen_policy(snapshot()), catalog)


def test_a_drifted_mapping_is_unavailable() -> None:
    entry = CatalogEntry(DEEPSEEK.wire_id, "deepseek/moved", frozenset({"max_tokens", "tools"}))
    with pytest.raises(ModelUnavailable, match="drifted"):
        prepared(frozen_policy(snapshot()), CatalogSnapshot("fixture", NOW, (entry,)))


# The catalog cache


def test_the_catalog_is_kept_until_its_refresh_is_due() -> None:
    fetched: list[int] = []
    clock = [NOW]

    async def fetch() -> dict[str, Any]:
        fetched.append(1)
        return catalog_payload()

    async def go() -> None:
        cache = CatalogCache(fetch, lambda: clock[0])
        await cache.current()
        clock[0] = NOW + CATALOG_REFRESH - timedelta(seconds=1)
        await cache.current()
        assert len(fetched) == 1
        clock[0] = NOW + CATALOG_REFRESH
        await cache.current()
        assert len(fetched) == 2

    asyncio.run(go())


def test_a_failed_refresh_keeps_the_last_catalog_and_its_true_age() -> None:
    answers: list[Any] = [catalog_payload(), None]
    clock = [NOW]

    async def fetch() -> Any:
        return answers.pop(0)

    async def go() -> None:
        cache = CatalogCache(fetch, lambda: clock[0])
        first = await cache.current()
        clock[0] = NOW + CATALOG_REFRESH
        assert (await cache.current()).retrieved_at == first.retrieved_at

    asyncio.run(go())


def test_no_catalog_at_all_is_unavailable() -> None:
    async def fetch() -> None:
        return None

    with pytest.raises(ModelUnavailable):
        asyncio.run(CatalogCache(fetch).current())


def test_a_malformed_catalog_is_a_failed_refresh_not_a_crash() -> None:
    async def fetch() -> dict[str, Any]:
        return {"data": ["not an entry"]}

    with pytest.raises(ModelUnavailable):
        asyncio.run(CatalogCache(fetch).current())


# Attempts, through the real adapter and SDK


@tool
def lookup(text: str) -> str:
    """Look something up."""
    return text


def test_a_request_carries_the_routes_identity_limits_and_routing_flags() -> None:
    fake = RecordingOpenRouter()
    invoke(attempt_model(source_with(fake, [ARRANGED_KEY])).bind_tools([lookup]))
    body = fake.bodies[0]
    assert body["model"] == DEEPSEEK_WIRE_ID
    assert body["max_tokens"] == MAX_OUTPUT_TOKENS
    assert body["provider"] == {"require_parameters": True, "allow_fallbacks": False}
    assert not body.get("models")
    assert [item["function"]["name"] for item in body["tools"]] == ["lookup"]
    assert fake.keys == [f"Bearer {ARRANGED_KEY}"]


def test_the_wire_id_follows_the_runs_binding() -> None:
    fake = RecordingOpenRouter()
    invoke(attempt_model(source_with(fake, [ARRANGED_KEY]), TERRA.id.value))
    assert fake.bodies[0]["model"] == TERRA_WIRE_ID


def test_the_reply_gives_the_loop_what_it_settles_on() -> None:
    fake = RecordingOpenRouter(cost=0.00025)
    message = invoke(attempt_model(source_with(fake, [ARRANGED_KEY])).bind_tools([lookup]))
    assert model_replies.charged(message) == 250
    assert message.response_metadata["finish_reason"] == "tool_calls"
    assert [(call["name"], call["args"]) for call in message.tool_calls] == [
        ("lookup", {"text": "a"})
    ]


def test_each_attempt_opens_its_own_client_so_a_rotation_reaches_the_next_call() -> None:
    fake = RecordingOpenRouter()
    model = attempt_model(source_with(fake, ["arranged-first-key", "arranged-next-key"]))
    invoke(model)
    invoke(model)
    assert fake.clients == 2
    assert fake.keys == ["Bearer arranged-first-key", "Bearer arranged-next-key"]


def test_a_missing_key_stops_the_attempt_before_anything_is_sent() -> None:
    fake = RecordingOpenRouter()
    missing = ProviderFailure(FailureClass.CREDENTIALS_REQUIRED)
    with pytest.raises(ProviderFailure) as caught:
        invoke(attempt_model(source_with(fake, [missing])))
    assert caught.value.failure is FailureClass.CREDENTIALS_REQUIRED
    assert fake.bodies == []


def test_a_stale_catalog_stops_the_attempt_before_any_key_is_read() -> None:
    fake = RecordingOpenRouter()
    answers: list[dict[str, Any] | None] = [catalog_payload(), None]

    async def fetch() -> dict[str, Any] | None:
        return answers.pop(0)

    # Read six minutes ago. The refresh due now fails, which leaves only that copy to age out.
    moments = [datetime.now(UTC) - timedelta(minutes=6)]
    catalog = CatalogCache(fetch, lambda: moments[-1])
    asyncio.run(catalog.current())
    moments.append(datetime.now(UTC))
    source = source_with(fake, [ARRANGED_KEY], catalog=catalog)
    with pytest.raises(ProviderFailure) as caught:
        invoke(attempt_model(source))
    assert caught.value.failure is FailureClass.MODEL_UNAVAILABLE
    assert fake.bodies == []
    assert source.keys == [ARRANGED_KEY]


def test_a_401_marks_the_key_rejected_and_is_still_raised_with_its_status() -> None:
    fake = RecordingOpenRouter(status=401)
    rejected: list[Any] = []
    with pytest.raises(openrouter.errors.OpenRouterError) as caught:
        invoke(attempt_model(source_with(fake, [ARRANGED_KEY], rejected)))
    assert caught.value.status_code == 401
    assert len(fake.bodies) == 1
    assert len(rejected) == 1


@pytest.mark.parametrize("status", [402, 429, 500])
def test_other_statuses_leave_the_key_alone(status: int) -> None:
    fake = RecordingOpenRouter(status=status)
    rejected: list[Any] = []
    with pytest.raises(openrouter.errors.OpenRouterError):
        invoke(attempt_model(source_with(fake, [ARRANGED_KEY], rejected)))
    assert rejected == []


def test_no_key_or_client_survives_on_the_model_the_graph_holds() -> None:
    fake = RecordingOpenRouter()
    model = attempt_model(source_with(fake, [ARRANGED_KEY])).bind_tools([lookup])
    invoke(model)
    assert ARRANGED_KEY not in repr(vars(model))
    admitted = AdmittedModel(delegate=model)
    assert ARRANGED_KEY not in repr(admitted)


# Binding a job


def lease() -> Lease:
    return Lease(uuid4(), uuid4(), 1, "worker", 1, "running")


class Rows(ScriptedConnection):
    """Every statement answers `value`, as the run's frozen snapshot."""

    def __init__(self, value: Any) -> None:
        super().__init__([(value,)])


def real_source(pricing: object = PRICE) -> InferenceSource:
    async def fetch() -> dict[str, Any]:
        return catalog_payload(pricing=pricing)

    return InferenceSource("postgresql://unused", provider_context(fetch), CatalogCache(fetch))


def bind_with(
    value: Any,
    refusal: tuple[str | None, int],
    monkeypatch: pytest.MonkeyPatch,
    pricing: object = PRICE,
) -> tuple[Any, LoopConfig]:
    source = real_source(pricing)

    async def arranged(*_: Any) -> tuple[str | None, int]:
        return refusal

    monkeypatch.setattr(InferenceSource, "_refusal", arranged)
    base = LoopConfig(route=UNBOUND)
    return asyncio.run(source.bind(Rows(value), lease(), base))


def test_binding_takes_the_route_from_each_runs_own_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for profile, wire in ((DEEPSEEK, DEEPSEEK_WIRE_ID), (TERRA, TERRA_WIRE_ID)):
        _, config = bind_with(snapshot(profile.id.value), (None, 777), monkeypatch)
        assert (config.route.role, config.route.profile) == ("executor", profile.id.value)
        assert (config.route.wire_id, config.route.worst_case_micro_usd) == (wire, 777)
        assert config.refusal is None


def test_a_refusal_is_carried_for_the_loop_to_apply_after_its_own_gates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, config = bind_with(snapshot(), ("credentials_required", 0), monkeypatch)
    assert config.refusal == "credentials_required"
    assert config.route.profile == DEEPSEEK.id.value


def test_an_unbound_snapshot_leaves_the_route_unbound(monkeypatch: pytest.MonkeyPatch) -> None:
    _, config = bind_with({"bindings": {}}, (None, 1), monkeypatch)
    assert config.route == UNBOUND


def test_binding_reserves_the_worst_case_and_routes_by_the_rate_and_tier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each attempt passes its reservation on, so a fresh price is compared with it, and the route
    keeps the input rate and the tier where a longer request is refused (PTST-08)."""
    seen: list[int | None] = []

    async def recording(
        _source: InferenceSource,
        _workspace: UUID,
        _policy: Any,
        reserved_micro_usd: int | None = None,
        role: ModelRole = ROLE,
    ) -> Any:
        seen.append(reserved_micro_usd)
        raise ProviderFailure(FailureClass.OTHER)

    tiered = {**PRICE, "overrides": [{"min_prompt_tokens": 272_000, "prompt": "0.01"}]}
    factory, config = bind_with(snapshot(), (None, 777), monkeypatch, pricing=tiered)
    route = config.route
    assert (route.worst_case_micro_usd, route.input_per_million_micro_usd) == (777, 1_000_000)
    assert route.tier_from_tokens == 272_000
    monkeypatch.setattr(InferenceSource, "open_attempt", recording)
    with pytest.raises(ProviderFailure):
        asyncio.run(factory().ainvoke([HumanMessage("hello")]))
    assert seen == [777]


# Inside a real attempt, with the database replaced


class Connected:
    async def __aenter__(self) -> "Connected":
        return self

    async def __aexit__(self, *_: Any) -> None:
        return None


async def connected(*_: Any, **__: Any) -> Connected:
    return Connected()


class Current:
    """The key `credential_for_attempt` returned, with its version."""

    def __init__(self, version: int | None = None) -> None:
        self.reference = CredentialReference("app", None, version)

    def client_secret(self) -> SecretStr:
        return SecretStr(ARRANGED_KEY)


def real_attempt(
    monkeypatch: pytest.MonkeyPatch, outcome: Any, fake: RecordingOpenRouter | None = None
) -> tuple[Any, CredentialReference]:
    async def credential(*_: Any) -> Any:
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr("psycopg.AsyncConnection.connect", connected)
    monkeypatch.setattr(ProviderSettings, "credential_for_attempt", credential)
    source = replace(real_source(), client_factory=(fake or RecordingOpenRouter()).client)
    return asyncio.run(source.open_attempt(uuid4(), frozen_policy(snapshot())))


@pytest.mark.parametrize(
    ("raised", "expected"),
    [
        (CredentialRefused("credentials_required"), FailureClass.CREDENTIALS_REQUIRED),
        (CredentialRefused("credential_invalid"), FailureClass.INVALID_CREDENTIAL),
        (CredentialRefused("credential_unavailable"), FailureClass.CREDENTIAL_UNAVAILABLE),
        (CredentialMissing("arranged"), FailureClass.CREDENTIALS_REQUIRED),
        (CredentialBlocked("arranged"), FailureClass.INVALID_CREDENTIAL),
        (CredentialStorageUnavailable("arranged"), FailureClass.CREDENTIAL_UNAVAILABLE),
        (CredentialUnreadable("arranged"), FailureClass.CREDENTIAL_UNAVAILABLE),
        (psycopg.OperationalError("arranged"), FailureClass.CREDENTIAL_UNAVAILABLE),
        (PermissionError("arranged"), FailureClass.CREDENTIAL_UNAVAILABLE),
        (UnicodeDecodeError("utf-8", b"x", 0, 1, "arranged"), FailureClass.CREDENTIAL_UNAVAILABLE),
    ],
)
def test_every_credential_failure_is_classed_as_never_sent(
    monkeypatch: pytest.MonkeyPatch, raised: Exception, expected: FailureClass
) -> None:
    with pytest.raises(ProviderFailure) as caught:
        real_attempt(monkeypatch, raised)
    assert caught.value.failure is expected
    assert caught.value.failure not in UNCERTAIN


def test_a_real_attempt_returns_the_client_and_what_it_used(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = RecordingOpenRouter()
    client, used = real_attempt(monkeypatch, Current(3), fake)
    assert fake.clients == 1
    assert used == CredentialReference("app", None, 3)
    assert ARRANGED_KEY not in repr(used)
    assert client.model_name == DEEPSEEK_WIRE_ID


def test_a_price_gone_mid_job_stops_the_next_attempt_before_any_key_is_read() -> None:
    async def fetch() -> dict[str, Any]:
        return catalog_payload(pricing=None)

    source = InferenceSource("postgresql://unused", provider_context(fetch), CatalogCache(fetch))
    with pytest.raises(ProviderFailure) as caught:
        asyncio.run(source.open_attempt(uuid4(), frozen_policy(snapshot())))
    assert caught.value.failure is FailureClass.COST_UNAVAILABLE


# The worker's refusal, for what a job's configuration can raise


@pytest.mark.parametrize(
    "raised", [PermissionError("arranged"), UnicodeDecodeError("utf-8", b"x", 0, 1, "arranged")]
)
def test_an_unreadable_configuration_refuses_a_job_rather_than_looping(
    monkeypatch: pytest.MonkeyPatch, raised: Exception
) -> None:
    async def intent(*_: Any) -> str:
        raise raised

    monkeypatch.setattr(ProviderSettings, "run_intent", intent)
    _, config = asyncio.run(
        real_source().bind(Rows(snapshot()), lease(), LoopConfig(route=UNBOUND))
    )
    assert config.refusal == "credential_unavailable"


# Browsing's researcher route


def _role_route(value: Any, *drop: str) -> Any:
    async def fetch() -> dict[str, Any]:
        return catalog_payload(*drop)

    source = InferenceSource("postgresql://unused", provider_context(fetch), CatalogCache(fetch))
    return asyncio.run(source.role_route(Rows(value), lease(), ModelRole.RESEARCHER))


def test_browsing_binds_the_runs_frozen_researcher_route(monkeypatch: pytest.MonkeyPatch) -> None:
    frozen = {
        **snapshot(DEEPSEEK.id.value),
        "bindings": {"executor": DEEPSEEK.id.value, "researcher": TERRA.id.value},
    }
    model, route = _role_route(frozen)
    assert (route.role, route.profile, route.wire_id) == (
        "researcher",
        TERRA.id.value,
        TERRA_WIRE_ID,
    )
    assert route.worst_case_micro_usd > 0
    opened: list[tuple[ModelRole, int | None]] = []

    async def recording(
        _source: InferenceSource,
        _workspace: UUID,
        _policy: Any,
        reserved_micro_usd: int | None = None,
        role: ModelRole = ROLE,
    ) -> Any:
        opened.append((role, reserved_micro_usd))
        raise ProviderFailure(FailureClass.OTHER)

    # Its attempts open on the researcher role, reserving what the route says.
    monkeypatch.setattr(InferenceSource, "open_attempt", recording)
    with pytest.raises(ProviderFailure):
        asyncio.run(model.ainvoke([HumanMessage("read")]))
    assert opened == [(ModelRole.RESEARCHER, route.worst_case_micro_usd)]


def test_a_researcher_route_without_tools_is_refused_before_anything_is_sent() -> None:
    frozen = {
        "version": 1,
        "bindings": {"executor": DEEPSEEK.id.value, "researcher": TERRA.id.value},
    }
    assert _role_route(frozen, "tools") == "unsupported_request_option"


def test_a_run_without_a_researcher_binding_has_no_browsing_route() -> None:
    assert _role_route(snapshot()) == "route_not_bound"


def test_a_browsing_step_reaches_the_transport_on_the_researcher_route_with_tools_required() -> (
    None
):
    from autobots.application.browsing_loop import ACTION_TOOLS, admitted_steps

    fake = RecordingOpenRouter()
    policy = frozen_policy(
        {"version": 1, "bindings": {"executor": DEEPSEEK.id.value, "researcher": TERRA.id.value}}
    )
    model = AttemptModel(
        source_with(fake, [ARRANGED_KEY]), uuid4(), policy, role=ModelRole.RESEARCHER
    )

    class Admits:
        async def admitted(self, request: Any, handler: Any, route: Any) -> Any:
            with admitted_scope():
                return await handler(request), True

    step = admitted_steps(Admits(), model, "route")  # type: ignore[arg-type]
    asyncio.run(step([HumanMessage("read")]))
    body = fake.bodies[0]
    assert body["model"] == TERRA_WIRE_ID
    assert [item["function"]["name"] for item in body["tools"]] == [
        item["function"]["name"] for item in ACTION_TOOLS
    ]
    assert body["tool_choice"] == "required"
    assert body["provider"] == {"require_parameters": True, "allow_fallbacks": False}
