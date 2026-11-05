"""The only two provider requests allowed outside inference: key metadata and the public catalog."""

from collections.abc import Callable
from typing import Any

import httpx
from pydantic import SecretStr

from autobots.adapters.models.factory import OPENROUTER_BASE_URL
from autobots.application.provider_settings import KeyCheck

TIMEOUT_SECONDS = 15.0


def http_client(transport: httpx.AsyncBaseTransport | None = None) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=OPENROUTER_BASE_URL, timeout=TIMEOUT_SECONDS, transport=transport
    )


def key_validator(make_client: Callable[[], httpx.AsyncClient] = http_client) -> Any:
    async def validate(key: SecretStr) -> KeyCheck:
        """A network failure is not a rejected key, MP-04."""
        headers = {"Authorization": f"Bearer {key.get_secret_value()}"}
        try:
            async with make_client() as client:
                reply = await client.get("/key", headers=headers)
        except httpx.HTTPError:
            return KeyCheck.UNREACHABLE
        if reply.status_code == 200:
            return KeyCheck.VALID
        return KeyCheck.REJECTED if reply.status_code in {401, 403} else KeyCheck.UNREACHABLE

    return validate


def catalog_fetcher(make_client: Callable[[], httpx.AsyncClient] = http_client) -> Any:
    async def fetch() -> dict[str, Any] | None:
        try:
            async with make_client() as client:
                reply = await client.get("/models")
        except httpx.HTTPError:
            return None
        if reply.status_code != 200:
            return None
        data: dict[str, Any] = reply.json()
        return data

    return fetch
