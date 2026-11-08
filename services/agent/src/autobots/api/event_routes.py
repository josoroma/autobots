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

from autobots.adapters.result_stream import CHANNEL as RESULT_CHANNEL
from autobots.api.errors import ApiError
from autobots.api.security import require_internal
from autobots.api.settings_routes import current_workspace
from autobots.application.run_projection import (
    RUN_LIST_SIZE,
    InvalidCursor,
    read_events,
    read_inspector,
    read_run_list,
    read_workspace,
)
from autobots.application.runs import RunNotFound
from autobots.application.tool_uses import list_tool_uses
from autobots.contracts.run_workspace import (
    EventPage,
    RunInspector,
    RunList,
    RunListGroup,
    RunWorkspace,
)
from autobots.contracts.runs import ResultTextDelta, RunEvent, ToolUseList
from autobots.domain.models import ModelProfileId
from autobots.domain.runs import TERMINAL, RunStatus

router = APIRouter(prefix="/v1", dependencies=[Depends(require_internal)])
Workspace = Annotated[UUID, Depends(current_workspace)]
Cursor = Annotated[int, Query(ge=0)]
POLL_SECONDS = 0.5
# A stream ends after a while, and the client reconnects from its cursor.
DEFAULT_STREAM_SECONDS = 60.0
KEEPALIVE_SECONDS = 15.0


def _pool(request: Request) -> Any:
    pool = request.app.state.pool
    if pool is None:
        raise ApiError(503, "service_unavailable", "The database is unavailable.")
    return pool


def _not_found() -> ApiError:
    return ApiError(404, "run_not_found", "That run is not available.")


@router.get("/runs/{run_id}/events", operation_id="listRunEvents", response_model=EventPage)
async def get_events(
    run_id: UUID, request: Request, workspace_id: Workspace, after: Cursor = 0
) -> EventPage:
    async with _pool(request).connection() as connection:
        try:
            return await read_events(connection, workspace_id, run_id, after=after)
        except RunNotFound:
            raise _not_found() from None


@router.get("/runs/{run_id}/workspace", operation_id="getRunWorkspace", response_model=RunWorkspace)
async def get_workspace(run_id: UUID, request: Request, workspace_id: Workspace) -> RunWorkspace:
    async with _pool(request).connection() as connection:
        try:
            return await read_workspace(connection, workspace_id, run_id)
        except RunNotFound:
            raise _not_found() from None


@router.get("/runs", operation_id="listRuns", response_model=RunList)
async def get_runs(
    request: Request,
    workspace_id: Workspace,
    group: RunListGroup = "all",
    q: Annotated[str | None, Query(max_length=200)] = None,
    profile: ModelProfileId | None = None,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=RUN_LIST_SIZE)] = RUN_LIST_SIZE,
) -> RunList:
    """PRD-Studio RN-01 and RN-02: status groups with server counts, filters and a keyset cursor."""
    async with _pool(request).connection() as connection:
        try:
            return await read_run_list(
                connection,
                workspace_id,
                limit,
                group=group,
                query=q,
                profile=profile.value if profile is not None else None,
                cursor=cursor,
            )
        except InvalidCursor:
            raise ApiError(422, "invalid_cursor", "That page cursor is not valid.") from None


@router.get("/runs/{run_id}/inspector", operation_id="getRunInspector", response_model=RunInspector)
async def get_inspector(run_id: UUID, request: Request, workspace_id: Workspace) -> RunInspector:
    async with _pool(request).connection() as connection:
        try:
            return await read_inspector(connection, workspace_id, run_id)
        except RunNotFound:
            raise _not_found() from None


@router.get("/runs/{run_id}/tool-uses", operation_id="listRunToolUses", response_model=ToolUseList)
async def get_tool_uses(
    run_id: UUID,
    request: Request,
    workspace_id: Workspace,
    after: Cursor = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> ToolUseList:
    """PRD-Tool-Catalog TU-07: the run's tree when it's a root, in order. Public fields only."""
    async with _pool(request).connection() as connection:
        found = await list_tool_uses(connection, workspace_id, run_id, after=after, limit=limit)
    if found is None:
        raise _not_found()
    return found


async def _listener(request: Request) -> Any:
    """US-15.24: this stream's own connection, listening for live result text. None when the API
    has no database address, as under a test client; then only durable events flow."""
    settings = getattr(request.app.state, "settings", None)
    url = settings.database_url.get_secret_value() if settings is not None else ""
    if not url:
        return None
    try:
        connection = await psycopg.AsyncConnection.connect(url, autocommit=True)
        await connection.execute(f"listen {RESULT_CHANNEL}")
    except psycopg.Error:
        return None
    return connection


def _live_frame(run_id: UUID, cursor: int, payload: str) -> str | None:
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
    return f"event: live\ndata: {event.model_dump_json()}\n\n"


async def _frames(
    request: Request, pool: Any, workspace_id: UUID, run_id: UUID, after: int
) -> AsyncIterator[str]:
    listener = await _listener(request)
    try:
        async for frame in _durable_and_live(request, pool, workspace_id, run_id, after, listener):
            yield frame
    finally:
        if listener is not None:
            await listener.close()


async def _durable_and_live(
    request: Request, pool: Any, workspace_id: UUID, run_id: UUID, after: int, listener: Any
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
            status_row = await (
                await connection.execute("select status from public.runs where id = %s", (run_id,))
            ).fetchone()
        if page.gap:
            yield f"event: gap\ndata: {json.dumps({'after': cursor})}\n\n"
            last_sent = loop.time()
        for event in page.events:
            yield (f"id: {event.sequence}\nevent: run\ndata: {event.model_dump_json()}\n\n")
            last_sent = loop.time()
        if page.next_cursor != cursor:
            cursor = page.next_cursor
            yield f"event: cursor\ndata: {json.dumps({'cursor': cursor})}\n\n"
        elif status_row is not None and RunStatus(status_row[0]) in TERMINAL:
            yield "event: end\ndata: {}\n\n"
            return
        if loop.time() - last_sent >= KEEPALIVE_SECONDS:
            yield ": keepalive\n\n"
            last_sent = loop.time()
        if listener is None:
            await asyncio.sleep(POLL_SECONDS)
            continue
        # Waits as the poll did, passing on this run's live text as it arrives.
        async for note in listener.notifies(timeout=POLL_SECONDS):
            frame = _live_frame(run_id, cursor, note.payload)
            if frame is not None:
                yield frame
                last_sent = loop.time()


@router.get("/runs/{run_id}/events/stream", include_in_schema=False)
async def stream_events(
    run_id: UUID, request: Request, workspace_id: Workspace, after: Cursor = 0
) -> StreamingResponse:
    """Authorized before the first byte, so a refusal is a status and not an empty stream."""
    pool = _pool(request)
    async with pool.connection() as connection:
        try:
            await read_events(connection, workspace_id, run_id, after=after, limit=1)
        except RunNotFound:
            raise _not_found() from None
    return StreamingResponse(
        _frames(request, pool, workspace_id, run_id, after),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )
