"""HTTP routes do small, bounded work. A request never owns a run or a background task."""

from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from autobots.api.dependencies import CurrentUser, require_workspace_member
from autobots.api.errors import ApiError
from autobots.api.pool import request_pool
from autobots.api.security import require_internal, session_email
from autobots.application.profiles import (
    DisplayNameInvalid,
    fallback_name,
    normalize_display_name,
    save_name,
    saved_name,
    workspaces_with_roles,
)
from autobots.contracts.service import (
    ProfileUpdate,
    ProfileView,
    ServiceHealth,
    SessionSummary,
    SessionWorkspace,
    WorkspaceSummary,
)

router = APIRouter(prefix="/v1", dependencies=[Depends(require_internal)])


@router.get("/health", operation_id="getHealth", response_model=ServiceHealth)
async def health() -> ServiceHealth:
    return ServiceHealth(schema_version=1, status="ok")


@router.get("/session", operation_id="getSession", response_model=SessionSummary)
async def get_session(
    request: Request,
    user_id: CurrentUser,
    email: Annotated[str | None, Depends(session_email)],
) -> SessionSummary:
    workspaces = await request.app.state.membership.workspaces_for(user_id)
    pool = request.app.state.pool
    saved = await saved_name(pool, user_id)
    detail = await workspaces_with_roles(pool, user_id)
    return SessionSummary(
        schema_version=1,
        user_id=user_id,
        workspace_ids=workspaces,
        display_name=saved if saved is not None else fallback_name(email),
        display_name_saved=saved is not None,
        email=email,
        workspaces=[
            SessionWorkspace(
                id=workspace_id,
                name=name,
                role=cast(Literal["owner", "member"], role),
                timezone=timezone,
            )
            for workspace_id, name, role, timezone in detail
        ],
    )


@router.get("/profile", operation_id="getProfile", response_model=ProfileView)
async def get_profile(
    request: Request,
    user_id: CurrentUser,
    email: Annotated[str | None, Depends(session_email)],
) -> ProfileView:
    saved = await saved_name(request.app.state.pool, user_id)
    return ProfileView(
        schema_version=1,
        display_name=saved if saved is not None else fallback_name(email),
        saved=saved is not None,
        email=email,
    )


@router.put("/profile", operation_id="updateProfile", response_model=ProfileView)
async def update_profile(
    body: ProfileUpdate,
    request: Request,
    user_id: CurrentUser,
    email: Annotated[str | None, Depends(session_email)],
) -> ProfileView:
    try:
        name = normalize_display_name(body.display_name)
    except DisplayNameInvalid as error:
        raise ApiError(
            422, "display_name_invalid", "A display name needs 1 to 60 characters."
        ) from error
    saved = await save_name(request_pool(request), user_id, name)
    return ProfileView(schema_version=1, display_name=saved, saved=True, email=email)


@router.get(
    "/workspaces/{workspace_id}",
    operation_id="getWorkspace",
    response_model=WorkspaceSummary,
)
async def get_workspace(
    workspace_id: Annotated[UUID, Depends(require_workspace_member)],
) -> WorkspaceSummary:
    return WorkspaceSummary(schema_version=1, id=workspace_id)
