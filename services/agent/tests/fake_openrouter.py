"""The paid path's fake provider, all in process (PTST-02): OpenRouter's replies and catalog, built
from the approved profiles, transports through the real adapter and SDK that record what went out,
and the worker's attempt source over them. Fake transports are the default test path, even with a
real key present (model-gateway rule)."""

import asyncio
import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx
import openrouter
from langchain_core.messages import AIMessage, HumanMessage
from langchain_openrouter import ChatOpenRouter
from pydantic import SecretStr

from autobots.adapters.models.catalog import ModelUnavailable
from autobots.adapters.models.factory import chat_model, default_sdk_client
from autobots.application.credentials.store import CredentialReference
from autobots.application.model_attempts import FailureClass, ProviderFailure
from autobots.application.provider_settings import CatalogFetcher, KeyCheck, ProviderContext
from autobots.application.worker_inference import (
    ROLE,
    AttemptModel,
    CatalogCache,
    InferenceSource,
    frozen_policy,
    prepared,
)
from autobots.domain.models import PROFILES, ModelProfile, ModelProfileId, ModelRole, RolePolicy
from autobots.operations.fake_stream import completion_to_sse

DEEPSEEK = PROFILES[ModelProfileId.DEEPSEEK_FLASH]
TERRA = PROFILES[ModelProfileId.TERRA]
SOL = PROFILES[ModelProfileId.SOL]
DEEPSEEK_WIRE_ID = DEEPSEEK.wire_id
TERRA_WIRE_ID = TERRA.wire_id
SOL_WIRE_ID = SOL.wire_id
# The three approved profiles (Decision 0019 S2). A fake refuses any other model, as policy does.
APPROVED = tuple(PROFILES.values())
APPROVED_WIRE_IDS = frozenset(profile.wire_id for profile in APPROVED)
ARRANGED_KEY = "arranged-not-a-real-key"
# USD per token, as the public catalog lists prices: 1 and 2 micro-USD.
PRICE = {"prompt": "0.000001", "completion": "0.000002"}
# Every request option a worker sends, so a catalog entry without one refuses the attempt.
SUPPORTED = ("max_tokens", "tools", "tool_choice")
USAGE = {"prompt_tokens": 5, "completion_tokens": 7, "total_tokens": 12}

Handle = Callable[[httpx.Request], httpx.Response]


# Reply and catalog shapes


def completion(
    message: Mapping[str, object],
    finish: str = "stop",
    *,
    model: str,
    usage: Mapping[str, object] | None = USAGE,
    cost: float | None = None,
) -> dict[str, Any]:
    """One whole chat completion. A reported `cost` sits in its usage, where OpenRouter puts it."""
    body: dict[str, Any] = {
        "id": "fake",
        "object": "chat.completion",
        "created": 1,
        "model": model,
        "system_fingerprint": "fake",
        "choices": [{"index": 0, "finish_reason": finish, "message": dict(message)}],
    }
    if usage is not None:
        body["usage"] = {**usage, **({} if cost is None else {"cost": cost})}
    return body


def tool_call(
    name: str, arguments: Mapping[str, object], call_id: str = "call-1"
) -> dict[str, Any]:
    """One call in a reply, its arguments the JSON text a provider sends."""
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments)},
    }


def calling(*calls: Mapping[str, object]) -> dict[str, Any]:
    """The assistant message that makes these calls and says nothing else."""
    return {"role": "assistant", "content": None, "tool_calls": list(calls)}


def catalog_payload(
    *drop: str, pricing: object = PRICE, profiles: Iterable[ModelProfile] = APPROVED
) -> dict[str, Any]:
    """The public `/models` listing for `profiles` at one price, supporting every option a worker
    sends except those named in `drop`."""
    return {
        "data": [
            {
                "id": profile.wire_id,
                "canonical_slug": profile.canonical_id,
                "supported_parameters": [name for name in SUPPORTED if name not in drop],
                "pricing": pricing,
            }
            for profile in profiles
        ]
    }


# Transports, through the real SDK


