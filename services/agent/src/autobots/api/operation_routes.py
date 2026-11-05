"""Local Operations. It has to answer with the database down, so a signed-in user is enough then."""

import os
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request

from autobots.api.errors import ApiError
from autobots.api.security import current_user, require_internal
from autobots.api.settings_routes import current_workspace, require_owner
from autobots.application.operations import (
    DEFAULT_MIN_FREE_BYTES,
    Condition,
    database_conditions,
    disk_condition,
    is_ready,
    queue_condition,
    queue_counts,
    storage_condition,
    worker_condition,
)
from autobots.application.retention import (
    RetentionPolicy,
    apply_retention,
    read_policy,
    write_policy,
)
from autobots.contracts.operations import (
    LocalStatus,
    OperationCondition,
    QueueStatus,
    RetentionApplied,
    RetentionSettings,
)
from autobots.operations.logs import remote_tracing_disabled

router = APIRouter(prefix="/v1", dependencies=[Depends(require_internal)])
Owner = Annotated[UUID, Depends(require_owner)]
User = Annotated[UUID, Depends(current_user)]


def _pool(request: Request) -> Any:
    pool = request.app.state.pool
    if pool is None:
        raise ApiError(503, "service_unavailable", "The database is unavailable.")
    return pool


async def _installation_conditions(request: Request) -> list[Condition]:
    database, schema = await database_conditions(request.app.state.pool)
    storage = await storage_condition(getattr(request.app.state, "object_store", None))
    minimum = int(os.environ.get("AUTOBOTS_MIN_FREE_BYTES", DEFAULT_MIN_FREE_BYTES))
    disk = disk_condition(Path(os.environ.get("AUTOBOTS_CONFIG_ROOT") or "."), minimum)
    return [database, schema, storage, disk]


async def require_ready(request: Request) -> None:
    """Admission stops when required persistence is unhealthy (LM-07), before any job can exist."""
    if not is_ready(await _installation_conditions(request)):
        raise ApiError(503, "not_ready", "Local services aren't ready, so nothing was started.")


@router.get("/operations/local-status", operation_id="getLocalStatus", response_model=LocalStatus)
async def get_local_status(
    request: Request,
    user_id: User,
    x_autobots_workspace: Annotated[UUID | None, Header()] = None,
) -> LocalStatus:
    conditions = await _installation_conditions(request)
    database_up = conditions[0].state == "ok" and conditions[1].state == "ok"
    queue: QueueStatus | None = None
    retention: RetentionSettings | None = None
    if database_up:
        workspace_id = await current_workspace(request, user_id, x_autobots_workspace)
        if await request.app.state.membership.role_in(user_id, workspace_id) != "owner":
            raise ApiError(403, "owner_required", "Only the workspace owner can see this.")
        async with _pool(request).connection() as connection:
            counts = await queue_counts(connection, workspace_id)
            conditions.append(queue_condition(counts))
            conditions.append(await worker_condition(connection, counts))
            policy = await read_policy(connection, workspace_id)
        queue = QueueStatus(
            queued=counts.queued,
            claimed=counts.claimed,
            expired_leases=counts.expired_leases,
            oldest_queued_seconds=counts.oldest_queued_seconds,
        )
        retention = RetentionSettings(run_days=policy.run_days, receipt_days=policy.receipt_days)
    return LocalStatus(
        schema_version=1,
        ready=is_ready(conditions),
        scope="workspace" if database_up else "installation",
        remote_tracing="disabled" if remote_tracing_disabled(os.environ) else "enabled",
        conditions=[
            OperationCondition(name=item.name, state=item.state, code=item.code)  # type: ignore[arg-type]
            for item in conditions
        ],
        queue=queue,
        retention=retention,
    )


@router.put("/operations/retention", operation_id="setRetention", response_model=RetentionSettings)
async def put_retention(
    body: RetentionSettings, request: Request, workspace_id: Owner, user_id: User
) -> RetentionSettings:
    async with _pool(request).connection() as connection:
        await write_policy(
            connection,
            workspace_id,
            user_id,
            RetentionPolicy(run_days=body.run_days, receipt_days=body.receipt_days),
        )
    return body


@router.post(
    "/operations/retention/apply",
    operation_id="applyRetention",
    response_model=RetentionApplied,
)
async def post_retention_apply(request: Request, workspace_id: Owner) -> RetentionApplied:
    async with _pool(request).connection() as connection:
        report = await apply_retention(
            connection, getattr(request.app.state, "object_store", None), workspace_id
        )
    return RetentionApplied(
        schema_version=1,
        purged_runs=report.purged_runs,
        refused=report.refused,
        keys_expired=report.keys_expired,
        objects_removed=report.objects_removed,
        objects_pending=report.objects_pending,
    )
