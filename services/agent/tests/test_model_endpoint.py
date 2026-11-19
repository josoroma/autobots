"""US-17.2 offline: the browser box's model endpoint, Decision 0035 Y7 and Y16. The request's
translation, one admitted call per request through a fake admission, typed refusals, and the server
on the Mac's loopback with its token. Real admission is checked on a disposable database
(tests/db/checks/model_endpoint_check.py)."""

import asyncio
import contextlib
import json
import socket
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

import pytest
from langchain_core.messages import AIMessage, BaseMessage

from autobots.adapters.model_endpoint import (
    EndpointRefused,
    ModelEndpoint,
    Reply,
    admitted_answer,
    parse_request,
)
from autobots.application.loop_admission import admitted_scope
from autobots.application.loop_policy import LoopStopped
from autobots.domain.models import ModelRoute

ROUTE = ModelRoute("researcher", "openrouter_sol", "openai/gpt-6.1-sol", 1000)
TOOLS = [
    {
        "type": "function",
        "function": {"name": "finish", "parameters": {"type": "object", "properties": {}}},
    }
]
REQUEST: dict[str, Any] = {
    "model": "gpt-6-luna",
    "messages": [{"role": "system", "content": "Browse."}, {"role": "user", "content": "Go"}],
    "tools": TOOLS,
    "tool_choice": "required",
}


class Model:
    """A delegate that records what it was bound and shown, and answers one tool call."""

    def __init__(self) -> None:
        self.bound: list[tuple[object, object]] = []
        self.seen: list[list[BaseMessage]] = []

    def bind_tools(self, tools: object, **kwargs: object) -> "Model":
        self.bound.append((tools, kwargs.get("tool_choice")))
        return self

    async def ainvoke(self, messages: list[BaseMessage], **_: object) -> AIMessage:
        self.seen.append(messages)
        return AIMessage(
            content="",
            tool_calls=[
                {"name": "finish", "args": {"done": True}, "id": "c1", "type": "tool_call"}
            ],
            usage_metadata={"input_tokens": 12, "output_tokens": 3, "total_tokens": 15},
        )


class Admission:
    """Admits as the loop does, opening the admitted scope around the dispatch, or stops."""

    def __init__(self, stop: str | None = None) -> None:
        self.stop = stop
        self.requests: list[object] = []

    async def admitted(
        self, request: object, handler: Callable[[Any], Awaitable[Any]], route: ModelRoute
    ) -> tuple[Any, bool]:
        self.requests.append(request)
        if self.stop is not None:
            raise LoopStopped(self.stop)
        with admitted_scope():
            return await handler(request), True


def answer(body: dict[str, Any], admission: Admission, model: Model) -> Reply:
    return asyncio.run(admitted_answer(admission, model, ROUTE)(body))  # type: ignore[arg-type]  # a fake admission


def test_one_request_is_one_admitted_call_answered_by_the_route_whatever_model_it_names() -> None:
    admission, model = Admission(), Model()
    reply = answer(REQUEST, admission, model)
    (choice,) = reply.completion["choices"]
    assert len(admission.requests) == 1 and len(model.seen) == 1
    assert [type(message).__name__ for message in model.seen[0]] == [
        "SystemMessage",
        "HumanMessage",
    ]
    assert model.bound == [(TOOLS, "any")]
    assert reply.completion["model"] == "openai/gpt-6.1-sol"
    assert choice["finish_reason"] == "tool_calls"
    assert choice["message"]["tool_calls"][0]["function"] == {
        "name": "finish",
        "arguments": '{"done": true}',
    }
    assert reply.completion["usage"] == {
        "prompt_tokens": 12,
        "completion_tokens": 3,
        "total_tokens": 15,
    }
    assert "key" not in json.dumps(reply.completion).lower()


def test_a_streamed_request_gets_the_reply_its_finish_and_its_usage() -> None:
    body = {**REQUEST, "stream": True, "stream_options": {"include_usage": True}}
    reply = answer(body, Admission(), Model())
    assert reply.chunks is not None
    first, finish, usage = reply.chunks
    assert first["choices"][0]["delta"]["tool_calls"][0]["index"] == 0
    assert finish["choices"][0]["finish_reason"] == "tool_calls"
    assert usage["choices"] == [] and usage["usage"]["total_tokens"] == 15
    assert {chunk["object"] for chunk in reply.chunks} == {"chat.completion.chunk"}


