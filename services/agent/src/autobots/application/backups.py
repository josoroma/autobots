"""What the backup directory says about backups and restores, for Local Operations (LM-07).

The readers glob and read files, so the API calls them through `backup_status`, which runs them off
the event loop (DH-06, POPS-04). Only times and counts leave here, never a path.
"""

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

RESTORES_SHOWN = 5
RESTORE_FIELDS = {"at", "result", "checks_passed", "checks_total"}


def backup_age_hours(directory: str, now: datetime) -> int | None:
    """The newest manifest under the backup directory: when it was taken, and nothing else."""
    newest: datetime | None = None
    for path in Path(directory).glob("*/manifest.json") if directory else ():
        try:
            created = datetime.fromisoformat(json.loads(path.read_text())["created_at"])
        except (OSError, ValueError, KeyError):
            continue
        newest = created if newest is None or created > newest else newest
    return None if newest is None else max(int((now - newest).total_seconds() // 3600), 0)


def restore_history(directory: str, limit: int = RESTORES_SHOWN) -> list[dict[str, Any]]:
    """What `local_backup.py` wrote beside each backup, newest first. A bad line is skipped."""
    found: list[dict[str, Any]] = []
    for path in Path(directory).glob("*/restores.jsonl") if directory else ():
        try:
            lines = path.read_text().splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for line in lines:
            try:
                item = json.loads(line)
            except ValueError:
                continue
            if isinstance(item, dict) and set(item) == RESTORE_FIELDS:
                found.append(item)
    return sorted(found, key=lambda item: str(item.get("at")), reverse=True)[:limit]


@dataclass(frozen=True)
class BackupStatus:
    age_hours: int | None
    restores: list[dict[str, Any]]


async def backup_status(directory: str, now: datetime) -> BackupStatus:
    """Both readers, each in a worker thread, so a slow disk never holds the event loop."""
    age = await asyncio.to_thread(backup_age_hours, directory, now)
    restores = await asyncio.to_thread(restore_history, directory)
    return BackupStatus(age, restores)
