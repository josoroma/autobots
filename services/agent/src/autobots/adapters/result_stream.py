"""US-15.24, PRD-Studio ST-01 and Decision 0022 D4: a run's result text while it's written.

Every worker model call streams (Decision 0022, streaming decision). While it does, this tap reads
the `save_artifact` calls taking shape, and once a call's path is known to be under `outputs/`, it
passes on that call's `content` as it grows. Nothing else is read: no reasoning, no other argument,
no other tool and no framework value. Text is coalesced and sent with Postgres NOTIFY, which stores
nothing, so durable events and the stored artifact stay the only record. A failure here never stops
the run.
"""

import json
import logging
import time
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import psycopg

from autobots.logs import log_event

logger = logging.getLogger("autobots.worker")
CHANNEL = "autobots_result_text"
RESULT_TOOL = "save_artifact"
RESULT_PREFIX = "outputs/"
# Coalescing: at most one notification per interval while text grows, and every piece small enough
# for NOTIFY's 8000-byte payload whatever the characters.
FLUSH_SECONDS = 0.15
PIECE_CHARACTERS = 1500

_TAP: ContextVar["ResultTap | None"] = ContextVar("autobots_result_tap", default=None)


def current_tap() -> "ResultTap | None":
    return _TAP.get()


def use_tap(tap: "ResultTap | None") -> Any:
    """Sets the tap for this context. Reset with `reset_tap(token)`."""
    return _TAP.set(tap)


def reset_tap(token: Any) -> None:
    _TAP.reset(token)


# A reader for one JSON object that is still arriving. It tolerates text that hasn't finished
# arriving, not malformed text: that raises ValueError, which ends that call's live text.


def _skip_ws(text: str, index: int) -> int:
    while index < len(text) and text[index] in " \t\r\n":
        index += 1
    return index


def _read_string(text: str, index: int) -> tuple[str, int, bool]:
    """From an opening quote: the decoded text so far, where it ended, and whether it closed.
    An escape that hasn't fully arrived, or half a surrogate pair, waits for the next piece."""
    start = index + 1
    position = start
    safe = start
    while position < len(text):
        character = text[position]
        if character == '"':
            return json.loads(text[index : position + 1]), position + 1, True
        if character == "\\":
            if position + 1 >= len(text):
                break
            if text[position + 1] == "u":
                if position + 6 > len(text):
                    break
                code = int(text[position + 2 : position + 6], 16)
                if 0xD800 <= code <= 0xDBFF and text[position + 6 : position + 8] in (
                    "",
                    "\\",
                    "\\u",
                ):
                    # A high surrogate needs its low half before it can be decoded.
                    if position + 12 > len(text):
                        break
                    position += 12
                else:
                    position += 6
            else:
                position += 2
            safe = position
            continue
        position += 1
        safe = position
    return json.loads('"' + text[start:safe] + '"'), len(text), False


def _skip_value(text: str, index: int) -> int:
    """Past one non-string value, or the end of the text if it hasn't finished arriving."""
    depth = 0
    position = index
    while position < len(text):
        character = text[position]
        if character == '"':
            _, position, closed = _read_string(text, position)
            if not closed:
                return len(text)
            continue
        if character in "{[":
            depth += 1
        elif character in "}]":
            if depth == 0:
                return position
            depth -= 1
        elif character == "," and depth == 0:
            return position
        position += 1
    return len(text)


def partial_object(text: str) -> tuple[dict[str, str], tuple[str, str] | None]:
    """The object's finished string fields, and the one string still arriving, with its text."""
    fields: dict[str, str] = {}
    index = _skip_ws(text, 0)
    if index >= len(text) or text[index] != "{":
        return fields, None
    index += 1
    while True:
        index = _skip_ws(text, index)
        if index >= len(text) or text[index] == "}":
            return fields, None
        if text[index] == ",":
            index += 1
            continue
        if text[index] != '"':
            return fields, None
        key, index, closed = _read_string(text, index)
        if not closed:
            return fields, None
        index = _skip_ws(text, index)
        if index >= len(text) or text[index] != ":":
            return fields, None
        index = _skip_ws(text, index + 1)
        if index >= len(text):
            return fields, None
        if text[index] == '"':
            value, index, closed = _read_string(text, index)
            if not closed:
                return fields, (key, value)
            fields[key] = value
        else:
            index = _skip_value(text, index)
            if index >= len(text):
                return fields, None


