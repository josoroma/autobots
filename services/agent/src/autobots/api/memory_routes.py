"""Memory search and notes, scoped by the verified workspace, PRD 8.4."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status

from autobots.api.errors import ApiError
from autobots.api.security import current_user, require_internal
from autobots.api.settings_routes import current_workspace, require_owner
from autobots.application.memory import search, store_memory
from autobots.contracts.memory import MemoryCreate, MemoryCreated, MemorySearchView

router = APIRouter(prefix="/v1", dependencies=[Depends(require_internal)])


def _pool(request: Request) -> Any:
    pool = request.app.state.pool
    if pool is None:
        raise ApiError(503, "service_unavailable", "The database is unavailable.")
    return pool


@router.get("/memory/search", operation_id="searchMemory", response_model=MemorySearchView)
async def get_search(
    request: Request,
    workspace: Annotated[UUID, Depends(current_workspace)],
    q: Annotated[str, Query(min_length=1, max_length=500)],
) -> MemorySearchView:
    async with _pool(request).connection() as connection:
        return MemorySearchView(schema_version=1, hits=await search(connection, workspace, q))


@router.post(
    "/memory",
    operation_id="createMemory",
    response_model=MemoryCreated,
    status_code=status.HTTP_201_CREATED,
)
async def post_memory(
    body: MemoryCreate,
    request: Request,
    workspace: Annotated[UUID, Depends(require_owner)],
    user: Annotated[UUID, Depends(current_user)],
) -> MemoryCreated:
    """A person's own note. Anything a run learned goes through review, in US-8.2."""
    async with _pool(request).connection() as connection:
        memory_id = await store_memory(
            connection,
            workspace_id=workspace,
            actor_id=user,
            title=body.title,
            content=body.content,
            source={"kind": "owner_note"},
        )
    return MemoryCreated(schema_version=1, id=str(memory_id))
