"""The checkpointer on its own direct connection, carrying the owner's generation."""

import hashlib
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from importlib import metadata
from typing import Any

import psycopg
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.postgres.base import BasePostgresSaver
from psycopg.rows import dict_row

from autobots.application.worker_leases import Lease

# Checkpoint before the next step begins, so a step never relies on progress that isn't saved.
DURABILITY = "sync"
STALE_OWNER_SQLSTATE = "AB001"


ADAPTER_STATEMENTS = (
    BasePostgresSaver.SELECT_SQL,
    BasePostgresSaver.UPSERT_CHECKPOINT_BLOBS_SQL,
    BasePostgresSaver.UPSERT_CHECKPOINTS_SQL,
    BasePostgresSaver.UPSERT_CHECKPOINT_WRITES_SQL,
    BasePostgresSaver.INSERT_CHECKPOINT_WRITES_SQL,
)


def identity_of(version: str, migrations: Sequence[str], statements: Sequence[str] = ()) -> str:
    joined = "\n".join([version, *migrations, *statements])
    return hashlib.sha256(joined.encode()).hexdigest()


def adapter_identity() -> tuple[str, str]:
    """The installed adapter: its release, its migrations and the SQL this code relies on."""
    version = metadata.version("langgraph-checkpoint-postgres")
    return version, identity_of(version, BasePostgresSaver.MIGRATIONS, ADAPTER_STATEMENTS)


async def adapter_qualified(connection: Any) -> bool:
    """A framework release continues saved work only after a migration records its qualification."""
    _, fingerprint = adapter_identity()
    cursor = await connection.execute(
        "select 1 from agent_runtime.adapter_qualifications where fingerprint = %s", (fingerprint,)
    )
    return await cursor.fetchone() is not None


@asynccontextmanager
async def fenced_checkpointer(database_url: str, lease: Lease) -> AsyncIterator[AsyncPostgresSaver]:
    """The database refuses this connection's writes once its generation stops being current.

    The tables come from a migration, so setup is never called here. Serialized state is plain to
    anyone with database access, so credentials and key-holding clients stay out of graph state.
    """
    async with await psycopg.AsyncConnection.connect(
        database_url,
        autocommit=True,
        prepare_threshold=0,
        row_factory=dict_row,
        options="-c search_path=agent_runtime",
    ) as connection:
        await connection.execute(
            "select set_config('autobots.fencing_generation', %s, false)",
            (str(lease.generation),),
        )
        yield AsyncPostgresSaver(connection)


def graph_config(lease: Lease) -> dict[str, Any]:
    return {"configurable": {"thread_id": lease.thread_id}}


def is_stale_owner(error: BaseException) -> bool:
    return getattr(error, "sqlstate", None) == STALE_OWNER_SQLSTATE
