"""US-14.13 offline: the egress proxy's decisions, the CDP gate and the qualification gate.

The live behaviour is qualified by scripts/qualify_browser_executor.py on Docker; these pin the
logic without a socket, a container or a network.
"""

import asyncio
import json
from pathlib import Path

import pytest

from autobots.adapters import egress_proxy
from autobots.adapters.browser_executor import (
    REQUIRED_CASES,
    BrowserExecutor,
    ExecutorUnavailable,
    executor_qualified,
    images_fingerprint,
)
from autobots.adapters.egress_proxy import Session, decide, handle_cdp, handle_egress

ROOT = Path(__file__).resolve().parents[3]
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
    return Session(log=lambda _: None, **options)  # type: ignore[arg-type]


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
    await handle_egress(stream.reader, stream, plain, resolve)  # type: ignore[arg-type]
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
    await handle_egress(client.reader, client, allowed, resolve, opener)  # type: ignore[arg-type]
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

    upstream.write = capture  # type: ignore[method-assign]

    async def opener(address: str, port: int) -> tuple[asyncio.StreamReader, Stream]:
        return upstream.reader, upstream

    client = Stream(f"GET {path} HTTP/1.1\r\nHost: 127.0.0.1:5555\r\n\r\n".encode())
    await handle_cdp(client.reader, client, "tok", ("browser", 9222), opener)  # type: ignore[arg-type]
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


def report(tmp_path: Path, **changes: object) -> Path:
    data: dict[str, object] = {
        "status": "passed",
        "executor_fingerprint": images_fingerprint(ROOT),
        "cases": [{"id": case, "status": "passed"} for case in REQUIRED_CASES],
    }
    data.update(changes)
    path = tmp_path / "qualification.json"
    path.write_text(json.dumps(data))
    return path


def test_qualified_only_from_a_passing_report_at_todays_fingerprint(tmp_path: Path) -> None:
    assert executor_qualified(ROOT, report(tmp_path))
    assert not executor_qualified(ROOT, tmp_path / "missing.json")
    assert not executor_qualified(ROOT, report(tmp_path, status="failed"))
    missing_one = [{"id": case, "status": "passed"} for case in REQUIRED_CASES[1:]]
    assert not executor_qualified(ROOT, report(tmp_path, cases=missing_one))
    one_failed = [{"id": REQUIRED_CASES[0], "status": "failed"}, *missing_one]
    assert not executor_qualified(ROOT, report(tmp_path, cases=one_failed))
    assert not executor_qualified(ROOT, report(tmp_path, executor_fingerprint={"x": "y"}))
