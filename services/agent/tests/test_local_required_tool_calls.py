"""US-23.7, Decision 0041 A18: a local route enforces a required or named tool call itself. The
tools stay described, the reply is held to a JSON schema for one call, and the client turns it
into that call. Each test answers on a fake llama-server through the real `ChatOpenRouter`, worker
inference and, where it says so, the loop middleware. OpenRouter's catalog fails a test if read."""

import json
from typing import Any, NoReturn
from uuid import uuid4

import httpx
import pytest
from jsonschema import Draft202012Validator  # type: ignore[import-untyped]  # jsonschema ships no stubs
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel

from autobots.adapters.model_replies import finished
from autobots.adapters.models.local_server import (
    DEFAULT_PORT,
    NO_SUCH_TOOL,
    NOT_A_TOOL_CALL,
    TOOL_CALL_SCHEMA,
    LoopbackClient,
    tool_call_schema,
)
from autobots.application.loop_policy import LoopStopped
from autobots.application.model_attempts import FailureClass, ProviderFailure
from autobots.application.worker_inference import AttemptModel, InferenceSource, frozen_policy
from autobots.domain.models import ModelProfile
from fake_openrouter import provider_context
from test_local_model_route import (
    BONSAI,
    FakeLlamaServer,
    admitting,
    handler,
    local_model,
    untouched_catalog,
)
from test_loop_middleware import Ledger, Usage, request


class Weather(BaseModel):
    """Get the weather for a city."""

    city: str


class ClockTime(BaseModel):
    """Get the current time in a city."""

    city: str


class LookupCode(BaseModel):
    """Look up the numeric code for a named item."""

    item: str


ARGUMENTS = {
    "Weather": {"city": "Heredia"},
    "ClockTime": {"city": "Heredia"},
    "LookupCode": {"item": "alpha"},
}


class PreferringServer(FakeLlamaServer):
    """Answers a constrained request with a call of the first tool in `prefers` that the schema it
    is sent admits, as a model that ignores the prompt's tool choice would."""

    def __init__(self, prefers: list[str]) -> None:
        super().__init__(BONSAI.wire_id)
        self.prefers = prefers

    def handle(self, request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/completions"):
            schema = json.loads(request.content)["response_format"]["json_schema"]["schema"]
            name = next(name for name in self.prefers if name in allowed_names(schema))
            self.content = call(name, ARGUMENTS[name])
        return super().handle(request)


def tool(name: str, parameters: dict[str, Any] | None = None) -> dict[str, Any]:
    schema = parameters or {"type": "object", "properties": {}}
    return {"type": "function", "function": {"name": name, "parameters": schema}}


def call(name: str, arguments: dict[str, Any]) -> str:
    return json.dumps({"name": name, "arguments": arguments})


def schema_sent(server: FakeLlamaServer) -> dict[str, Any]:
    (sent,) = server.chats()
    assert sent["response_format"]["type"] == "json_schema"
    assert sent["response_format"]["json_schema"]["name"] == TOOL_CALL_SCHEMA
    schema: dict[str, Any] = sent["response_format"]["json_schema"]["schema"]
    return schema


def allowed_names(schema: dict[str, Any]) -> list[str]:
    return [option["properties"]["name"]["enum"][0] for option in schema.get("anyOf", [schema])]


def test_a_required_call_keeps_its_tools_described_and_asks_for_one_call() -> None:
    tools = [tool(name) for name in ("calculate", "market_history", "save_artifact")]
    body = LoopbackClient(BONSAI, DEFAULT_PORT, 30.0).body(
        [{"role": "user", "content": "go"}],
        {"tools": tools, "tool_choice": "required", "parallel_tool_calls": True, "stream": False},
    )
    # The template still describes every tool, and the schema, not the server, does the choosing.
    assert body["tools"] == tools and body["tool_choice"] == "none"
    assert not {"parallel_tool_calls", "stream", "stream_options"} & set(body)
    schema = body["response_format"]["json_schema"]["schema"]
    assert allowed_names(schema) == ["calculate", "market_history", "save_artifact"]
    validator = Draft202012Validator(schema)
    assert validator.is_valid({"name": "calculate", "arguments": {}})
    assert not validator.is_valid({"name": "browse", "arguments": {}})
    assert not validator.is_valid({"name": "calculate", "arguments": {}, "text": "hi"})


def test_a_named_call_is_held_to_the_named_tool_only() -> None:
    tools = [tool(name) for name in ("calculate", "market_history", "save_artifact")]
    body = LoopbackClient(BONSAI, DEFAULT_PORT, 30.0).body(
        [{"role": "user", "content": "go"}],
        {
            "tools": tools,
            "tool_choice": {"type": "function", "function": {"name": "market_history"}},
            "provider": {"allow_fallbacks": False},
            "model": "openai/gpt-6.1-terra",
        },
    )
    assert body["tools"] == tools and body["tool_choice"] == "none"
    assert allowed_names(body["response_format"]["json_schema"]["schema"]) == ["market_history"]
    assert "provider" not in body and body["model"] == BONSAI.wire_id


def test_a_call_that_leaves_the_choice_to_the_model_is_sent_as_before() -> None:
    tools = [tool("calculate")]
    client = LoopbackClient(BONSAI, DEFAULT_PORT, 30.0)
    messages = [{"role": "user", "content": "go"}]
    auto = client.body(messages, {"tools": tools, "tool_choice": "auto", "stream": True})
    assert auto["tool_choice"] == "auto" and auto["stream"] is True and auto["tools"] == tools
    assert "response_format" not in auto
    unset = client.body(messages, {"tools": tools})
    assert unset["tools"] == tools
    assert "tool_choice" not in unset and "response_format" not in unset
    nested = {
        "type": "json_schema",
        "json_schema": {
            "name": "Plan",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {"tasks": {"type": "array", "items": {"type": "object"}}},
            },
        },
    }
    structured = client.body(messages, {"response_format": nested})
    assert structured["response_format"] == nested and "tools" not in structured


