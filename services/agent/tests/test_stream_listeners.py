"""Live streams share a cap on LISTEN connections (refactor plan R-55, PAPI-11; US-15.24).

Each live stream listens on a direct connection outside the pool. Up to the cap, each stream gets
one; past it, a stream polls stored events only, as one does when LISTEN can't connect. Closing a
stream, or its client going away, gives its slot back. No database, socket or model is used.
"""

import asyncio
from collections.abc import AsyncGenerator, AsyncIterator, MutableMapping
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import psycopg
import pytest
from fastapi import Request
from pydantic import SecretStr

from autobots.api import event_routes
from autobots.api.app import create_app
from autobots.api.event_routes import END_FRAME, MAX_LISTENERS, ListenerSlots, listener_slots
from autobots.api.pool import ConnectionPool
from autobots.api.settings import Settings
from fake_api import INTERNAL, SECRET, WORKSPACE, FakeDatabase, FakeMembership, token

RUN = UUID("0b000000-0000-4000-8000-0000000000c1")
CONNECTED = ": connected\n\n"


class Listener:
    """A LISTEN connection that hears nothing, waiting out each wait as psycopg's does."""

    def __init__(self) -> None:
        self.closed = False

    async def execute(self, _statement: str) -> None:
        return None

    def notifies(self, *, timeout: float) -> AsyncIterator[object]:
        return self._nothing(timeout)

    async def _nothing(self, seconds: float) -> AsyncIterator[object]:
        await asyncio.sleep(seconds)
        notes: tuple[object, ...] = ()
        for note in notes:
            yield note

    async def close(self) -> None:
        self.closed = True


@dataclass
class Arranged:
    """A stream's request over the app state streams read, and every listener opened."""

    slots: ListenerSlots
    listeners: list[Listener] = field(default_factory=list)
    database: FakeDatabase = field(default_factory=lambda: FakeDatabase([]))

    def request(self) -> Request:
        settings = Settings(database_url=SecretStr("postgresql://fixture"))
        state = SimpleNamespace(settings=settings, listener_slots=self.slots, stream_seconds=5.0)

        async def connected() -> bool:
            return False

        return cast(
            Request, SimpleNamespace(app=SimpleNamespace(state=state), is_disconnected=connected)
        )

    def stream(self) -> AsyncGenerator[str]:
        frames = event_routes._frames(
            self.request(), cast(ConnectionPool, self.database), WORKSPACE, RUN, 0
        )
        # An async generator, so a test can close it as a client's disconnect does.
        return cast(AsyncGenerator[str], frames)


@pytest.fixture
def arranged(monkeypatch: pytest.MonkeyPatch) -> Arranged:
    found = Arranged(ListenerSlots(limit=2))

    async def connect(*_args: object, **_kwargs: object) -> Listener:
        listener = Listener()
        found.listeners.append(listener)
        return listener

    monkeypatch.setattr(psycopg.AsyncConnection, "connect", connect)
    # The run has finished, so a stream ends once it has read its stored events.
    found.database.answer("from public.runs r where r.id = %(run)s", (RUN,))
    found.database.answer("select status from public.runs where id = %s", ("succeeded",))
    return found


def test_the_cap_is_ten_listeners_made_on_first_use() -> None:
    state = SimpleNamespace()
    request = cast(Request, SimpleNamespace(app=SimpleNamespace(state=state)))
    slots = listener_slots(request)
    assert (MAX_LISTENERS, slots.limit, slots.held) == (10, 10, 0)
    assert listener_slots(request) is slots


@pytest.mark.asyncio
async def test_up_to_the_cap_each_stream_listens(arranged: Arranged) -> None:
    first, second = arranged.stream(), arranged.stream()
    assert [await anext(first), await anext(second)] == [CONNECTED, CONNECTED]
    assert len(arranged.listeners) == 2 and arranged.slots.held == 2
    await first.aclose()
    await second.aclose()
    assert all(listener.closed for listener in arranged.listeners)
    assert arranged.slots.held == 0


