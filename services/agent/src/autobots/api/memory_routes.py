"""Memory search and notes, scoped by the verified workspace, PRD 8.4."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from autobots.api.dependencies import CurrentUser, MemberWorkspace, OwnerWorkspace
from autobots.api.pool import request_pool
from autobots.api.security import require_internal
from autobots.application.memory import search, store_memory
from autobots.contracts.memory import MemoryCreate, MemoryCreated, MemorySearchView

router = APIRouter(prefix="/v1", dependencies=[Depends(require_internal)])


@router.get("/memory/search", operation_id="searchMemory", response_model=MemorySearchView)
async def get_search(
    request: Request,
    workspace_id: MemberWorkspace,
    q: Annotated[str, Query(min_length=1, max_length=500)],
) -> MemorySearchView:
    async with request_pool(request).connection() as connection:
        return MemorySearchView(schema_version=1, hits=await search(connection, workspace_id, q))


@router.post(
    "/memory",
    operation_id="createMemory",
    response_model=MemoryCreated,
    status_code=status.HTTP_201_CREATED,
)
async def post_memory(
    body: MemoryCreate,
    request: Request,
    workspace_id: OwnerWorkspace,
    user_id: CurrentUser,
) -> MemoryCreated:
    """A person's own note. Anything a run learned goes through review, in US-8.2."""
    async with request_pool(request).connection() as connection:
        memory_id = await store_memory(
            connection,
            workspace_id=workspace_id,
            actor_id=user_id,
            title=body.title,
            content=body.content,
            source={"kind": "owner_note"},
            expert_id=body.expert_id,
        )
    return MemoryCreated(schema_version=1, id=str(memory_id))