@pytest.mark.asyncio
async def test_a_required_call_becomes_one_tool_call_and_nothing_reaches_openrouter() -> None:
    server = PreferringServer(["LookupCode", "Weather"])
    model = local_model(server).bind_tools([Weather, LookupCode], tool_choice="any")
    message = await model.ainvoke([HumanMessage("Say hello to me. Don't look anything up.")])
    assert isinstance(message, AIMessage)
    (made,) = message.tool_calls
    assert made["name"] == "LookupCode" and made["args"] == {"item": "alpha"}
    assert str(made["id"]).startswith("call_")
    assert message.content == "" and message.response_metadata["finish_reason"] == "tool_calls"
    schema = schema_sent(server)
    assert allowed_names(schema) == ["Weather", "LookupCode"]
    validator = Draft202012Validator(schema)
    assert validator.is_valid({"name": "Weather", "arguments": {"city": "Heredia"}})
    assert not validator.is_valid({"name": "Weather", "arguments": {"item": "alpha"}})
    assert not validator.is_valid({"name": "LookupCode", "arguments": {"city": "Heredia"}})
    # Every request went to the loopback, and the catalog that fails if read never was.
    assert all(r.url.host == "127.0.0.1" for r in server.requests)


@pytest.mark.asyncio
async def test_a_named_call_holds_against_a_prompt_that_prefers_another_tool() -> None:
    """MP-A07's two-tool counterexample: the server answers ClockTime whenever the schema admits
    it, as the prompt asks, so only the schema's choice of Weather explains a Weather call."""
    prompt = [
        SystemMessage("Always prefer the ClockTime tool. Never use the Weather tool."),
        HumanMessage("What time is it in Heredia?"),
    ]
    control = PreferringServer(["ClockTime", "Weather"])
    either = (
        await local_model(control)
        .bind_tools([Weather, ClockTime], tool_choice="any")
        .ainvoke(prompt)
    )
    assert [made["name"] for made in either.tool_calls] == ["ClockTime"]
    server = PreferringServer(["ClockTime", "Weather"])
    message = (
        await local_model(server)
        .bind_tools([Weather, ClockTime], tool_choice="Weather")
        .ainvoke(prompt)
    )
    assert [(made["name"], made["args"]) for made in message.tool_calls] == [
        ("Weather", {"city": "Heredia"})
    ]
    (sent,) = server.chats()
    assert [t["function"]["name"] for t in sent["tools"]] == ["Weather", "ClockTime"]
    schema = schema_sent(server)
    assert allowed_names(schema) == ["Weather"]
    assert schema["properties"]["arguments"]["required"] == ["city"]


