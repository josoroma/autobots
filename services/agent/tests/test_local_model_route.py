"""US-23.1, Decision 0041 A2, A3, A7 and A9: a model call on a local profile, answered by a fake
llama-server on an httpx transport, through the real `ChatOpenRouter`, worker inference and loop
middleware. The admission ledger and usage row are the in-memory stand-ins
`test_loop_middleware.py` uses, and OpenRouter's catalog fails the test if it is read."""

import json
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import uuid4

import httpx
import pytest
from langchain.agents.middleware.types import ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.prebuilt.tool_node import ToolCallRequest
from pydantic import SecretStr

from autobots.adapters.loop_middleware import LoopMiddleware
from autobots.adapters.model_replies import charged
from autobots.adapters.models.catalog import ModelUnavailable
from autobots.adapters.models.factory import (
    UnsupportedRequestOption,
    chat_model,
    local_chat_model,
    prepare_attempt,
)
from autobots.adapters.models.local_server import (
    DEFAULT_PORT,
    PORT_VARIABLE,
    LocalServerUnavailable,
    LoopbackClient,
    check_served,
    local_port,
)
from autobots.application import loop_admission
from autobots.application.loop_policy import LoopStopped
from autobots.application.model_attempts import FailureClass, ProviderFailure
from autobots.application.model_policy import validated_choice
from autobots.application.run_admission import WorkspacePolicy
from autobots.application.run_usage import RootLimits
from autobots.application.worker_inference import (
    AttemptModel,
    CatalogCache,
    InferenceSource,
    frozen_policy,
    prepared,
)
from autobots.contracts.experts import ExpertConfig
from autobots.domain.models import (
    OFFERED_FOR_NEW_RUNS,
    PROFILES,
    ModelProfile,
    ModelProfileId,
    ModelRole,
    ModelRoute,
    ProfileNotOffered,
    require_offered,
)
from autobots.domain.stops import DISPOSITION, Disposition, StopCode
from fake_openrouter import TERRA, catalog_payload, provider_context
from test_loop_middleware import SCOPE, Ledger, Usage, request, tool_request
from test_provider_settings import settings_over, stored_key

BONSAI = PROFILES[ModelProfileId.LOCAL_BONSAI_2_5]
INKLING = PROFILES[ModelProfileId.LOCAL_INKLING_2_MINI]
LOCAL_ROUTE = ModelRoute("executor", BONSAI.id.value, BONSAI.wire_id, 0)
USAGE = {"prompt_tokens": 11, "completion_tokens": 3, "total_tokens": 14}


class FakeLlamaServer:
    """The owner's llama-server, as `/v1/models` and `/v1/chat/completions` answer. Every request
    is kept, so a test can show what was sent and what wasn't."""

    def __init__(
        self,
        served: str,
        *,
        reasoning: str | None = None,
        tool_call: dict[str, Any] | None = None,
        down: bool = False,
    ) -> None:
        self.served = served
        self.reasoning = reasoning
        self.tool_call = tool_call
        self.down = down
        self.requests: list[httpx.Request] = []
        self.transport = httpx.MockTransport(self.handle)

    def chats(self) -> list[dict[str, Any]]:
        return [json.loads(r.content) for r in self.requests if r.url.path.endswith("/completions")]

    def message(self) -> dict[str, Any]:
        message: dict[str, Any] = {"role": "assistant", "content": "ready"}
        if self.reasoning is not None:
            message["reasoning_content"] = self.reasoning
        if self.tool_call is not None:
            message["content"] = None
            message["tool_calls"] = [self.tool_call]
        return message

    def handle(self, request: httpx.Request) -> httpx.Response:
        if self.down:
            raise httpx.ConnectError("connection refused", request=request)
        self.requests.append(request)
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"object": "list", "data": [{"id": self.served}]})
        body = json.loads(request.content)
        finish = "tool_calls" if self.tool_call else "stop"
        if body.get("stream"):
            delta = self.message()
            chunks = [
                {"choices": [{"index": 0, "delta": delta, "finish_reason": None}]},
                {"choices": [{"index": 0, "delta": {}, "finish_reason": finish}]},
                {"choices": [], "usage": dict(USAGE)},
            ]
            text = (
                "".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks) + "data: [DONE]\n\n"
            )
            return httpx.Response(200, text=text, headers={"content-type": "text/event-stream"})
        return httpx.Response(
            200,
            json={
                "id": "local-1",
                "model": self.served,
                "choices": [{"index": 0, "message": self.message(), "finish_reason": finish}],
                "usage": dict(USAGE),
            },
        )


