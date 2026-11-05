"""Authorized artifact metadata and downloads. A request never names a storage path."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response

from autobots.adapters.object_storage import StorageUnavailable
from autobots.api.errors import ApiError
from autobots.api.security import require_internal
from autobots.api.settings_routes import current_workspace
from autobots.application.artifacts import ArtifactUnavailable, list_artifacts, read_artifact
from autobots.contracts.artifacts import ArtifactList, ArtifactSummary

router = APIRouter(prefix="/v1", dependencies=[Depends(require_internal)])
Workspace = Annotated[UUID, Depends(current_workspace)]


def _pool(request: Request) -> Any:
    pool = request.app.state.pool
    if pool is None:
        raise ApiError(503, "service_unavailable", "The database is unavailable.")
    return pool


@router.get(
    "/runs/{run_id}/artifacts", operation_id="listRunArtifacts", response_model=ArtifactList
)
async def get_artifacts(run_id: UUID, request: Request, workspace_id: Workspace) -> ArtifactList:
    async with _pool(request).connection() as connection:
        rows = await list_artifacts(connection, workspace_id, run_id)
    return ArtifactList(
        schema_version=1, artifacts=[ArtifactSummary.model_validate(row) for row in rows]
    )


@router.get("/artifacts/{artifact_id}/download", include_in_schema=False)
async def download(artifact_id: UUID, request: Request, workspace_id: Workspace) -> Response:
    """Binary, so it has no generated client. Always an attachment, and never sniffed."""
    store = getattr(request.app.state, "object_store", None)
    if store is None:
        raise ApiError(503, "storage_unavailable", "Artifact storage is unavailable.")
    try:
        async with _pool(request).connection() as connection:
            name, media_type, content = await read_artifact(
                connection, store, workspace_id, artifact_id
            )
    except ArtifactUnavailable as error:
        status = 404 if error.code == "artifact_not_found" else 409
        raise ApiError(status, error.code, "That artifact is not available.") from None
    except StorageUnavailable:
        raise ApiError(503, "storage_unavailable", "Artifact storage is unavailable.") from None
    return Response(
        content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{name}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )
