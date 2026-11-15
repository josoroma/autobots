"""The typed SQL boundary (refactor plan R-54, XTYP-04): `one()`, rows built by column name, and the
read-only snapshot a run view reads from.

A statement that always finds a row raises a named defect when it finds none, instead of a
TypeError from subscripting None. A row is built by its columns' names, as psycopg's `class_row`
builds one, so a missing, extra or duplicate name raises. No database is used: Postgres's own
refusal of a write inside the snapshot is checked by the db profile.
"""

import asyncio
from collections.abc import AsyncIterator, Coroutine, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, Literal

import pytest

from autobots.application.sql import (
    SNAPSHOT,
    RowNotFound,
    RowShapeMismatch,
    SqlParams,
    UnknownStoredValue,
    all_rows,
    one,
    optional_row,
    required_row,
    snapshot,
    stored,
)


@dataclass(frozen=True)
class Column:
    name: str


@dataclass
class Cursor:
    rows: list[tuple[Any, ...]]
    names: Sequence[str] = ()

    @property
    def description(self) -> list[Column] | None:
        return [Column(name) for name in self.names] if self.names else None

    async def fetchone(self) -> tuple[Any, ...] | None:
        return self.rows[0] if self.rows else None

    async def fetchall(self) -> list[tuple[Any, ...]]:
        return list(self.rows)


@dataclass
class Connection:
    answer: Cursor = field(default_factory=lambda: Cursor([]))
    sent: list[tuple[object, ...]] = field(default_factory=list)

    async def execute(self, query: str, params: SqlParams | None = None, /) -> Cursor:
        self.sent.append((query,) if params is None else (query, params))
        return self.answer

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[None]:
        self.sent.append(("begin",))
        try:
            yield
        except BaseException:
            self.sent.append(("rollback",))
            raise
        self.sent.append(("commit",))


@dataclass(frozen=True, slots=True, kw_only=True)
class Pair:
    id: int
    status: str


def run[T](work: Coroutine[Any, Any, T]) -> T:
    return asyncio.run(work)


def test_one_returns_the_first_row_with_the_statements_values() -> None:
    connection = Connection(Cursor([(3,), (4,)]))
    assert run(one(connection, "select count(*) from t where a = %s", (1,))) == (3,)
    assert connection.sent == [("select count(*) from t where a = %s", (1,))]


def test_one_without_values_sends_the_statement_alone() -> None:
    connection = Connection(Cursor([("now",)]))
    run(one(connection, "select now()"))
    assert connection.sent == [("select now()",)]


def test_one_finding_no_row_is_a_named_defect_that_shows_no_value() -> None:
    connection = Connection(Cursor([]))
    with pytest.raises(RowNotFound) as raised:
        run(one(connection, "select version\n  from public.runs where id = %s", ("secret",)))
    assert str(raised.value) == "select version from public.runs where id = %s"
    assert isinstance(raised.value, LookupError)


def test_a_row_is_built_by_its_column_names_in_any_order() -> None:
    connection = Connection(Cursor([("open", 7)], names=("status", "id")))
    assert run(required_row(connection, Pair, "select status, id from t")) == Pair(
        id=7, status="open"
    )


def test_every_row_keeps_the_statements_order() -> None:
    connection = Connection(Cursor([(1, "a"), (2, "b")], names=("id", "status")))
    assert run(all_rows(connection, Pair, "select id, status from t order by id")) == [
        Pair(id=1, status="a"),
        Pair(id=2, status="b"),
    ]


def test_no_rows_read_as_none_or_empty_and_required_raises() -> None:
    connection = Connection(Cursor([]))
    assert run(optional_row(connection, Pair, "select id, status from t")) is None
    assert run(all_rows(connection, Pair, "select id, status from t")) == []
    with pytest.raises(RowNotFound):
        run(required_row(connection, Pair, "select id, status from t"))


@pytest.mark.parametrize(
    ("names", "values"),
    [
        (("id",), (1,)),
        (("id", "status", "extra"), (1, "a", "x")),
        (("id", "id"), (1, 2)),
        ((), (1, "a")),
    ],
    ids=["missing", "extra", "duplicate", "undescribed"],
)
def test_a_column_that_doesnt_name_a_field_one_to_one_raises(
    names: tuple[str, ...], values: tuple[Any, ...]
) -> None:
    connection = Connection(Cursor([values], names=names))
    with pytest.raises(RowShapeMismatch):
        run(required_row(connection, Pair, "select id from t"))
    with pytest.raises(RowShapeMismatch):
        run(all_rows(connection, Pair, "select id from t"))


def test_the_snapshot_is_set_first_inside_its_own_transaction() -> None:
    connection = Connection(Cursor([(1,)]))

    async def view() -> None:
        async with snapshot(connection):
            await one(connection, "select 1")

    run(view())
    assert connection.sent == [("begin",), (SNAPSHOT,), ("select 1",), ("commit",)]
    assert SNAPSHOT == "set transaction isolation level repeatable read, read only"


def test_a_failed_read_rolls_the_snapshot_back() -> None:
    connection = Connection(Cursor([]))

    async def view() -> None:
        async with snapshot(connection):
            await one(connection, "select 1")

    with pytest.raises(RowNotFound):
        run(view())
    assert connection.sent == [("begin",), (SNAPSHOT,), ("select 1",), ("rollback",)]


def test_a_stored_value_reads_as_its_vocabulary_or_raises() -> None:
    vocabulary: tuple[Literal["open", "finished"], ...] = ("open", "finished")
    assert stored(vocabulary, "finished") == "finished"
    with pytest.raises(UnknownStoredValue, match="archived"):
        stored(vocabulary, "archived")
