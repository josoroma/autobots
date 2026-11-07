"""The one guard for every URL a tool fetches or sends to a provider, PRD-Tool-Catalog UG-01 and
Decision 0017 C6.

`https` only, no userinfo, a bounded length, and a host whose every DNS answer is a public address,
so no tool can reach this Mac's loopback services, a private network or cloud metadata. A fetch
revalidates each redirect target, follows at most three, and stops at a size and a time cap. Every
refusal is a typed code raised before the request it refuses.
"""

import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx

from autobots.application.tool_gateway import ToolFailed

MAX_URL_LENGTH = 2048
MAX_REDIRECTS = 3
DEFAULT_MAX_BYTES = 1_048_576
DEFAULT_SECONDS = 20.0
REDIRECTS = frozenset({301, 302, 303, 307, 308})

Resolver = Callable[[str, int], Awaitable[list[str]]]


class UrlRefused(ToolFailed):
    """A typed refusal. Its code is the failure the model sees, and never the URL itself."""


async def system_resolver(host: str, port: int) -> list[str]:
    answers = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return sorted({str(answer[4][0]) for answer in answers})


def public(address: str) -> bool:
    """Globally routable only. That excludes loopback, private, link-local (with the metadata
    address), carrier-grade NAT, multicast, reserved, unspecified and documentation ranges."""
    try:
        ip = ipaddress.ip_address(address.split("%", 1)[0])
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast


async def check_url(url: str, resolver: Resolver = system_resolver) -> str:
    """The URL, unchanged, if it may be fetched. Called before any request that names it."""
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
        answers = [host]
    except ValueError:
        try:
            answers = await resolver(host, port)
        except (OSError, UnicodeError):
            raise UrlRefused("url_unresolvable") from None
    if not answers:
        raise UrlRefused("url_unresolvable")
    if not all(public(answer) for answer in answers):
        raise UrlRefused("url_host_refused")
    return url


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


async def _follow(
    url: str,
    transport: httpx.AsyncBaseTransport | None,
    resolver: Resolver,
    headers: Mapping[str, str],
    max_bytes: int,
) -> Fetched:
    current = url
    async with httpx.AsyncClient(
        transport=transport, follow_redirects=False, trust_env=False, headers=dict(headers)
    ) as client:
        for hop in range(MAX_REDIRECTS + 1):
            await check_url(current, resolver)
            try:
                async with client.stream("GET", current) as reply:
                    if reply.status_code in REDIRECTS:
                        location = reply.headers.get("location")
                        if not location:
                            raise UrlRefused("url_redirect_malformed")
                        if hop == MAX_REDIRECTS:
                            raise UrlRefused("url_too_many_redirects")
                        current = urljoin(current, location)
                        continue
                    body = bytearray()
                    declared = reply.headers.get("content-length")
                    if declared is not None and declared.isdigit() and int(declared) > max_bytes:
                        raise UrlRefused("url_too_large")
                    async for chunk in reply.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > max_bytes:
                            raise UrlRefused("url_too_large")
                    return Fetched(
                        url=current,
                        status=reply.status_code,
                        content_type=reply.headers.get("content-type", ""),
                        body=bytes(body),
                    )
            except httpx.HTTPError:
                raise UrlRefused("url_unreachable") from None
    raise UrlRefused("url_too_many_redirects")  # pragma: no cover - the loop returns or raises.
