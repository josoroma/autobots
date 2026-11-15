"""The one guard for every URL a tool fetches or sends to a provider, PRD-Tool-Catalog UG-01 and
Decision 0017 C6.

`https` only, no userinfo, a bounded length, and a host whose every DNS answer is a public address,
so no tool can reach this Mac's loopback services, a private network or cloud metadata. A fetch
connects to the address it checked, never to a second answer for the same name, sends the URL's
own host and verifies its certificate for that name; it revalidates each redirect target, follows at
most three, and stops at a size and a time cap. Every refusal is a typed code raised before the
request it refuses (PADP-15).
"""

import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx

from autobots.adapters.provider_http import http_client
from autobots.application.tool_gateway import ToolFailed

MAX_URL_LENGTH = 2048
MAX_REDIRECTS = 3
DEFAULT_MAX_BYTES = 1_048_576
DEFAULT_SECONDS = 20.0
# Each hop's connect, read and write bound, inside the fetch's own cap of DEFAULT_SECONDS.
HOP_SECONDS = 5.0
REDIRECTS = frozenset({301, 302, 303, 307, 308})

Resolver = Callable[[str, int], Awaitable[list[str]]]


class UrlRefused(ToolFailed):
    """A typed refusal. Its code is the failure the model sees, and never the URL itself."""


async def system_resolver(host: str, port: int) -> list[str]:
    """Each address once, in the resolver's order, which is the order a fetch tries them in."""
    answers = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return list(dict.fromkeys(str(answer[4][0]) for answer in answers))


def public(address: str) -> bool:
    """Globally routable only. That excludes loopback, private, link-local (with the metadata
    address), carrier-grade NAT, multicast, reserved, unspecified and documentation ranges.

    The egress proxy keeps a standard-library copy (egress_proxy.public), and
    tests/test_url_guard.py holds the two to the same answers."""
    try:
        ip = ipaddress.ip_address(address.split("%", 1)[0])
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast


@dataclass(frozen=True)
class Vetted:
    """A URL the guard passed, and the public addresses it checked for the URL's host, in the
    resolver's order. `literal` when the URL names its one address itself."""

    url: str
    addresses: tuple[str, ...]
    literal: bool


Target = tuple[str, dict[str, str], dict[str, str]]


def _pinned(vetted: Vetted, address: str) -> Target:
    """The request to one checked address: its URL, with the address in place of the host so
    nothing resolves the name again, the URL's own `Host`, and the name its certificate must hold.
    A URL that names its address is sent as it is."""
    if vetted.literal:
        return vetted.url, {}, {}
    named = httpx.URL(vetted.url)
    ip = ipaddress.ip_address(address)
    host = f"[{ip}]" if isinstance(ip, ipaddress.IPv6Address) else str(ip)
    parts = urlsplit(vetted.url)
    netloc = host if parts.port is None else f"{host}:{parts.port}"
    return (
        urlunsplit(("https", netloc, parts.path, parts.query, "")),
        {"Host": named.netloc.decode("ascii")},
        {"sni_hostname": named.raw_host.decode("ascii")},
    )


async def vet_url(url: str, resolver: Resolver = system_resolver) -> Vetted:
    """The URL and the address checked for it, if it may be fetched. Called before any request
    that names it."""
    if len(url) > MAX_URL_LENGTH:
        raise UrlRefused("url_too_long")
    try:
        parts = urlsplit(url)
        port = parts.port or 443
    except ValueError:
        raise UrlRefused("url_malformed") from None
    if parts.scheme != "https":
        raise UrlRefused("url_scheme_refused")
    if parts.username is not None or parts.password is not None or "@" in parts.netloc:
        raise UrlRefused("url_userinfo_refused")
    host = parts.hostname
    if not host:
        raise UrlRefused("url_malformed")
    try:
        ipaddress.ip_address(host)
        answers, literal = [host], True
    except ValueError:
        try:
            answers, literal = await resolver(host, port), False
        except (OSError, UnicodeError):
            raise UrlRefused("url_unresolvable") from None
    if not answers:
        raise UrlRefused("url_unresolvable")
    if not all(public(answer) for answer in answers):
        raise UrlRefused("url_host_refused")
    return Vetted(url, tuple(answers), literal)


