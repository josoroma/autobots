"""The `search_memory` and `read_offload` tools: a run searches its workspace's memory and its own
files, and reads back a long tool result page by page (PRD 8.4). Tool definitions sit apart from the
services they call, so the registry composes them without the services depending on it (Decision
0029 F12, PPRD-15).
"""

from uuid import UUID

from autobots.application.memory import search_memory
from autobots.application.sql import optional_row
from autobots.application.tool_definitions import ToolContext, ToolDefinition, ToolFailed
from autobots.contracts.memory import OffloadContent, ReadOffload, SearchMemory, SearchResults
from autobots.domain.tool_catalog import ToolGroup
from autobots.domain.tools import OperationClass
from autobots.persistence.rows import OffloadRow, ReplayProposalRow


async def _search_tool(arguments: SearchMemory, context: ToolContext) -> SearchResults:
    # A run reaches its own files only: its grant covers those, not every run's in the workspace.
    cursor = await context.connection.execute(
        "select expert_id from public.runs where id = %s", (context.scope.run_id,)
    )
    expert = await cursor.fetchone()
    # A run of a memory proposal's held-out replay finds the proposal in place of the active key.
    replay = await optional_row(
        context.connection,
        ReplayProposalRow,
        "select c.id, c.key, c.content from app_private.improvement_replay_runs rr "
        "join app_private.improvement_replays r on r.id = rr.replay_id "
        "join public.improvement_candidates c on c.id = r.candidate_id "
        "where rr.run_id = %s and c.kind = 'memory'",
        (context.scope.run_id,),
    )
    hits = await search_memory(
        context.connection,
        context.scope.workspace_id,
        arguments.query,
        run_id=context.scope.run_id,
        expert_id=expert[0] if expert else None,
        for_run=True,
        replay=(replay.id, replay.key, replay.content) if replay else None,
    )
    return SearchResults(hits=hits)


async def _read_offload(arguments: ReadOffload, context: ToolContext) -> OffloadContent:
    try:
        offload_id = UUID(arguments.offload_id)
    except ValueError:
        raise ToolFailed("offload_not_found") from None
    row = await optional_row(
        context.connection,
        OffloadRow,
        "select tool_name, content, sha256 from app_private.run_offloads "
        "where id = %s and run_id = %s",
        (offload_id, context.scope.run_id),
    )
    if row is None:
        raise ToolFailed("offload_not_found")
    content = row.content
    end = arguments.offset + arguments.limit
    return OffloadContent(
        tool_name=row.tool_name,
        content=content[arguments.offset : end],
        sha256=row.sha256,
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
