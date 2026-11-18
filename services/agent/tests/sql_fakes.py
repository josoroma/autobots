"""Scripted cursors, connections and a pool that satisfy the SQL boundary's Protocols
(application/sql.py and api/pool.py), for tests' fakes.

`RuledConnection` is the one fake that matches on SQL text: it answers each statement by the first
rule whose fragment it contains and refuses any statement no rule matches, so a reworded or added
query fails its test instead of getting an invented row (refactor plan R-66, PTST-09).
`ScriptedConnection` answers every statement alike, for code whose statements a test doesn't
distinguish.

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


class UnscriptedStatement(AssertionError):
    """A statement no rule of a `RuledConnection` answers."""


class RuledConnection:
    """Answers each statement by the first `(fragment, rows)` rule whose fragment it contains, and
    refuses any other. Every statement is kept with its values, in order. It is autocommit, so
    retention never commits on it (application/retention.py), and it opens as its own context."""

    autocommit = True

    def __init__(self, *rules: tuple[str, Sequence[Row]]) -> None:
        self.rules = list(rules)
        self.statements: list[tuple[str, SqlParams | None]] = []

    async def execute(self, query: str, params: SqlParams | None = None, /) -> ScriptedRows:
        self.statements.append((query, params))
        for fragment, rows in self.rules:
            if fragment in query:
                return ScriptedRows(rows)
        raise UnscriptedStatement(f"no rule answers: {' '.join(query.split())[:300]}")

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[None]:
        yield

    async def commit(self) -> None:
        return None

    async def __aenter__(self) -> "RuledConnection":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None


class RuledPool:
    """A pool that lends one `RuledConnection`."""

    def __init__(self, connection: RuledConnection) -> None:
        self.lent = connection

    async def open(self) -> None:
        return None

    async def close(self) -> None:
        return None

    @asynccontextmanager
    async def connection(self) -> AsyncIterator[RuledConnection]:
        yield self.lent
