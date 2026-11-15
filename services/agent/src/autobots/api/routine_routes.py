"""Routines. Creating or changing one changes what can start unattended, so only an owner can."""

from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from autobots.api.dependencies import CurrentUser, IdempotencyKey, MemberWorkspace, OwnerWorkspace
from autobots.api.pool import request_pool
from autobots.api.security import require_internal
from autobots.application.routines import (
    add_routine_version,
    create_routine,
    get_routine,
    list_routines,
    set_enabled,
)
from autobots.contracts.routines import (
    RoutineCreate,
    RoutineEnabled,
    RoutineList,
    RoutineRevision,
    RoutineView,
)

router = APIRouter(prefix="/v1", dependencies=[Depends(require_internal)])


@router.get("/routines", operation_id="listRoutines", response_model=RoutineList)
async def get_routines(request: Request, workspace_id: MemberWorkspace) -> RoutineList:
    async with request_pool(request).connection() as connection:
        return RoutineList(schema_version=1, routines=await list_routines(connection, workspace_id))


@router.post(
    "/routines",
    operation_id="createRoutine",
    response_model=RoutineView,
    status_code=status.HTTP_201_CREATED,
)
async def post_routine(
    body: RoutineCreate,
    request: Request,
    idempotency_key: IdempotencyKey,
    workspace_id: OwnerWorkspace,
    user_id: CurrentUser,
) -> RoutineView:
    async with request_pool(request).connection() as connection:
        return await create_routine(
            connection,
            workspace_id=workspace_id,
            actor_id=user_id,
            idempotency_key=idempotency_key,
            name=body.name,
            config=body.config,
            # A person's routine: the workspace's run limit caps each run (Decision 0029 F2).
            budget_cap=None,
        )


@router.get("/routines/{routine_id}", operation_id="getRoutine", response_model=RoutineView)
async def read_routine(
    routine_id: UUID, request: Request, workspace_id: MemberWorkspace
) -> RoutineView:
    async with request_pool(request).connection() as connection:
        return await get_routine(connection, workspace_id, routine_id)


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
    idempotency_key: IdempotencyKey,
    workspace_id: OwnerWorkspace,
    user_id: CurrentUser,
) -> RoutineView:
    async with request_pool(request).connection() as connection:
        return await add_routine_version(
            connection,
            workspace_id=workspace_id,
            actor_id=user_id,
            routine_id=routine_id,
            idempotency_key=idempotency_key,
            expected_version=body.expected_version,
            config=body.config,
            budget_cap=None,
        )


@router.post(
    "/routines/{routine_id}/enabled", operation_id="setRoutineEnabled", response_model=RoutineView
)
async def post_enabled(
    routine_id: UUID, body: RoutineEnabled, request: Request, workspace_id: OwnerWorkspace
) -> RoutineView:
    async with request_pool(request).connection() as connection:
        return await set_enabled(connection, workspace_id, routine_id, body.enabled)
