"""The worker's route and attempt client, through the real adapter and SDK over a fake transport."""

import asyncio
import json
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import openrouter
import psycopg
import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool
from pydantic import SecretStr

from autobots.adapters.loop_middleware import (
    MAX_FACT_CHARS,
    MAX_FACT_NAMES,
    AdmittedModel,
    LoopMiddleware,
    LoopStopped,
    _charged,
    _failure_without_status,
    _finished,
    _retry_after,
    reply_facts,
)
from autobots.adapters.models.catalog import (
    RESERVED_PROMPT_TOKENS,
    CatalogEntry,
    CatalogSnapshot,
    ModelUnavailable,
    parse_catalog,
    parse_pricing,
)
from autobots.adapters.models.factory import chat_model, default_sdk_client
from autobots.application.credentials.crypto import CredentialDecryptionError
from autobots.application.credentials.precedence import EnvironmentCandidate
from autobots.application.credentials.store import (
    CredentialBlocked,
    CredentialMissing,
    CredentialReference,
    CredentialStorageUnavailable,
)
from autobots.application.goal_loop import UNBOUND, LoopConfig
from autobots.application.model_admission import (
    BudgetExceeded,
    NoInferenceSlot,
    Pricing,
    worst_case_cost,
)
from autobots.application.model_attempts import (
    UNCERTAIN,
    FailureClass,
    ProviderFailure,
    classify_status,
)
from autobots.application.provider_settings import (
    CredentialRefused,
    ProviderContext,
    ProviderSettings,
)
from autobots.application.worker_inference import (
    CATALOG_REFRESH,
    MAX_OUTPUT_TOKENS,
    ROLE,
    AttemptModel,
    CatalogCache,
    InferenceSource,
    frozen_policy,
    prepared,
)
from autobots.application.worker_leases import Lease
from autobots.domain.models import PROFILES, ModelProfileId, UnknownModelProfile
from autobots.operations import worker
from fake_openrouter import ARRANGED_KEY, DEEPSEEK_WIRE_ID, TERRA_WIRE_ID

NOW = datetime.now(UTC)
DEEPSEEK = PROFILES[ModelProfileId.DEEPSEEK_FLASH]
TERRA = PROFILES[ModelProfileId.TERRA]
PRICE = {"prompt": "0.000001", "completion": "0.000002"}


def catalog_payload(*drop: str, pricing: Any = PRICE) -> dict[str, Any]:
    supported = ["max_tokens", "tools", "tool_choice"]
    return {
        "data": [
            {
                "id": profile.wire_id,
                "canonical_slug": profile.canonical_id,
                "supported_parameters": [name for name in supported if name not in drop],
                "pricing": pricing,
            }
            for profile in (DEEPSEEK, TERRA)
        ]
    }


def snapshot(deepseek_or_terra: str = DEEPSEEK.id.value) -> dict[str, Any]:
    return {"version": 1, "bindings": {"executor": deepseek_or_terra, "summarizer": DEEPSEEK.id}}


def fresh_catalog(**kwargs: Any) -> CatalogSnapshot:
    return parse_catalog(catalog_payload(**kwargs), retrieved_at=NOW, revision="fixture")


# Pricing


def test_a_catalog_price_is_scaled_to_micro_usd_per_million_tokens() -> None:
    assert parse_pricing({"pricing": PRICE}) == Pricing(1_000_000, 2_000_000)


def test_the_highest_listed_rate_counts_including_overrides_and_cache_writes() -> None:
    pricing = {
        "prompt": "0.00001",
        "completion": "0.00005",
        "input_cache_write": "0.0000125",
        "internal_reasoning": "0.00006",
        "request": "0.001",
        "overrides": [{"prompt": "0.00002", "completion": "0.0001", "min_prompt_tokens": 5}],
    }
    assert parse_pricing({"pricing": pricing}) == Pricing(20_000_000, 100_000_000, 1000)


@pytest.mark.parametrize(
    "pricing",
    [None, {}, {"prompt": "0.1"}, {"prompt": "free", "completion": "0.1"}, {"prompt": "NaN"}],
)
def test_a_missing_or_unreadable_price_is_no_price(pricing: Any) -> None:
    assert parse_pricing({"pricing": pricing}) is None


