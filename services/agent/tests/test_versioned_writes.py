"""The shared new-version step over its closed set of parent tables (PPRD-08, refactor plan R-63).

Each table name is composed as an identifier, a removed routine takes no new version, and a missing
row or a stale expected version raises its typed error, which each service maps to its own code.
The version insert and the `latest_version` update keep their order: the caller inserts between
`next_version` and `set_latest` (tests/test_persisted_documents.py pins each writer's receipt).
"""

import asyncio
from uuid import UUID

import pytest

from autobots.application.idempotency import (
    ExpectedVersionStale,
    Versioned,
    VersionedRowMissing,
    next_version,
    set_latest,
)
from fake_api import FakeConnection, FakeDatabase

ROW = UUID("0f100000-0000-4000-8000-000000000001")
WORKSPACE = UUID("0f100000-0000-4000-8000-000000000002")


@pytest.mark.parametrize(
    ("table", "statement"),
    [
        (
            "experts",
            'select latest_version from "public"."experts" '
            "where id = %s and workspace_id = %s for update",
        ),
        (
            "workflows",
            'select latest_version from "public"."workflows" '
            "where id = %s and workspace_id = %s for update",
        ),
        (
            "routines",
            'select latest_version from "public"."routines" '
            "where id = %s and workspace_id = %s and removed_at is null for update",
        ),
    ],
)
def test_the_next_version_locks_its_row_and_follows_the_expected_one(
    table: Versioned, statement: str
) -> None:
    database = FakeDatabase([])
    database.answer("select latest_version from", (4,))
    version = asyncio.run(next_version(FakeConnection(database), table, ROW, WORKSPACE, 4))
    assert version == 5
    assert database.statements == [(statement, (ROW, WORKSPACE))]


def test_a_missing_row_or_a_stale_version_raises_its_typed_error() -> None:
    database = FakeDatabase([])
    with pytest.raises(VersionedRowMissing):
        asyncio.run(next_version(FakeConnection(database), "experts", ROW, WORKSPACE, 1))
    database.answer("select latest_version from", (2,))
    with pytest.raises(ExpectedVersionStale):
        asyncio.run(next_version(FakeConnection(database), "experts", ROW, WORKSPACE, 1))


def test_the_latest_version_is_set_on_its_own_table() -> None:
    database = FakeDatabase([])
    asyncio.run(set_latest(FakeConnection(database), "workflows", ROW, 5))
    assert database.statements == [
        ('update "public"."workflows" set latest_version = %s where id = %s', (5, ROW))
    ]
