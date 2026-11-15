"""A run's event stream frames are declared contracts (R-49, XTYP-07). `StreamFrame` names them,
and `StreamCursor` and `StreamGap` are the bodies of the cursor and gap frames, so the browser
parses them with generated parsers. The stream route itself stays out of the OpenAPI paths."""

import json
from datetime import UTC, datetime
from typing import get_args
from uuid import uuid4

import pytest
from pydantic import ValidationError

from autobots.api.event_routes import END_FRAME, cursor_frame, event_frame, gap_frame, live_frame
from autobots.api.openapi_export import openapi_document
from autobots.contracts.primitives import MAX_SAFE_INTEGER
from autobots.contracts.run_workspace import StreamCursor, StreamFrame, StreamFrameName, StreamGap
from autobots.contracts.runs import RunEvent, RunStatusChanged
from autobots.domain.runs import RunStatus


def _fields(frame: str) -> dict[str, str]:
    """A server-sent event's fields, one per line, ended by a blank line."""
    assert frame.endswith("\n\n")
    return dict(line.split(": ", 1) for line in frame[:-2].split("\n"))


def test_the_stream_sends_five_named_frames() -> None:
    assert get_args(StreamFrameName) == ("run", "live", "cursor", "gap", "end")
    assert StreamFrame.model_validate("cursor").root == "cursor"
    with pytest.raises(ValidationError):
        StreamFrame.model_validate("status")


def test_a_cursor_frame_carries_a_stream_cursor() -> None:
    fields = _fields(cursor_frame(7))
    assert fields["event"] == "cursor"
    assert StreamCursor.model_validate_json(fields["data"]) == StreamCursor(cursor=7)
    assert "id" not in fields


def test_a_gap_frame_says_where_retained_events_stopped_filling_the_range() -> None:
    fields = _fields(gap_frame(4))
    assert fields["event"] == "gap"
    assert StreamGap.model_validate_json(fields["data"]) == StreamGap(after=4)


def test_the_end_frame_has_an_empty_body() -> None:
    assert _fields(END_FRAME) == {"event": "end", "data": "{}"}


def test_a_run_frame_carries_the_event_with_its_sequence_as_the_replay_id() -> None:
    event = RunEvent(
        schema_version=1,
        run_id=uuid4(),
        sequence=3,
        causal_ids=[],
        occurred_at=datetime(2026, 11, 15, tzinfo=UTC),
        payload=RunStatusChanged(
            type="run.status_changed", previous=RunStatus.QUEUED, current=RunStatus.RUNNING
        ),
    )
    assert _fields(event_frame(event)) == {
        "id": "3",
        "event": "run",
        "data": event.model_dump_json(),
    }


def test_a_live_frame_has_no_id_so_it_never_moves_the_replay_cursor() -> None:
    run = uuid4()
    note = {"run_id": str(run), "segment": 1, "offset": 0, "text": "Hello"}
    frame = live_frame(run, 2, json.dumps(note))
    assert frame is not None
    fields = _fields(frame)
    assert set(fields) == {"event", "data"}
    assert fields["event"] == "live"
    assert RunEvent.model_validate_json(fields["data"]).sequence == 2


@pytest.mark.parametrize("value", [-1, MAX_SAFE_INTEGER + 1])
def test_a_position_outside_a_safe_integer_is_refused(value: int) -> None:
    with pytest.raises(ValidationError):
        StreamCursor(cursor=value)
    with pytest.raises(ValidationError):
        StreamGap(after=value)


def test_the_frames_are_in_the_contract_and_the_stream_route_is_not() -> None:
    document = openapi_document()
    assert "/v1/runs/{run_id}/events/stream" not in document["paths"]
    schemas = document["components"]["schemas"]
    assert schemas["StreamFrame"]["enum"] == ["run", "live", "cursor", "gap", "end"]
    assert schemas["StreamCursor"]["required"] == ["cursor"]
    assert schemas["StreamGap"]["required"] == ["after"]
