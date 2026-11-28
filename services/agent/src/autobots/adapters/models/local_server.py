"""The client for a local route: the owner's llama-server on 127.0.0.1 (Decision 0041 A2 to A4, A9).

`factory.chat_model` hands this to the same `ChatOpenRouter` an OpenRouter route uses, in place of
OpenRouter's SDK client. `ChatOpenRouter` takes any client whose `chat.send` and `chat.send_async`
return a reply as a dict, or chunks with `model_dump`. So message conversion, tool binding and usage
stay in one place, and no other model package is locked.

The request carries no key and is never retried here, since application policy owns every retry.
OpenRouter's own parameters are dropped and the profile's thinking switch is added. Reasoning the
server returns in its own field is dropped, so it reaches neither the reply nor a log. A local call
costs nothing, which the reply reports as cost 0, so the ledger settles it rather than leaving it
open.

Leading system messages reach the server as one, their texts joined in order. Bonsai 2.5's chat
template refuses a system message after the first, and browser-use in the box sends its
instructions as two, so on Local its browse failed before a step (Decision 0041 A10).

A call that requires a tool call, by `required` or a named tool, is enforced here rather than left
to the server (Decision 0041 A18): llama.cpp 1.1.0 let Bonsai 2.5 answer such a call in text. The
tools stay in the prompt with `tool_choice` `none`, so the chat template still describes them, and
the reply is constrained by a JSON schema to one call of an allowed tool with that tool's
arguments. The reply is then checked and turned into the tool call. One cut off by its output cap
reads as cut off, and one that doesn't match fails the call, never passed on as text.
"""

import json
import os
from collections.abc import AsyncIterator, Iterator, Mapping
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import httpx
from jsonschema import validators  # type: ignore[import-untyped]  # jsonschema ships no stubs
from jsonschema.exceptions import SchemaError  # type: ignore[import-untyped]  # jsonschema ships no stubs
from referencing.exceptions import Unresolvable

from autobots.adapters.models.catalog import ModelUnavailable
from autobots.application.model_attempts import FailureClass, ProviderFailure
from autobots.domain.models import ModelProfile

LOOPBACK_HOST = "127.0.0.1"
DEFAULT_PORT = 9931
PORT_VARIABLE = "AUTOBOTS_LOCAL_MODEL_PORT"
# The identity check is one loopback round trip. A server that can't answer it in this is down.
IDENTITY_SECONDS = 5.0
# Each of these means something only to OpenRouter, and could reach another model or provider.
OPENROUTER_ONLY = frozenset(
    {"provider", "route", "plugins", "session_id", "trace", "reasoning", "models", "transforms"}
)
LOCAL_PROVIDER = "local"
# The name the constrained reply's schema goes by. The server sees it; nothing else does.
TOOL_CALL_SCHEMA = "tool_call"
# Why a required tool call failed, for the worker's log (A18). Neither is retried.
NOT_A_TOOL_CALL = "required_tool_call_not_returned"
NO_SUCH_TOOL = "required_tool_not_offered"


class LocalServerUnavailable(Exception):
    """Nothing answers on the local route's port, so the owner's server isn't running (A3)."""

    code = "local_model_server_unavailable"


class LocalServerError(Exception):
    """The server answered with an error. `status_code` is what `classify_status` reads (MP-08)."""

    def __init__(self, status_code: int) -> None:
        super().__init__(f"the local model server answered {status_code}")
        self.status_code = status_code


def local_port(environ: Mapping[str, str] | None = None) -> int:
    """Ordinary non-secret configuration (A2). A value that isn't a port is refused, not guessed."""
    raw = (environ if environ is not None else os.environ).get(PORT_VARIABLE, "").strip()
    if not raw:
        return DEFAULT_PORT
    if not raw.isdigit() or not 0 < int(raw) < 65536:
        raise ValueError(f"{PORT_VARIABLE} is not a port")
    return int(raw)


def base_url(port: int) -> str:
    return f"http://{LOOPBACK_HOST}:{port}/v1"


