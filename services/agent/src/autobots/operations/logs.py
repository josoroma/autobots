"""Local structured logs, PRD-LangChain-Deep-Agents 12.2 and LM-07. Nothing here sends a record
off this machine.

Conventions for every service log line (R-25, XERR-12):

- Event names are dotted and lower case. A new event takes the PRD-LangChain-Deep-Agents 12.2
  category its condition belongs to, such as `tool.operation.unknown`. A process condition with no
  category takes its component: `worker.*`, `api.*`, `retention.*`, `routine.*`. Existing names
  stay as they are, since the qualification scripts count them (`worker.step_failed`).
- Context keys name what the line is about: `workspace`, `run`, `operation`, `tool`, `version`,
  `routine`, `worker`, and `method` and `route` in the API. The route is the template, never the
  path, which holds whole run IDs. The formatter shortens any identifier.
- A caught exception goes in as `error=error`. The formatter writes `error_fields(error)`, the same
  as for a record's `exc_info`, and never the message or a local, which can carry a connection
  string, a key or a provider's reply.
- Levels follow the audience. ERROR: someone has to look, such as a defect or a failed unattended
  step. WARNING: degraded, tolerated or retrying by itself. INFO: lifecycle.
- A failure that can recur on every pass goes through `Repeated` (`autobots.domain.repetition`),
  which logs its first occurrence and then every Nth, with the count.
- A module that STD-01 keeps from importing this one, such as the tool gateway or the API's error
  handlers, writes the same record with its own logger:
  `logger.log(level, event, extra={"fields": {...}})`.
"""

import json
import logging
import os
import re
import sys
import traceback
from collections import deque
from collections.abc import MutableMapping
from datetime import UTC, datetime
from typing import Any, TextIO

# Defined in the domain, so the run lifecycle uses it without importing this layer (R-33).
# Re-exported for this module's users.
from autobots.domain.repetition import Repeated as Repeated
from autobots.domain.secret_patterns import LOG_SHAPES, mask

# Logs also mask a key inside a word. Shown text doesn't, so "task-specific" stays readable there.
_SHAPES = (*LOG_SHAPES, re.compile(r"sk-or-[\w-]+"), re.compile(r"sk-[A-Za-z0-9_-]{8,}"))
_IDENTIFIER = re.compile(
    r"\b([0-9a-fA-F]{8})-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)

# A distributed trace can't start from any of these once they're set.
_TRACING_OFF = (
    "LANGSMITH_TRACING",
    "LANGSMITH_TRACING_V2",
    "LANGCHAIN_TRACING",
    "LANGCHAIN_TRACING_V2",
)
_TRACING_REMOVED = (
    "LANGSMITH_API_KEY",
    "LANGSMITH_ENDPOINT",
    "LANGSMITH_RUNS_ENDPOINTS",
    "LANGSMITH_OTEL_ENABLED",
    "LANGCHAIN_API_KEY",
    "LANGCHAIN_ENDPOINT",
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
)


def redact(text: str) -> str:
    """Removes what looks like a secret and shortens an identifier to the part an operator needs."""
    return _IDENTIFIER.sub(r"\1…", mask(text, _SHAPES))


# How much of a failure a line keeps: enough to find it, bounded so one line stays short.
CAUSES_KEPT = 4
FRAMES_KEPT = 6


def _qualified_name(error: BaseException) -> str:
    kind = type(error)
    return f"{kind.__module__}.{kind.__qualname__}"


def _cause(error: BaseException) -> BaseException | None:
    """The exception this one was raised from, as Python's own traceback follows the chain."""
    if error.__cause__ is not None:
        return error.__cause__
    return None if error.__suppress_context__ else error.__context__


def _source(filename: str) -> str:
    """Relative to the import root the file came from, so no home or checkout directory shows."""
    roots = [
        root
        for root in (os.path.join(os.path.abspath(entry), "") for entry in sys.path if entry)
        if filename.startswith(root)
    ]
    return filename[len(max(roots, key=len)) :] if roots else os.path.basename(filename)


def error_fields(error: BaseException) -> dict[str, Any]:
    """Where a failure happened and what it came from, without its text (R-25, XERR-01).

    The class name, the module-qualified type, the types of up to CAUSES_KEPT causes, and the last
    FRAMES_KEPT frames of its traceback as path:line:function. Frames are read from code objects,
    so no source line, message or local is ever read.
    """
    causes: list[str] = []
    seen = {id(error)}
    cause = _cause(error)
    while cause is not None and id(cause) not in seen and len(causes) < CAUSES_KEPT:
        seen.add(id(cause))
        causes.append(_qualified_name(cause))
        cause = _cause(cause)
    frames = deque(
        (
            f"{_source(frame.f_code.co_filename)}:{line}:{frame.f_code.co_qualname}"
            for frame, line in traceback.walk_tb(error.__traceback__)
        ),
        maxlen=FRAMES_KEPT,
    )
    fields: dict[str, Any] = {
        "error": type(error).__name__,
        "error_type": _qualified_name(error),
        "frames": list(frames),
    }
    if causes:
        fields["causes"] = causes
    return fields


def _shown(value: Any) -> Any:
    if isinstance(value, bool | int | float):
        return value
    if isinstance(value, list | tuple):
        return [_shown(item) for item in value]
    return redact(str(value))


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "at": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "event": redact(record.getMessage()),
        }
        failures: list[BaseException] = []
        for name, value in getattr(record, "fields", {}).items():
            if isinstance(value, BaseException):
                failures.append(value)
            else:
                entry[name] = _shown(value)
        if record.exc_info and record.exc_info[1] is not None:
            failures.append(record.exc_info[1])
        for failure in failures:
            entry.update({name: _shown(value) for name, value in error_fields(failure).items()})
        return json.dumps(entry, ensure_ascii=False, sort_keys=True)


def configure_logging(stream: TextIO | None = None) -> None:
    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(logging.INFO)
    # uvicorn's own handlers would print a traceback whole, with whatever its message holds.
    for name in ("uvicorn", "uvicorn.error"):
        server = logging.getLogger(name)
        server.handlers[:] = []
        server.propagate = True
    # An access line holds a whole run ID in its path, so it isn't logged at all.
    access = logging.getLogger("uvicorn.access")
    access.handlers[:] = []
    access.propagate = False
    # httpx logs each request URL at info, which is a provider or Storage address and path.
    logging.getLogger("httpx").setLevel(logging.WARNING)


def log_event(logger: logging.Logger, event: str, level: int = logging.INFO, **fields: Any) -> None:
    """One line, by the conventions at the top of this module."""
    logger.log(level, event, extra={"fields": fields})


def forbid_remote_tracing(environ: MutableMapping[str, str]) -> None:
    """Before any agent is built, so an inherited host setting can't reach a hosted collector."""
    for name in _TRACING_OFF:
        environ[name] = "false"
    for name in _TRACING_REMOVED:
        environ.pop(name, None)
    if environ is os.environ:
        # langsmith caches what it read, so a setting seen before this call would otherwise stick.
        try:
            from langsmith import utils
        except ImportError:
            return
        utils.get_env_var.cache_clear()  # type: ignore[attr-defined]  # functools.cache adds cache_clear, which the stubs omit


def remote_tracing_disabled(environ: MutableMapping[str, str]) -> bool:
    return all(environ.get(name) == "false" for name in _TRACING_OFF) and not any(
        environ.get(name) for name in _TRACING_REMOVED
    )
