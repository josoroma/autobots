"""The receipt-guarded create and new-version sequence the product services share (PPRD-08,
refactor plan R-63). SQL migrations own the tables; each service keeps its own statements, rows and
views, and these helpers only take the steps every one of them repeated.

`receipted` opens the transaction, takes the key's advisory lock and reads its first result, through
`runs.Idempotent`, which builds each receipt's scope, lock key and fingerprint
(tests/test_persisted_documents.py pins all three for every writer). `next_version` locks a
versioned row, checks the version its caller expected and names the next; `set_latest` records it
once the caller has inserted that version, in that order.
"""

from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Literal, get_args
from uuid import UUID

from psycopg import sql

from autobots.application.runs import Idempotent
from autobots.application.sql import SqlConnection
from autobots.contracts.persisted import StoredReceipt


@dataclass(frozen=True)
class Receipt[T: StoredReceipt]:
    """The first result under a key, or None, and how to store this one's."""

    prior: T | None
    _connection: SqlConnection
    _command: Idempotent

    async def store(self, result: T) -> None:
        await self._command.store(self._connection, result)


@asynccontextmanager
async def receipted[T: StoredReceipt](
    connection: SqlConnection, command: Idempotent, kind: type[T]
) -> AsyncIterator[Receipt[T]]:
    """One transaction under the key's advisory lock. A concurrent duplicate waits, then reads
    the first result as `kind`; other content under the key raises IdempotencyConflict."""
    async with connection.transaction():
        yield Receipt(await command.replayed(connection, kind), connection, command)


# The parents whose rows count their versions. Each name is composed as an identifier, never as
# text a caller passed.
Versioned = Literal["experts", "routines", "workflows"]
# A removed routine takes no new version (Decision 0026 C7).
_LIVE: Mapping[Versioned, str] = {"routines": " and removed_at is null"}


def _composed(table: Versioned, template: str) -> str:
    return (
        sql.SQL(template)
        .format(table=sql.Identifier("public", table), live=sql.SQL(_LIVE.get(table, "")))
        .as_string()
    )


_LOCK = {
    table: _composed(
        table,
        "select latest_version from {table} where id = %s and workspace_id = %s{live} for update",
    )
    for table in get_args(Versioned)
}
_SET_LATEST = {
    table: _composed(table, "update {table} set latest_version = %s where id = %s")
    for table in get_args(Versioned)
}


class VersionedRowMissing(LookupError):
    """No row of this workspace has that id, or it was removed."""


class ExpectedVersionStale(Exception):
    """The row's latest version isn't the one its caller expected."""


async def next_version(
    connection: SqlConnection, table: Versioned, row_id: UUID, workspace_id: UUID, expected: int
) -> int:
    """Locks the row for the caller's transaction and returns the version after `expected`."""
    row = await (await connection.execute(_LOCK[table], (row_id, workspace_id))).fetchone()
    if row is None:
        raise VersionedRowMissing(table)
    if row[0] != expected:
        raise ExpectedVersionStale(table)
    return expected + 1


async def set_latest(
    connection: SqlConnection, table: Versioned, row_id: UUID, version: int
) -> None:
    await connection.execute(_SET_LATEST[table], (version, row_id))