class FakeOpenRouter:
    """Records requests and refuses what the approved-profile policy forbids: a model outside the
    three profiles, or a fallback list (Decision 0019 S2)."""

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []

    def models(self) -> list[str]:
        return [request["model"] for request in self.requests]

    def _handle(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.requests.append(body)
        if not request.headers.get("authorization", "").startswith("Bearer "):
            return httpx.Response(401, json={"error": {"code": 401, "message": "missing key"}})
        if body.get("model") not in APPROVED_WIRE_IDS or body.get("models"):
            error = {"code": 400, "message": "not an approved profile"}
            return httpx.Response(400, json={"error": error})
        reply = {"role": "assistant", "content": "fake reply"}
        return httpx.Response(200, json=completion(reply, model=body["model"]))

    def chat_model(self, wire_id: str) -> ChatOpenRouter:
        http = httpx.Client(transport=httpx.MockTransport(self._handle))
        client = openrouter.OpenRouter(api_key=ARRANGED_KEY, client=http)
        return ChatOpenRouter(
            model=wire_id, api_key=SecretStr(ARRANGED_KEY), max_retries=0, client=client
        )


class RecordingOpenRouter:
    """Answers the worker's async SDK client over a mock transport, and records the bodies, keys
    and clients that really went out. Unless `reply` answers instead, a call gets one `lookup` tool
    call, or the arranged error `status`, streamed when the request streams, as every worker call
    does (Decision 0022's streaming decision)."""

    def __init__(
        self, status: int = 200, cost: float | None = 0.00025, reply: Handle | None = None
    ) -> None:
        self.status = status
        self.cost = cost
        self.reply = reply
        self.bodies: list[dict[str, Any]] = []
        self.keys: list[str] = []
        self.clients = 0

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.bodies.append(json.loads(request.content))
        self.keys.append(request.headers.get("authorization", ""))
        if self.reply is not None:
            return self.reply(request)
        if self.status != 200:
            error = {"code": self.status, "message": "arranged"}
            return httpx.Response(self.status, json={"error": error})
        answer = completion(
            calling(tool_call("lookup", {"text": "a"})),
            "tool_calls",
            model=self.bodies[-1]["model"],
            cost=self.cost,
        )
        if self.bodies[-1].get("stream"):
            return httpx.Response(
                200,
                content=completion_to_sse(answer),
                headers={"content-type": "text/event-stream"},
            )
        return httpx.Response(200, json=answer)

    def client(self, key: str) -> openrouter.OpenRouter:
        self.clients += 1
        return default_sdk_client(
            key, async_http=httpx.AsyncClient(transport=httpx.MockTransport(self.handle))
        )


# The worker's attempts, over the transports


def provider_context(
    fetch: CatalogFetcher | None = None, environment: Mapping[str, str] | None = None
) -> ProviderContext:
    """No configuration files or master key, and no key validation, which no attempt performs.
    Without `fetch` the catalog is unreachable."""

    async def validate(_: SecretStr) -> KeyCheck:
        raise AssertionError("a model attempt never validates a key")

    async def unreachable() -> dict[str, Any] | None:
        return None

    return ProviderContext(
        "/nonexistent",
        "test",
        Path("/nonexistent"),
        dict(environment or {}),
        validate,
        fetch or unreachable,
    )


def snapshot(deepseek_or_terra: str = DEEPSEEK.id.value) -> dict[str, Any]:
    """A run's frozen policy: the executor as given, and DeepSeek summarizing."""
    return {"version": 1, "bindings": {"executor": deepseek_or_terra, "summarizer": DEEPSEEK.id}}


@dataclass(frozen=True)
class ScriptedKeys(InferenceSource):
    """`open_attempt` with keys from a list instead of a database, each an arranged key or what
    reading it raised. The disposable check reads real rows
    (tests/db/workers/product_inference_worker.py).
    """

    keys: list[str | Exception] = field(default_factory=list)
    rejected: list[CredentialReference] = field(default_factory=list)

    async def open_attempt(
        self,
        workspace_id: UUID,
        policy: RolePolicy,
        reserved_micro_usd: int | None = None,
        role: ModelRole = ROLE,
    ) -> tuple[ChatOpenRouter, CredentialReference]:
        try:
            attempt, _ = prepared(policy, await self.catalog.current(), role)
        except ModelUnavailable:
            raise ProviderFailure(FailureClass.MODEL_UNAVAILABLE) from None
        key = self.keys.pop(0)
        if isinstance(key, Exception):
            raise key
        model = chat_model(attempt, SecretStr(key), client_factory=self.client_factory)
        return model, CredentialReference("app", None, 1)

    async def reject_key(self, workspace_id: UUID, used: CredentialReference) -> None:
        self.rejected.append(used)


def source_with(
    fake: RecordingOpenRouter,
    keys: list[str | Exception],
    rejected: list[CredentialReference] | None = None,
    *,
    catalog: CatalogCache | None = None,
) -> ScriptedKeys:
    """Attempts over `fake`, priced by a fresh catalog unless `catalog` is given."""

    async def fetch() -> dict[str, Any]:
        return catalog_payload()

    return ScriptedKeys(
        "postgresql://unused",
        provider_context(fetch),
        catalog if catalog is not None else CatalogCache(fetch),
        fake.client,
        keys=keys,
        rejected=rejected if rejected is not None else [],
    )


def attempt_model(source: InferenceSource, profile: str = DEEPSEEK.id.value) -> AttemptModel:
    return AttemptModel(source, uuid4(), frozen_policy(snapshot(profile)))


def model_over(reply: Handle) -> AttemptModel:
    """An attempt whose transport answers with `reply`, through the real SDK."""
    return attempt_model(source_with(RecordingOpenRouter(reply=reply), [ARRANGED_KEY]))


def invoke(model: AttemptModel) -> AIMessage:
    message: AIMessage = asyncio.run(model.ainvoke([HumanMessage("hello")]))
    return message
