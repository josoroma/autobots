"""PRD-Studio SR-01: ⌘K's one search endpoint, for any member of the workspace."""

import os
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request

from autobots.api.errors import ApiError
from autobots.api.security import require_internal
from autobots.api.settings_routes import current_workspace
from autobots.application.run_projection import public_text
from autobots.application.search import search
from autobots.contracts.search import SearchResult, SearchResults

router = APIRouter(prefix="/v1", dependencies=[Depends(require_internal)])
PATHS = {"run": "runs", "expert": "experts", "workflow": "workflows", "tool": "tools"}


@router.get("/search", operation_id="search", response_model=SearchResults)
async def get_search(
    request: Request,
    workspace_id: Annotated[UUID, Depends(current_workspace)],
    q: Annotated[str, Query(min_length=1, max_length=100)],
) -> SearchResults:
    query = q.strip()
    if not query:
        return SearchResults(schema_version=1, query="", results=[])
    pool = request.app.state.pool
    if pool is None:
        raise ApiError(503, "service_unavailable", "The database is unavailable.")
    async with pool.connection() as connection:
        hits = await search(connection, workspace_id, query, os.environ)
    return SearchResults(
        schema_version=1,
        query=query,
        results=[
            SearchResult(
                kind=hit.kind,  # type: ignore[arg-type]
                id=hit.id,
                title=public_text(hit.title, limit=200) or "Untitled",
                detail=hit.detail,
                href=f"/{PATHS[hit.kind]}/{hit.id}",
            )
            for hit in hits
        ],
    )
