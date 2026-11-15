"""Cursor replay, a live stream and a snapshot. Closing a stream never touches the run."""

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from psycopg import AsyncConnection

from autobots.adapters.result_stream import CHANNEL as RESULT_CHANNEL
from autobots.api.dependencies import MemberWorkspace
from autobots.api.errors import ApiError
from autobots.api.pool import ConnectionPool, request_pool
from autobots.api.security import require_internal
from autobots.application.run_projection import (
    RUN_LIST_SIZE,
    read_events,
    read_inspector,
    read_run_list,
    read_workspace,
)
from autobots.application.runs import current_status
from autobots.application.tool_uses import list_tool_uses
from autobots.contracts.run_workspace import (
    EventPage,
    RunInspector,
    RunList,
    RunListGroup,
    RunWorkspace,
    StreamCursor,
    StreamFrameName,
    StreamGap,
)
from autobots.contracts.runs import ResultTextDelta, RunEvent, ToolUseList
from autobots.domain.models import ModelProfileId
from autobots.domain.runs import TERMINAL

router = APIRouter(prefix="/v1", dependencies=[Depends(require_internal)])
Cursor = Annotated[int, Query(ge=0)]
POLL_SECONDS = 0.5
# A stream ends after a while, and the client reconnects from its cursor.
DEFAULT_STREAM_SECONDS = 60.0
KEEPALIVE_SECONDS = 15.0
# Each live stream listens on a direct connection outside the pool. Past this many at once, a
# stream polls stored events only, as one does when LISTEN can't connect (PAPI-11).
MAX_LISTENERS = 10


class ListenerSlots:
    """How many streams hold a LISTEN connection now, in this process. One event loop serves every
    stream, and nothing awaits between reading the count and changing it."""

    def __init__(self, limit: int = MAX_LISTENERS) -> None:
        self.limit = limit
        self.held = 0

    def take(self) -> bool:
        if self.held >= self.limit:
            return False
        self.held += 1
        return True

    def give_back(self) -> None:
        self.held -= 1


def listener_slots(request: Request) -> ListenerSlots:
    """This process's slots, made on first use."""
    slots: ListenerSlots | None = getattr(request.app.state, "listener_slots", None)
    if slots is None:
        slots = ListenerSlots()
        request.app.state.listener_slots = slots
    return slots


def _not_found() -> ApiError:
    return ApiError(404, "run_not_found", "That run is not available.")


@router.get("/runs/{run_id}/events", operation_id="listRunEvents", response_model=EventPage)
async def get_events(
    run_id: UUID, request: Request, workspace_id: MemberWorkspace, after: Cursor = 0
) -> EventPage:
    async with request_pool(request).connection() as connection:
        return await read_events(connection, workspace_id, run_id, after=after)


@router.get("/runs/{run_id}/workspace", operation_id="getRunWorkspace", response_model=RunWorkspace)
async def get_workspace(
    run_id: UUID, request: Request, workspace_id: MemberWorkspace
) -> RunWorkspace:
    async with request_pool(request).connection() as connection:
        return await read_workspace(connection, workspace_id, run_id)


@router.get("/runs", operation_id="listRuns", response_model=RunList)
async def get_runs(
    request: Request,
    workspace_id: MemberWorkspace,
    group: RunListGroup = "all",
    q: Annotated[str | None, Query(max_length=200)] = None,
    profile: ModelProfileId | None = None,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=RUN_LIST_SIZE)] = RUN_LIST_SIZE,
) -> RunList:
    """PRD-Studio RN-01 and RN-02: status groups with server counts, filters and a keyset cursor."""
    async with request_pool(request).connection() as connection:
        return await read_run_list(
            connection,
            workspace_id,
            limit,
            group=group,
            query=q,
            profile=profile.value if profile is not None else None,
            cursor=cursor,
        )


@router.get("/runs/{run_id}/inspector", operation_id="getRunInspector", response_model=RunInspector)
async def get_inspector(
    run_id: UUID, request: Request, workspace_id: MemberWorkspace
) -> RunInspector:
    async with request_pool(request).connection() as connection:
        return await read_inspector(connection, workspace_id, run_id)


