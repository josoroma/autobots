"""The checkpointer on its own direct connection, carrying the owner's generation."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import psycopg
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row

from autobots.application.worker_leases import Lease

# Checkpoint before the next step begins, so a step never relies on progress that isn't saved.
DURABILITY = "sync"
STALE_OWNER_SQLSTATE = "AB001"


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