async def check_served(
    profile: ModelProfile, port: int, *, transport: httpx.AsyncBaseTransport | None = None
) -> None:
    """Before each call (A3). Nothing listening raises LocalServerUnavailable, and any other model
    raises ModelUnavailable. Neither sends a chat completion, and nothing else is tried."""
    try:
        async with httpx.AsyncClient(transport=transport, timeout=IDENTITY_SECONDS) as http:
            response = await http.get(base_url(port) + "/models")
    except httpx.TransportError:
        # Refused, timed out or cut off: no chat was sent, so this is never an uncertain call.
        raise LocalServerUnavailable("the local model server isn't running") from None
    if response.status_code != 200:
        raise ModelUnavailable("the local model server didn't list its model")
    try:
        served = [str(item.get("id")) for item in response.json().get("data", [])]
    except (ValueError, AttributeError, TypeError):
        raise ModelUnavailable("the local model server didn't list its model") from None
    if served != [profile.wire_id]:
        raise ModelUnavailable("the local model server is serving another model")


class _Chunk:
    """What `ChatOpenRouter` reads from a streamed chunk."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def model_dump(self, by_alias: bool = True) -> dict[str, Any]:
        return self._data


Reply = dict[str, Any] | Iterator[_Chunk]
AsyncReply = dict[str, Any] | AsyncIterator[_Chunk]


def _without_reasoning(message: object) -> None:
    if isinstance(message, dict):
        message.pop("reasoning_content", None)
        message.pop("reasoning", None)


def _local_reply(data: dict[str, Any]) -> dict[str, Any]:
    """The server's reply, with reasoning removed and a cost of 0 reported (A2, A9)."""
    for choice in data.get("choices") or []:
        _without_reasoning(choice.get("message"))
        _without_reasoning(choice.get("delta"))
    usage = data.get("usage")
    if isinstance(usage, dict):
        usage["cost"] = 0
        data["provider"] = LOCAL_PROVIDER
    return data


def _system_text(content: object) -> str | None:
    """A system message's text, from a string or text parts. None for anything else."""
    if isinstance(content, str):
        return content
    if isinstance(content, list) and all(
        isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str)
        for part in content
    ):
        return "".join(part["text"] for part in content)
    return None