def test_a_variable_price_has_no_bound_so_a_reservation_refuses_it() -> None:
    pricing = parse_pricing({"pricing": {"prompt": "-1", "completion": "-1"}})
    with pytest.raises(Exception, match="price is not known"):
        worst_case_cost(pricing, 1, 1)


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


# Attempts, through the real adapter and SDK


class Fake:
    """Answers chat completions over a mock transport, and records what really went out."""

    def __init__(self, status: int = 200, cost: float | None = 0.00025) -> None:
        self.status = status
        self.cost = cost
        self.bodies: list[dict[str, Any]] = []
        self.keys: list[str] = []
        self.clients = 0

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.bodies.append(json.loads(request.content))
        self.keys.append(request.headers.get("authorization", ""))
        if self.status != 200:
            error = {"code": self.status, "message": "arranged"}
            return httpx.Response(self.status, json={"error": error})
        usage: dict[str, Any] = {"prompt_tokens": 5, "completion_tokens": 7, "total_tokens": 12}
        if self.cost is not None:
            usage["cost"] = self.cost
        message = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call-1",
                    "type": "function",
                    "function": {"name": "lookup", "arguments": json.dumps({"text": "a"})},
                }
            ],
        }
        choice = {"index": 0, "finish_reason": "tool_calls", "message": message}
        return httpx.Response(
            200,
            json={
                "id": "fake",
                "object": "chat.completion",
                "created": 1,
                "model": self.bodies[-1]["model"],
                "system_fingerprint": "fake",
                "choices": [choice],
                "usage": usage,
            },
        )

    def client(self, key: str) -> openrouter.OpenRouter:
        self.clients += 1
        return default_sdk_client(
            key, async_http=httpx.AsyncClient(transport=httpx.MockTransport(self.handle))
        )


def _context(fetch: Any) -> ProviderContext:
    async def validate(_: Any) -> Any:
        raise AssertionError("a model attempt never validates a key")

    return ProviderContext("/nonexistent", "test", Path("/nonexistent"), {}, validate, fetch)


class ScriptedKeys:
    """`open_attempt` with keys from a list instead of a database. The disposable check has that."""

    def __init__(
        self, client_factory: Callable[[str], Any], keys: list[Any], rejected: list[Any]
    ) -> None:
        async def fetch() -> dict[str, Any]:
            return catalog_payload()

        self.catalog = CatalogCache(fetch)
        self.client_factory = client_factory
        self.keys = keys
        self.rejected = rejected

    async def open_attempt(self, workspace_id: Any, policy: Any) -> Any:
        try:
            attempt, _ = prepared(policy, await self.catalog.current())
        except ModelUnavailable:
            raise ProviderFailure(FailureClass.MODEL_UNAVAILABLE) from None
        key = self.keys.pop(0)
        if isinstance(key, Exception):
            raise key
        model = chat_model(attempt, SecretStr(key), client_factory=self.client_factory)
        return model, CredentialReference("app", None, 1)

    async def reject_key(self, workspace_id: Any, used: CredentialReference) -> None:
        self.rejected.append(used)


def source_with(fake: Fake, keys: list[Any], rejected: list[Any] | None = None) -> Any:
    return ScriptedKeys(fake.client, keys, rejected if rejected is not None else [])


@tool
def lookup(text: str) -> str:
    """Look something up."""
    return text


def attempt_model(source: Any, profile: str = DEEPSEEK.id.value) -> AttemptModel:
    return AttemptModel(source, uuid4(), frozen_policy(snapshot(profile)))


def invoke(model: Any) -> Any:
    return asyncio.run(model.ainvoke([HumanMessage("hello")]))


