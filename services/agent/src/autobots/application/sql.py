"""What the application needs of a database connection, typed without importing psycopg (refactor
plan R-54, XTYP-04, PPRD-12, PRUN-12 and PTOL-13). SQL migrations own the schema.

A psycopg `AsyncConnection` satisfies `SqlConnection`, and so does a test's fake. A row is a tuple.
A read of three or more columns, or a row that leaves its function, is a frozen dataclass from
`persistence/rows.py`, built by column name from the cursor's description, as psycopg's `class_row`
builds one: a missing, extra or duplicate name raises. Each read maps its row explicitly, so a row
never becomes a response by itself.
"""

from collections.abc import AsyncIterator, Collection, Mapping, Sequence
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any, Protocol

type SqlParams = Sequence[object] | Mapping[str, object]
# Postgres takes these only as the first statement of a transaction (PRUN-11).
SNAPSHOT = "set transaction isolation level repeatable read, read only"


class SqlColumn(Protocol):
    @property
    def name(self) -> str: ...


class SqlCursor(Protocol):
    # A tuple's columns are whatever its statement selects, so they stay untyped here.
    @property
    def description(self) -> Sequence[SqlColumn] | None: ...

    async def fetchone(self) -> tuple[Any, ...] | None: ...

    async def fetchall(self) -> list[tuple[Any, ...]]: ...


class SqlConnection(Protocol):
    """The worker's or the API's psycopg connection, as far as the application uses one."""

    async def execute(self, query: str, params: SqlParams | None = None, /) -> SqlCursor: ...

    def transaction(self) -> AbstractAsyncContextManager[object]: ...


class SqlPool(Protocol):
    """A pool that lends connections, as the API's does (api/pool.py)."""

    def connection(self) -> AbstractAsyncContextManager[SqlConnection]: ...


class CommittingConnection(SqlConnection, Protocol):
    """A connection whose holder commits between steps, as retention does on the API's pool."""

    @property
    def autocommit(self) -> bool: ...

    async def commit(self) -> None: ...


class RowNotFound(LookupError):
    """A statement that always finds a row found none: a defect, so a 500. A row a person asked for
    keeps its own refusal and status instead. Its text is the statement, never a value."""


class RowShapeMismatch(TypeError):
    """A row's columns don't name its row type's fields one to one."""


class UnknownStoredValue(ValueError):
    """A stored value outside its vocabulary, such as a status a newer release wrote. It raises
    where the row is read, instead of reaching a client, as an unknown run status does."""


def stored[T: str](vocabulary: Collection[T], value: str) -> T:
    """A stored text value as its vocabulary's type, converted once where its row is read. A domain
    enum converts itself, as `RunStatus(row.status)`; this is for a contract's Literal, whose
    members a typed tuple names (refactor plan R-54, XTYP-05)."""
    for member in vocabulary:
        if member == value:
            return member
    raise UnknownStoredValue(value)


def _statement(query: str) -> str:
    return " ".join(query.split())[:200]


async def _execute(connection: SqlConnection, query: str, params: SqlParams | None) -> SqlCursor:
    """Without parameters the statement is sent alone, as each call site always sent it."""
    if params is None:
        return await connection.execute(query)
    return await connection.execute(query, params)


async def one(
    connection: SqlConnection, query: str, params: SqlParams | None = None
) -> tuple[Any, ...]:
    """The first row of a statement that always finds one, such as an aggregate or a returning
    write. None raises `RowNotFound` rather than being subscripted."""
    row = await (await _execute(connection, query, params)).fetchone()
    if row is None:
        raise RowNotFound(_statement(query))
    return row


def _names(cursor: SqlCursor, kind: type[object]) -> tuple[str, ...]:
    described = cursor.description
    names = tuple(column.name for column in described or ())
    if not names or len(set(names)) != len(names):
        raise RowShapeMismatch(f"{kind.__qualname__}: columns {names}")
    return names


def _built[R](kind: type[R], names: tuple[str, ...], values: tuple[Any, ...]) -> R:
    try:
        return kind(**dict(zip(names, values, strict=True)))
    except TypeError as error:
        raise RowShapeMismatch(f"{kind.__qualname__}: columns {names}") from error


async def optional_row[R](
    connection: SqlConnection, kind: type[R], query: str, params: SqlParams | None = None
) -> R | None:
    """The first row as `kind`, or None when there is none."""
    cursor = await _execute(connection, query, params)
    values = await cursor.fetchone()
    return None if values is None else _built(kind, _names(cursor, kind), values)


async def required_row[R](
    connection: SqlConnection, kind: type[R], query: str, params: SqlParams | None = None
) -> R:
    """The first row as `kind`, of a statement that always finds one, as `one` reads it."""
    found = await optional_row(connection, kind, query, params)
    if found is None:
        raise RowNotFound(_statement(query))
    return found


async def all_rows[R](
    connection: SqlConnection, kind: type[R], query: str, params: SqlParams | None = None
) -> list[R]:
    """Every row as `kind`, in the statement's order."""
    cursor = await _execute(connection, query, params)
    found = await cursor.fetchall()
    if not found:
        return []
    names = _names(cursor, kind)
    return [_built(kind, names, values) for values in found]


@asynccontextmanager
async def snapshot(connection: SqlConnection) -> AsyncIterator[None]:
    """One read-only, repeatable-read transaction, so a view's statements all read the same
    committed state (PRUN-11, SP-011's authoritative snapshot) and none of them can write.

    Only for a read that never writes, opened before any other statement of the connection's
    transaction: inside an open one, Postgres refuses to set the isolation level."""
    async with connection.transaction():
        await connection.execute(SNAPSHOT)
        yield
