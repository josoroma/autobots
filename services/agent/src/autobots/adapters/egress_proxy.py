"""The browser executor's egress proxy and CDP gate, PRD-Tool-Catalog BX-02, BX-03, Decision 0018.

Runs in the sidecar container, so it uses the standard library only and imports nothing from
Autobots. Two listeners:

- **Egress (port 3128)**, the browser's only way out. It accepts `CONNECT host:443` and nothing
  else, only to the hosts this call names (each with its subdomains). It resolves the host itself,
  requires every answer to be a public address, connects to the address it checked (so a
  rebinding name can't reach a private one), and caps requests and bytes per session. It logs the
  host, address and decision, never a path or query, which a tunnel doesn't show anyway.
- **CDP gate (port 9223)**, published on the Mac's loopback only. A connection must name the session
  token as the first path segment; the gate strips it, rewrites `Host` to an address Chromium
  accepts, and forwards the bytes to the browser's DevTools port. Anything else is refused.
- **Model relay (port 9300)**, only when the call has a model endpoint (Decision 0035 Y7). It
  forwards `POST /v1/chat/completions` from the box to the worker's admitted endpoint, replacing any
  `Authorization` with the session's token, which only this sidecar holds. It reaches that one port
  and path only, so nothing else of the host is open to the box.

The same checks run in the worker's tests, against fake resolvers and sockets.
"""

import asyncio
import ipaddress
import json
import os
import socket
import sys
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

HEAD_LIMIT = 16_384
Resolver = Callable[[str, int], Awaitable[list[str]]]
Opener = Callable[[str, int], Awaitable[tuple[asyncio.StreamReader, asyncio.StreamWriter]]]


def public(address: str) -> bool:
    """Globally routable only, as the worker's URL guard decides it."""
    try:
        ip = ipaddress.ip_address(address.split("%", 1)[0])
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast


async def system_resolver(host: str, port: int) -> list[str]:
    answers = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return sorted({str(answer[4][0]) for answer in answers})


async def system_opener(
    address: str, port: int
) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    return await asyncio.open_connection(address, port)


@dataclass
class Session:
    """One browsing call's limits and its log. One sidecar serves one call."""

    max_requests: int = 500
    max_bytes: int = 50 * 1024 * 1024
    # The hosts this call may reach, each with its subdomains. Empty means none at all.
    allowed: tuple[str, ...] = ()
    requests: int = 0
    bytes: int = 0
    log: Callable[[dict[str, object]], None] = field(
        default=lambda entry: print(json.dumps(entry, sort_keys=True), flush=True)
    )

    def record(self, **entry: object) -> None:
        self.log({"at": round(time.time(), 3), **entry})


async def decide(target: str, session: Session, resolver: Resolver) -> tuple[str | None, str, str]:
    """The address to connect to, or None with a reason. `target` is a CONNECT's `host:port`."""
    host, _, port_text = target.rpartition(":")
    host = host.strip("[]")
    if not host or not port_text.isdigit():
        return None, host or target, "malformed"
    if int(port_text) != 443:
        return None, host, "port_refused"
    name = host.lower().rstrip(".")
    if not any(name == domain or name.endswith("." + domain) for domain in session.allowed):
        return None, host, "host_not_allowed"
    if session.requests >= session.max_requests:
        return None, host, "request_cap"
    session.requests += 1
    try:
        ipaddress.ip_address(host)
        answers = [host]
    except ValueError:
        try:
            answers = await resolver(host, 443)
        except (OSError, UnicodeError):
            return None, host, "unresolvable"
    if not answers:
        return None, host, "unresolvable"
    if not all(public(answer) for answer in answers):
        return None, host, "host_refused"
    return answers[0], host, "allowed"


async def _head(reader: asyncio.StreamReader) -> bytes:
    data = await reader.readuntil(b"\r\n\r\n")
    if len(data) > HEAD_LIMIT:
        raise ValueError("head too large")
    return data


async def _pipe(
    source: asyncio.StreamReader,
    sink: asyncio.StreamWriter,
    session: Session | None,
) -> None:
    try:
        while chunk := await source.read(65_536):
            if session is not None:
                session.bytes += len(chunk)
                if session.bytes > session.max_bytes:
                    session.record(event="byte_cap", bytes=session.bytes)
                    break
            sink.write(chunk)
            await sink.drain()
    except (ConnectionError, asyncio.IncompleteReadError):
        pass
    finally:
        sink.close()


async def _refuse(writer: asyncio.StreamWriter, status: str = "403 Forbidden") -> None:
    writer.write(f"HTTP/1.1 {status}\r\nContent-Length: 0\r\nConnection: close\r\n\r\n".encode())
    try:
        await writer.drain()
    finally:
        writer.close()


async def handle_egress(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    session: Session,
    resolver: Resolver = system_resolver,
    opener: Opener = system_opener,
) -> None:
    try:
        head = await _head(reader)
    except (ValueError, asyncio.IncompleteReadError, asyncio.LimitOverrunError):
        await _refuse(writer, "400 Bad Request")
        return
    method, _, rest = head.split(b"\r\n", 1)[0].decode("latin-1").partition(" ")
    target = rest.split(" ", 1)[0]
    if method != "CONNECT":
        # Plain HTTP would show paths; only https tunnels leave, and only by CONNECT.
        session.record(event="refused", host=_host_of(target), reason="scheme_refused")
        await _refuse(writer)
        return
    address, host, reason = await decide(target, session, resolver)
    if address is None:
        session.record(event="refused", host=host, reason=reason)
        await _refuse(writer)
        return
    try:
        upstream_reader, upstream_writer = await opener(address, 443)
    except OSError:
        session.record(event="refused", host=host, reason="unreachable", address=address)
        await _refuse(writer, "502 Bad Gateway")
        return
    session.record(event="allowed", host=host, address=address)
    writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
    await writer.drain()
    await asyncio.gather(
        _pipe(reader, upstream_writer, session), _pipe(upstream_reader, writer, session)
    )


