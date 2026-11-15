"""A run's public events: a page after a cursor, each event as the public contract accepts it."""

import logging
from collections.abc import Mapping
from datetime import datetime
from typing import get_args
from uuid import UUID

from pydantic import ValidationError

from autobots.application.run_projection.summary import require_run
from autobots.application.sql import SqlConnection, all_rows, snapshot
from autobots.contracts.run_workspace import EventPage
from autobots.contracts.runs import RunEvent
from autobots.domain.repetition import Repeated
from autobots.persistence.rows import RunEventRow

logger = logging.getLogger("autobots.runs")
PAGE_SIZE = 200
# The payload types the public stream carries (contracts/runs.py RunEvent).
PUBLIC_EVENT_TYPES = frozenset(
    literal
    for payload in get_args(RunEvent.model_fields["payload"].annotation)
    for literal in get_args(payload.model_fields["type"].annotation)
)
# A stored event that fails is read again by every page that reaches it, so its line is written
# the first time and then every Nth, with the count (autobots.logs conventions).
_NOT_PROJECTED = Repeated()


def project_event(
    run_id: UUID, sequence: int, payload: object, occurred_at: datetime
) -> RunEvent | None:
    """Only what the public contract accepts. Anything else stays out, and the cursor moves on.

    A payload of a public type that fails is logged by its type and sequence, never its content
    (refactor plan R-51, XTYP-03). Any other type, such as a raw framework event, stays out quietly
    (Decision 0017 Q13)."""
    try:
        return RunEvent.model_validate(
            {
                "schema_version": 1,
                "run_id": str(run_id),
                "sequence": sequence,
                "causal_ids": [],
                "occurred_at": occurred_at.isoformat(),
                "payload": payload,
            },
            strict=False,
        )
    except ValidationError:
        kind = payload.get("type") if isinstance(payload, Mapping) else None
        if isinstance(kind, str) and kind in PUBLIC_EVENT_TYPES and _NOT_PROJECTED.failed():
            fields = {
                "run": run_id,
                "type": kind,
                "sequence": sequence,
                "failures": _NOT_PROJECTED.count,
            }
            logger.log(logging.WARNING, "run.event.not_projected", extra={"fields": fields})
        return None


async def read_events(
    connection: SqlConnection,
    workspace_id: UUID,
    run_id: UUID,
    *,
    after: int,
    limit: int = PAGE_SIZE,
) -> EventPage:
    """The run and its page from one snapshot (PRUN-11)."""
    async with snapshot(connection):
        await require_run(connection, workspace_id, run_id)
        rows = await all_rows(
            connection,
            RunEventRow,
            "select sequence, payload, occurred_at from public.run_events "
            "where run_id = %s and sequence > %s order by sequence limit %s",
            (run_id, after, limit),
        )
    events = [
        event
        for event in (
            project_event(run_id, row.sequence, row.payload, row.occurred_at) for row in rows
        )
        if event is not None
    ]
    return EventPage(
        schema_version=1,
        run_id=run_id,
        events=events,
        next_cursor=rows[-1].sequence if rows else after,
        gap=bool(rows) and rows[0].sequence > after + 1,
    )
