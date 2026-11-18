"""The one provider HTTP layer: how every client is made and how every reply maps (refactor plan
R-62: PADP-04, PADP-05, PADP-07 and XDUP-11). Fake transports only; nothing leaves the process.
"""

from typing import Annotated

import httpx
import pytest
from pydantic import Field, SecretStr

from autobots.adapters.models import openrouter_metadata
from autobots.adapters.models.factory import OPENROUTER_BASE_URL
from autobots.adapters.object_storage import StorageUnavailable, SupabaseObjectStore
from autobots.adapters.provider_http import (
    MALFORMED,
    Number,
    Objects,
    ProviderReply,
    Strings,
    Text,
    UnclearReply,
    http_client,
    parsed,
    read,
    refusal_code,
    write,
    write_json,
)
from autobots.application.tool_definitions import OutcomeUnknown, ToolFailed

REFUSED = frozenset({400, 401, 403, 404, 410, 422, 429})


class Item(ProviderReply):
    title: Text = ""
    score: Number = None


class Listing(ProviderReply):
    items: Annotated[list[Item], Objects] = Field(default_factory=list)
    urls: Annotated[list[str], Strings] = Field(default_factory=list)


def answering(reply: httpx.Response | Exception) -> httpx.MockTransport:
    def answer(_: httpx.Request) -> httpx.Response:
        if isinstance(reply, Exception):
            raise reply
        return reply

    return httpx.MockTransport(answer)


def client(reply: httpx.Response | Exception) -> httpx.AsyncClient:
    return http_client("https://provider.invalid", timeout=5.0, transport=answering(reply))


def test_every_client_follows_no_redirect_and_reads_nothing_from_the_environment() -> None:
    made = http_client("https://provider.invalid", timeout=7.0, headers={"Accept": "x"})
    assert (made.follow_redirects, made.trust_env) == (False, False)
    assert made.timeout == httpx.Timeout(7.0)
    assert made.headers["accept"] == "x"


def test_a_client_needs_a_named_timeout() -> None:
    with pytest.raises(TypeError):
        http_client("https://provider.invalid")  # type: ignore[call-arg]  # the omission under test


def test_the_environments_certificate_and_proxy_settings_are_never_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """httpx reads SSL_CERT_FILE when it trusts the environment, so a missing file proves which."""
    monkeypatch.setenv("SSL_CERT_FILE", "/nonexistent/autobots-ca.pem")
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.invalid:1")
    with pytest.raises(FileNotFoundError):
        httpx.AsyncClient()
    assert http_client("https://provider.invalid", timeout=5.0).trust_env is False
    assert openrouter_metadata.http_client().trust_env is False
    store = SupabaseObjectStore("http://storage.invalid", SecretStr("k"))
    assert store._client().trust_env is False


def test_the_storage_client_keeps_its_timeout_and_headers() -> None:
    store = SupabaseObjectStore("http://storage.invalid/", SecretStr("service"), timeout=12)
    made = store._client()
    assert made.base_url == httpx.URL("http://storage.invalid/storage/v1/")
    assert made.timeout == httpx.Timeout(12)
    assert (made.headers["apikey"], made.headers["authorization"]) == ("service", "Bearer service")
    assert (made.follow_redirects, made.trust_env) == (False, False)
    assert SupabaseObjectStore("http://s.invalid", SecretStr("k"))._client().timeout == (
        httpx.Timeout(30)
    )


def test_the_openrouter_metadata_client_keeps_its_timeout_and_base() -> None:
    made = openrouter_metadata.http_client()
    assert made.base_url == httpx.URL(f"{OPENROUTER_BASE_URL}/")
    assert made.timeout == httpx.Timeout(openrouter_metadata.TIMEOUT_SECONDS) == httpx.Timeout(15)
    assert (made.follow_redirects, made.trust_env) == (False, False)


