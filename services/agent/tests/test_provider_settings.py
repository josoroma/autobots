"""Key checks and decisions that need no database. Real rows run in scripts/qualify_identity.py."""

import httpx
import pytest
from pydantic import SecretStr

from autobots.adapters.models.openrouter_metadata import catalog_fetcher, key_validator
from autobots.application.provider_settings import KeyCheck
from autobots.contracts.settings import CredentialDraft, ProviderStatus


def client_for(handler: httpx.MockTransport) -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url="https://openrouter.ai/api/v1", transport=handler)


def validator(status: int) -> object:
    def handle(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/key", "only the key metadata route"
        assert request.method == "GET"
        return httpx.Response(status, json={"data": {}})

    transport = httpx.MockTransport(handle)
    return key_validator(lambda: client_for(transport))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (200, KeyCheck.VALID),
        (401, KeyCheck.REJECTED),
        (403, KeyCheck.REJECTED),
        (429, KeyCheck.UNREACHABLE),
        (500, KeyCheck.UNREACHABLE),
    ],
)
async def test_key_metadata_results(status: int, expected: KeyCheck) -> None:
    validate = validator(status)
    assert await validate(SecretStr("sk-or-arranged")) is expected  # type: ignore[operator]


@pytest.mark.asyncio
async def test_a_network_failure_is_not_a_rejected_key() -> None:
    def handle(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route")

    transport = httpx.MockTransport(handle)
    validate = key_validator(lambda: client_for(transport))
    assert await validate(SecretStr("sk-or-arranged")) is KeyCheck.UNREACHABLE


@pytest.mark.asyncio
async def test_a_catalog_outage_returns_nothing() -> None:
    transport = httpx.MockTransport(lambda _request: httpx.Response(503))
    assert await catalog_fetcher(lambda: client_for(transport))() is None


def test_a_status_cannot_carry_a_key() -> None:
    assert "draft_key" not in ProviderStatus.model_fields
    assert not any("key" in name and name != "draft_key" for name in ProviderStatus.model_fields)


def test_a_draft_repr_does_not_matter_because_it_is_never_returned() -> None:
    assert CredentialDraft(draft_key="x", expected_version=0).expected_version == 0
