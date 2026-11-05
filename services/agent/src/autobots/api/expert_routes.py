"""Experts and sessions. Revisions change grants, so only an owner saves them."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status

from autobots.api.errors import ApiError
from autobots.api.security import current_user, require_internal
from autobots.api.settings_routes import current_workspace, require_owner
from autobots.application.experts import (
    ExpertRefused,
    add_version,
    create_expert,
    create_session,
    get_expert,
    get_session,
    list_experts,
)
from autobots.application.runs import IdempotencyConflict
from autobots.contracts.experts import (
    ExpertCreate,
    ExpertList,
    ExpertRevision,
    ExpertView,
    SessionCreate,
    SessionView,
)

router = APIRouter(prefix="/v1", dependencies=[Depends(require_internal)])
Key = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)]
Member = Annotated[UUID, Depends(current_workspace)]
Owner = Annotated[UUID, Depends(require_owner)]
User = Annotated[UUID, Depends(current_user)]
NOT_FOUND = {"expert_not_found", "session_not_found"}
CONFLICT = {"expert_name_taken", "expert_version_conflict"}


def _pool(request: Request) -> Any:
    pool = request.app.state.pool
    if pool is None:
        raise ApiError(503, "service_unavailable", "The database is unavailable.")
    return pool


def _error(error: ExpertRefused | IdempotencyConflict) -> ApiError:
    if isinstance(error, IdempotencyConflict):
        return ApiError(409, error.code, "This key was already used with different content.")
    if error.code in NOT_FOUND:
        return ApiError(404, error.code, "That is not available.")
    if error.code in CONFLICT:
        return ApiError(409, error.code, "That conflicts with what is saved. Reload and try again.")
    return ApiError(422, error.code, "That configuration is not allowed.")


@router.get("/experts", operation_id="listExperts", response_model=ExpertList)
async def get_experts(request: Request, workspace: Member) -> ExpertList:
    async with _pool(request).connection() as connection:
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
    async with _pool(request).connection() as connection:
        try:
            return await create_expert(
                connection,
                workspace_id=workspace,
                actor_id=user,
                idempotency_key=key,
                name=body.name,
                config=body.config,
            )
        except (ExpertRefused, IdempotencyConflict) as error:
            raise _error(error) from None


@router.get("/experts/{expert_id}", operation_id="getExpert", response_model=ExpertView)
async def read_expert(expert_id: UUID, request: Request, workspace: Member) -> ExpertView:
    async with _pool(request).connection() as connection:
        try:
            return await get_expert(connection, workspace, expert_id)
        except ExpertRefused as error:
            raise _error(error) from None


@router.post(
    "/experts/{expert_id}/versions",
    operation_id="addExpertVersion",
    response_model=ExpertView,
    status_code=status.HTTP_201_CREATED,
)
async def post_version(
    expert_id: UUID, body: ExpertRevision, request: Request, key: Key, workspace: Owner, user: User
) -> ExpertView:
    async with _pool(request).connection() as connection:
        try:
            return await add_version(
                connection,
                workspace_id=workspace,
                actor_id=user,
                expert_id=expert_id,
                idempotency_key=key,
                expected_version=body.expected_version,
                config=body.config,
            )
        except (ExpertRefused, IdempotencyConflict) as error:
            raise _error(error) from None


@router.post(
    "/sessions",
    operation_id="createWorkSession",
    response_model=SessionView,
    status_code=status.HTTP_201_CREATED,
)
async def post_session(
    body: SessionCreate, request: Request, key: Key, workspace: Member, user: User
) -> SessionView:
    async with _pool(request).connection() as connection:
        try:
            return await create_session(
                connection,
                workspace_id=workspace,
                actor_id=user,
                idempotency_key=key,
                kind=body.kind,
                experts=body.experts,
            )
        except (ExpertRefused, IdempotencyConflict) as error:
            raise _error(error) from None


@router.get("/sessions/{session_id}", operation_id="getWorkSession", response_model=SessionView)
async def read_session(session_id: UUID, request: Request, workspace: Member) -> SessionView:
    async with _pool(request).connection() as connection:
        try:
            return await get_session(connection, workspace, session_id)
        except ExpertRefused as error:
            raise _error(error) from None