@pytest.mark.asyncio
async def test_refusing_redirects_changes_no_path_that_worked() -> None:
    """httpx follows none by default, which the OpenRouter metadata client used, and the storage
    client already refused them, so neither path ever followed one. A redirect still reads as an
    outage on both, as it did."""
    assert httpx.AsyncClient().follow_redirects is False
    moved = httpx.Response(307, headers={"location": "https://elsewhere.invalid/models"})
    fetch = openrouter_metadata.catalog_fetcher(
        lambda: openrouter_metadata.http_client(answering(moved))
    )
    assert await fetch() is None
    store = SupabaseObjectStore(
        "http://storage.invalid", SecretStr("k"), transport=answering(httpx.Response(302))
    )
    with pytest.raises(StorageUnavailable):
        await store.ping()


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (429, "rate_limited"),
        (401, "tavily_key_refused"),
        (403, "tavily_key_refused"),
        (400, "provider_refused_400"),
        (404, "provider_refused_404"),
        (500, "provider_unavailable"),
        (302, "provider_unavailable"),
    ],
)
def test_a_refusal_maps_to_one_typed_code(status: int, code: str) -> None:
    assert refusal_code("tavily", status) == code


@pytest.mark.asyncio
async def test_a_read_maps_transport_errors_and_statuses_to_typed_codes() -> None:
    async def go(reply: httpx.Response | Exception) -> httpx.Response:
        async with client(reply) as made:
            return await read(made, "GET", "/x", code_for=lambda status: f"code_{status}")

    with pytest.raises(ToolFailed, match=r"^provider_unavailable$"):
        await go(httpx.ReadError("arranged"))
    with pytest.raises(ToolFailed, match=r"^code_503$"):
        await go(httpx.Response(503))
    assert (await go(httpx.Response(200, json={}))).status_code == 200


@pytest.mark.parametrize(
    "body",
    [b"not json", b"[]", b'{"items": "nope"}', b'{"items": [{"title": "t"}], "urls": 3}'],
)
def test_a_reply_of_the_wrong_shape_is_malformed(body: bytes) -> None:
    with pytest.raises(ToolFailed) as failed:
        parsed(httpx.Response(200, content=body), Listing)
    assert str(failed.value) == MALFORMED


def test_a_reply_reads_leniently_where_its_shape_allows() -> None:
    body = b'{"items": [{"title": null, "score": "high"}, 3, {"title": 5, "score": 0.5}], '
    body += b'"urls": ["https://a.example", 7], "extra": true}'
    reply = parsed(httpx.Response(200, content=body), Listing)
    assert [(item.title, item.score) for item in reply.items] == [("", None), ("5", 0.5)]
    assert reply.urls == ["https://a.example"]


@pytest.mark.parametrize("error", [httpx.ConnectError("arranged"), httpx.ConnectTimeout("x")])
@pytest.mark.asyncio
async def test_a_write_whose_connection_never_opened_failed(error: Exception) -> None:
    with pytest.raises(ToolFailed, match=r"^destination_unreachable$"):
        await _write(error)


@pytest.mark.parametrize("status", sorted(REFUSED))
@pytest.mark.asyncio
async def test_a_write_refused_by_status_failed(status: int) -> None:
    with pytest.raises(ToolFailed, match=rf"^github_refused_{status}$"):
        await _write(httpx.Response(status))


@pytest.mark.parametrize("status", [200, 202, 302, 409, 500, 502, 504])
@pytest.mark.asyncio
async def test_any_other_write_reply_stays_unknown(status: int) -> None:
    with pytest.raises(UnclearReply) as unclear:
        await _write(httpx.Response(status))
    assert isinstance(unclear.value, OutcomeUnknown)
    assert unclear.value.detail == f"github_unclear_{status}"


@pytest.mark.asyncio
async def test_a_write_whose_reply_was_lost_after_sending_stays_unknown() -> None:
    """Not a ToolFailed: the request went out, so only a readback can say."""
    with pytest.raises(httpx.ReadError):
        await _write(httpx.ReadError("arranged"))


@pytest.mark.asyncio
async def test_a_created_reply_that_cant_be_read_stays_unknown() -> None:
    async def go() -> Item:
        async with client(httpx.Response(201, content=b"[1]")) as made:
            return await write_json(made, "/x", {}, Item, provider="github", refused=REFUSED)

    with pytest.raises(UnclearReply) as unclear:
        await go()
    assert unclear.value.detail == "github_unclear_201"


async def _write(reply: httpx.Response | Exception) -> httpx.Response:
    async with client(reply) as made:
        return await write(made, "/x", {"a": 1}, provider="github", refused=REFUSED)
