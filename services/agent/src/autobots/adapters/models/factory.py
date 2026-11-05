"""The one OpenRouter factory, MP-01 and MP-02. Nothing else builds a model client."""

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
from autobots.domain.models import ModelProfile, ModelRole, RolePolicy

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


def prepare_attempt(
    policy: RolePolicy,
    role: ModelRole,
    catalog: CatalogSnapshot,
    *,
    options: Mapping[str, Any] | None = None,
    now: datetime | None = None,
) -> PreparedAttempt:
    """Every check before dispatch. Any failure blocks the attempt and selects no other model."""
    profile = policy.profile_for(role)
    entry = validated_entry(profile, catalog, now or datetime.now(UTC))
    checked = checked_options(options or {}, entry.supported_parameters)
    return PreparedAttempt(profile, role, catalog.revision, checked)


def chat_model(
    attempt: PreparedAttempt,
    api_key: SecretStr,
    *,
    client_factory: Callable[[str], Any] | None = None,
) -> ChatOpenRouter:
    """A client for one prepared attempt. Route, retries and fallbacks are fixed here."""
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
