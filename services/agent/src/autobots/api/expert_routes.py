"""Experts and sessions. Revisions change grants, so only an owner saves them."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status

from autobots.api.errors import ApiError
from autobots.api.pool import request_pool
from autobots.api.security import current_user, require_internal
from autobots.api.settings_routes import current_workspace, require_owner
from autobots.api.tool_routes import catalog_of
from autobots.application.experts import (
    add_version,
    create_expert,
    create_session,
    get_expert,
    get_session,
    list_experts,
)
from autobots.contracts.experts import (
    ExpertCreate,
    ExpertList,
    ExpertRevision,
    ExpertView,
    SessionCreate,
    SessionView,
)
from autobots.domain.models import require_offered

router = APIRouter(prefix="/v1", dependencies=[Depends(require_internal)])
Key = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)]
Member = Annotated[UUID, Depends(current_workspace)]
Owner = Annotated[UUID, Depends(require_owner)]
User = Annotated[UUID, Depends(current_user)]


@router.get("/experts", operation_id="listExperts", response_model=ExpertList)
async def get_experts(request: Request, workspace: Member) -> ExpertList:
    async with request_pool(request).connection() as connection:
        return ExpertList(schema_version=1, experts=await list_experts(connection, workspace))


@router.post(
    "/experts",
    operation_id="createExpert",
    response_model=ExpertView,
    status_code=status.HTTP_201_CREATED,
)
async def post_expert(
    body: ExpertCreate, request: Request, key: Key, workspace: Owner, user: User
) -> ExpertView:
    # Named in this request, a profile not offered is a bad request (ProfileNotOffered).
    require_offered(body.config.role_bindings.values())
    async with request_pool(request).connection() as connection:
        return await create_expert(
            connection,
            workspace_id=workspace,
            actor_id=user,
            idempotency_key=key,
            name=body.name,
            config=body.config,
            catalog=catalog_of(request),
        )


@router.get("/experts/{expert_id}", operation_id="getExpert", response_model=ExpertView)
async def read_expert(expert_id: UUID, request: Request, workspace: Member) -> ExpertView:
    async with request_pool(request).connection() as connection:
        return await get_expert(connection, workspace, expert_id)


@router.post(
    "/experts/{expert_id}/versions",
    operation_id="addExpertVersion",
    response_model=ExpertView,
    status_code=status.HTTP_201_CREATED,
)
async def post_version(
    expert_id: UUID, body: ExpertRevision, request: Request, key: Key, workspace: Owner, user: User
) -> ExpertView:
    # Named in this request, a profile not offered is a bad request (ProfileNotOffered).
    require_offered(body.config.role_bindings.values())
    async with request_pool(request).connection() as connection:
        return await add_version(
            connection,
            workspace_id=workspace,
            actor_id=user,
            expert_id=expert_id,
            idempotency_key=key,
            expected_version=body.expected_version,
            config=body.config,
            catalog=catalog_of(request),
        )


@router.post(
    "/sessions",
    operation_id="createWorkSession",
    response_model=SessionView,
    status_code=status.HTTP_201_CREATED,
)
async def post_session(
    body: SessionCreate, request: Request, key: Key, workspace: Member, user: User
) -> SessionView:
    if (
        any(item.version is not None for item in body.experts)
        and await request.app.state.membership.role_in(user, workspace) != "owner"
    ):
        # An earlier version could hold tools an owner has since removed, Decision 0011.
        raise ApiError(403, "owner_required", "Only an owner can choose an Expert version.")
    async with request_pool(request).connection() as connection:
        return await create_session(
            connection,
            workspace_id=workspace,
            actor_id=user,
            idempotency_key=key,
            kind=body.kind,
            experts=body.experts,
        )


@router.get("/sessions/{session_id}", operation_id="getWorkSession", response_model=SessionView)
async def read_session(session_id: UUID, request: Request, workspace: Member) -> SessionView:
    async with request_pool(request).connection() as connection:
        return await get_session(connection, workspace, session_id)
