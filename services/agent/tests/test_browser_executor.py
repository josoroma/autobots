"""US-14.13 offline: the egress proxy's decisions, the CDP gate, the request guard and the session.

The live behaviour is qualified by scripts/qualify_browser_executor.py on Docker; these pin the
logic without a socket, a container or a network. test_browser_qualification.py covers what a
qualification binds.
"""

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from autobots.adapters import browser_cdp, browser_executor, browser_qualification, egress_proxy
from autobots.adapters.browser_cdp import RequestGuard
from autobots.adapters.browser_executor import BrowserExecutor, ExecutorConfig, ExecutorUnavailable
from autobots.adapters.egress_proxy import Session, decide, handle_cdp, handle_egress, handle_model

NAMES = {
    "example.com": ["93.184.215.14"],
    "rebind.example.com": ["93.184.215.14", "127.0.0.1"],
    "local.example.com": ["10.0.0.5"],
}


async def resolve(host: str, _: int) -> list[str]:
    if host not in NAMES:
        raise OSError("not found")
    return NAMES[host]


def session(**options: object) -> Session:
    return Session(log=lambda _: None, **options)  # type: ignore[arg-type]  # each test passes the fields it needs


@pytest.mark.parametrize(
    ("target", "allowed", "decision"),
    [
        ("example.com:443", ("example.com",), ("93.184.215.14", "allowed")),
        ("www.example.com:443", ("example.com",), (None, "unresolvable")),
        ("example.com:80", ("example.com",), (None, "port_refused")),
        ("example.org:443", ("example.com",), (None, "host_not_allowed")),
        ("notexample.com:443", ("example.com",), (None, "host_not_allowed")),
        ("rebind.example.com:443", ("example.com",), (None, "host_refused")),
        ("local.example.com:443", ("example.com",), (None, "host_refused")),
        ("127.0.0.1:443", ("127.0.0.1",), (None, "host_refused")),
        ("[::1]:443", ("::1",), (None, "host_refused")),
        ("169.254.169.254:443", ("169.254.169.254",), (None, "host_refused")),
        ("example.com:443", (), (None, "host_not_allowed")),
        ("nonsense", ("example.com",), (None, "malformed")),
    ],
)
@pytest.mark.asyncio
async def test_each_connect_is_decided_by_port_allowlist_and_every_answer(
    target: str, allowed: tuple[str, ...], decision: tuple[str | None, str]
) -> None:
    address, _, reason = await decide(target, session(allowed=allowed), resolve)
    assert (address, reason) == decision


@pytest.mark.asyncio
async def test_the_request_cap_refuses_past_its_count() -> None:
    capped = session(allowed=("example.com",), max_requests=2)
    reasons = [(await decide("example.com:443", capped, resolve))[2] for _ in range(3)]
    assert reasons == ["allowed", "allowed", "request_cap"]


class Stream:
    """An in-memory stand-in for a connection's two halves."""

    def __init__(self, data: bytes) -> None:
        self.reader = asyncio.StreamReader()
        self.reader.feed_data(data)
        self.reader.feed_eof()
        self.written = bytearray()
        self.closed = False

    def write(self, data: bytes) -> None:
        self.written.extend(data)

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_only_connect_leaves_and_its_log_names_no_path() -> None:
    entries: list[dict[str, object]] = []
    plain = Session(allowed=("example.com",), log=entries.append)
    stream = Stream(
        b"GET http://example.com/secret?token=abc HTTP/1.1\r\nHost: example.com\r\n\r\n"
    )
    await handle_egress(stream.reader, stream, plain, resolve)  # type: ignore[arg-type]  # a fake stream for asyncio.StreamWriter
    assert stream.written.startswith(b"HTTP/1.1 403")
    assert [(e["event"], e["host"], e["reason"]) for e in entries] == [
        ("refused", "example.com", "scheme_refused")
    ]
    assert "secret" not in json.dumps(entries)


