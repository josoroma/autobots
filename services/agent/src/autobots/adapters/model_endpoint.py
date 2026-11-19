"""The browser box's model endpoint, Decision 0035 Y7 and Y16, and Decision 0020 L3.

browser-use runs in the isolated box and calls an OpenAI-compatible server. Each chat completion it
sends here becomes one call through the running loop's admission on the run's frozen `researcher`
route, as a browsing-loop step does: a reservation, an invocation ticket and receipt, the run's
budget and `model_calls`, and the shared transport. The model the request names is ignored. Nothing
here holds a key or a model client of its own: the attempt model answers only inside an admitted
dispatch (`AdmittedModel`).

The server listens on the Mac's loopback, on a free port, and answers only a request carrying the
session's token. Only the browse's egress sidecar holds that token, and relays to this endpoint from
the box's network (`egress_proxy.handle_model`). A refusal is a typed JSON error, and comes before
anything is sent.
"""

import asyncio
import contextlib
import hmac
import json
import secrets
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    convert_to_messages,
    convert_to_openai_messages,
)

from autobots.adapters.loop_middleware import AdmittedModel
from autobots.application.browsing_loop import StepRequest, StepResponse
from autobots.application.loop_admission import AdmittingLoop
from autobots.application.loop_policy import LoopStopped
from autobots.domain.models import ModelRoute

PATH = "/v1/chat/completions"
HEAD_LIMIT = 16_384
BODY_LIMIT = 2 * 1024 * 1024
READ_SECONDS = 30.0


class EndpointRefused(Exception):
    """A typed refusal: the HTTP status and the code the error body names."""

    def __init__(self, status: int, code: str, message: str = "") -> None:
        super().__init__(code)
        self.status = status
        self.code = code
        self.message = message or code


@dataclass(frozen=True)
class Reply:
    """A completion, and the chunks a streamed request is answered with instead."""

    completion: dict[str, Any]
    chunks: tuple[dict[str, Any], ...] | None = None


def _text_only(messages: Sequence[Mapping[str, Any]]) -> None:
    """Y16: no route is qualified for image input, so a request carrying one is refused."""
    for message in messages:
        content = message.get("content")
        if isinstance(content, list):
            for part in content:
                if isinstance(part, Mapping) and part.get("type") not in (None, "text"):
                    raise EndpointRefused(400, "content_not_qualified", "Only text is accepted.")


def _choice(value: object) -> str | None:
    """OpenAI's `tool_choice` in LangChain's words."""
    if value in (None, "auto"):
        return None
    if value == "required":
        return "any"
    if value == "none":
        return "none"
    if isinstance(value, Mapping):
        function = value.get("function")
        if isinstance(function, Mapping) and isinstance(function.get("name"), str):
            return str(function["name"])
    raise EndpointRefused(400, "malformed_request", "tool_choice isn't understood.")


def parse_request(
    body: Mapping[str, Any],
) -> tuple[list[BaseMessage], list[dict[str, Any]], str | None]:
    """The request's messages, its function tools and its tool choice, or a typed refusal."""
    messages = body.get("messages")
    tools = body.get("tools") or []
    if not isinstance(messages, list) or not messages or not isinstance(tools, list):
        raise EndpointRefused(400, "malformed_request", "messages must be a non-empty list.")
    _text_only(messages)
    if any(not isinstance(tool, Mapping) or tool.get("type") != "function" for tool in tools):
        raise EndpointRefused(400, "malformed_request", "Only function tools are accepted.")
    try:
        converted = convert_to_messages(messages)
    except (ValueError, TypeError, KeyError) as error:
        raise EndpointRefused(400, "malformed_request", "A message isn't understood.") from error
    return converted, [dict(tool) for tool in tools], _choice(body.get("tool_choice"))


def completion(message: AIMessage, model: str) -> dict[str, Any]:
    """An OpenAI `chat.completion` for one reply, with the tokens the call reported."""
    openai = convert_to_openai_messages(message)
    assert isinstance(openai, dict)
    usage: Mapping[str, Any] = message.usage_metadata or {}
    prompt, output = int(usage.get("input_tokens", 0)), int(usage.get("output_tokens", 0))
    content = openai.get("content")
    reply: dict[str, Any] = {"role": "assistant", "content": content if content else None}
    if openai.get("tool_calls"):
        reply["tool_calls"] = openai["tool_calls"]
    return {
        "id": f"chatcmpl-{uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": reply,
                "finish_reason": "tool_calls" if message.tool_calls else "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt,
            "completion_tokens": output,
            "total_tokens": prompt + output,
        },
    }


def chunks(whole: Mapping[str, Any], *, usage: bool) -> tuple[dict[str, Any], ...]:
    """The same completion as a stream: the reply, its finish, then its usage when asked for."""
    base = {key: whole[key] for key in ("id", "created", "model")}
    base["object"] = "chat.completion.chunk"
    (choice,) = whole["choices"]
    message = choice["message"]
    delta: dict[str, Any] = {"role": "assistant"}
    if message.get("content"):
        delta["content"] = message["content"]
    if message.get("tool_calls"):
        delta["tool_calls"] = [
            {"index": index, **call} for index, call in enumerate(message["tool_calls"])
        ]
    stream = [
        {**base, "choices": [{"index": 0, "delta": delta, "finish_reason": None}]},
        {**base, "choices": [{"index": 0, "delta": {}, "finish_reason": choice["finish_reason"]}]},
    ]
    if usage:
        stream.append({**base, "choices": [], "usage": whole["usage"]})
    return tuple(stream)


