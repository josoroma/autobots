"""PRD-Studio SR-01: ⌘K's one search endpoint, for any member of the workspace."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from autobots.api.dependencies import MemberWorkspace, catalog_of, process_environment
from autobots.api.resources import request_pool
from autobots.api.security import require_internal
from autobots.application.run_projection import public_text
from autobots.application.search import search_workspace
from autobots.application.tool_keys import key_sources
from autobots.contracts.search import SearchResult, SearchResults

router = APIRouter(prefix="/v1", dependencies=[Depends(require_internal)])
PATHS = {"run": "runs", "expert": "experts", "workflow": "workflows", "tool": "tools"}


@router.get("/search", operation_id="search", response_model=SearchResults)
async def get_search(
    request: Request,
    workspace_id: MemberWorkspace,
    q: Annotated[str, Query(min_length=1, max_length=100)],
) -> SearchResults:
    query = q.strip()
    if not query:
        return SearchResults(schema_version=1, query="", results=[])
    async with request_pool(request).connection() as connection:
        keys = await key_sources(connection, workspace_id, process_environment(request))
        hits = await search_workspace(connection, workspace_id, query, keys, catalog_of(request))
    return SearchResults(
        schema_version=1,
        query=query,
        results=[
            SearchResult(
                kind=hit.kind,
                id=hit.id,
                title=public_text(hit.title, limit=200) or "Untitled",
                detail=hit.detail,
                href=f"/{PATHS[hit.kind]}/{hit.id}",
            )
            for hit in hits
        ],
    )
