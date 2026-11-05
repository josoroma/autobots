"""Redaction, tracing bootstrap and conditions, without a database or a process."""

import asyncio
import io
import json
import logging
from pathlib import Path

import pytest

from autobots.application.operations import (
    Condition,
    QueueCounts,
    disk_condition,
    is_ready,
    queue_condition,
    storage_condition,
)
from autobots.contracts.operations import RetentionSettings
from autobots.operations.logs import (
    configure_logging,
    forbid_remote_tracing,
    log_event,
    redact,
    remote_tracing_disabled,
)


@pytest.mark.parametrize(
    "secret",
    [
        "sk-or-v1-abcdef0123456789",
        "Bearer abc.def-ghi",
        "eyJhbGciOi.eyJzdWIiOiIx.c2lnbmF0dXJl",
        "postgresql://autobots_runtime:hunter2@127.0.0.1:5432/postgres",
        "password=hunter2",
        "api_key: hunter2",
    ],
)
def test_redact_removes_each_secret_shape(secret: str) -> None:
    cleaned = redact(f"before {secret} after")
    assert "hunter2" not in cleaned
    assert secret not in cleaned
    assert cleaned.startswith("before ") and "[redacted]" in cleaned


def test_redact_shortens_an_identifier_to_its_prefix() -> None:
    assert redact("run 11111111-1111-4111-8111-111111111111 ok") == "run 11111111… ok"


def test_log_records_are_json_with_fields_redacted_and_no_exception_text() -> None:
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


def test_low_disk_is_visible_and_stops_admission(tmp_path: Path) -> None:
    low = disk_condition(tmp_path, 2**62)
    assert (low.state, low.code) == ("degraded", "disk_low")
    assert not is_ready([low])
    assert disk_condition(tmp_path, 1).state == "ok"


def test_a_missing_worker_or_queue_problem_does_not_stop_admission() -> None:
    assert is_ready(
        [
            Condition("database", "ok", "database_ready"),
            Condition("worker", "degraded", "worker_absent"),
            Condition("queue", "degraded", "leases_expired"),
        ]
    )
    assert not is_ready([Condition("storage", "unavailable", "storage_unreachable")])


def test_expired_leases_degrade_the_queue() -> None:
    assert queue_condition(QueueCounts(0, 0, 1, 0)).code == "leases_expired"
    assert queue_condition(QueueCounts(3, 1, 0, 9)).state == "ok"


def test_storage_failure_message_stays_out_of_the_condition() -> None:
    class Broken:
        async def ping(self) -> None:
            raise RuntimeError("http://secret-host/storage")

    condition = asyncio.run(storage_condition(Broken()))
    assert condition == Condition("storage", "unavailable", "storage_unreachable")
    assert asyncio.run(storage_condition(None)).code == "storage_not_configured"


def test_keys_cannot_expire_before_the_run_content_they_answer_for() -> None:
    with pytest.raises(ValueError, match="receipt_days"):
        RetentionSettings(run_days=30, receipt_days=7)
    assert RetentionSettings().run_days is None
    assert RetentionSettings(run_days=7, receipt_days=7).receipt_days == 7