def test_a_request_carries_the_routes_identity_limits_and_routing_flags() -> None:
    fake = Fake()
    invoke(attempt_model(source_with(fake, [ARRANGED_KEY])).bind_tools([lookup]))
    body = fake.bodies[0]
    assert body["model"] == DEEPSEEK_WIRE_ID
    assert body["max_tokens"] == MAX_OUTPUT_TOKENS
    assert body["provider"] == {"require_parameters": True, "allow_fallbacks": False}
    assert not body.get("models")
    assert [item["function"]["name"] for item in body["tools"]] == ["lookup"]
    assert fake.keys == [f"Bearer {ARRANGED_KEY}"]


def test_the_wire_id_follows_the_runs_binding() -> None:
    fake = Fake()
    invoke(attempt_model(source_with(fake, [ARRANGED_KEY]), TERRA.id.value))
    assert fake.bodies[0]["model"] == TERRA_WIRE_ID


def test_the_reply_gives_the_loop_what_it_settles_on() -> None:
    fake = Fake(cost=0.00025)
    message = invoke(attempt_model(source_with(fake, [ARRANGED_KEY])).bind_tools([lookup]))
    assert _charged(message) == 250
    assert message.response_metadata["finish_reason"] == "tool_calls"
    assert [(call["name"], call["args"]) for call in message.tool_calls] == [
        ("lookup", {"text": "a"})
    ]


def test_each_attempt_opens_its_own_client_so_a_rotation_reaches_the_next_call() -> None:
    fake = Fake()
    model = attempt_model(source_with(fake, ["arranged-first-key", "arranged-next-key"]))
    invoke(model)
    invoke(model)
    assert fake.clients == 2
    assert fake.keys == ["Bearer arranged-first-key", "Bearer arranged-next-key"]


def test_a_missing_key_stops_the_attempt_before_anything_is_sent() -> None:
    fake = Fake()
    missing = ProviderFailure(FailureClass.CREDENTIALS_REQUIRED)
    with pytest.raises(ProviderFailure) as caught:
        invoke(attempt_model(source_with(fake, [missing])))
    assert caught.value.failure is FailureClass.CREDENTIALS_REQUIRED
    assert fake.bodies == []


def test_a_stale_catalog_stops_the_attempt_before_any_key_is_read() -> None:
    fake = Fake()
    source = source_with(fake, [ARRANGED_KEY])
    source.catalog._snapshot = parse_catalog(
        catalog_payload(), retrieved_at=NOW - timedelta(minutes=6), revision="old"
    )

    async def nothing() -> None:
        return None

    source.catalog._fetch = nothing
    with pytest.raises(ProviderFailure) as caught:
        invoke(attempt_model(source))
    assert caught.value.failure is FailureClass.MODEL_UNAVAILABLE
    assert fake.bodies == []
    assert source.keys == [ARRANGED_KEY]


def test_a_401_marks_the_key_rejected_and_is_still_raised_with_its_status() -> None:
    fake = Fake(status=401)
    rejected: list[Any] = []
    with pytest.raises(openrouter.errors.OpenRouterError) as caught:
        invoke(attempt_model(source_with(fake, [ARRANGED_KEY], rejected)))
    assert caught.value.status_code == 401
    assert len(fake.bodies) == 1
    assert len(rejected) == 1


@pytest.mark.parametrize("status", [402, 429, 500])
def test_other_statuses_leave_the_key_alone(status: int) -> None:
    fake = Fake(status=status)
    rejected: list[Any] = []
    with pytest.raises(openrouter.errors.OpenRouterError):
        invoke(attempt_model(source_with(fake, [ARRANGED_KEY], rejected)))
    assert rejected == []


def test_no_key_or_client_survives_on_the_model_the_graph_holds() -> None:
    fake = Fake()
    model = attempt_model(source_with(fake, [ARRANGED_KEY])).bind_tools([lookup])
    invoke(model)
    assert ARRANGED_KEY not in repr(vars(model))
    admitted = AdmittedModel(delegate=model)
    assert ARRANGED_KEY not in repr(admitted)


# Binding a job


def lease() -> Lease:
    return Lease(uuid4(), uuid4(), 1, "worker", 1, "running")


class Rows:
    def __init__(self, value: Any) -> None:
        self.value = value

    async def execute(self, *_: Any) -> "Rows":
        return self

    async def fetchone(self) -> tuple[Any]:
        return (self.value,)