Answer = Callable[[Mapping[str, Any]], Awaitable[Reply]]


def admitted_answer(middleware: AdmittingLoop, model: Any, route: ModelRoute) -> Answer:  # noqa: ANN401 - the worker's attempt model, of whichever chat class the route's factory built
    """Each request one admitted call on `route`, answered only inside that admission (BM-02)."""

    async def answer(body: Mapping[str, Any]) -> Reply:
        messages, tools, choice = parse_request(body)
        delegate = AdmittedModel(delegate=model)
        bound = delegate.bind_tools(tools, tool_choice=choice) if tools else delegate

        async def handler(request: StepRequest) -> StepResponse:
            message = await bound.ainvoke(list(request.messages))
            return StepResponse([message])

        try:
            response, complete = await middleware.admitted(
                StepRequest(messages, tuple(tools)), handler, route
            )
        except LoopStopped as stopped:
            raise EndpointRefused(403, stopped.code, "The run can't make this call.") from None
        if not complete:
            raise EndpointRefused(403, "incomplete_output", "The reply was cut off.")
        whole = completion(response.result[-1], route.wire_id)
        if body.get("stream"):
            options = body.get("stream_options")
            usage = isinstance(options, Mapping) and bool(options.get("include_usage"))
            return Reply(whole, chunks(whole, usage=usage))
        return Reply(whole)

    return answer


def _error(status: int, code: str, message: str) -> bytes:
    body = json.dumps({"error": {"code": code, "message": message, "type": code}}).encode()
    reason = {
        400: "Bad Request",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not Found",
        405: "Method Not Allowed",
        413: "Payload Too Large",
        500: "Internal Server Error",
    }
    return (
        f"HTTP/1.1 {status} {reason.get(status, 'Error')}\r\nContent-Type: application/json\r\n"
        f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n"
    ).encode() + body


def _ok(reply: Reply) -> bytes:
    if reply.chunks is None:
        body = json.dumps(reply.completion).encode()
        return (
            "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n"
        ).encode() + body
    events = (
        "".join(f"data: {json.dumps(chunk)}\n\n" for chunk in reply.chunks) + "data: [DONE]\n\n"
    )
    body = events.encode()
    return (
        "HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nCache-Control: no-cache\r\n"
        f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n"
    ).encode() + body


class ModelEndpoint:
    """One browse's endpoint: open it around the call, give the sidecar its port and token."""

    def __init__(self, answer: Answer, *, host: str = "127.0.0.1") -> None:
        self.answer = answer
        self.host = host
        self.token = secrets.token_urlsafe(32)
        self.port = 0
        self._server: asyncio.Server | None = None

    async def __aenter__(self) -> "ModelEndpoint":
        self._server = await asyncio.start_server(self._serve, self.host, 0, limit=HEAD_LIMIT * 2)
        self.port = int(self._server.sockets[0].getsockname()[1])
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._server is not None:
            self._server.close()
            with contextlib.suppress(Exception):
                await self._server.wait_closed()

    async def _serve(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            writer.write(await self._respond(reader))
            await writer.drain()
        except (ConnectionError, asyncio.IncompleteReadError, TimeoutError):
            pass
        finally:
            writer.close()

    async def _respond(self, reader: asyncio.StreamReader) -> bytes:
        try:
            return _ok(await self.answer(await self._request(reader)))
        except EndpointRefused as refused:
            return _error(refused.status, refused.code, refused.message)

    async def _request(self, reader: asyncio.StreamReader) -> Mapping[str, Any]:
        """The request's JSON body, or a typed refusal. The token is checked first, so nothing but
        the session's relay learns anything about this endpoint."""
        try:
            head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), READ_SECONDS)
        except (asyncio.LimitOverrunError, asyncio.IncompleteReadError, ValueError):
            raise EndpointRefused(
                400, "malformed_request", "The request couldn't be read."
            ) from None
        lines = head.decode("latin-1").split("\r\n")
        method, _, rest = lines[0].partition(" ")
        path = rest.partition(" ")[0]
        headers = {
            name.strip().lower(): value.strip()
            for name, _, value in (line.partition(":") for line in lines[1:] if line)
        }
        given = headers.get("authorization", "").encode()
        if len(head) > HEAD_LIMIT or not hmac.compare_digest(
            given, f"Bearer {self.token}".encode()
        ):
            raise EndpointRefused(401, "token_required", "This endpoint answers only its browse.")
        if path != PATH or method != "POST":
            raise EndpointRefused(404, "not_found", "Only POST /v1/chat/completions is served.")
        size = headers.get("content-length", "")
        length = int(size) if size.isdigit() else -1
        if length < 0 or length > BODY_LIMIT:
            raise EndpointRefused(413, "body_too_large", "A body within 2 MiB is required.")
        try:
            body = json.loads(await asyncio.wait_for(reader.readexactly(length), READ_SECONDS))
        except (ValueError, asyncio.IncompleteReadError):
            raise EndpointRefused(400, "malformed_request", "The body isn't JSON.") from None
        if not isinstance(body, Mapping):
            raise EndpointRefused(400, "malformed_request", "The body isn't a JSON object.")
        return body
