"""US-14.8: the URL guard, with a fake resolver and a fake transport. No socket is ever opened.

A fetch is sent to the address the guard checked, with the URL's host as `Host` and as the name its
certificate must hold (refactor plan R-62, PADP-15), so the fakes route by `Host`.
"""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable

import httpx
import pytest

from autobots.adapters import egress_proxy
from autobots.adapters.url_guard import (
    DEFAULT_SECONDS,
    HOP_SECONDS,
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


def named(request: httpx.Request) -> str:
    """The URL as the tool named it, from the address the guard sent it to and its `Host`."""
    return f"{request.url.scheme}://{request.headers['host']}{request.url.raw_path.decode()}"


class Recorder:
    def __init__(
        self, handler: Callable[[httpx.Request], httpx.Response | Awaitable[httpx.Response]]
    ) -> None:
        self.requests: list[str] = []
        self.sent: list[httpx.Request] = []
        self.handler = handler

    def transport(self) -> httpx.MockTransport:
        async def answer(request: httpx.Request) -> httpx.Response:
            self.requests.append(named(request))
            self.sent.append(request)
            result = self.handler(request)
            return await result if isinstance(result, Awaitable) else result

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
    target = hops.get(request.headers["host"])
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
        if request.headers["host"] == "example.com":
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


@pytest.mark.asyncio
async def test_a_fetch_connects_to_the_address_it_checked_and_no_other() -> None:
    """A name that answers public to the check and private to a second lookup can't reach the
    private one: nothing looks the name up again (PADP-15)."""
    answers = iter([[PUBLIC], ["127.0.0.1"]])
    asked: list[str] = []

    async def rebinding(host: str, _: int) -> list[str]:
        asked.append(host)
        return next(answers)

    recorder = Recorder(ok)
    fetched = await guarded_fetch(
        "https://rebinding.example.com/page?q=1", transport=recorder.transport(), resolver=rebinding
    )
    assert fetched.url == "https://rebinding.example.com/page?q=1" and fetched.status == 200
    assert asked == ["rebinding.example.com"]
    [request] = recorder.sent
    assert str(request.url) == f"https://{PUBLIC}/page?q=1"
    assert request.headers["host"] == "rebinding.example.com"
    assert request.extensions["sni_hostname"] == "rebinding.example.com"


@pytest.mark.asyncio
async def test_each_hop_is_pinned_to_its_own_checked_address() -> None:
    recorder = Recorder(chain)
    await guarded_fetch(
        "https://three.example.com/", transport=recorder.transport(), resolver=resolve
    )
    assert [request.url.host for request in recorder.sent] == [
        "93.184.215.16",
        "93.184.215.17",
        "93.184.215.18",
    ]
    assert [request.extensions["sni_hostname"] for request in recorder.sent] == [
        "three.example.com",
        "four.example.com",
        "five.example.com",
    ]


@pytest.mark.asyncio
async def test_an_ipv6_answer_and_an_explicit_port_are_kept() -> None:
    recorder = Recorder(ok)
    await guarded_fetch(
        "https://v6.example.com:8443/x", transport=recorder.transport(), resolver=resolve
    )
    [request] = recorder.sent
    assert str(request.url) == "https://[2606:2800:220:1:248:1893:25c8:1946]:8443/x"
    assert request.headers["host"] == "v6.example.com:8443"


@pytest.mark.asyncio
async def test_a_url_naming_its_address_is_sent_as_it_is() -> None:
    recorder = Recorder(ok)
    await guarded_fetch(f"https://{PUBLIC}/x", transport=recorder.transport(), resolver=resolve)
    [request] = recorder.sent
    assert str(request.url) == f"https://{PUBLIC}/x" and "sni_hostname" not in request.extensions


@pytest.mark.asyncio
async def test_an_international_name_is_sent_in_its_ascii_form() -> None:
    recorder = Recorder(ok)

    async def anywhere(_: str, __: int) -> list[str]:
        return [PUBLIC]

    await guarded_fetch(
        "https://bücher.example/", transport=recorder.transport(), resolver=anywhere
    )
    [request] = recorder.sent
    assert request.headers["host"] == "xn--bcher-kva.example"
    assert request.extensions["sni_hostname"] == "xn--bcher-kva.example"


def test_each_hop_has_a_bound_inside_the_fetchs_own_cap() -> None:
    assert HOP_SECONDS < DEFAULT_SECONDS


@pytest.mark.parametrize(
    "address",
    [
        PUBLIC,
        "8.8.8.8",
        "2606:4700:4700::1111",
        "127.0.0.1",
        "10.0.0.1",
        "172.16.0.1",
        "192.168.1.1",
        "100.64.0.1",
        "169.254.169.254",
        "fd00:ec2::254",
        "224.0.0.1",
        "ff02::1",
        "240.0.0.1",
        "0.0.0.0",
        "::",
        "::1",
        "fe80::1%eth0",
        "::ffff:127.0.0.1",
        "::ffff:93.184.215.14",
        "192.0.2.1",
        "198.51.100.1",
        "203.0.113.1",
        "2001:db8::1",
        "not an address",
        "",
    ],
)
def test_the_egress_proxy_and_the_guard_agree_on_public(address: str) -> None:
    """The proxy keeps a standard-library copy (Decision 0018 B3). If one changes what counts as
    public and the other doesn't, the browser and the fetch tools disagree (PADP-20)."""
    assert egress_proxy.public(address) == public(address)


DUAL = ["2606:2800:220:1:248:1893:25c8:1946", PUBLIC]


async def dual(_: str, __: int) -> list[str]:
    return DUAL


@pytest.mark.asyncio
async def test_a_dead_first_address_falls_back_to_the_next_checked_one() -> None:
    """A network without working IPv6 still reaches the name over IPv4, as httpx itself would."""

    def ipv4_only(request: httpx.Request) -> httpx.Response:
        if request.url.host == DUAL[0]:
            raise httpx.ConnectError("arranged: no IPv6 route")
        return ok(request)

    recorder = Recorder(ipv4_only)
    fetched = await guarded_fetch(
        "https://dual.example.com/x", transport=recorder.transport(), resolver=dual
    )
    assert fetched.status == 200 and fetched.url == "https://dual.example.com/x"
    assert [request.url.host for request in recorder.sent] == DUAL
    assert {request.headers["host"] for request in recorder.sent} == {"dual.example.com"}


@pytest.mark.asyncio
async def test_with_every_checked_address_dead_the_fetch_is_unreachable() -> None:
    def dead(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("arranged")

    recorder = Recorder(dead)
    with pytest.raises(UrlRefused) as refused:
        await guarded_fetch(
            "https://dual.example.com/x", transport=recorder.transport(), resolver=dual
        )
    assert str(refused.value) == "url_unreachable"
    assert [request.url.host for request in recorder.sent] == DUAL


@pytest.mark.asyncio
async def test_a_failure_after_the_connection_opened_doesnt_move_on() -> None:
    """Only a connection that never opened is tried elsewhere."""

    def lost(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadError("arranged")

    recorder = Recorder(lost)
    with pytest.raises(UrlRefused) as refused:
        await guarded_fetch(
            "https://dual.example.com/x", transport=recorder.transport(), resolver=dual
        )
    assert str(refused.value) == "url_unreachable"
    assert len(recorder.sent) == 1


@pytest.mark.asyncio
async def test_the_system_resolver_keeps_its_order_and_each_address_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from autobots.adapters.url_guard import system_resolver

    async def answers(host: str, port: int, **_: object) -> list[tuple[object, ...]]:
        return [
            (10, 1, 6, "", (DUAL[0], port, 0, 0)),
            (2, 1, 6, "", (PUBLIC, port)),
            (10, 1, 6, "", (DUAL[0], port, 0, 0)),
        ]

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", answers)
    assert await system_resolver("dual.example.com", 443) == DUAL