def untouched_catalog() -> CatalogCache:
    async def fetch() -> dict[str, Any]:
        raise AssertionError("OpenRouter's catalog was read for a local route")

    return CatalogCache(fetch)


def local_source(server: FakeLlamaServer) -> InferenceSource:
    """Inference for a local route: no database is ever opened ("postgresql://never"), and any read
    of OpenRouter's catalog fails."""

    def client(profile: ModelProfile, port: int) -> LoopbackClient:
        return LoopbackClient(
            profile, port, 30.0, transport=server.transport, async_transport=server.transport
        )

    return InferenceSource(
        "postgresql://never",
        provider_context(),
        untouched_catalog(),
        local_client=client,
        local_transport=server.transport,
    )


def local_model(server: FakeLlamaServer, profile: ModelProfile = BONSAI) -> AttemptModel:
    policy = frozen_policy({"version": 1, "bindings": {"executor": profile.id.value}})
    return AttemptModel(local_source(server), uuid4(), policy)


def admitting(
    model: AttemptModel, ledger: Ledger, usage: Usage, limits: RootLimits | None = None
) -> LoopMiddleware:
    async def owned() -> float:
        return 60.0

    return LoopMiddleware(
        usage, SCOPE, limits or RootLimits(), LOCAL_ROUTE, guard=owned, admission=lambda: ledger
    )


def handler(model: AttemptModel) -> Callable[[ModelRequest[Any]], Awaitable[ModelResponse[Any]]]:
    async def call(req: ModelRequest[Any]) -> ModelResponse[Any]:
        return ModelResponse(result=[await model.ainvoke(req.messages)])

    return call


@pytest.mark.asyncio
async def test_a_local_call_is_admitted_sent_to_the_loopback_with_no_key_and_settles_nothing() -> (
    None
):
    server = FakeLlamaServer(BONSAI.wire_id)
    usage, ledger = Usage(), Ledger()
    model = local_model(server)
    response = await admitting(model, ledger, usage).awrap_model_call(
        request([HumanMessage("hello")]), handler(model)
    )
    message = response.result[-1]
    assert isinstance(message, AIMessage) and message.content == "ready"
    assert [r.url.path for r in server.requests] == ["/v1/models", "/v1/chat/completions"]
    assert all(r.url.host == "127.0.0.1" and r.url.port == DEFAULT_PORT for r in server.requests)
    assert all("authorization" not in r.headers for r in server.requests)
    (sent,) = server.chats()
    assert sent["model"] == BONSAI.wire_id
    assert not {"provider", "route", "plugins", "reasoning"} & set(sent)
    # Admitted with a ticket, reserved US$0, settled at US$0 rather than left open, and counted.
    assert ledger.asked[0].worst_case_micro_usd == 0
    assert ledger.events[:2] == [("admitted", "executor"), ("dispatched", None)]
    assert ("settled", 0) in ledger.events and not any(e == "uncertain" for e, _ in ledger.events)
    assert usage.used["model_calls"] == 1
    assert message.usage_metadata is not None and message.usage_metadata["input_tokens"] == 11
    assert charged(message) == 0


@pytest.mark.asyncio
async def test_a_streamed_local_call_reports_its_usage_and_no_cost() -> None:
    server = FakeLlamaServer(BONSAI.wire_id, reasoning="thinking out loud")
    chunks = [chunk async for chunk in local_model(server).astream([HumanMessage("hello")])]
    text = "".join(str(chunk.content) for chunk in chunks)
    assert text == "ready"
    assert any(chunk.usage_metadata for chunk in chunks)
    assert all("thinking out loud" not in json.dumps(chunk.additional_kwargs) for chunk in chunks)
    (sent,) = server.chats()
    assert sent["stream"] is True and sent["chat_template_kwargs"] == {"enable_thinking": False}


@pytest.mark.asyncio
async def test_a_different_served_model_is_refused_before_any_chat_is_sent() -> None:
    server = FakeLlamaServer("some-other-model")
    with pytest.raises(ProviderFailure) as caught:
        await local_model(server).ainvoke([HumanMessage("hello")])
    assert caught.value.failure is FailureClass.MODEL_UNAVAILABLE
    assert [r.url.path for r in server.requests] == ["/v1/models"]


@pytest.mark.asyncio
async def test_a_stopped_server_blocks_with_its_own_reason_and_sends_nothing() -> None:
    server = FakeLlamaServer(BONSAI.wire_id, down=True)
    with pytest.raises(ProviderFailure) as caught:
        await local_model(server).ainvoke([HumanMessage("hello")])
    assert caught.value.failure is FailureClass.LOCAL_MODEL_SERVER_UNAVAILABLE
    assert server.requests == []
    code = StopCode(caught.value.failure.value)
    assert DISPOSITION[code] is Disposition.SUSPEND