@pytest.mark.asyncio
async def test_a_connect_reaches_only_the_checked_address() -> None:
    opened: list[tuple[str, int]] = []
    upstream = Stream(b"")

    async def opener(address: str, port: int) -> tuple[asyncio.StreamReader, Stream]:
        opened.append((address, port))
        return upstream.reader, upstream

    allowed = session(allowed=("example.com",))
    client = Stream(b"CONNECT example.com:443 HTTP/1.1\r\nHost: example.com:443\r\n\r\n")
    await handle_egress(client.reader, client, allowed, resolve, opener)  # type: ignore[arg-type]  # a fake stream for asyncio.StreamWriter
    assert opened == [("93.184.215.14", 443)]
    assert client.written.startswith(b"HTTP/1.1 200")


@pytest.mark.parametrize(
    ("path", "forwarded"),
    [
        ("/tok/json/version", True),
        ("/json/version", False),
        ("/other/json/version", False),
        ("/tokx/json/version", False),
    ],
)
@pytest.mark.asyncio
async def test_the_cdp_gate_needs_the_token(path: str, forwarded: bool) -> None:
    sent: list[bytes] = []
    upstream = Stream(b"")
    upstream_write = upstream.write

    def capture(data: bytes) -> None:
        sent.append(bytes(data))
        upstream_write(data)

    upstream.write = capture  # type: ignore[method-assign]  # records what the proxy forwards

    async def opener(address: str, port: int) -> tuple[asyncio.StreamReader, Stream]:
        return upstream.reader, upstream

    client = Stream(f"GET {path} HTTP/1.1\r\nHost: 127.0.0.1:5555\r\n\r\n".encode())
    await handle_cdp(client.reader, client, "tok", ("browser", 9222), opener)  # type: ignore[arg-type]  # a fake stream for asyncio.StreamWriter
    if forwarded:
        assert sent and sent[0].startswith(b"GET /json/version HTTP/1.1")
        assert b"Host: 127.0.0.1:9222" in sent[0] and b"tok" not in sent[0]
    else:
        assert not sent and client.written.startswith(b"HTTP/1.1 403")


def test_the_proxy_uses_the_standard_library_only() -> None:
    source = Path(egress_proxy.__file__).read_text()
    assert "import autobots" not in source and "from autobots" not in source


@pytest.mark.parametrize("host", ["", "example.com/path", "a,b", ".example.com", "two words"])
@pytest.mark.asyncio
async def test_a_malformed_allowed_host_is_refused_before_docker(host: str) -> None:
    with pytest.raises(ExecutorUnavailable):
        await BrowserExecutor(environ={}).start("run", 1, (host,))


def test_the_executor_starts_the_images_the_qualification_binds() -> None:
    """The label check reads the very images a session starts (refactor plan R-57)."""
    config = ExecutorConfig()
    assert (config.browser_image, config.proxy_image) == (
        browser_qualification.BROWSER.tag,
        browser_qualification.PROXY.tag,
    )


def test_the_executor_module_still_offers_what_its_importers_name() -> None:
    assert browser_executor.Cdp is browser_cdp.Cdp
    assert browser_executor.RequestGuard is browser_cdp.RequestGuard
    assert browser_executor.executor_qualified is browser_qualification.executor_qualified


class Sent:
    """Records the commands a request guard sends, in place of a DevTools connection."""

    def __init__(self) -> None:
        self.commands: list[tuple[str, dict[str, Any] | None, str | None]] = []
        self.handlers: list[Any] = []

    async def send(
        self, method: str, params: dict[str, Any] | None = None, session: str | None = None
    ) -> dict[str, Any]:
        self.commands.append((method, params, session))
        return {}


