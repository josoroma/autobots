"""The spend ledger that holds every paid call outside a run, on disk and across runs (Decision
0009).

A call is written down at its worst case before it is sent, so a crash can't lose track of spend,
and an outcome that isn't known stays charged at that price. scripts/paid_run.py copies
`LedgerState`, `LedgerEntry` and `Ledger`'s methods by shape (tests/harness/test_paid_run.py).
"""

import fcntl
import json
import os
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, TypedDict


class CapReached(Exception):
    """The next call's worst case wouldn't fit."""


# What a ledger entry records. scripts/persistent_install.py settles its goals with the last two.
LedgerState = Literal[
    "reserved", "settled", "usage_unreported", "uncertain", "not_started", "run_not_finished"
]


class LedgerEntry(TypedDict):
    """One held call, as stored. A dict, as scripts/persistent_install.py reads its state."""

    label: str
    worst_case: int
    reported: int | None
    state: LedgerState
    at: str


@dataclass
class Charge:
    """What a held call settles to: the reply's reported charge, unless its outcome is unknown."""

    reported: int | None = None
    known: bool = True


class Ledger:
    """On disk and across runs, so a rerun against the same file can't spend its cap twice.

    A missing file starts empty.
    """

    def __init__(self, path: Path, cap_micro_usd: int) -> None:
        self.path = path
        self.cap = cap_micro_usd
        self.entries: list[LedgerEntry] = (
            json.loads(path.read_text())["entries"] if path.exists() else []
        )

    def committed(self) -> int:
        """Reported charges where known, and the worst case for everything else."""
        return sum(
            entry["reported"] if entry["reported"] is not None else entry["worst_case"]
            for entry in self.entries
        )

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        body = {"cap_micro_usd": self.cap, "committed": self.committed(), "entries": self.entries}
        with temporary.open("w") as handle:
            handle.write(json.dumps(body, indent=2))
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(self.path)

    @contextmanager
    def _locked(self) -> Iterator[None]:
        """Reads the file again under a lock, so a second process's spend is counted, not lost."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.with_suffix(".lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if self.path.exists():
                self.entries = json.loads(self.path.read_text())["entries"]
            yield

    def reserve(self, label: str, worst_case: int) -> LedgerEntry:
        with self._locked():
            if self.committed() + worst_case > self.cap:
                raise CapReached(label)
            entry: LedgerEntry = {
                "label": label,
                "worst_case": worst_case,
                "reported": None,
                "state": "reserved",
                "at": datetime.now(UTC).isoformat(),
            }
            self.entries.append(entry)
            self._save()
            return entry

    def settle(self, entry: LedgerEntry, reported: int | None, state: LedgerState) -> None:
        with self._locked():
            for held in self.entries:
                if held["label"] == entry["label"] and held["at"] == entry["at"]:
                    held["reported"] = reported
                    held["state"] = state
            self._save()
        entry["reported"] = reported
        entry["state"] = state

    @asynccontextmanager
    async def charge(self, label: str, worst_case: int) -> AsyncIterator[Charge]:
        """Holds one call at its worst case while it runs (Decision 0009, POPS-06).

        Anything that stops it, cancellation included, settles it as uncertain and propagates
        (DH-06). Otherwise it settles from what the caller recorded on the yielded `Charge`.
        """
        entry = self.reserve(label, worst_case)
        charge = Charge()
        try:
            yield charge
        except BaseException:
            # Sent, and its outcome isn't known. It stays charged at the worst case.
            self.settle(entry, None, "uncertain")
            raise
        if not charge.known:
            self.settle(entry, None, "uncertain")
        elif charge.reported is None:
            self.settle(entry, None, "usage_unreported")
        else:
            self.settle(entry, charge.reported, "settled")