def one_leading_system(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The messages with their leading system messages joined into one, a blank line between
    each text. A later system message, or one that isn't text, is sent as it came."""
    count = 0
    while count < len(messages) and messages[count].get("role") == "system":
        count += 1
    texts = [_system_text(message.get("content")) for message in messages[:count]]
    if count < 2 or any(text is None for text in texts):
        return messages
    joined = "\n\n".join(text for text in texts if text is not None)
    return [{"role": "system", "content": joined}, *messages[count:]]


def _named_tool(choice: object) -> str | None:
    if isinstance(choice, dict) and isinstance(choice.get("function"), dict):
        name = choice["function"].get("name")
        return name if isinstance(name, str) else None
    return None


def _tool_name(tool: object) -> str | None:
    function = tool.get("function") if isinstance(tool, dict) else None
    name = function.get("name") if isinstance(function, dict) else None
    return name if isinstance(name, str) else None


def _parameters(tool: dict[str, Any]) -> dict[str, Any]:
    parameters = (tool.get("function") or {}).get("parameters")
    return parameters if isinstance(parameters, dict) else {"type": "object", "properties": {}}


def required_tools(params: Mapping[str, object]) -> dict[str, dict[str, Any]] | None:
    """The tools a reply must call one of, by name with their parameters, or None when the model
    may answer in text (A18). A named tool the request doesn't offer is refused before sending."""
    raw = params.get("tools")
    tools = [tool for tool in raw if isinstance(tool, dict)] if isinstance(raw, list) else []
    by_name = {name: _parameters(tool) for tool in tools if (name := _tool_name(tool)) is not None}
    choice = params.get("tool_choice")
    named = _named_tool(choice)
    if named is not None:
        if named not in by_name:
            raise ProviderFailure(FailureClass.OTHER, reason=NO_SUCH_TOOL)
        return {named: by_name[named]}
    if choice in {"required", "any"} and by_name:
        return by_name
    return None


def _hoisted(schema: object, prefix: str, defs: dict[str, Any]) -> object:
    """One tool's schema with its local definitions moved to the root under `prefix`, so several
    tools' schemas can sit in one without their `$ref`s colliding."""
    if isinstance(schema, list):
        return [_hoisted(item, prefix, defs) for item in schema]
    if not isinstance(schema, dict):
        return schema
    out: dict[str, Any] = {}
    for key, value in schema.items():
        if key in {"$defs", "definitions"} and isinstance(value, dict):
            for name, definition in value.items():
                defs[prefix + name] = _hoisted(definition, prefix, defs)
        elif (
            key == "$ref"
            and isinstance(value, str)
            and value.startswith(("#/$defs/", "#/definitions/"))
        ):
            out[key] = "#/$defs/" + prefix + value.rsplit("/", 1)[1]
        else:
            out[key] = _hoisted(value, prefix, defs)
    return out


def tool_call_schema(allowed: Mapping[str, dict[str, Any]]) -> dict[str, Any]:
    """A JSON schema for one call of one allowed tool: its name and its arguments, nothing else."""
    defs: dict[str, Any] = {}
    options = [
        {
            "type": "object",
            "properties": {
                "name": {"enum": [name]},
                "arguments": _hoisted(parameters, f"t{index}_", defs),
            },
            "required": ["name", "arguments"],
            "additionalProperties": False,
        }
        for index, (name, parameters) in enumerate(allowed.items())
    ]
    schema: dict[str, Any] = options[0] if len(options) == 1 else {"anyOf": options}
    if defs:
        schema = {**schema, "$defs": defs}
    return schema


def _matches(arguments: object, parameters: dict[str, Any]) -> bool:
    try:
        validator = validators.validator_for(parameters)(parameters)
        return bool(validator.is_valid(arguments))
    except (SchemaError, Unresolvable):
        return False


def _not_a_tool_call() -> ProviderFailure:
    return ProviderFailure(FailureClass.OTHER, reason=NOT_A_TOOL_CALL)


def _as_tool_call(data: dict[str, Any], allowed: Mapping[str, dict[str, Any]]) -> dict[str, Any]:
    """The constrained reply as the tool call it describes (A18). A reply cut off by its output cap
    keeps no text, so it reads as cut off and its partial call never runs."""
    choices = data.get("choices") or []
    if not choices or not isinstance(choices[0], dict):
        raise _not_a_tool_call()
    choice = choices[0]
    message: dict[str, Any] = choice["message"] if isinstance(choice.get("message"), dict) else {}
    if choice.get("finish_reason") == "length":
        choice["message"] = {"role": "assistant", "content": ""}
        return data
    try:
        call = json.loads(message.get("content") or "")
    except ValueError:
        raise _not_a_tool_call() from None
    if not isinstance(call, dict) or set(call) != {"name", "arguments"}:
        raise _not_a_tool_call()
    name, arguments = call["name"], call["arguments"]
    if (
        name not in allowed
        or not isinstance(arguments, dict)
        or not _matches(arguments, allowed[name])
    ):
        raise _not_a_tool_call()
    choice["message"] = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": f"call_{uuid4().hex[:24]}",
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(arguments, ensure_ascii=False)},
            }
        ],
    }
    choice["finish_reason"] = "tool_calls"
    return data


def _as_chunks(data: dict[str, Any]) -> list[dict[str, Any]]:
    """A whole reply as the chunks a streamed one ends with: its message, then its usage."""
    choice = data["choices"][0]
    message = choice["message"]
    delta: dict[str, Any] = {"role": "assistant", "content": message.get("content") or ""}
    if message.get("tool_calls"):
        delta["tool_calls"] = [{"index": i, **call} for i, call in enumerate(message["tool_calls"])]
    head: dict[str, Any] = {key: data[key] for key in ("id", "model") if key in data}
    chunks: list[dict[str, Any]] = [
        {
            **head,
            "choices": [{"index": 0, "delta": delta, "finish_reason": choice["finish_reason"]}],
        }
    ]
    if data.get("usage"):
        chunks.append({**head, "choices": [], "usage": data["usage"]})
    return chunks


@dataclass(frozen=True)
class _Request:
    """What the server is sent, and what the reply must be turned into."""

    body: dict[str, Any]
    allowed: Mapping[str, dict[str, Any]] | None
    streamed: bool


