"""The redacting JSON log format, and where tracing is turned off (autobots/logs.py). A test that
configures logging restores it afterwards (conftest.restore_logging, PTST-07). Moved from
test_operations.py and test_final_review.py by module (refactor plan R-66, PTST-05).
"""

import io
import json
import logging
import logging.config
from pathlib import Path
from typing import Any

import pytest
import uvicorn

from autobots.logs import (
    CAUSES_KEPT,
    FRAMES_KEPT,
    JsonFormatter,
    configure_logging,
    error_fields,
    forbid_remote_tracing,
    log_event,
    redact,
    remote_tracing_disabled,
)


def test_uvicorns_own_loggers_go_through_the_redacting_format(restore_logging: None) -> None:
    # What uvicorn itself installs before the app loads: without the fix, this keeps its handler.
    logging.config.dictConfig(uvicorn.config.LOGGING_CONFIG)
    server = logging.getLogger("uvicorn.error")
    assert logging.getLogger("uvicorn").handlers != []
    stream = io.StringIO()
    configure_logging(stream)
    assert logging.getLogger("uvicorn").handlers == []
    assert logging.getLogger("uvicorn").propagate is True
    assert server.propagate is True
    # The access logger's own check, which decides whether a line is logged at all.
    assert logging.getLogger("uvicorn.access").hasHandlers() is False
    try:
        raise RuntimeError("postgresql://user:hunter2@host/db")
    except RuntimeError:
        server.exception("Exception in ASGI application")
    line = stream.getvalue()
    assert "hunter2" not in line
    assert json.loads(line.splitlines()[-1])["error"] == "RuntimeError"
    assert isinstance(logging.getLogger().handlers[0].formatter, JsonFormatter)


def _lines(stream: io.StringIO) -> list[dict[str, Any]]:
    return [json.loads(line) for line in stream.getvalue().splitlines()]


@pytest.mark.parametrize(
    "secret",
    [
        "sk-or-v1-abcdef0123456789",
        "Bearer abc.def-ghi",
        "eyJhbGciOi.eyJzdWIiOiIx.c2lnbmF0dXJl",
        "postgresql://autobots_runtime:hunter2@127.0.0.1:5432/postgres",
        "password=hunter2",
        "api_key: hunter2",
        "tvly-fixtureKEY0123hunter2",
        "jina_fixture0123hunter2",
        "ghp_fixture0123456789abcdefhunter2",
        "github_pat_fixture_0123456789abcdefhunter2",
    ],
)
def test_redact_removes_each_secret_shape(secret: str) -> None:
    cleaned = redact(f"before {secret} after")
    assert "hunter2" not in cleaned
    assert secret not in cleaned
    assert cleaned.startswith("before ") and "[redacted]" in cleaned


def test_redact_shortens_an_identifier_to_its_prefix() -> None:
    assert redact("run 11111111-1111-4111-8111-111111111111 ok") == "run 11111111… ok"


def test_log_records_are_json_with_fields_redacted_and_no_exception_text(
    restore_logging: None,
) -> None:
    stream = io.StringIO()
    configure_logging(stream)
    logger = logging.getLogger("autobots.test")
    log_event(logger, "worker.started", worker="11111111-1111-4111-8111-111111111111", count=2)
    try:
        raise RuntimeError("postgresql://user:hunter2@host/db")
    except RuntimeError:
        logger.exception("failed sk-or-v1-abcdef0123")
    first, second = (json.loads(line) for line in stream.getvalue().splitlines())
    assert first["event"] == "worker.started"
    assert first["worker"] == "11111111…"
    assert first["count"] == 2
    assert second["error"] == "RuntimeError"
    assert "hunter2" not in stream.getvalue()
    assert "sk-or-v1" not in stream.getvalue()


def _raise_from_a_hidden_cause() -> None:
    password = "hunter2"  # A local, which no line may show.
    try:
        raise ValueError(f"postgresql://user:{password}@host/db")
    except ValueError as cause:
        raise KeyError("sk-or-v1-abcdef0123 planted") from cause


def test_a_failure_line_locates_the_failure_without_its_text_or_locals(
    restore_logging: None,
) -> None:
    """R-25, XERR-01: the qualified type, causes and last frames, never a message or a local."""
    stream = io.StringIO()
    configure_logging(stream)
    logger = logging.getLogger("autobots.test")
    try:
        _raise_from_a_hidden_cause()
    except KeyError as error:
        log_event(logger, "worker.step_failed", logging.ERROR, error=error)
        logger.exception("Exception in ASGI application")
    lines = _lines(stream)
    assert [line["event"] for line in lines] == [
        "worker.step_failed",
        "Exception in ASGI application",
    ]
    for line in lines:
        assert line["error"] == "KeyError"
        assert line["error_type"] == "builtins.KeyError"
        assert line["causes"] == ["builtins.ValueError"]
        frames = line["frames"]
        assert isinstance(frames, list) and 0 < len(frames) <= FRAMES_KEPT
        path, number, function = frames[-1].split(":")
        assert path.endswith("test_logs.py") and not path.startswith("/")
        assert int(number) > 0
        assert function == "_raise_from_a_hidden_cause"
    written = stream.getvalue()
    assert "hunter2" not in written
    assert "sk-or-v1" not in written
    assert "planted" not in written
    assert str(Path.home()) not in written


def test_a_cause_chain_is_bounded_and_ends_where_python_ends_it() -> None:
    error: BaseException = RuntimeError("first")
    for _ in range(CAUSES_KEPT + 3):
        try:
            raise ValueError("next") from error
        except ValueError as raised:
            error = raised
    assert error_fields(error)["causes"] == ["builtins.ValueError"] * CAUSES_KEPT
    looped = ValueError("a")
    looped.__context__ = KeyError("b")
    looped.__context__.__context__ = looped
    assert error_fields(looped)["causes"] == ["builtins.KeyError"]
    try:
        try:
            raise ValueError("hidden")
        except ValueError:
            raise KeyError("shown") from None
    except KeyError as suppressed:
        assert "causes" not in error_fields(suppressed)
    assert error_fields(KeyError("never raised"))["frames"] == []


def test_inherited_tracing_is_turned_off_and_its_key_is_dropped() -> None:
    environ = {
        "LANGSMITH_TRACING": "true",
        "LANGCHAIN_TRACING_V2": "true",
        "LANGSMITH_API_KEY": "lsv2-planted",
        "LANGSMITH_ENDPOINT": "https://collector.example.invalid",
        "OTEL_EXPORTER_OTLP_ENDPOINT": "https://collector.example.invalid",
        "PATH": "/usr/bin",
    }
    assert not remote_tracing_disabled(environ)
    forbid_remote_tracing(environ)
    assert remote_tracing_disabled(environ)
    assert environ["LANGSMITH_TRACING"] == "false"
    assert "LANGSMITH_API_KEY" not in environ
    assert "OTEL_EXPORTER_OTLP_ENDPOINT" not in environ
    assert environ["PATH"] == "/usr/bin"


def test_langsmith_itself_reads_tracing_as_off(monkeypatch: pytest.MonkeyPatch) -> None:
    utils = pytest.importorskip("langsmith.utils")
    environ: dict[str, str] = {"LANGSMITH_TRACING": "true"}
    forbid_remote_tracing(environ)
    for name, value in environ.items():
        monkeypatch.setenv(name, value)
    utils.get_env_var.cache_clear()
    assert not utils.tracing_is_enabled()