@router.get("/runs/{run_id}/tool-uses", operation_id="listRunToolUses", response_model=ToolUseList)
async def get_tool_uses(
    run_id: UUID,
    request: Request,
    workspace_id: MemberWorkspace,
    after: Cursor = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> ToolUseList:
    """PRD-Tool-Catalog TU-07: the run's tree when it's a root, in order. Public fields only."""
    async with request_pool(request).connection() as connection:
        found = await list_tool_uses(connection, workspace_id, run_id, after=after, limit=limit)
    if found is None:
        raise _not_found()
    return found


async def _listener(request: Request) -> AsyncConnection[Any] | None:
    """US-15.24: this stream's own connection, listening for live result text. None when the API
    has no database address, as under a test client; then only durable events flow."""
    settings = getattr(request.app.state, "settings", None)
    url = settings.database_url.get_secret_value() if settings is not None else ""
    if not url:
        return None
    try:
        connection = await psycopg.AsyncConnection.connect(url, autocommit=True)
    except psycopg.Error:
        return None
    try:
        await connection.execute(f"listen {RESULT_CHANNEL}")
    except psycopg.Error:
        # Closed here, so a connection that can't listen never outlives its stream's slot.
        await connection.close()
        return None
    return connection


async def _held_listener(request: Request, slots: ListenerSlots) -> AsyncConnection[Any] | None:
    """A listening connection within the process's cap, or None past it or when none connects."""
    if not slots.take():
        return None
    try:
        listener = await _listener(request)
    except BaseException:
        slots.give_back()
        raise
    if listener is None:
        slots.give_back()
    return listener


def _frame(name: StreamFrameName, data: str, *, event_id: int | None = None) -> str:
    """One server-sent event. Only a stored event has an id, so only it moves the replay cursor."""
    head = "" if event_id is None else f"id: {event_id}\n"
    return f"{head}event: {name}\ndata: {data}\n\n"


def event_frame(event: RunEvent) -> str:
    """A stored event, sent as `run` with its sequence as the id the browser resumes after."""
    return _frame("run", event.model_dump_json(), event_id=event.sequence)


def cursor_frame(cursor: int) -> str:
    return _frame("cursor", StreamCursor(cursor=cursor).model_dump_json())


def gap_frame(after: int) -> str:
    return _frame("gap", StreamGap(after=after).model_dump_json())


# The run has finished and every event is sent, so the browser stops listening.
END_FRAME = _frame("end", "{}")


def live_frame(run_id: UUID, cursor: int, payload: str) -> str | None:
    """Only this run's text, re-validated as the typed delta. Sent as `live`, with no `id:`, so it
    never moves the browser's replay cursor; `sequence` names the durable event it follows."""
    try:
        note = json.loads(payload)
    except ValueError:
        return None
    if not isinstance(note, dict) or note.get("run_id") != str(run_id) or cursor < 1:
        return None
    try:
        event = RunEvent(
            schema_version=1,
            run_id=run_id,
            sequence=cursor,
            causal_ids=[],
            occurred_at=datetime.now(UTC),
            payload=ResultTextDelta(
                type="result.text.delta",
                segment=note["segment"],
                offset=note["offset"],
                text=note["text"],
            ),
        )
    except (KeyError, ValueError):
        return None
    return _frame("live", event.model_dump_json())


async def _frames(
    request: Request, pool: ConnectionPool, workspace_id: UUID, run_id: UUID, after: int
) -> AsyncIterator[str]:
    slots = listener_slots(request)
    listener = await _held_listener(request, slots)
    try:
        async for frame in _durable_and_live(request, pool, workspace_id, run_id, after, listener):
            yield frame
    finally:
        if listener is not None:
            try:
                await listener.close()
            finally:
                slots.give_back()


async def _durable_and_live(
    request: Request,
    pool: ConnectionPool,
    workspace_id: UUID,
    run_id: UUID,
    after: int,
    listener: AsyncConnection[Any] | None,
) -> AsyncIterator[str]:
    cursor = after
    loop = asyncio.get_running_loop()
    started = last_sent = loop.time()
    # Sends the headers now, or a quiet run would look like a connection that never opened.
    yield ": connected\n\n"
    lifetime = getattr(request.app.state, "stream_seconds", DEFAULT_STREAM_SECONDS)
    while loop.time() - started < lifetime and not await request.is_disconnected():
        async with pool.connection() as connection:
            page = await read_events(connection, workspace_id, run_id, after=cursor)
            status = await current_status(connection, run_id)
        if page.gap:
            yield gap_frame(cursor)
            last_sent = loop.time()
        for event in page.events:
            yield event_frame(event)
            last_sent = loop.time()
        if page.next_cursor != cursor:
            cursor = page.next_cursor
            yield cursor_frame(cursor)
        elif status is not None and status in TERMINAL:
            yield END_FRAME
            return
        if loop.time() - last_sent >= KEEPALIVE_SECONDS:
            yield ": keepalive\n\n"
            last_sent = loop.time()
        if listener is None:
            await asyncio.sleep(POLL_SECONDS)
            continue
        # Waits as the poll did, passing on this run's live text as it arrives.
        async for note in listener.notifies(timeout=POLL_SECONDS):
            frame = live_frame(run_id, cursor, note.payload)
            if frame is not None:
                yield frame
                last_sent = loop.time()


@router.get("/runs/{run_id}/events/stream", include_in_schema=False)
async def stream_events(
    run_id: UUID, request: Request, workspace_id: MemberWorkspace, after: Cursor = 0
) -> StreamingResponse:
    """Authorized before the first byte, so a refusal is a status and not an empty stream."""
    pool = request_pool(request)
    async with pool.connection() as connection:
        await read_events(connection, workspace_id, run_id, after=after, limit=1)
    return StreamingResponse(
        _frames(request, pool, workspace_id, run_id, after),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )
