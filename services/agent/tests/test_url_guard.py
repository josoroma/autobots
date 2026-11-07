"""US-14.8: the URL guard, with a fake resolver and a fake transport. No socket is ever opened."""

import asyncio
from collections.abc import AsyncIterator

import httpx
import pytest

from autobots.adapters.url_guard import (
    MAX_URL_LENGTH,
    UrlRefused,
    check_url,
    guarded_fetch,
    public,
)

PUBLIC = "93.184.215.14"
NAMES = {
    "example.com": [PUBLIC],
    "two.example.com": ["93.184.215.15"],
    "three.example.com": ["93.184.215.16"],
    "four.example.com": ["93.184.215.17"],
    "five.example.com": ["93.184.215.18"],
    "mixed.example.com": [PUBLIC, "10.0.0.5"],
    "local.example.com": ["127.0.0.1"],
    "metadata.example.com": ["169.254.169.254"],
    "rebind.example.com": ["::ffff:127.0.0.1"],
    "v6.example.com": ["2606:2800:220:1:248:1893:25c8:1946"],
}


async def resolve(host: str, _: int) -> list[str]:
    if host not in NAMES:
        raise OSError("not found")
    return NAMES[host]


class Recorder:
    def __init__(self, handler) -> None:  # type: ignore[no-untyped-def]
        self.requests: list[str] = []
        self.handler = handler

    def transport(self) -> httpx.MockTransport:
        async def answer(request: httpx.Request) -> httpx.Response:
            self.requests.append(str(request.url))
            result = self.handler(request)
            if asyncio.iscoroutine(result):
                result = await result
            return result  # type: ignore[no-any-return]

        return httpx.MockTransport(answer)


def ok(_: httpx.Request) -> httpx.Response:
    return httpx.Response(200, text="hello", headers={"content-type": "text/plain"})


@pytest.mark.parametrize(
    ("url", "code"),
    [
        ("http://example.com/", "url_scheme_refused"),
        ("ftp://example.com/", "url_scheme_refused"),
        ("file:///etc/passwd", "url_scheme_refused"),
        ("https://user:pass@example.com/", "url_userinfo_refused"),
        ("https://user@example.com/", "url_userinfo_refused"),
        ("https://example.com/" + "a" * MAX_URL_LENGTH, "url_too_long"),
        ("https://127.0.0.1/", "url_host_refused"),
        ("https://[::1]/", "url_host_refused"),
        ("https://10.1.2.3/", "url_host_refused"),
        ("https://192.168.1.1/", "url_host_refused"),
        ("https://172.16.0.1/", "url_host_refused"),
        ("https://169.254.169.254/latest/meta-data/", "url_host_refused"),
        ("https://100.64.0.1/", "url_host_refused"),
        ("https://224.0.0.1/", "url_host_refused"),
        ("https://240.0.0.1/", "url_host_refused"),
        ("https://0.0.0.0/", "url_host_refused"),
        ("https://[fd00:ec2::254]/", "url_host_refused"),
        ("https://local.example.com/", "url_host_refused"),
        ("https://metadata.example.com/", "url_host_refused"),
        ("https://mixed.example.com/", "url_host_refused"),
        ("https://rebind.example.com/", "url_host_refused"),
        ("https://missing.example.com/", "url_unresolvable"),
        ("https:///nohost", "url_malformed"),
    ],
)
@pytest.mark.asyncio
async def test_unsafe_urls_are_refused_before_any_request(url: str, code: str) -> None:
    recorder = Recorder(ok)
    with pytest.raises(UrlRefused) as refused:
        await guarded_fetch(url, transport=recorder.transport(), resolver=resolve)
    assert str(refused.value) == code
    assert recorder.requests == []
    with pytest.raises(UrlRefused):
        await check_url(url, resolve)