@pytest.mark.asyncio
async def test_past_the_cap_a_stream_polls_stored_events_until_a_slot_frees(
    arranged: Arranged,
) -> None:
    held = [arranged.stream(), arranged.stream()]
    for stream in held:
        await anext(stream)
    polling = arranged.stream()
    assert await anext(polling) == CONNECTED
    assert len(arranged.listeners) == 2 and arranged.slots.held == 2
    # It still reads stored events, and ends as any stream does once its run has finished.
    assert [frame async for frame in polling] == [END_FRAME]
    assert arranged.slots.held == 2
    await held[0].aclose()
    assert arranged.listeners[0].closed and arranged.slots.held == 1
    after = arranged.stream()
    await anext(after)
    assert len(arranged.listeners) == 3 and arranged.slots.held == 2
    for stream in (held[1], after):
        await stream.aclose()
    assert arranged.slots.held == 0


@pytest.mark.asyncio
async def test_a_listener_that_cant_connect_gives_its_slot_back(
    arranged: Arranged, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def refused(*_args: object, **_kwargs: object) -> Listener:
        raise psycopg.OperationalError("arranged")

    monkeypatch.setattr(psycopg.AsyncConnection, "connect", refused)
    stream = arranged.stream()
    assert await anext(stream) == CONNECTED
    assert arranged.slots.held == 0
    assert [frame async for frame in stream] == [END_FRAME]


@pytest.mark.asyncio
async def test_a_connection_that_cant_listen_is_closed_and_gives_its_slot_back(
    arranged: Arranged, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Deaf(Listener):
        async def execute(self, _statement: str) -> None:
            raise psycopg.OperationalError("arranged")

    async def connect(*_args: object, **_kwargs: object) -> Listener:
        listener = Deaf()
        arranged.listeners.append(listener)
        return listener

    monkeypatch.setattr(psycopg.AsyncConnection, "connect", connect)
    stream = arranged.stream()
    assert await anext(stream) == CONNECTED
    assert arranged.listeners[0].closed and arranged.slots.held == 0
    await stream.aclose()


@pytest.mark.asyncio
async def test_a_client_that_goes_away_gives_its_slot_back(arranged: Arranged) -> None:
    """Through the app's own StreamingResponse, which stops when its client disconnects."""
    settings = Settings(
        internal_token=SecretStr(INTERNAL),
        jwt_secret=SecretStr(SECRET),
        database_url=SecretStr("postgresql://fixture"),
        allowed_hosts=("testserver",),
    )
    app = create_app(settings, membership=FakeMembership([]))
    app.state.pool = arranged.database
    app.state.listener_slots = arranged.slots
    # A run still going, so only the client's going away ends the stream.
    arranged.database.answer("select status from public.runs where id = %s", ("running",))
    path = f"/v1/runs/{RUN}/events/stream"
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "root_path": "",
        "query_string": b"",
        "headers": [
            (b"host", b"testserver"),
            (b"x-autobots-internal", INTERNAL.encode()),
            (b"authorization", f"Bearer {token()}".encode()),
        ],
        "client": ("127.0.0.1", 50000),
        "server": ("testserver", 80),
    }
    first_frame = asyncio.Event()
    sent: list[bytes] = []
    asked = 0

    async def receive() -> MutableMapping[str, object]:
        nonlocal asked
        asked += 1
        if asked == 1:
            return {"type": "http.request", "body": b"", "more_body": False}
        await first_frame.wait()
        return {"type": "http.disconnect"}

    async def send(message: MutableMapping[str, object]) -> None:
        body = message.get("body")
        if message["type"] == "http.response.body" and isinstance(body, bytes) and body:
            sent.append(body)
            first_frame.set()

    await asyncio.wait_for(app(scope, receive, send), timeout=5)
    assert sent[0] == CONNECTED.encode()
    assert len(arranged.listeners) == 1 and arranged.listeners[0].closed
    assert arranged.slots.held == 0