def test_a_stopped_run_is_refused_with_its_code_and_nothing_reaches_the_model() -> None:
    model = Model()
    with pytest.raises(EndpointRefused) as refused:
        answer(REQUEST, Admission(stop="budget_exhausted"), model)
    assert (refused.value.status, refused.value.code) == (403, "budget_exhausted")
    assert model.seen == []


@pytest.mark.parametrize(
    ("change", "code"),
    [
        (
            {
                "messages": [
                    {
                        "role": "user",
                        "content": [{"type": "image_url", "image_url": {"url": "x"}}],
                    }
                ]
            },
            "content_not_qualified",
        ),
        ({"messages": []}, "malformed_request"),
        ({"tools": [{"type": "web_search"}]}, "malformed_request"),
        ({"tool_choice": {"type": "custom"}}, "malformed_request"),
    ],
)
def test_content_the_route_isnt_qualified_for_or_a_malformed_request_is_refused_first(
    change: dict[str, Any], code: str
) -> None:
    with pytest.raises(EndpointRefused) as refused:
        parse_request({**REQUEST, **change})
    assert refused.value.code == code


def test_tool_choice_is_passed_on_in_langchains_words() -> None:
    assert parse_request({**REQUEST, "tool_choice": "auto"})[2] is None
    assert parse_request({**REQUEST, "tool_choice": "none"})[2] == "none"
    named = {"type": "function", "function": {"name": "finish"}}
    assert parse_request({**REQUEST, "tool_choice": named})[2] == "finish"


async def fixed(body: Mapping[str, object]) -> Reply:
    if body.get("stream"):
        return Reply({}, ({"object": "chat.completion.chunk", "choices": []},))
    return Reply({"object": "chat.completion", "echo": body["model"]})


async def exchange(endpoint: ModelEndpoint, raw: bytes) -> tuple[int, str]:
    """One request through the endpoint's handler over a socket pair, which needs no connect. The
    loopback listener itself is exercised by tests/db/checks/model_endpoint_check.py."""
    server, client = socket.socketpair()
    server_reader, server_writer = await asyncio.open_connection(sock=server)
    client_reader, client_writer = await asyncio.open_connection(sock=client)

    async def send() -> None:
        # Sent while the endpoint reads, so a body larger than the pair's buffer doesn't stall.
        with contextlib.suppress(ConnectionError):
            client_writer.write(raw)
            await client_writer.drain()

    sender = asyncio.create_task(send())
    await endpoint._serve(server_reader, server_writer)
    answer = await client_reader.read()
    await sender
    client_writer.close()
    head, _, body = answer.decode().partition("\r\n\r\n")
    return int(head.split(" ")[1]), body


def request(body: bytes, *, token: str | None, path: str = "/v1/chat/completions") -> bytes:
    auth = f"Authorization: Bearer {token}\r\n" if token is not None else ""
    return (
        f"POST {path} HTTP/1.1\r\nHost: proxy\r\nContent-Type: application/json\r\n"
        f"Content-Length: {len(body)}\r\n{auth}\r\n"
    ).encode() + body


def test_the_endpoint_answers_its_token_and_refuses_without_it() -> None:
    endpoint = ModelEndpoint(fixed)
    plain = json.dumps({"model": "m"}).encode()
    streamed = json.dumps({"model": "m", "stream": True}).encode()

    async def go() -> list[tuple[int, str]]:
        return [
            await exchange(endpoint, request(plain, token=endpoint.token)),
            await exchange(endpoint, request(plain, token=None)),
            await exchange(endpoint, request(plain, token="other")),
            await exchange(endpoint, request(plain, token=endpoint.token, path="/v1/models")),
            await exchange(endpoint, request(streamed, token=endpoint.token)),
            await exchange(endpoint, request(b"x" * (2 * 1024 * 1024 + 1), token=endpoint.token)),
            await exchange(endpoint, request(b"not json", token=endpoint.token)),
        ]

    ok, missing, wrong, other_path, stream, large, broken = asyncio.run(go())
    assert (ok[0], json.loads(ok[1])) == (200, {"object": "chat.completion", "echo": "m"})
    for refused in (missing, wrong):
        assert refused[0] == 401
        assert json.loads(refused[1])["error"]["code"] == "token_required"
    assert other_path[0] == 404
    assert stream[0] == 200 and stream[1].endswith("data: [DONE]\n\n")
    assert large[0] == 413
    assert (broken[0], json.loads(broken[1])["error"]["code"]) == (400, "malformed_request")
