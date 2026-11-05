"""Scoped memory and lexical evidence, all local Postgres, PRD 8.4.

There's no embedding or reranking service here. Authorization is the workspace on each row, checked
in the query, rather than anything a namespace label could claim.
"""

import json
from typing import Any
from uuid import UUID, uuid4

from autobots.application.run_projection import public_text
from autobots.application.tool_gateway import ToolContext, ToolDefinition, ToolFailed
from autobots.contracts.memory import (
    OffloadContent,
    ReadOffload,
    SearchHit,
    SearchMemory,
    SearchResults,
)
from autobots.domain.tools import OperationClass

MAX_HITS = 10
_HEADLINE = 'MaxFragments=2, MaxWords=25, MinWords=5, StartSel="", StopSel=""'


async def store_memory(
    connection: Any,
    *,
    workspace_id: UUID,
    actor_id: UUID,
    title: str,
    content: str,
    source: dict[str, Any],
) -> UUID:
    memory_id = uuid4()
    await connection.execute(
        "insert into public.memory_items (id, workspace_id, title, content, source, created_by) "
        "values (%s, %s, %s, %s, %s, %s)",
        (memory_id, workspace_id, title, content, json.dumps(source), actor_id),
    )
    return memory_id


async def search(
    connection: Any, workspace_id: UUID, query: str, *, run_id: UUID | None = None
) -> list[SearchHit]:
    """Lexical only. `websearch_to_tsquery` takes any text, so a query can't be malformed."""
    hits: list[SearchHit] = []
    cursor = await connection.execute(
        "select id, title, ts_headline('english', content, q, %s), source, created_at "
        "from public.memory_items, websearch_to_tsquery('english', %s) q "
        "where workspace_id = %s and search @@ q and retired_at is null "
        "order by ts_rank(search, q) desc limit %s",
        (_HEADLINE, query, workspace_id, MAX_HITS),
    )
    for row in await cursor.fetchall():
        hits.append(
            SearchHit(
                kind="memory",
                title=public_text(row[1]),
                snippet=public_text(row[2]),
                source={**row[3], "memory_id": str(row[0]), "stored_at": row[4].isoformat()},
            )
        )
    # The workspace comes through the run, so a file in another workspace can't match.
    cursor = await connection.execute(
        "select f.run_id, f.path, f.version, f.sha256, "
        "ts_headline('english', f.content, q, %s), f.created_at "
        "from app_private.run_files f join public.runs r on r.id = f.run_id, "
        "websearch_to_tsquery('english', %s) q "
        "where r.workspace_id = %s and f.search @@ q and (%s::uuid is null or f.run_id = %s) "
        "order by ts_rank(f.search, q) desc limit %s",
        (_HEADLINE, query, workspace_id, run_id, run_id, MAX_HITS),
    )
    for row in await cursor.fetchall():
        hits.append(
            SearchHit(
                kind="evidence",
                title=public_text(row[1]),
                snippet=public_text(row[4]),
                source={
                    "run_id": str(row[0]),
                    "path": row[1],
                    "version": row[2],
                    "sha256": row[3],
                    "stored_at": row[5].isoformat(),
                },
            )
        )
    return hits


async def _search_tool(arguments: SearchMemory, context: ToolContext) -> SearchResults:
    hits = await search(context.connection, context.scope.workspace_id, arguments.query)
    return SearchResults(hits=hits)


async def _read_offload(arguments: ReadOffload, context: ToolContext) -> OffloadContent:
    try:
        offload_id = UUID(arguments.offload_id)
    except ValueError:
        raise ToolFailed("offload_not_found") from None
    cursor = await context.connection.execute(
        "select tool_name, content, sha256 from app_private.run_offloads "
        "where id = %s and run_id = %s",
        (offload_id, context.scope.run_id),
    )
    row = await cursor.fetchone()
    if row is None:
        raise ToolFailed("offload_not_found")
    return OffloadContent(tool_name=row[0], content=row[1], sha256=row[2])


SEARCH_MEMORY = ToolDefinition(
    tool_id="search_memory",
    version=1,
    description="Search this workspace's memory and saved evidence by keyword.",
    input_model=SearchMemory,
    output_model=SearchResults,
    operation_class=OperationClass.READ_ONLY,
    handler=_search_tool,
    timeout_seconds=5.0,
    retries=1,
)
READ_OFFLOAD = ToolDefinition(
    tool_id="read_offload",
    version=1,
    description="Read back a long tool result that was stored outside the conversation.",
    input_model=ReadOffload,
    output_model=OffloadContent,
    operation_class=OperationClass.READ_ONLY,
    handler=_read_offload,
    timeout_seconds=5.0,
    retries=1,
    max_output_bytes=2_000_000,
)