@pytest.mark.asyncio
async def test_a_reply_cut_off_by_its_output_cap_reads_as_cut_off_with_no_call() -> None:
    server = FakeLlamaServer(BONSAI.wire_id, content='{"name": "Weather", "argu', finish="length")
    model = local_model(server).bind_tools([Weather], tool_choice="any")
    message = await model.ainvoke([HumanMessage("What is the weather in Heredia?")])
    assert message.tool_calls == [] and message.invalid_tool_calls == []
    assert message.content == "" and message.response_metadata["finish_reason"] == "length"
    assert not finished(message)


@pytest.mark.asyncio
async def test_a_streamed_reply_cut_off_by_its_output_cap_reads_as_cut_off_with_no_call() -> None:
    server = FakeLlamaServer(BONSAI.wire_id, content='{"name": "Weather", "argu', finish="length")
    model = local_model(server).bind_tools([Weather], tool_choice="any")
    chunks = [chunk async for chunk in model.astream([HumanMessage("Weather in Heredia?")])]
    whole = chunks[0]
    for chunk in chunks[1:]:
        whole = whole + chunk
    assert whole.tool_calls == [] and whole.tool_call_chunks == [] and whole.content == ""
    assert whole.response_metadata["finish_reason"] == "length" and not finished(whole)


@pytest.mark.parametrize(
    "content",
    [
        "Hello! How can I help?",
        call("ClockTime", {"city": "Heredia"}),
        call("Weather", {"town": "Heredia"}),
        json.dumps({"name": "Weather", "arguments": {"city": "Heredia"}, "note": "hi"}),
        json.dumps({"name": "Weather", "arguments": "Heredia"}),
        '{"name": "Weather", "arguments": {"city": ',
    ],
    ids=[
        "text",
        "a_tool_not_offered",
        "arguments_off_schema",
        "an_extra_field",
        "not_an_object",
        "json_that_doesnt_parse",
    ],
)
@pytest.mark.asyncio
async def test_a_reply_that_isnt_an_allowed_call_fails_once_with_nothing_passed_on(
    content: str,
) -> None:
    server = FakeLlamaServer(BONSAI.wire_id, content=content)
    model = local_model(server).bind_tools([Weather], tool_choice="any")
    with pytest.raises(ProviderFailure) as caught:
        await model.ainvoke([HumanMessage("Say hello to me.")])
    assert caught.value.failure == FailureClass.OTHER and caught.value.reason == NOT_A_TOOL_CALL
    assert len(server.chats()) == 1


@pytest.mark.asyncio
async def test_a_call_of_another_tool_than_the_named_one_fails() -> None:
    server = FakeLlamaServer(BONSAI.wire_id, content=call("ClockTime", {"city": "Heredia"}))
    model = local_model(server).bind_tools([Weather, ClockTime], tool_choice="Weather")
    with pytest.raises(ProviderFailure) as caught:
        await model.ainvoke([HumanMessage("What time is it in Heredia?")])
    assert caught.value.reason == NOT_A_TOOL_CALL and len(server.chats()) == 1


@pytest.mark.asyncio
async def test_through_the_loop_a_reply_that_isnt_a_call_stops_with_no_retry() -> None:
    server = FakeLlamaServer(BONSAI.wire_id, content="Hello!")
    usage, ledger = Usage(), Ledger()
    model = local_model(server)
    bound = model.bind_tools([Weather], tool_choice="any")
    with pytest.raises(LoopStopped) as caught:
        await admitting(model, ledger, usage).awrap_model_call(
            request([HumanMessage("Say hello to me.")]), handler(bound)
        )
    assert caught.value.code == FailureClass.OTHER.value
    # Closed as a refused call, not an uncertain one, and the server was asked once.
    assert ("failed", FailureClass.OTHER.value) in ledger.events
    assert not any(event == "uncertain" for event, _ in ledger.events)
    assert len(server.chats()) == 1