def real_source() -> InferenceSource:
    async def fetch() -> dict[str, Any]:
        return catalog_payload()

    return InferenceSource("postgresql://unused", _context(fetch), CatalogCache(fetch))


def bind_with(
    value: Any, refusal: tuple[str | None, int], monkeypatch: pytest.MonkeyPatch
) -> tuple[Any, LoopConfig]:
    source = real_source()

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


def test_the_worst_case_is_an_upper_bound_at_the_stated_limits() -> None:
    entry = fresh_catalog().entries[0]
    assert entry.pricing is not None
    worst = worst_case_cost(entry.pricing, RESERVED_PROMPT_TOKENS, MAX_OUTPUT_TOKENS)
    assert worst == RESERVED_PROMPT_TOKENS * 1 + MAX_OUTPUT_TOKENS * 2


def test_the_real_catalog_prices_both_profiles_within_a_runs_default_cap() -> None:
    """Terra's cache-write rate is its highest input rate. Its long-prompt override starts far above
    what this app sends, so it doesn't count."""
    path = Path(__file__).parents[3] / "research/openrouter-model-catalog-2026-11-05.json"
    matches = {item["id"]: item for item in json.loads(path.read_text())["matches"]}
    prices = {wire: parse_pricing(matches[wire]) for wire in (DEEPSEEK_WIRE_ID, TERRA_WIRE_ID)}
    assert prices[DEEPSEEK_WIRE_ID] == Pricing(300_000, 1_200_000)
    assert prices[TERRA_WIRE_ID] == Pricing(1_250_000, 5_000_000)
    worst = {
        wire: worst_case_cost(price, RESERVED_PROMPT_TOKENS, MAX_OUTPUT_TOKENS)
        for wire, price in prices.items()
    }
    assert worst == {DEEPSEEK_WIRE_ID: 10_215, TERRA_WIRE_ID: 42_560}


def test_an_override_this_app_can_reach_still_counts() -> None:
    near = {"min_prompt_tokens": RESERVED_PROMPT_TOKENS, "prompt": "0.5", "completion": "0.5"}
    far = {"min_prompt_tokens": RESERVED_PROMPT_TOKENS + 1, "prompt": "9", "completion": "9"}
    pricing = {"prompt": "0.1", "completion": "0.1", "overrides": [near, far]}
    assert parse_pricing({"pricing": pricing}) == Pricing(500_000_000_000, 500_000_000_000)


def test_a_per_request_price_counts_wherever_it_is_listed() -> None:
    pricing = {"prompt": "0", "completion": "0", "overrides": [{"request": "0.002"}]}
    assert parse_pricing({"pricing": pricing}) == Pricing(0, 0, 2000)


@pytest.mark.parametrize(
    "pricing",
    [
        {"prompt": "0.1", "completion": "0.1", "overrides": [{"prompt": "-1"}]},
        {"prompt": "0.1", "completion": "0.1", "request": "-1"},
    ],
)
def test_a_variable_rate_is_not_hidden_by_a_fixed_one(pricing: dict[str, Any]) -> None:
    with pytest.raises(Exception, match="price is not known"):
        worst_case_cost(parse_pricing({"pricing": pricing}), 1, 1)


# What a provider's replies mean for the ledger, through the real SDK


def model_over(handle: Any) -> AttemptModel:
    fake = Fake()
    fake.handle = handle  # type: ignore[method-assign]
    return attempt_model(source_with(fake, [ARRANGED_KEY]))


def test_a_success_the_sdk_cant_parse_keeps_its_reservation() -> None:
    """A reply arrived, so it may have been charged. A 200 is not a refusal."""

    def handle(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"error": {"code": 500, "message": "arranged"}})

    with pytest.raises(openrouter.errors.ResponseValidationError) as caught:
        invoke(model_over(handle))
    assert classify_status(caught.value.status_code) is FailureClass.UNCERTAIN_ACCEPTANCE


