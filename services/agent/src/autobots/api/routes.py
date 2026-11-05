"""HTTP routes do small, bounded work. A request never owns a run or a background task."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from autobots.api.security import require_internal, require_workspace_member
from autobots.contracts.service import ServiceHealth, WorkspaceSummary

router = APIRouter(prefix="/v1", dependencies=[Depends(require_internal)])


@router.get("/health", operation_id="getHealth", response_model=ServiceHealth)
async def health() -> ServiceHealth:
    return ServiceHealth(schema_version=1, status="ok")


@router.get(
    "/workspaces/{workspace_id}",
    operation_id="getWorkspace",
    response_model=WorkspaceSummary,
)
async def get_workspace(
    workspace_id: Annotated[UUID, Depends(require_workspace_member)],
) -> WorkspaceSummary:
    return WorkspaceSummary(schema_version=1, id=workspace_id)
