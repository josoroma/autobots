"""Decision 0023 E2: the schema check reads the applied count against what this release ships."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from autobots.application.operations import (
    REQUIRED_COLUMNS,
    REQUIRED_RELATIONS,
    Condition,
    database_conditions,
    is_ready,
    schema_condition,
)
from autobots.application.schema_release import NEWEST_MIGRATION, SHIPPED_MIGRATIONS
from autobots.application.sql import SqlParams
from sql_fakes import ScriptedRows

MIGRATIONS = Path(__file__).resolve().parents[3] / "supabase/migrations"


def test_the_shipped_record_matches_the_migration_files() -> None:
    names = sorted(path.name for path in MIGRATIONS.glob("*.sql"))
    assert (SHIPPED_MIGRATIONS, NEWEST_MIGRATION) == (len(names), names[-1])


def test_fewer_applied_is_behind_and_blocks() -> None:
    condition = schema_condition(0, SHIPPED_MIGRATIONS - 14)
    assert (condition.state, condition.code) == ("unavailable", "schema_behind")
    assert not is_ready([condition])


def test_equal_is_ready_and_a_missing_object_still_is_behind() -> None:
    assert schema_condition(0, SHIPPED_MIGRATIONS).code == "schema_ready"
    assert schema_condition(1, SHIPPED_MIGRATIONS).code == "schema_behind"
    assert schema_condition(0, None).code == "schema_ready"
    assert schema_condition(2, None).code == "schema_behind"


def test_more_applied_is_ahead_and_doesnt_block() -> None:
    condition = schema_condition(0, SHIPPED_MIGRATIONS + 1)
    assert (condition.state, condition.code) == ("degraded", "schema_ahead")
    assert is_ready([condition, Condition("database", "ok", "database_ready")])
    # Only schema_ahead is let through: another degraded blocking check still stops admission.
    assert not is_ready([Condition("disk", "degraded", "disk_low")])


def test_the_newer_objects_are_required() -> None:
    for relation in (
        "app_private.tool_uses",
        "public.user_profiles",
        "public.workflow_drafts",
        "app_private.plan_task_times",
    ):
        assert relation in REQUIRED_RELATIONS
    for column in (
        ("app_private.tool_uses", "instance_key"),
        ("public.workflows", "description"),
        ("public.approval_requests", "review_detail"),
    ):
        assert column in REQUIRED_COLUMNS


def answered(row: tuple[Any, ...] | None) -> ScriptedRows:
    return ScriptedRows([] if row is None else [row])


class Connection:
    """Every object present; the counting function and its answer are set per test."""

    def __init__(self, has_function: bool, applied: int | None) -> None:
        self.has_function = has_function
        self.applied = applied
        self.statements: list[str] = []

    async def execute(self, statement: str, _params: SqlParams | None = None, /) -> ScriptedRows:
        self.statements.append(statement)
        if "to_regprocedure" in statement:
            return answered((self.has_function,))
        if "applied_migration_count" in statement:
            return answered((self.applied,))
        if "installation_holds" in statement:
            return answered(None)
        return answered((0,))

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[None]:
        yield

    async def __aenter__(self) -> "Connection":
        return self

    async def __aexit__(self, *_: Any) -> None:
        return None


class Pool:
    def __init__(self, connection: Connection) -> None:
        self._connection = connection

    def connection(self) -> Connection:
        return self._connection


def schema_of(connection: Connection) -> str:
    return asyncio.run(database_conditions(Pool(connection)))[1].code


def test_the_probe_reads_the_applied_count() -> None:
    assert schema_of(Connection(True, SHIPPED_MIGRATIONS - 1)) == "schema_behind"
    assert schema_of(Connection(True, SHIPPED_MIGRATIONS)) == "schema_ready"
    assert schema_of(Connection(True, SHIPPED_MIGRATIONS + 2)) == "schema_ahead"


def test_without_the_counting_function_it_isnt_called() -> None:
    connection = Connection(False, None)
    assert schema_of(connection) == "schema_ready"
    assert not any(
        "applied_migration_count()" in statement and "to_regprocedure" not in statement
        for statement in connection.statements
    )