@pytest.mark.parametrize(
    ("method", "url", "body", "answer"),
    [
        ("GET", "https://example.com/", False, "Fetch.continueRequest"),
        ("HEAD", "data:text/plain,x", False, "Fetch.continueRequest"),
        ("GET", "about:blank", False, "Fetch.continueRequest"),
        ("POST", "https://example.com/form", True, "Fetch.failRequest"),
        ("GET", "https://example.com/", True, "Fetch.failRequest"),
        ("GET", "http://example.com/", False, "Fetch.failRequest"),
        ("GET", "file:///etc/hosts", False, "Fetch.failRequest"),
    ],
)
@pytest.mark.asyncio
async def test_the_request_guard_lets_through_only_bodiless_reads_of_allowed_schemes(
    method: str, url: str, body: bool, answer: str
) -> None:
    sent = Sent()
    guard = RequestGuard(sent)  # type: ignore[arg-type]  # a fake CDP sender
    request = {"method": method, "url": url, "hasPostData": body}
    paused = {"requestId": "r1", "request": request}
    await guard._event({"method": "Fetch.requestPaused", "sessionId": "s1", "params": paused})
    assert [(command, session) for command, _, session in sent.commands] == [(answer, "s1")]
    assert bool(guard.refused) == (answer == "Fetch.failRequest")
    assert all("/" not in entry["host"] for entry in guard.refused)


@pytest.mark.parametrize(
    ("request_head", "forwarded"),
    [
        (
            "POST /v1/chat/completions HTTP/1.1\r\nHost: proxy:9300\r\n"
            "Authorization: Bearer from-the-box\r\nContent-Length: 2\r\n\r\n{}",
            True,
        ),
        ("GET /v1/chat/completions HTTP/1.1\r\nHost: proxy:9300\r\n\r\n", False),
        ("POST /v1/models HTTP/1.1\r\nHost: proxy:9300\r\nContent-Length: 0\r\n\r\n", False),
    ],
)
@pytest.mark.asyncio
async def test_the_model_relay_forwards_only_chat_completions_with_the_session_token(
    request_head: str, forwarded: bool
) -> None:
    """Decision 0035 Y7: the box reaches the endpoint only here, and never holds the token."""
    sent: list[bytes] = []
    upstream = Stream(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\n{}")
    upstream_write = upstream.write

    def capture(data: bytes) -> None:
        sent.append(bytes(data))
        upstream_write(data)

    upstream.write = capture  # type: ignore[method-assign]  # records what the relay forwards
    opened: list[tuple[str, int]] = []

    async def opener(address: str, port: int) -> tuple[asyncio.StreamReader, Stream]:
        opened.append((address, port))
        return upstream.reader, upstream

    client = Stream(request_head.encode())
    await handle_model(client.reader, client, "secret", ("host.docker.internal", 4321), opener)  # type: ignore[arg-type]  # a fake stream for asyncio.StreamWriter
    if forwarded:
        head = sent[0]
        assert head.startswith(b"POST /v1/chat/completions HTTP/1.1\r\n")
        assert b"Authorization: Bearer secret" in head and b"from-the-box" not in head
        assert b"Host: host.docker.internal:4321" in head
        assert opened == [("host.docker.internal", 4321)]
        assert b"".join(sent).endswith(b"{}") and client.written.startswith(b"HTTP/1.1 200 OK")
    else:
        assert not sent and not opened and client.written.startswith(b"HTTP/1.1 404")


@pytest.mark.asyncio
async def test_a_session_with_a_model_link_gives_only_the_sidecar_its_upstream_and_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, ...]] = []

    async def docker(self: BrowserExecutor, *arguments: str, check: bool = True) -> str:
        calls.append(arguments)
        return "127.0.0.1:5555" if arguments[0] == "port" else ""

    async def ready(self: BrowserExecutor, session: object, seconds: float = 20.0) -> None:
        return None

    monkeypatch.setattr(BrowserExecutor, "_docker", docker)
    monkeypatch.setattr(BrowserExecutor, "_ready", ready)
    link = browser_executor.ModelLink(port=4321, token="model-token")
    await BrowserExecutor(environ={}).start("run", 1, ("en.wikivoyage.org",), link)
    started = {call[3]: call for call in calls if call[:2] == ("run", "-d")}
    proxy = next(call for name, call in started.items() if name.endswith("-proxy"))
    browser = next(call for name, call in started.items() if name.endswith("-browser"))
    assert "host.docker.internal:host-gateway" in proxy
    assert "AUTOBOTS_MODEL_UPSTREAM=host.docker.internal:4321" in proxy
    assert "AUTOBOTS_MODEL_TOKEN=model-token" in proxy
    assert not any("model-token" in part or "MODEL" in part for part in browser)