@dataclass
class _Call:
    name: str | None = None
    arguments: str = ""
    segment: int | None = None
    sent: int = 0
    changed: bool = False
    unreadable: bool = False


@dataclass
class ResultTap:
    """One per run in a worker. `notify` sends one JSON payload; the default opens its own
    connection to `database_url` on first use, separate from the loop's own."""

    run_id: UUID
    database_url: str = ""
    notify: Any = None
    segments: int = 0
    _calls: dict[int, _Call] = field(default_factory=dict)
    _last_flush: float = 0.0
    _connection: Any = None
    _broken: bool = False

    def begin(self) -> None:
        """A model call starts: tool-call indexes count from zero again."""
        self._calls = {}

    async def feed(self, chunk: Any) -> None:
        if self._broken:
            return
        try:
            for piece in getattr(chunk, "tool_call_chunks", None) or ():
                index = int(piece.get("index") or 0)
                call = self._calls.setdefault(index, _Call())
                if piece.get("name"):
                    call.name = str(piece["name"])
                if piece.get("args"):
                    call.arguments += str(piece["args"])
                    call.changed = True
            if time.monotonic() - self._last_flush >= FLUSH_SECONDS:
                await self.flush()
        except Exception as error:  # noqa: BLE001 - live text is a courtesy, so a tap failure never stops the run (Decision 0022 D4)
            self._stop(error)

    async def finish(self) -> None:
        try:
            if not self._broken:
                await self.flush()
        except Exception as error:  # noqa: BLE001 - live text is a courtesy, so a tap failure never stops the run (Decision 0022 D4)
            self._stop(error)
        finally:
            self._calls = {}

    def _stop(self, error: Exception) -> None:
        """PADP-01: live text is a courtesy, so a tap failure ends it and never reaches the call,
        where it would read as a failed stream and stop a paid run."""
        self._broken = True
        log_event(logger, "result_text.unavailable", logging.WARNING, error=error)

    async def flush(self) -> None:
        self._last_flush = time.monotonic()
        for call in self._calls.values():
            if call.name != RESULT_TOOL or call.unreadable or not call.changed:
                continue
            call.changed = False
            try:
                fields, growing = partial_object(call.arguments)
            except ValueError as error:
                # Malformed, not unfinished. The assembled reply still settles this call, as an
                # invalid tool call, so only its live text ends here.
                call.unreadable = True
                log_event(
                    logger,
                    "result_text.unavailable",
                    logging.WARNING,
                    error=error,
                    reason="malformed_arguments",
                )
                continue
            path = fields.get("path")
            if path is None or not path.startswith(RESULT_PREFIX):
                continue
            content = fields.get("content")
            if content is None and growing is not None and growing[0] == "content":
                content = growing[1]
            if not content or len(content) <= call.sent:
                continue
            if call.segment is None:
                self.segments += 1
                call.segment = self.segments
            new = content[call.sent :]
            for start in range(0, len(new), PIECE_CHARACTERS):
                piece = new[start : start + PIECE_CHARACTERS]
                await self._send(
                    {
                        "run_id": str(self.run_id),
                        "segment": call.segment,
                        "offset": call.sent + start,
                        "text": piece,
                    }
                )
            call.sent = len(content)

    async def _send(self, payload: dict[str, Any]) -> None:
        if self._broken:
            return
        try:
            if self.notify is not None:
                await self.notify(payload)
                return
            if self._connection is None:
                self._connection = await psycopg.AsyncConnection.connect(
                    self.database_url, autocommit=True
                )
            await self._connection.execute(
                "select pg_notify(%s, %s)", (CHANNEL, json.dumps(payload))
            )
        except Exception as error:  # noqa: BLE001 - live text is a courtesy, so a send failure never stops the run (Decision 0022 D4)
            # Live text is a courtesy. The stored artifact is the record, so the run goes on.
            self._broken = True
            log_event(logger, "result_text.unavailable", logging.WARNING, error=error)

    async def close(self) -> None:
        connection, self._connection = self._connection, None
        if connection is None:
            return
        try:
            await connection.close()
        except Exception as error:  # noqa: BLE001 - in the run's cleanup, a close failure must not replace the run's outcome
            # Called from the run's own cleanup, where a failure would replace the run's outcome.
            log_event(logger, "result_text.close_failed", logging.WARNING, error=error)
