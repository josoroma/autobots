"""Local structured logs, PRD 12.2 and LM-07. Nothing here sends a record off this machine."""

import json
import logging
import os
import re
import sys
from collections.abc import MutableMapping
from datetime import UTC, datetime
from typing import Any, TextIO

_SECRET = re.compile(
    r"sk-or-[\w-]+"
    r"|sk-[A-Za-z0-9_-]{8,}"
    r"|(?i:bearer)\s+[\w.~+/=-]+"
    r"|eyJ[\w-]+\.[\w-]+\.[\w-]*"
    r"|\b(?:postgres(?:ql)?|https?)://[^\s/@]+:[^\s/@]+@\S+"
    r"|\b(?:postgres(?:ql)?)://\S+"
    r"|(?i:(?:password|passwd|token|secret|api[_-]?key|authorization)\s*[=:]\s*)\S+"
)
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
    return _IDENTIFIER.sub(r"\1…", _SECRET.sub("[redacted]", text))


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "at": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "event": redact(record.getMessage()),
        }
        for name, value in getattr(record, "fields", {}).items():
            entry[name] = value if isinstance(value, bool | int | float) else redact(str(value))
        if record.exc_info and record.exc_info[0] is not None:
            # The type only: a message can carry a connection string or a provider's reply.
            entry["error"] = record.exc_info[0].__name__
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
        utils.get_env_var.cache_clear()  # type: ignore[attr-defined]


def remote_tracing_disabled(environ: MutableMapping[str, str]) -> bool:
    return all(environ.get(name) == "false" for name in _TRACING_OFF) and not any(
        environ.get(name) for name in _TRACING_REMOVED
    )