class LoopbackClient:
    """One attempt's client. `transport` and `async_transport` are for tests only."""

    def __init__(
        self,
        profile: ModelProfile,
        port: int,
        timeout_seconds: float,
        *,
        transport: httpx.BaseTransport | None = None,
        async_transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if profile.local is None:
            raise ValueError("an OpenRouter profile has no local server")
        self.profile = profile
        self.url = base_url(port) + "/chat/completions"
        self.timeout = httpx.Timeout(timeout_seconds, connect=IDENTITY_SECONDS)
        self._transport = transport
        self._async_transport = async_transport
        self.chat = _Chat(self)

    def body(self, messages: list[dict[str, Any]], params: Mapping[str, object]) -> dict[str, Any]:
        """The request the server gets. Its model is the profile's own, whatever was asked."""
        return self._request(messages, params).body

    def _request(self, messages: list[dict[str, Any]], params: Mapping[str, object]) -> _Request:
        body: dict[str, Any] = {
            k: v for k, v in params.items() if k not in OPENROUTER_ONLY and k != "model"
        }
        body["model"] = self.profile.wire_id
        body["messages"] = one_leading_system(messages)
        if self.profile.local is not None and self.profile.local.thinking:
            body["chat_template_kwargs"] = dict(self.profile.local.thinking)
        allowed = required_tools(body)
        streamed = bool(body.get("stream"))
        if allowed is not None:
            # A18: the tools stay described, the choice is the schema's, and the reply is read
            # whole, since only a complete call can be checked.
            body["tool_choice"] = "none"
            body.pop("parallel_tool_calls", None)
            body.pop("stream", None)
            body.pop("stream_options", None)
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": TOOL_CALL_SCHEMA,
                    "strict": True,
                    "schema": tool_call_schema(allowed),
                },
            }
        return _Request(body, allowed, streamed)

    def _raise_for(self, response: httpx.Response) -> None:
        if response.status_code >= 400:
            raise LocalServerError(response.status_code)

    def _whole(self, data: dict[str, Any], request: _Request) -> dict[str, Any]:
        if request.allowed is not None:
            data = _as_tool_call(data, request.allowed)
        return _local_reply(data)

    def send(self, messages: list[dict[str, Any]], **params: object) -> Reply:
        request = self._request(messages, params)
        if request.streamed and request.allowed is None:
            return self._stream(request.body)
        with httpx.Client(transport=self._transport, timeout=self.timeout) as http:
            response = http.post(self.url, json=request.body)
            self._raise_for(response)
            reply = self._whole(response.json(), request)
        return iter([_Chunk(c) for c in _as_chunks(reply)]) if request.streamed else reply

    def _stream(self, body: dict[str, Any]) -> Iterator[_Chunk]:
        with (
            httpx.Client(transport=self._transport, timeout=self.timeout) as http,
            http.stream("POST", self.url, json=body) as response,
        ):
            self._raise_for(response)
            for line in response.iter_lines():
                chunk = _event(line)
                if chunk is not None:
                    yield _Chunk(_local_reply(chunk))

    async def send_async(self, messages: list[dict[str, Any]], **params: object) -> AsyncReply:
        request = self._request(messages, params)
        if request.streamed and request.allowed is None:
            return self._astream(request.body)
        async with httpx.AsyncClient(transport=self._async_transport, timeout=self.timeout) as http:
            response = await http.post(self.url, json=request.body)
            self._raise_for(response)
            reply = self._whole(response.json(), request)
        return _replayed(_as_chunks(reply)) if request.streamed else reply

    async def _astream(self, body: dict[str, Any]) -> AsyncIterator[_Chunk]:
        async with (
            httpx.AsyncClient(transport=self._async_transport, timeout=self.timeout) as http,
            http.stream("POST", self.url, json=body) as response,
        ):
            self._raise_for(response)
            async for line in response.aiter_lines():
                chunk = _event(line)
                if chunk is not None:
                    yield _Chunk(_local_reply(chunk))


async def _replayed(chunks: list[dict[str, Any]]) -> AsyncIterator[_Chunk]:
    for chunk in chunks:
        yield _Chunk(chunk)


def _event(line: str) -> dict[str, Any] | None:
    """One server-sent event's JSON, or None for anything else, such as `[DONE]`."""
    line = line.strip()
    if not line.startswith("data:"):
        return None
    payload = line[5:].strip()
    if not payload or payload == "[DONE]":
        return None
    data = json.loads(payload)
    return data if isinstance(data, dict) else None


class _Chat:
    """The `chat` namespace `ChatOpenRouter` calls."""

    def __init__(self, client: LoopbackClient) -> None:
        self._client = client

    def send(self, messages: list[dict[str, Any]], **params: object) -> Reply:
        return self._client.send(messages, **params)

    async def send_async(self, messages: list[dict[str, Any]], **params: object) -> AsyncReply:
        return await self._client.send_async(messages, **params)