def test_retry_after_is_read_from_a_real_sdk_error() -> None:
    def handle(_: httpx.Request) -> httpx.Response:
        error = {"error": {"code": 429, "message": "arranged"}}
        return httpx.Response(429, json=error, headers={"Retry-After": "60"})

    with pytest.raises(openrouter.errors.OpenRouterError) as caught:
        invoke(model_over(handle))
    assert _retry_after(caught.value) == 60.0


def test_an_unusable_retry_after_is_ignored() -> None:
    def handle(_: httpx.Request) -> httpx.Response:
        error = {"error": {"code": 429, "message": "arranged"}}
        return httpx.Response(429, json=error, headers={"Retry-After": "soon"})

    with pytest.raises(openrouter.errors.OpenRouterError) as caught:
        invoke(model_over(handle))
    assert _retry_after(caught.value) is None


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (httpx.ConnectError("arranged"), FailureClass.NETWORK_BEFORE_ACCEPTANCE),
        (httpx.ConnectTimeout("arranged"), FailureClass.NETWORK_BEFORE_ACCEPTANCE),
        (httpx.ReadTimeout("arranged"), FailureClass.UNCERTAIN_ACCEPTANCE),
        (httpx.RemoteProtocolError("arranged"), FailureClass.UNCERTAIN_ACCEPTANCE),
        (RuntimeError("arranged"), FailureClass.UNCERTAIN_ACCEPTANCE),
    ],
)
def test_only_a_connection_that_never_opened_counts_as_unsent(
    error: Exception, expected: FailureClass
) -> None:
    assert _failure_without_status(error) is expected


@pytest.mark.parametrize(
    ("finish", "finished"),
    [
        ("stop", True),
        ("tool_calls", True),
        ("length", False),
        ("error", False),
        ("content_filter", False),
    ],
)
def test_only_a_reply_the_model_finished_can_run(finish: str, finished: bool) -> None:
    assert _finished(AIMessage(content="", response_metadata={"finish_reason": finish})) is finished


def test_reply_facts_hold_no_content_and_stay_bounded() -> None:
    calls = [
        {"name": "x" * 500, "args": {"content": "the report's text"}, "id": str(number)}
        for number in range(30)
    ]
    message = AIMessage(
        content="the report's text",
        tool_calls=calls,
        invalid_tool_calls=[{"name": "save_artifact", "args": '{"pa', "id": "cut", "error": "bad"}],
        response_metadata={"finish_reason": "length"},
        usage_metadata={
            "input_tokens": 9,
            "output_tokens": 512,
            "total_tokens": 521,
            "output_token_details": {"reasoning": 400},
        },
    )
    facts = reply_facts(message)
    assert (
        facts.finish_reason,
        facts.input_tokens,
        facts.output_tokens,
        facts.reasoning_tokens,
    ) == ("length", 9, 512, 400)
    assert facts.invalid_tool_calls == 1
    assert len(facts.tool_names) == MAX_FACT_NAMES and {len(name) for name in facts.tool_names} == {
        MAX_FACT_CHARS
    }
    assert "report" not in repr(facts)
    # A reply with nothing to report is still a record, not a failure.
    empty = reply_facts(AIMessage(content=""))
    assert (
        empty.finish_reason,
        empty.output_tokens,
        empty.tool_names,
        empty.invalid_tool_calls,
    ) == (None, None, (), 0)


def test_a_refused_summary_stops_the_loop_with_its_reason() -> None:
    """A budget that runs out during compaction pauses the run like one at any other call."""

    class Refusing(LoopMiddleware):
        def __init__(self) -> None:
            self._summary_route = UNBOUND

        async def _guard(self) -> float:
            return 1.0

        async def _admitted_call(self, *_: Any, **__: Any) -> Any:
            raise BudgetExceeded("arranged")

    class Request:
        def override(self, **_: Any) -> "Request":
            return self

    async def go() -> None:
        await Refusing()._summarize(Request(), None, [HumanMessage("old")], None, 0, 1)

    with pytest.raises(LoopStopped) as caught:
        asyncio.run(go())
    assert caught.value.code == "budget_exceeded"


