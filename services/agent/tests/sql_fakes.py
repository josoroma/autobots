"""Scripted cursors, connections and a pool that satisfy the SQL boundary's Protocols
(application/sql.py and api/pool.py), for tests' fakes.

A row is a tuple, as psycopg returns one, or a mapping by column name for a read the application
builds into a row type by those names. A cursor's rows are all tuples or all mappings.
"""

from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from autobots.application.sql import SqlParams

# What a test scripts for one row.
Row = tuple[Any, ...] | Mapping[str, Any]
# The columns of the approval gate's two reads (application/approvals.py), for tuple answers.
GATE_COLUMNS = ("id", "status", "scope_hash", "expired", "consumed")
RECEIPT_COLUMNS = ("status", "reconciled_at", "failure_code")


@dataclass(frozen=True)
class Column:
    name: str


class ScriptedRows:
    def __init__(self, rows: Sequence[Row] = (), names: Sequence[str] = ()) -> None:
        mapped = [row for row in rows if isinstance(row, Mapping)]
        if mapped and len(mapped) != len(rows):
            raise ValueError("script a cursor's rows all as tuples or all as mappings")
        self.names: tuple[str, ...] = tuple(mapped[0]) if mapped else tuple(names)
        self.rows: list[tuple[Any, ...]] = [
            tuple(row[name] for name in self.names) if isinstance(row, Mapping) else row
            for row in rows
        ]

    @property
    def description(self) -> list[Column] | None:
        return [Column(name) for name in self.names] if self.names else None

    async def fetchone(self) -> tuple[Any, ...] | None:
        return self.rows[0] if self.rows else None

    async def fetchall(self) -> list[tuple[Any, ...]]:
        return list(self.rows)


class ScriptedConnection:
    """A connection whose every statement answers `rows`, none by default. It is autocommit, so
    retention never commits on it (application/retention.py)."""

    autocommit = True

    def __init__(self, rows: Sequence[Row] = ()) -> None:
        self.rows = rows
        self.statements: list[str] = []

    async def execute(self, query: str, _params: SqlParams | None = None, /) -> ScriptedRows:
        self.statements.append(query)
        return ScriptedRows(self.rows)

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[None]:
        yield

    async def commit(self) -> None:
        return None


class LendingPool:
    """A pool that lends one connection, for an app whose routes' reads a test has replaced."""

    def __init__(self, connection: ScriptedConnection | None = None) -> None:
        self.lent = ScriptedConnection() if connection is None else connection

    async def open(self) -> None:
        return None

    async def close(self) -> None:
        return None

    @asynccontextmanager
    async def connection(self) -> AsyncIterator[ScriptedConnection]:
        yield self.lent