@pytest.mark.asyncio
async def test_a_stopped_server_is_refused_as_its_reason_through_the_middleware() -> None:
    """The ledger closes it as never accepted, and the run's settings and files aren't read."""
    server = FakeLlamaServer(BONSAI.wire_id, down=True)
    usage, ledger = Usage(), Ledger()
    model = local_model(server)
    with pytest.raises(LoopStopped) as caught:
        await admitting(model, ledger, usage).awrap_model_call(
            request([HumanMessage("hello")]), handler(model)
        )
    assert caught.value.code == "local_model_server_unavailable"
    assert ("failed", "local_model_server_unavailable") in ledger.events
    assert server.requests == []


@pytest.mark.asyncio
async def test_a_local_run_stops_on_its_model_calls_as_an_openrouter_run_does() -> None:
    server = FakeLlamaServer(BONSAI.wire_id)
    model = local_model(server)
    middleware = admitting(model, Ledger(), Usage(), RootLimits(model_calls=0))
    with pytest.raises(LoopStopped) as caught:
        await middleware.awrap_model_call(request([HumanMessage("hello")]), handler(model))
    assert caught.value.code == "model_calls_limit"
    assert server.requests == []


@pytest.mark.asyncio
async def test_a_local_run_stops_on_its_tool_dispatches_as_an_openrouter_run_does() -> None:
    async def never(_: ToolCallRequest) -> ToolMessage:
        raise AssertionError("dispatched past the limit")

    model = local_model(FakeLlamaServer(BONSAI.wire_id))
    middleware = admitting(model, Ledger(), Usage(), RootLimits(tool_dispatches=0))
    with pytest.raises(LoopStopped) as caught:
        await middleware.awrap_tool_call(tool_request(), never)
    assert caught.value.code == "tool_dispatches_limit"