def test_a_busy_slot_during_a_summary_is_waited_out_like_any_other_call() -> None:
    answers: list[Any] = [NoInferenceSlot("arranged"), NoInferenceSlot("arranged"), ("reply", True)]
    waits: list[float] = []

    class Busy(LoopMiddleware):
        def __init__(self) -> None:
            self._slot_wait_seconds = 30.0

        async def _guard(self) -> float:
            return 1.0

        async def _sleep(self, seconds: float) -> None:
            waits.append(seconds)

        async def _admitted_call(self, *_: Any, **__: Any) -> Any:
            answer = answers.pop(0)
            if isinstance(answer, Exception):
                raise answer
            return answer

    assert asyncio.run(Busy()._with_slot(None, None)) == ("reply", True)
    assert waits == [1.0, 1.0]


@pytest.mark.parametrize(
    ("finish", "repairs"), [("length", 1), ("error", 0), ("content_filter", 0)]
)
def test_only_a_cut_off_reply_is_worth_a_repair(finish: str, repairs: int) -> None:
    done: list[str] = []
    message = AIMessage(content="", response_metadata={"finish_reason": finish})

    class Reply:
        def __init__(self) -> None:
            self.result = [message]

    class Request:
        def __init__(self) -> None:
            self.messages: list[Any] = []

        def override(self, **_: Any) -> "Request":
            return self

    async def handler(_: Any) -> Any:
        raise AssertionError("the stand-in never calls the model")

    class Stopping(LoopMiddleware):
        def __init__(self) -> None:
            pass

        async def _guard(self) -> float:
            return 1.0

        async def _compacted(self, request: Any, _: Any) -> Any:
            return request

        async def _with_slot(self, *_: Any, **__: Any) -> Any:
            return Reply(), False

        async def _repair(self, code: str) -> None:
            done.append(code)
            raise LoopStopped(code)

    with pytest.raises(LoopStopped) as caught:
        asyncio.run(Stopping().awrap_model_call(Request(), handler))
    assert caught.value.code == "incomplete_output"
    assert len(done) == repairs


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
    monkeypatch: pytest.MonkeyPatch, outcome: Any, fake: Fake | None = None
) -> tuple[Any, CredentialReference]:
    async def credential(*_: Any) -> Any:
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr("psycopg.AsyncConnection.connect", connected)
    monkeypatch.setattr(ProviderSettings, "credential_for_attempt", credential)
    source = replace(real_source(), client_factory=(fake or Fake()).client)
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
        (CredentialDecryptionError(), FailureClass.CREDENTIAL_UNAVAILABLE),
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
    fake = Fake()
    client, used = real_attempt(monkeypatch, Current(3), fake)
    assert fake.clients == 1
    assert used == CredentialReference("app", None, 3)
    assert ARRANGED_KEY not in repr(used)
    assert client.model_name == DEEPSEEK_WIRE_ID


def test_a_price_gone_mid_job_stops_the_next_attempt_before_any_key_is_read() -> None:
    async def fetch() -> dict[str, Any]:
        return catalog_payload(pricing=None)

    source = InferenceSource("postgresql://unused", _context(fetch), CatalogCache(fetch))
    with pytest.raises(ProviderFailure) as caught:
        asyncio.run(source.open_attempt(uuid4(), frozen_policy(snapshot())))
    assert caught.value.failure is FailureClass.COST_UNAVAILABLE


# Marking a key rejected


class Settings(ProviderSettings):
    """The real gate over a stored status and an arranged key, with no database."""

    def __init__(self, active: Any, stored: str = "configured") -> None:
        self.active = active
        self.stored = stored
        self.recorded: list[str] = []
        self._store = self  # type: ignore[assignment]

    async def _effective_environment(self, _: Any) -> Any:
        return None

    async def _settings_row(self, *_: Any, **__: Any) -> tuple[int, str, Any]:
        return 1, self.stored, None

    async def route_qualifications(self) -> list[Any]:
        return []

    async def _record(self, _: Any, status: str) -> None:
        self.recorded.append(status)

    async def load_active(self, _: Any) -> Any:
        if isinstance(self.active, Exception):
            raise self.active
        return self.active