@pytest.mark.asyncio
async def test_a_public_url_is_fetched() -> None:
    recorder = Recorder(ok)
    fetched = await guarded_fetch(
        "https://example.com/page?q=1", transport=recorder.transport(), resolver=resolve
    )
    assert (fetched.status, fetched.body, fetched.content_type) == (200, b"hello", "text/plain")
    assert recorder.requests == ["https://example.com/page?q=1"]
    assert await check_url("https://v6.example.com/", resolve) == "https://v6.example.com/"


def chain(request: httpx.Request) -> httpx.Response:
    hops = {
        "example.com": "https://two.example.com/",
        "two.example.com": "https://three.example.com/",
        "three.example.com": "https://four.example.com/",
        "four.example.com": "https://five.example.com/",
    }
    target = hops.get(request.url.host)
    if target is None:
        return ok(request)
    return httpx.Response(302, headers={"location": target})


@pytest.mark.asyncio
async def test_three_redirects_are_followed_and_a_fourth_is_refused() -> None:
    recorder = Recorder(chain)
    fetched = await guarded_fetch(
        "https://two.example.com/", transport=recorder.transport(), resolver=resolve
    )
    assert fetched.url == "https://five.example.com/"
    assert len(recorder.requests) == 4
    recorder = Recorder(chain)
    with pytest.raises(UrlRefused) as refused:
        await guarded_fetch(
            "https://example.com/", transport=recorder.transport(), resolver=resolve
        )
    assert str(refused.value) == "url_too_many_redirects"
    # The fourth redirect's target was never requested.
    assert "https://five.example.com/" not in recorder.requests
    assert len(recorder.requests) == 4


@pytest.mark.parametrize(
    "target",
    [
        "https://127.0.0.1/admin",
        "https://local.example.com/",
        "http://two.example.com/",
        "https://169.254.169.254/latest/meta-data/",
    ],
)
@pytest.mark.asyncio
async def test_each_redirect_target_is_revalidated(target: str) -> None:
    def redirect(request: httpx.Request) -> httpx.Response:
        if request.url.host == "example.com":
            return httpx.Response(307, headers={"location": target})
        return ok(request)

    recorder = Recorder(redirect)
    with pytest.raises(UrlRefused) as refused:
        await guarded_fetch(
            "https://example.com/", transport=recorder.transport(), resolver=resolve
        )
    assert str(refused.value) in {"url_host_refused", "url_scheme_refused"}
    assert recorder.requests == ["https://example.com/"]


@pytest.mark.asyncio
async def test_a_body_over_the_cap_stops_the_fetch() -> None:
    declared = Recorder(lambda _: httpx.Response(200, content=b"x" * 2048))
    with pytest.raises(UrlRefused) as refused:
        await guarded_fetch(
            "https://example.com/", transport=declared.transport(), resolver=resolve, max_bytes=1024
        )
    assert str(refused.value) == "url_too_large"

    async def chunks() -> AsyncIterator[bytes]:
        for _ in range(64):
            yield b"y" * 64

    streamed = Recorder(lambda _: httpx.Response(200, content=chunks()))
    with pytest.raises(UrlRefused) as refused:
        await guarded_fetch(
            "https://example.com/", transport=streamed.transport(), resolver=resolve, max_bytes=1024
        )
    assert str(refused.value) == "url_too_large"


@pytest.mark.asyncio
async def test_a_slow_response_stops_at_the_time_cap() -> None:
    async def slow(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(5)
        return ok(request)

    recorder = Recorder(slow)
    with pytest.raises(UrlRefused) as refused:
        await guarded_fetch(
            "https://example.com/", transport=recorder.transport(), resolver=resolve, seconds=0.2
        )
    assert str(refused.value) == "url_timeout"


def test_public_means_globally_routable() -> None:
    assert public(PUBLIC)
    for address in ("127.0.0.1", "10.0.0.1", "169.254.169.254", "100.64.0.1", "::1", "fe80::1"):
        assert not public(address)
    assert not public("not an address")