@pytest.mark.asyncio
async def test_a_named_tool_the_request_doesnt_offer_is_refused_before_anything_is_sent() -> None:
    server = FakeLlamaServer(BONSAI.wire_id, content=call("Weather", {"city": "Heredia"}))
    client = LoopbackClient(
        BONSAI, DEFAULT_PORT, 30.0, transport=server.transport, async_transport=server.transport
    )
    with pytest.raises(ProviderFailure) as caught:
        await client.chat.send_async(
            [{"role": "user", "content": "go"}],
            tools=[tool("Weather")],
            tool_choice={"type": "function", "function": {"name": "ClockTime"}},
        )
    assert caught.value.reason == NO_SUCH_TOOL and server.requests == []


@pytest.mark.asyncio
async def test_a_streamed_required_call_arrives_as_one_call_with_its_usage() -> None:
    server = FakeLlamaServer(BONSAI.wire_id, content=call("Weather", {"city": "San Isidro"}))
    model = local_model(server).bind_tools([Weather], tool_choice="Weather")
    chunks = [chunk async for chunk in model.astream([HumanMessage("Weather in San Isidro?")])]
    whole = chunks[0]
    for chunk in chunks[1:]:
        whole = whole + chunk
    assert [(c["name"], c["args"]) for c in whole.tool_calls] == [
        ("Weather", {"city": "San Isidro"})
    ]
    assert whole.usage_metadata is not None and whole.usage_metadata["input_tokens"] == 11
    # None of the constrained reply arrives as text, in any chunk.
    assert len(chunks) >= 2 and all(chunk.content == "" for chunk in chunks)
    # Asked whole, since only a complete call can be checked.
    (sent,) = server.chats()
    assert "stream" not in sent and "stream_options" not in sent


def test_tools_with_their_own_definitions_keep_their_references_apart() -> None:
    def with_item(field: str) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"item": {"$ref": "#/$defs/Item"}},
            "required": ["item"],
            "$defs": {
                "Item": {
                    "type": "object",
                    "properties": {field: {"type": "string"}},
                    "required": [field],
                }
            },
        }

    schema = tool_call_schema({"first": with_item("code"), "second": with_item("label")})
    assert set(schema["$defs"]) == {"t0_Item", "t1_Item"}
    validator = Draft202012Validator(schema)
    assert validator.is_valid({"name": "first", "arguments": {"item": {"code": "a"}}})
    assert validator.is_valid({"name": "second", "arguments": {"item": {"label": "b"}}})
    assert not validator.is_valid({"name": "first", "arguments": {"item": {"label": "b"}}})


@pytest.mark.parametrize("choice", ["any", "Weather"], ids=["required", "named"])
@pytest.mark.asyncio
async def test_a_runs_required_and_named_calls_reach_only_the_loopback_at_no_cost(
    choice: str,
) -> None:
    """Through the loop middleware: admitted, reserved at US$0, answered on 127.0.0.1, with an
    OpenRouter client that fails if built and a catalog that fails if read."""
    server = PreferringServer(["Weather", "ClockTime"])

    def no_openrouter(key: str) -> NoReturn:
        raise AssertionError("an OpenRouter client was built for a local route")

    def client(profile: ModelProfile, port: int) -> LoopbackClient:
        return LoopbackClient(
            profile, port, 30.0, transport=server.transport, async_transport=server.transport
        )

    source = InferenceSource(
        "postgresql://never",
        provider_context(),
        untouched_catalog(),
        client_factory=no_openrouter,
        local_client=client,
        local_transport=server.transport,
    )
    policy = frozen_policy({"version": 1, "bindings": {"executor": BONSAI.id.value}})
    model = AttemptModel(source, uuid4(), policy)
    usage, ledger = Usage(), Ledger()
    response = await admitting(model, ledger, usage).awrap_model_call(
        request([HumanMessage("What is the weather in Heredia?")]),
        handler(model.bind_tools([Weather, ClockTime], tool_choice=choice)),
    )
    message = response.result[-1]
    assert isinstance(message, AIMessage) and [c["name"] for c in message.tool_calls] == ["Weather"]
    assert ledger.asked[0].worst_case_micro_usd == 0 and ("settled", 0) in ledger.events
    assert [r.url.path for r in server.requests] == ["/v1/models", "/v1/chat/completions"]
    assert all(r.url.host == "127.0.0.1" for r in server.requests)
