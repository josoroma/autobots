"""A controlled destination, a file outside the database, so a killed worker can't take it down.

Every attempt is logged. `effects` counts what really happened, once per key when the destination
honors idempotency keys, and once per attempt when it doesn't.
"""
from __future__ import annotations

import json
from pathlib import Path


class Sink:
    def __init__(self, path: Path | str, *, idempotent: bool = False) -> None:
        self.path, self.idempotent = Path(path), idempotent

    def _lines(self) -> list[dict[str, str]]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text().splitlines()]

    def deliver(self, key: str, body: str) -> None:
        with self.path.open('a') as handle:
            handle.write(json.dumps({'key': key, 'body': body}) + '\n')

    def attempts(self) -> int:
        return len(self._lines())

    def effects(self) -> int:
        lines = self._lines()
        return len({line['key'] for line in lines}) if self.idempotent else len(lines)

    def holds(self, key: str) -> bool:
        return any(line['key'] == key for line in self._lines())
