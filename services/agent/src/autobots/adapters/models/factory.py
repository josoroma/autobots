"""The one model factory, MP-01 and MP-02. Nothing else builds a model client.

An OpenRouter profile gets OpenRouter's SDK client. A local profile gets the same `ChatOpenRouter`
on a loopback client to the owner's llama-server, with no key sent (Decision 0041 A2,
adapters/models/local_server.py).
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
import openrouter
from langchain_openrouter import ChatOpenRouter
from openrouter.utils import BackoffStrategy, RetryConfig
from pydantic import SecretStr

from autobots.adapters.models.catalog import (
    CatalogSnapshot,
    ModelUnavailable,
    validated_entry,
)

# The local route's names, which worker inference reaches through this one factory.
from autobots.adapters.models.local_server import (
    DEFAULT_PORT,
    LocalServerUnavailable,
    LoopbackClient,
    base_url,
    check_served,
)
from autobots.domain.models import ModelProfile, ModelRole, RolePolicy, limits_for

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
PROVIDER_ROUTING: Mapping[str, bool] = {"require_parameters": True, "allow_fallbacks": False}
# Never sent, whatever a caller asks: each could reach something other than the bound model.
FORBIDDEN_OPTIONS = frozenset(
    {
        "model",
        "models",
        "route",
        "plugins",
        "provider",
        "base_url",
        "api_key",
        "transforms",
        "preset",
    }
)
# Options this factory passes through once the catalog shows the model supports them.
PARAMETER_OPTIONS = frozenset(
    {
        "temperature",
        "top_p",
        "max_tokens",
        "parallel_tool_calls",
        "reasoning",
        "seed",
        "stop",
    }
)


__all__ = [
    "DEFAULT_PORT",
    "FORBIDDEN_OPTIONS",
    "LocalServerUnavailable",
    "LoopbackClient",
    "PreparedAttempt",
    "UnsupportedRequestOption",
    "chat_model",
    "check_served",
    "checked_options",
    "default_sdk_client",
    "local_chat_model",
    "prepare_attempt",
]


class UnsupportedRequestOption(ModelUnavailable):
    code = "unsupported_request_option"


def checked_options(options: Mapping[str, Any], supported: frozenset[str]) -> dict[str, Any]:
    """Refuse instead of omitting, so a role's required capability is never silently lost."""
    for name in options:
        if name in FORBIDDEN_OPTIONS:
            raise UnsupportedRequestOption(f"{name} cannot be set on a model request")
        if name not in PARAMETER_OPTIONS:
            raise UnsupportedRequestOption(f"{name} is not a known request option")
        if name not in supported:
            raise UnsupportedRequestOption(f"this model's catalog entry does not support {name}")
    return dict(options)


@dataclass(frozen=True)
class PreparedAttempt:
    profile: ModelProfile
    role: ModelRole
    catalog_revision: str
    options: Mapping[str, Any]


# What a local route takes (Decision 0041 A2). OpenRouter's `reasoning` isn't among them: a local
# profile's thinking switch is its own (LocalServing.thinking).
LOCAL_PARAMETERS = frozenset({"temperature", "top_p", "max_tokens", "seed", "stop", "tools"})
LOCAL_CATALOG_REVISION = "local"
# ChatOpenRouter insists on a non-empty key string. The loopback client never sends it.
NOT_A_KEY = SecretStr("local-route-sends-no-key")


def _is_local(profile: object) -> bool:
    """A paid trial's route stands in for a profile and has no `local` (operations/paid)."""
    return getattr(profile, "local", None) is not None


def prepare_attempt(
    policy: RolePolicy,
    role: ModelRole,
    catalog: CatalogSnapshot | None,
    *,
    options: Mapping[str, Any] | None = None,
    now: datetime | None = None,
) -> PreparedAttempt:
    """Every check before dispatch. Any failure blocks the attempt and selects no other model.

    A local profile reads no catalog, since OpenRouter's says nothing about it. Its identity is
    checked against the server itself before each call (local_server.check_served)."""
    profile = policy.profile_for(role)
    if _is_local(profile):
        checked = checked_options(options or {}, LOCAL_PARAMETERS)
        return PreparedAttempt(profile, role, LOCAL_CATALOG_REVISION, checked)
    if catalog is None:
        raise ModelUnavailable("the model catalog could not be read")
    entry = validated_entry(profile, catalog, now or datetime.now(UTC))
    checked = checked_options(options or {}, entry.supported_parameters)
    return PreparedAttempt(profile, role, catalog.revision, checked)


def local_chat_model(
    attempt: PreparedAttempt, port: int, *, client: LoopbackClient | None = None
) -> ChatOpenRouter:
    """The same class on a loopback client: no key, no retries and no OpenRouter routing flags.
    The request timeout sits above the route's bound on a call, so that bound decides (Decision
    0041 A11)."""
    loopback = client or LoopbackClient(
        attempt.profile, port, limits_for(attempt.profile).call_seconds + REQUEST_MARGIN_SECONDS
    )
    return ChatOpenRouter(
        model=attempt.profile.wire_id,
        api_key=NOT_A_KEY,
        base_url=base_url(port),
        max_retries=0,
        client=loopback,
        **attempt.options,
    )


def chat_model(
    attempt: PreparedAttempt,
    api_key: SecretStr,
    *,
    client_factory: Callable[[str], Any] | None = None,
) -> ChatOpenRouter:
    """A client for one prepared attempt. Route, retries and fallbacks are fixed here."""
    if _is_local(attempt.profile):
        raise ValueError("a local profile's client is built by local_chat_model")
    make_client = default_sdk_client if client_factory is None else client_factory
    client = make_client(api_key.get_secret_value())
    return ChatOpenRouter(
        model=attempt.profile.wire_id,
        api_key=api_key,
        base_url=OPENROUTER_BASE_URL,
        max_retries=0,
        client=client,
        openrouter_provider=dict(PROVIDER_ROUTING),
        **attempt.options,
    )


# The SDK otherwise retries 5XX and connection errors with backoff for up to an hour, and
# `ChatOpenRouter(max_retries=0)` leaves that default in place. Application policy owns every retry.
NO_SDK_RETRIES = RetryConfig("none", BackoffStrategy(1, 1, 1.0, 1), False)
# The SDK's own HTTP client otherwise gives up after httpx's 5 seconds, and a model can take longer
# than that to reply. This sits above the goal loop's bound on a call, so that bound decides.
REQUEST_TIMEOUT_MS = 130_000
# A local request's timeout sits this far above the route's bound on a call (`limits_for`).
REQUEST_MARGIN_SECONDS = 30.0


def default_sdk_client(
    api_key: str,
    *,
    http: httpx.Client | None = None,
    async_http: httpx.AsyncClient | None = None,
) -> openrouter.OpenRouter:
    return openrouter.OpenRouter(
        api_key=api_key,
        server_url=OPENROUTER_BASE_URL,
        retry_config=NO_SDK_RETRIES,
        timeout_ms=REQUEST_TIMEOUT_MS,
        client=http,
        async_client=async_http,
    )
