"""A browse's steps and screenshots for members of the run's workspace, Decision 0035 Y11."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Request, Response

from autobots.adapters.object_storage import StorageUnavailable
from autobots.api.dependencies import MemberWorkspace
from autobots.api.resources import app_resources, request_pool
from autobots.api.security import require_internal
from autobots.application.browse_steps import MEDIA_TYPE, list_steps, read_screenshot
from autobots.contracts.browse_steps import BrowseStepList

router = APIRouter(prefix="/v1", dependencies=[Depends(require_internal)])
UseId = Annotated[int, Path(ge=1)]
Step = Annotated[int, Path(ge=1, le=100)]


@router.get(
    "/runs/{run_id}/tool-uses/{use_id}/steps",
    operation_id="listBrowseSteps",
    response_model=BrowseStepList,
)
async def get_steps(
    run_id: UUID, use_id: UseId, request: Request, workspace_id: MemberWorkspace
) -> BrowseStepList:
    async with request_pool(request).connection() as connection:
        steps = await list_steps(connection, workspace_id, run_id, use_id)
    return BrowseStepList(schema_version=1, steps=steps)


@router.get("/runs/{run_id}/tool-uses/{use_id}/steps/{step}/screenshot", include_in_schema=False)
async def get_screenshot(
    run_id: UUID, use_id: UseId, step: Step, request: Request, workspace_id: MemberWorkspace
) -> Response:
    """Binary, so it has no generated client. Shown inline as a JPEG, never sniffed or cached."""
    store = app_resources(request).object_store
    if store is None:
        raise StorageUnavailable("no object store is configured")
    async with request_pool(request).connection() as connection:
        content = await read_screenshot(connection, store, workspace_id, run_id, use_id, step)
    return Response(
        content,
        media_type=MEDIA_TYPE,
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"},
    )
