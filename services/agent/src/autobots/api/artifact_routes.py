"""Authorized artifact metadata and downloads. A request never names a storage path."""

from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response

from autobots.adapters.object_storage import StorageUnavailable
from autobots.api.dependencies import MemberWorkspace
from autobots.api.errors import ApiError
from autobots.api.pool import request_pool
from autobots.api.security import require_internal
from autobots.application.artifacts import list_artifacts, read_artifact
from autobots.contracts.artifacts import ArtifactList, ArtifactSummary

router = APIRouter(prefix="/v1", dependencies=[Depends(require_internal)])


@router.get(
    "/runs/{run_id}/artifacts", operation_id="listRunArtifacts", response_model=ArtifactList
)
async def get_artifacts(
    run_id: UUID, request: Request, workspace_id: MemberWorkspace
) -> ArtifactList:
    async with request_pool(request).connection() as connection:
        rows = await list_artifacts(connection, workspace_id, run_id)
    return ArtifactList(
        schema_version=1, artifacts=[ArtifactSummary.model_validate(row) for row in rows]
    )


@router.get("/artifacts/{artifact_id}/download", include_in_schema=False)
async def download(artifact_id: UUID, request: Request, workspace_id: MemberWorkspace) -> Response:
    """Binary, so it has no generated client. Always an attachment, and never sniffed."""
    store = getattr(request.app.state, "object_store", None)
    if store is None:
        raise ApiError(503, "storage_unavailable", "Artifact storage is unavailable.")
    try:
        async with request_pool(request).connection() as connection:
            name, media_type, content = await read_artifact(
                connection, store, workspace_id, artifact_id
            )
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
