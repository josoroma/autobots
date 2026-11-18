"""Redaction, tracing bootstrap and conditions, without a database or a process."""

import io
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from autobots.application import retention
from autobots.application.operations import (
    REQUIRED_COLUMNS,
    Condition,
    QueueCounts,
    database_conditions,
    disk_condition,
    is_ready,
    queue_condition,
    storage_condition,
)
from autobots.application.sql import SqlParams
from autobots.contracts.operations import RetentionSettings
from autobots.domain.repetition import Repeated
from autobots.logs import (
    configure_logging,
)
from autobots.operations import worker
from sql_fakes import RuledConnection, RuledPool, ScriptedConnection, ScriptedRows

WORKSPACE = UUID("a0000000-0000-4000-8000-000000000001")


def _lines(stream: io.StringIO) -> list[dict[str, Any]]:
    return [json.loads(line) for line in stream.getvalue().splitlines()]


def test_a_repeating_failure_is_logged_first_and_then_every_nth_time() -> None:
    repeats = Repeated(every=3)
    assert [repeats.failed() for _ in range(7)] == [True, False, True, False, False, True, False]
    assert repeats.count == 7
    repeats.cleared()
    assert repeats.failed() is True


@pytest.mark.asyncio
async def test_a_failed_worker_step_says_where_it_failed(restore_logging: None) -> None:
    stream = io.StringIO()
    configure_logging(stream)

    async def broken(_: object) -> bool:
        reply: dict[str, bool] = {}
        return reply["sk-or-v1-abcdef0123"]

    async def working(_: object) -> bool:
        return False

    async def step() -> bool:
        return await worker.both(broken, working)(ScriptedConnection())

    assert await step() is False
    [line] = _lines(stream)
    assert (line["event"], line["level"], line["error_type"]) == (
        "worker.step_failed",
        "error",
        "builtins.KeyError",
    )
    assert line["frames"][-1].endswith(
        ":test_a_failed_worker_step_says_where_it_failed.<locals>.broken"
    )
    assert "sk-or-v1" not in stream.getvalue()


@pytest.mark.asyncio
async def test_a_failed_retention_pass_names_its_workspace(
    monkeypatch: pytest.MonkeyPatch, restore_logging: None
) -> None:
    stream = io.StringIO()
    configure_logging(stream)

    async def broken(_connection: object, _store: object, _workspace: UUID) -> None:
        raise KeyError("password=hunter2")

    class Connection(ScriptedConnection):
        async def execute(self, _query: str, _params: SqlParams | None = None, /) -> ScriptedRows:
            return ScriptedRows([(WORKSPACE,)])

    monkeypatch.setattr(retention, "apply_retention", broken)
    await retention.apply_all(Connection(), None)
    [line] = _lines(stream)
    assert (line["event"], line["workspace"], line["error_type"]) == (
        "retention.failed",
        "a0000000…",
        "builtins.KeyError",
    )
    assert "hunter2" not in stream.getvalue()


@pytest.mark.asyncio
async def test_bytes_storage_keeps_are_counted_with_one_warning_per_pass(
    restore_logging: None,
) -> None:
    """XERR-11: the bytes wait for the next pass, as before, and the cause is now kept once."""
    stream = io.StringIO()
    configure_logging(stream)

    class Connection(ScriptedConnection):
        async def execute(self, query: str, _params: SqlParams | None = None, /) -> ScriptedRows:
            if "from public.artifacts" in query:
                return ScriptedRows([(1, "a/one"), (2, "a/two"), (3, "a/three")])
            return ScriptedRows()

    class Storage:
        async def remove(self, _path: str) -> None:
            raise ConnectionError("http://user:hunter2@storage.invalid")

    now = datetime(2026, 11, 14, tzinfo=UTC)
    report = await retention.apply_retention(Connection(), Storage(), WORKSPACE, now)
    assert (report.objects_removed, report.objects_pending) == (0, 3)
    kept = [line for line in _lines(stream) if line["event"] == "retention.object_kept"]
    assert len(kept) == 1
    assert (kept[0]["level"], kept[0]["workspace"], kept[0]["error_type"]) == (
        "warning",
        "a0000000…",
        "builtins.ConnectionError",
    )
    assert "hunter2" not in stream.getvalue()


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


@pytest.mark.asyncio
async def test_storage_failure_message_stays_out_of_the_condition() -> None:
    class Broken:
        async def ping(self) -> None:
            raise RuntimeError("http://secret-host/storage")

    condition = await storage_condition(Broken())
    assert condition == Condition("storage", "unavailable", "storage_unreachable")
    assert (await storage_condition(None)).code == "storage_not_configured"


def test_keys_cannot_expire_before_the_run_content_they_answer_for() -> None:
    with pytest.raises(ValueError, match="receipt_days"):
        RetentionSettings(run_days=30, receipt_days=7)
    assert RetentionSettings().run_days is None
    with pytest.raises(ValueError, match="needs run_days"):
        RetentionSettings(receipt_days=1)
    assert RetentionSettings(run_days=7, receipt_days=7).receipt_days == 7


@pytest.mark.asyncio
async def test_a_missing_column_reads_as_schema_behind() -> None:
    """A column-only migration used to leave Operations reading ready on a stale database. Each of
    the probe's reads is scripted, and any other statement fails the test (PTST-09). Found by
    US-11.12's review, filed in test_final_review.py until refactor plan R-66."""
    connection = RuledConnection(
        ("pg_attribute", [(1,)]),
        ("where to_regclass(r) is null", [(0,)]),
        # No counting function, so the required objects alone decide the schema.
        ("to_regprocedure", [(0,)]),
        # A row, so a restore hold is arranged, as the fake this replaces arranged it unasserted.
        ("installation_holds", [()]),
        ("adapter_qualifications", [(0,)]),
    )
    conditions = await database_conditions(RuledPool(connection))
    assert [condition.code for condition in conditions] == [
        "database_ready",
        "schema_behind",
        "restore_hold",
        "adapter_qualified",
    ]
    assert REQUIRED_COLUMNS