def test_a_401_marks_the_key_that_received_it_while_it_is_current() -> None:
    settings = Settings(Current(2))
    asyncio.run(settings.mark_invalid(uuid4(), CredentialReference("app", None, 2)))
    assert settings.recorded == ["invalid"]


def test_a_401_for_a_key_replaced_mid_call_leaves_its_successor_alone() -> None:
    settings = Settings(Current(3))
    asyncio.run(settings.mark_invalid(uuid4(), CredentialReference("app", None, 2)))
    assert settings.recorded == []


def test_a_key_that_wont_decrypt_reads_as_unavailable_not_an_error() -> None:
    settings = Settings(CredentialDecryptionError())
    assert asyncio.run(settings.run_intent(uuid4())) == "credential_unavailable"


def test_a_damaged_key_still_gives_the_version_needed_to_replace_it() -> None:
    async def nothing() -> None:
        return None

    settings = Settings(CredentialDecryptionError())
    settings._context = _context(nothing)
    status = asyncio.run(settings.status(uuid4()))
    assert (status.auth_status, status.settings_version) == ("unavailable", 1)


def test_rechecking_a_damaged_key_says_storage_not_an_error() -> None:
    settings = Settings(CredentialDecryptionError())
    with pytest.raises(CredentialStorageUnavailable):
        asyncio.run(settings.revalidate(uuid4()))


def test_a_stored_failed_check_blocks_an_environment_key_too() -> None:
    class FromEnvironment(Settings):
        async def _effective_environment(self, _: Any) -> Any:
            return EnvironmentCandidate("process_environment", ARRANGED_KEY)

    settings = FromEnvironment(None, stored="unavailable")
    assert asyncio.run(settings.run_intent(uuid4())) == "credential_unavailable"
    settings.stored = "configured"
    assert asyncio.run(settings.run_intent(uuid4())) == "ready"


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


def test_a_malformed_catalog_is_a_failed_refresh_not_a_crash() -> None:
    async def fetch() -> dict[str, Any]:
        return {"data": ["not an entry"]}

    with pytest.raises(ModelUnavailable):
        asyncio.run(CatalogCache(fetch).current())


# The entry point


def test_the_switch_needs_its_configuration_rather_than_starting_half_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AUTOBOTS_CONFIG_ROOT", raising=False)
    with pytest.raises(SystemExit, match="AUTOBOTS_CONFIG_ROOT"):
        worker.inference_from_environment("postgresql://unused", object(), None, None)
    monkeypatch.setenv("AUTOBOTS_CONFIG_ROOT", "/nonexistent")
    with pytest.raises(SystemExit, match="service key"):
        worker.inference_from_environment("postgresql://unused", None, None, None)


def test_a_failing_first_step_does_not_starve_the_second() -> None:
    async def broken(_: Any) -> bool:
        raise RuntimeError("arranged")

    async def working(_: Any) -> bool:
        return True

    async def go() -> bool:
        return await worker.both(broken, working)(None)

    assert asyncio.run(go()) is True


def test_losing_the_database_still_reaches_the_serve_loop() -> None:
    async def lost(_: Any) -> bool:
        raise psycopg.OperationalError("arranged")

    async def working(_: Any) -> bool:
        raise AssertionError("no second step on a lost connection")

    async def go() -> bool:
        return await worker.both(lost, working)(None)

    with pytest.raises(psycopg.OperationalError):
        asyncio.run(go())


def test_a_relative_configuration_root_refuses_to_start(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTOBOTS_CONFIG_ROOT", "relative/path")
    with pytest.raises(SystemExit, match="absolute"):
        worker.inference_from_environment("postgresql://unused", object(), None, None)


def test_both_steps_run_and_either_one_counts_as_work() -> None:
    calls: list[str] = []

    def step(name: str, worked: bool) -> Any:
        async def inner(_: Any) -> bool:
            calls.append(name)
            return worked

        return inner

    async def run_both(first: bool, second: bool) -> bool:
        return await worker.both(step("first", first), step("second", second))(None)

    assert asyncio.run(run_both(False, True)) is True
    assert calls == ["first", "second"]
    assert asyncio.run(run_both(True, False)) is True
    assert asyncio.run(run_both(False, False)) is False