@pytest.mark.asyncio
async def test_a_local_run_stops_on_its_active_time_as_an_openrouter_run_does(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The real guard, with its two reads answered: still the owner, and every second used."""

    async def owner(*_: object) -> None:
        return None

    async def all_used(*_: object) -> float:
        return RootLimits().active_seconds

    monkeypatch.setattr(loop_admission, "ownership_refusal", owner)
    monkeypatch.setattr(loop_admission, "active_seconds_used", all_used)
    server = FakeLlamaServer(BONSAI.wire_id)
    model = local_model(server)
    ledger = Ledger()
    middleware = LoopMiddleware(Usage(), SCOPE, RootLimits(), LOCAL_ROUTE, admission=lambda: ledger)
    with pytest.raises(LoopStopped) as caught:
        await middleware.awrap_model_call(request([HumanMessage("hello")]), handler(model))
    assert caught.value.code == "active_time_limit"
    assert server.requests == []


@pytest.mark.asyncio
async def test_bonsai_turns_thinking_off_and_inklings_reasoning_never_reaches_the_reply() -> None:
    call = {
        "id": "call-1",
        "type": "function",
        "function": {"name": "calculate", "arguments": '{"expression": "840 * 0.125"}'},
    }
    bonsai = FakeLlamaServer(BONSAI.wire_id)
    await local_model(bonsai).ainvoke([HumanMessage("hello")])
    assert bonsai.chats()[0]["chat_template_kwargs"] == {"enable_thinking": False}
    inkling = FakeLlamaServer(INKLING.wire_id, reasoning="secret plan", tool_call=call)
    message = await local_model(inkling, INKLING).ainvoke([HumanMessage("hello")])
    assert inkling.chats()[0]["chat_template_kwargs"] == {"reasoning_effort": "none"}
    assert message.tool_calls[0]["args"] == {"expression": "840 * 0.125"}
    assert "secret plan" not in json.dumps(
        [message.content, message.tool_calls, message.additional_kwargs, message.response_metadata]
    )


def test_one_named_tool_is_sent_as_required_with_only_that_tool() -> None:
    tools = [
        {"type": "function", "function": {"name": name, "parameters": {"type": "object"}}}
        for name in ("calculate", "market_history", "save_artifact")
    ]
    client = LoopbackClient(BONSAI, DEFAULT_PORT, 30.0)
    body = client.body(
        [{"role": "user", "content": "go"}],
        {
            "tools": tools,
            "tool_choice": {"type": "function", "function": {"name": "market_history"}},
            "provider": {"allow_fallbacks": False},
            "model": "openai/gpt-6.1-terra",
        },
    )
    assert body["tool_choice"] == "required"
    assert [tool["function"]["name"] for tool in body["tools"]] == ["market_history"]
    assert "provider" not in body and body["model"] == BONSAI.wire_id


@pytest.mark.asyncio
async def test_an_openrouter_route_still_reads_its_catalog_and_never_the_loopback() -> None:
    server = FakeLlamaServer(BONSAI.wire_id)

    async def fetch() -> dict[str, Any]:
        return catalog_payload()

    source = InferenceSource(
        "postgresql://never",
        provider_context(fetch),
        CatalogCache(fetch),
        local_transport=server.transport,
    )
    policy = frozen_policy({"version": 1, "bindings": {"executor": TERRA.id.value}})
    attempt, worst = prepared(policy, await source.catalog.current())
    assert attempt.profile == TERRA and worst > 0
    assert attempt.catalog_revision == "live"
    assert server.requests == []


def test_a_local_profile_reads_no_catalog_and_refuses_openrouters_reasoning_option() -> None:
    policy = frozen_policy({"version": 1, "bindings": {"executor": BONSAI.id.value}})
    attempt = prepare_attempt(policy, ModelRole.EXECUTOR, None, options={"max_tokens": 4_096})
    assert attempt.catalog_revision == "local"
    with pytest.raises(UnsupportedRequestOption):
        prepare_attempt(policy, ModelRole.EXECUTOR, None, options={"reasoning": {"effort": "low"}})
    with pytest.raises(ValueError, match="local_chat_model"):
        chat_model(attempt, SecretStr("arranged-not-a-real-key"))
    local = local_chat_model(attempt, DEFAULT_PORT)
    assert local.model_name == BONSAI.wire_id
    # No SDK retries and no OpenRouter routing flags: application policy owns every retry.
    assert local.max_retries == 0 and local.openrouter_provider is None


def test_an_openrouter_profile_without_a_catalog_is_unavailable() -> None:
    policy = frozen_policy({"version": 1, "bindings": {"executor": TERRA.id.value}})
    with pytest.raises(ModelUnavailable):
        prepare_attempt(policy, ModelRole.EXECUTOR, None)


@pytest.mark.parametrize("profile", [BONSAI, INKLING])
def test_a_local_profile_isnt_offered_and_says_which_model(profile: ModelProfile) -> None:
    assert profile.id not in OFFERED_FOR_NEW_RUNS
    with pytest.raises(ProfileNotOffered) as caught:
        require_offered([profile.id])
    assert caught.value.code == "model_not_offered"
    assert profile.wire_id.split("-")[0].capitalize() in caught.value.reason


def test_the_port_is_configuration_and_a_malformed_one_is_refused() -> None:
    assert local_port({}) == DEFAULT_PORT
    assert local_port({PORT_VARIABLE: "9944"}) == 9944
    for bad in ("0", "70000", "nine", "-1"):
        with pytest.raises(ValueError, match=PORT_VARIABLE):
            local_port({PORT_VARIABLE: bad})


@pytest.mark.parametrize("profile", [BONSAI, INKLING], ids=["bonsai", "inkling"])
@pytest.mark.parametrize(
    "where", ["a new run", "the workspace default", "a role override", "an Expert's binding"]
)
def test_every_choice_naming_a_local_profile_is_refused_as_not_offered(
    profile: ModelProfile, where: str
) -> None:
    """The same gates that refuse DeepSeek (test_model_work_gate.py), each naming the model."""
    with pytest.raises(ProfileNotOffered) as refused:
        if where == "a new run":
            WorkspacePolicy().for_new_work(run_profile=profile.id, require_offer=True)
        elif where == "the workspace default":
            validated_choice(profile.id, {})
        elif where == "a role override":
            validated_choice(None, {"executor": profile.id})
        else:
            require_offered(
                ExpertConfig(role_bindings={"executor": profile.id}).role_bindings.values()
            )
    assert refused.value.code == "model_not_offered"
    assert "local route is qualified" in str(refused.value)


@pytest.mark.asyncio
async def test_the_model_list_leaves_out_local_profiles_that_arent_offered() -> None:
    listed = {model.profile for model in (await settings_over(stored_key(1)).models()).models}
    assert listed == {
        ModelProfileId.DEEPSEEK_FLASH,
        ModelProfileId.TERRA,
        ModelProfileId.SOL,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error", [httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError, httpx.ReadError]
)
async def test_any_transport_failure_of_the_identity_check_is_a_stopped_server(
    error: type[httpx.TransportError],
) -> None:
    """Whatever cut the check short, no chat was sent, so it's never left as an uncertain call."""

    def fail(request: httpx.Request) -> httpx.Response:
        raise error("arranged", request=request)

    with pytest.raises(LocalServerUnavailable):
        await check_served(BONSAI, DEFAULT_PORT, transport=httpx.MockTransport(fail))