async def check_url(url: str, resolver: Resolver = system_resolver) -> str:
    """The URL, unchanged, if it may be fetched or sent to a provider."""
    return (await vet_url(url, resolver)).url


@dataclass(frozen=True)
class Fetched:
    url: str
    status: int
    content_type: str
    body: bytes


async def guarded_fetch(
    url: str,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
    resolver: Resolver = system_resolver,
    headers: Mapping[str, str] | None = None,
    max_bytes: int = DEFAULT_MAX_BYTES,
    seconds: float = DEFAULT_SECONDS,
) -> Fetched:
    """GET through the guard. Each hop is checked before it is requested."""
    try:
        async with asyncio.timeout(seconds):
            return await _follow(url, transport, resolver, headers or {}, max_bytes)
    except TimeoutError:
        raise UrlRefused("url_timeout") from None


@dataclass(frozen=True)
class _Redirect:
    location: str


async def _follow(
    url: str,
    transport: httpx.AsyncBaseTransport | None,
    resolver: Resolver,
    headers: Mapping[str, str],
    max_bytes: int,
) -> Fetched:
    current = url
    for hop in range(MAX_REDIRECTS + 1):
        vetted = await vet_url(current, resolver)
        try:
            targets = [_pinned(vetted, address) for address in vetted.addresses]
        except (httpx.InvalidURL, UnicodeError):
            raise UrlRefused("url_malformed") from None
        try:
            answer = await _first_answer(vetted.url, targets, transport, headers, max_bytes)
        except httpx.HTTPError:
            raise UrlRefused("url_unreachable") from None
        if isinstance(answer, Fetched):
            return answer
        if not answer.location:
            raise UrlRefused("url_redirect_malformed")
        if hop == MAX_REDIRECTS:
            raise UrlRefused("url_too_many_redirects")
        current = urljoin(current, answer.location)
    raise UrlRefused("url_too_many_redirects")  # pragma: no cover - the loop returns or raises.


async def _first_answer(
    url: str,
    targets: list[Target],
    transport: httpx.AsyncBaseTransport | None,
    headers: Mapping[str, str],
    max_bytes: int,
) -> Fetched | _Redirect:
    """The hop's request to each checked address in the resolver's order, as a client connecting to
    the name would try them, so a host without working IPv6 is still reached over IPv4. Only a
    connection that never opened moves on to the next, and together they have HOP_SECONDS to open
    one. Any other failure ends the hop."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + HOP_SECONDS
    for target in targets:
        left = deadline - loop.time()
        if left <= 0:
            break
        try:
            return await _hop(url, target, transport, headers, max_bytes, left)
        except (httpx.ConnectError, httpx.ConnectTimeout):
            continue
    raise UrlRefused("url_unreachable")


async def _hop(
    url: str,
    target: Target,
    transport: httpx.AsyncBaseTransport | None,
    headers: Mapping[str, str],
    max_bytes: int,
    connect_seconds: float,
) -> Fetched | _Redirect:
    """One request, to one checked address. A client per request, so no connection made for one
    name carries another name's request. A redirect's body is never read."""
    pinned_url, host, extensions = target
    timeout = httpx.Timeout(HOP_SECONDS, connect=connect_seconds)
    async with (
        http_client(timeout=timeout, headers=headers, transport=transport) as client,
        client.stream("GET", pinned_url, headers=host, extensions=extensions) as reply,
    ):
        if reply.status_code in REDIRECTS:
            return _Redirect(reply.headers.get("location", ""))
        # Defense in depth: when the connection says where it went, that address must pass too,
        # before any of the body is read.
        stream = reply.extensions.get("network_stream")
        peer = stream.get_extra_info("server_addr") if stream is not None else None
        if peer and not public(str(peer[0])):
            raise UrlRefused("url_host_refused")
        declared = reply.headers.get("content-length")
        if declared is not None and declared.isdigit() and int(declared) > max_bytes:
            raise UrlRefused("url_too_large")
        body = bytearray()
        async for chunk in reply.aiter_bytes():
            body.extend(chunk)
            if len(body) > max_bytes:
                raise UrlRefused("url_too_large")
        return Fetched(
            url=url,
            status=reply.status_code,
            content_type=reply.headers.get("content-type", ""),
            body=bytes(body),
        )
