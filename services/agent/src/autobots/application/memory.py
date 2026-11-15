"""Scoped memory and lexical evidence, all local Postgres, PRD 8.4.

There's no embedding or reranking service here. Authorization is the workspace on each row, checked
in the query, rather than anything a namespace label could claim.
"""

import json
from types import MappingProxyType
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
from autobots.domain.errors import Refusal, RefusalKind
from autobots.domain.tool_catalog import ToolGroup
from autobots.domain.tools import OperationClass

MAX_HITS = 10
_HEADLINE = 'MaxFragments=2, MaxWords=25, MinWords=5, StartSel="", StopSel=""'


class MemoryRefused(Refusal):
    kinds = MappingProxyType({"expert_not_found": RefusalKind.NOT_FOUND})


async def store_memory(
    connection: Any,
    *,
    workspace_id: UUID,
    actor_id: UUID,
    title: str,
    content: str,
    source: dict[str, Any],
    expert_id: UUID | None = None,
) -> UUID:
    if expert_id is not None:
        cursor = await connection.execute(
            "select 1 from public.experts where id = %s and workspace_id = %s",
            (expert_id, workspace_id),
        )
        if await cursor.fetchone() is None:
            raise MemoryRefused("expert_not_found")
    memory_id = uuid4()
    await connection.execute(
        "insert into public.memory_items (id, workspace_id, title, content, source, created_by, "
        "expert_id) values (%s, %s, %s, %s, %s, %s, %s)",
        (memory_id, workspace_id, title, content, json.dumps(source), actor_id, expert_id),
    )
    return memory_id


async def search(
    connection: Any,
    workspace_id: UUID,
    query: str,
    *,
    run_id: UUID | None = None,
    expert_id: UUID | None = None,
    for_run: bool = False,
    replay: tuple[UUID, str, str] | None = None,
) -> list[SearchHit]:
    """Lexical only. `websearch_to_tsquery` takes any text, so a query can't be malformed.

    `replay` is a memory proposal under a held-out replay, as (candidate, key, content). It stands
    in for that key's active version, in this search alone, Decision 0016.
    """
    hits: list[SearchHit] = []
    replaced = replay[1] if replay else None
    if replay is not None:
        cursor = await connection.execute(
            "select ts_headline('english', %s, q, %s) from websearch_to_tsquery('english', %s) q "
            "where to_tsvector('english', %s) @@ q",
            (replay[2], _HEADLINE, query, f"{replay[1]} {replay[2]}"),
        )
        found = await cursor.fetchone()
        if found is not None:
            hits.append(
                SearchHit(
                    kind="memory",
                    title=public_text(replay[1]),
                    snippet=public_text(found[0]),
                    source={"kind": "proposal", "key": replay[1], "candidate_id": str(replay[0])},
                )
            )
    cursor = await connection.execute(
        "select id, title, ts_headline('english', content, q, %s), source, created_at "
        "from public.memory_items, websearch_to_tsquery('english', %s) q "
        "where workspace_id = %s and search @@ q and retired_at is null "
        "and (not %s or expert_id is null or expert_id = %s) "
        "and (%s::text is null or key is distinct from %s) "
        "order by ts_rank(search, q) desc limit %s",
        (_HEADLINE, query, workspace_id, for_run, expert_id, replaced, replaced, MAX_HITS),
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
    # A run reaches its own files only: its grant covers those, not every run's in the workspace.
    cursor = await context.connection.execute(
        "select expert_id from public.runs where id = %s", (context.scope.run_id,)
    )
    expert = await cursor.fetchone()
    # A run of a memory proposal's held-out replay finds the proposal in place of the active key.
    cursor = await context.connection.execute(
        "select c.id, c.key, c.content from app_private.improvement_replay_runs rr "
        "join app_private.improvement_replays r on r.id = rr.replay_id "
        "join public.improvement_candidates c on c.id = r.candidate_id "
        "where rr.run_id = %s and c.kind = 'memory'",
        (context.scope.run_id,),
    )
    replay = await cursor.fetchone()
    hits = await search(
        context.connection,
        context.scope.workspace_id,
        arguments.query,
        run_id=context.scope.run_id,
        expert_id=expert[0] if expert else None,
        for_run=True,
        replay=(replay[0], replay[1], replay[2]) if replay else None,
    )
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
    content: str = row[1]
    end = arguments.offset + arguments.limit
    return OffloadContent(
        tool_name=row[0],
        content=content[arguments.offset : end],
        sha256=row[2],
        total_chars=len(content),
        next_offset=end if end < len(content) else None,
    )


SEARCH_MEMORY = ToolDefinition(
    tool_id="search_memory",
    title="Search memory",
    group=ToolGroup.GENERAL,
    public_input_fields=("query",),
    public_output_fields=(),
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
    title="Read offloaded result",
    group=ToolGroup.GENERAL,
    public_input_fields=("offload_id", "offset", "limit"),
    public_output_fields=("tool_name", "sha256", "total_chars", "next_offset"),
    version=1,
    description=(
        "Read back a long tool result stored outside the conversation, a page at a time. "
        "Keep passing next_offset as offset until it is null."
    ),
    input_model=ReadOffload,
    output_model=OffloadContent,
    operation_class=OperationClass.READ_ONLY,
    handler=_read_offload,
    timeout_seconds=5.0,
    retries=1,
    max_output_bytes=2_000_000,
)