def _host_of(target: str) -> str:
    """The host of an absolute URL or authority, without its path or query."""
    without = target.split("://", 1)[-1]
    return without.split("/", 1)[0].split("?", 1)[0]


async def handle_cdp(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    token: str,
    browser: tuple[str, int],
    opener: Opener = system_opener,
) -> None:
    try:
        head = await _head(reader)
    except (ValueError, asyncio.IncompleteReadError, asyncio.LimitOverrunError):
        await _refuse(writer, "400 Bad Request")
        return
    lines = head.decode("latin-1").split("\r\n")
    method, _, rest = lines[0].partition(" ")
    path, _, version = rest.partition(" ")
    prefix = f"/{token}"
    if not token or not (path == prefix or path.startswith(prefix + "/")):
        await _refuse(writer)
        return
    forwarded = [f"{method} {path[len(prefix) :] or '/'} {version}"]
    for line in lines[1:]:
        if line.lower().startswith("host:"):
            # Chromium only answers a Host that is an address or localhost.
            forwarded.append(f"Host: 127.0.0.1:{browser[1]}")
        elif line:
            forwarded.append(line)
    try:
        upstream_reader, upstream_writer = await opener(*browser)
    except OSError:
        await _refuse(writer, "502 Bad Gateway")
        return
    upstream_writer.write(("\r\n".join(forwarded) + "\r\n\r\n").encode("latin-1"))
    await upstream_writer.drain()
    await asyncio.gather(_pipe(reader, upstream_writer, None), _pipe(upstream_reader, writer, None))


MODEL_PATH = "/v1/chat/completions"


async def handle_model(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    token: str,
    upstream: tuple[str, int],
    opener: Opener = system_opener,
) -> None:
    try:
        head = await _head(reader)
    except (ValueError, asyncio.IncompleteReadError, asyncio.LimitOverrunError):
        await _refuse(writer, "400 Bad Request")
        return
    lines = head.decode("latin-1").split("\r\n")
    method, _, rest = lines[0].partition(" ")
    path = rest.partition(" ")[0]
    if not token or method != "POST" or path != MODEL_PATH:
        await _refuse(writer, "404 Not Found")
        return
    # Header lines the relay sets itself, matched by their name and colon.
    replaced = ("authorization:", "host:", "connection:", "proxy-authorization:")
    forwarded = [lines[0]]
    forwarded += [line for line in lines[1:] if line and not line.lower().startswith(replaced)]
    forwarded += [
        f"Host: {upstream[0]}:{upstream[1]}",
        f"Authorization: Bearer {token}",
        "Connection: close",
    ]
    try:
        upstream_reader, upstream_writer = await opener(*upstream)
    except OSError:
        await _refuse(writer, "502 Bad Gateway")
        return
    upstream_writer.write(("\r\n".join(forwarded) + "\r\n\r\n").encode("latin-1"))
    await upstream_writer.drain()
    await asyncio.gather(_pipe(reader, upstream_writer, None), _pipe(upstream_reader, writer, None))


def model_upstream(value: str) -> tuple[str, int] | None:
    """`host:port` from the environment, or None when the call has no model endpoint."""
    host, _, port = value.rpartition(":")
    return (host, int(port)) if host and port.isdigit() else None


async def serve() -> None:
    token = os.environ["AUTOBOTS_CDP_TOKEN"]
    session = Session(
        max_requests=int(os.environ.get("AUTOBOTS_MAX_REQUESTS", "500")),
        max_bytes=int(os.environ.get("AUTOBOTS_MAX_BYTES", str(50 * 1024 * 1024))),
        allowed=tuple(
            domain.strip().lower().rstrip(".")
            for domain in os.environ.get("AUTOBOTS_ALLOWED_HOSTS", "").split(",")
            if domain.strip()
        ),
    )
    browser = (os.environ.get("AUTOBOTS_BROWSER_HOST", "browser"), 9222)
    egress = await asyncio.start_server(
        lambda r, w: handle_egress(r, w, session), "0.0.0.0", 3128, limit=HEAD_LIMIT * 2
    )
    gate = await asyncio.start_server(
        lambda r, w: handle_cdp(r, w, token, browser), "0.0.0.0", 9223, limit=HEAD_LIMIT * 2
    )
    servers = [egress, gate]
    upstream = model_upstream(os.environ.get("AUTOBOTS_MODEL_UPSTREAM", ""))
    model_token = os.environ.get("AUTOBOTS_MODEL_TOKEN", "")
    if upstream is not None and model_token:
        servers.append(
            await asyncio.start_server(
                lambda r, w: handle_model(r, w, model_token, upstream),
                "0.0.0.0",
                9300,
                limit=HEAD_LIMIT * 2,
            )
        )
    session.record(event="ready")
    await asyncio.gather(*(server.serve_forever() for server in servers))


if __name__ == "__main__":  # pragma: no cover - the sidecar's entry point.
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        sys.exit(0)
