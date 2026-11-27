"""The client for a local route: the owner's llama-server on 127.0.0.1 (Decision 0041 A2 to A4, A9).

`factory.chat_model` hands this to the same `ChatOpenRouter` an OpenRouter route uses, in place of
OpenRouter's SDK client. `ChatOpenRouter` takes any client whose `chat.send` and `chat.send_async`
return a reply as a dict, or chunks with `model_dump`. So message conversion, tool binding and usage
stay in one place, and no other model package is locked.

The request carries no key and is never retried here, since application policy owns every retry.
OpenRouter's own parameters are dropped, the profile's thinking switch is added, and one named tool
is sent as `required` with only that tool (llama.cpp doesn't take a named choice). Reasoning the
server returns in its own field is dropped, so it reaches neither the reply nor a log. A local call
costs nothing, which the reply reports as cost 0, so the ledger settles it rather than leaving it
open.
"""

import json
import os
from collections.abc import AsyncIterator, Iterator, Mapping
from typing import Any

import httpx

from autobots.adapters.models.catalog import ModelUnavailable
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


def _named_tool(choice: object) -> str | None:
    if isinstance(choice, dict) and isinstance(choice.get("function"), dict):
        name = choice["function"].get("name")
        return name if isinstance(name, str) else None
    return None


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
        body: dict[str, Any] = {
            k: v for k, v in params.items() if k not in OPENROUTER_ONLY and k != "model"
        }
        body["model"] = self.profile.wire_id
        body["messages"] = messages
        if self.profile.local is not None and self.profile.local.thinking:
            body["chat_template_kwargs"] = dict(self.profile.local.thinking)
        named = _named_tool(body.get("tool_choice"))
        if named is not None:
            body["tool_choice"] = "required"
            body["tools"] = [
                tool
                for tool in body.get("tools") or []
                if (tool.get("function") or {}).get("name") == named
            ]
        return body

    def _raise_for(self, response: httpx.Response) -> None:
        if response.status_code >= 400:
            raise LocalServerError(response.status_code)

    def send(self, messages: list[dict[str, Any]], **params: object) -> Reply:
        body = self.body(messages, params)
        if body.get("stream"):
            return self._stream(body)
        with httpx.Client(transport=self._transport, timeout=self.timeout) as http:
            response = http.post(self.url, json=body)
            self._raise_for(response)
            return _local_reply(response.json())

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
        body = self.body(messages, params)
        if body.get("stream"):
            return self._astream(body)
        async with httpx.AsyncClient(transport=self._async_transport, timeout=self.timeout) as http:
            response = await http.post(self.url, json=body)
            self._raise_for(response)
            return _local_reply(response.json())

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
