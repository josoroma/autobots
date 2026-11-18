"""Backup age and restore history, read from the backup folder and off the event loop
(application/backups.py). Moved from test_operations.py and test_final_review.py by module
(refactor plan R-66, PTST-05).
"""

import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from autobots.application import backups
from autobots.application.backups import backup_age_hours, restore_history


def test_a_bad_restore_line_is_skipped_and_the_rest_read(tmp_path: Path) -> None:
    good = {
        "at": "2026-11-06T12:00:00+00:00",
        "result": "passed",
        "checks_passed": 1,
        "checks_total": 1,
    }
    folder = tmp_path / "a"
    folder.mkdir()
    (folder / "restores.jsonl").write_text(
        "not json\n" + json.dumps({"at": "x", "extra": True}) + "\n[1]\n" + json.dumps(good) + "\n"
    )
    binary = tmp_path / "b"
    binary.mkdir()
    (binary / "restores.jsonl").write_bytes(b"\xff\xfe")
    assert restore_history(str(tmp_path)) == [good]


def test_backup_age_reads_the_newest_manifest_and_ignores_damage(tmp_path: Path) -> None:
    now = datetime(2026, 11, 5, 12, tzinfo=UTC)
    assert backup_age_hours("", now) is None
    assert backup_age_hours(str(tmp_path), now) is None
    for name, moment in (
        ("old", "2026-11-01T12:00:00+00:00"),
        ("new", "2026-11-05T09:30:00+00:00"),
    ):
        (tmp_path / name).mkdir()
        (tmp_path / name / "manifest.json").write_text(json.dumps({"created_at": moment}))
    (tmp_path / "bad").mkdir()
    (tmp_path / "bad" / "manifest.json").write_text("not json")
    assert backup_age_hours(str(tmp_path), now) == 2


@pytest.mark.asyncio
async def test_the_backup_files_are_read_off_the_event_loop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DH-06, POPS-04: Local Operations' status route awaits `backup_status`, whose file reads run
    in worker threads."""
    loop_thread: list[int] = []
    read_in: list[int] = []

    def age(directory: str, now: datetime) -> int:
        read_in.append(threading.get_ident())
        return 2

    def history(directory: str) -> list[dict[str, Any]]:
        read_in.append(threading.get_ident())
        return [{"at": "2026-11-05T09:30:00+00:00"}]

    async def status() -> backups.BackupStatus:
        loop_thread.append(threading.get_ident())
        return await backups.backup_status(str(tmp_path), datetime(2026, 11, 5, 12, tzinfo=UTC))

    monkeypatch.setattr(backups, "backup_age_hours", age)
    monkeypatch.setattr(backups, "restore_history", history)
    found = await status()
    assert found == backups.BackupStatus(2, [{"at": "2026-11-05T09:30:00+00:00"}])
    assert len(read_in) == 2 and loop_thread[0] not in read_in
