"""Routines. Creating or changing one changes what can start unattended, so only an owner can."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status

from autobots.api.errors import ApiError
from autobots.api.security import current_user, require_internal
from autobots.api.settings_routes import current_workspace, require_owner
from autobots.application.routines import (
    RoutineRefused,
    add_routine_version,
    create_routine,
    get_routine,
    list_routines,
    set_enabled,
)
from autobots.application.runs import IdempotencyConflict
from autobots.contracts.routines import (
    RoutineCreate,
    RoutineEnabled,
    RoutineList,
    RoutineRevision,
    RoutineView,
)

router = APIRouter(prefix="/v1", dependencies=[Depends(require_internal)])
Key = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)]
Member = Annotated[UUID, Depends(current_workspace)]
Owner = Annotated[UUID, Depends(require_owner)]
User = Annotated[UUID, Depends(current_user)]


def _pool(request: Request) -> Any:
    pool = request.app.state.pool
    if pool is None:
        raise ApiError(503, "service_unavailable", "The database is unavailable.")
    return pool


def _error(error: RoutineRefused | IdempotencyConflict) -> ApiError:
    if isinstance(error, IdempotencyConflict):
        return ApiError(409, error.code, "This key was already used with different content.")
    if error.code.endswith("not_found"):
        return ApiError(404, error.code, "That is not available.")
    if error.code in {"routine_name_taken", "routine_version_conflict"}:
        return ApiError(409, error.code, "That conflicts with what is saved. Reload and try again.")
    return ApiError(422, error.code, "That routine isn't valid.")


@router.get("/routines", operation_id="listRoutines", response_model=RoutineList)
async def get_routines(request: Request, workspace: Member) -> RoutineList:
    async with _pool(request).connection() as connection:
        return RoutineList(schema_version=1, routines=await list_routines(connection, workspace))


@router.post(
    "/routines",
    operation_id="createRoutine",
    response_model=RoutineView,
    status_code=status.HTTP_201_CREATED,
)
async def post_routine(
    body: RoutineCreate, request: Request, key: Key, workspace: Owner, user: User
) -> RoutineView:
    async with _pool(request).connection() as connection:
        try:
            return await create_routine(
                connection,
                workspace_id=workspace,
                actor_id=user,
                idempotency_key=key,
                name=body.name,
                config=body.config,
            )
        except (RoutineRefused, IdempotencyConflict) as error:
            raise _error(error) from None


@router.get("/routines/{routine_id}", operation_id="getRoutine", response_model=RoutineView)
async def read_routine(routine_id: UUID, request: Request, workspace: Member) -> RoutineView:
    async with _pool(request).connection() as connection:
        try:
            return await get_routine(connection, workspace, routine_id)
        except RoutineRefused as error:
            raise _error(error) from None


@router.post(
    "/routines/{routine_id}/versions",
    operation_id="addRoutineVersion",
    response_model=RoutineView,
    status_code=status.HTTP_201_CREATED,
)
async def post_version(
    routine_id: UUID,
    body: RoutineRevision,
    request: Request,
    key: Key,
    workspace: Owner,
    user: User,
) -> RoutineView:
    async with _pool(request).connection() as connection:
        try:
            return await add_routine_version(
                connection,
                workspace_id=workspace,
                actor_id=user,
                routine_id=routine_id,
                idempotency_key=key,
                expected_version=body.expected_version,
                config=body.config,
            )
        except (RoutineRefused, IdempotencyConflict) as error:
            raise _error(error) from None


@router.post(
    "/routines/{routine_id}/enabled", operation_id="setRoutineEnabled", response_model=RoutineView
)
async def post_enabled(
    routine_id: UUID, body: RoutineEnabled, request: Request, workspace: Owner
) -> RoutineView:
    async with _pool(request).connection() as connection:
        try:
            return await set_enabled(connection, workspace, routine_id, body.enabled)
        except RoutineRefused as error:
            raise _error(error) from None
