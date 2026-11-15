"""Local Operations. It has to answer with the database down, so a signed-in user is enough then."""

import os
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request

from autobots.api.errors import ApiError
from autobots.api.pool import request_pool
from autobots.api.security import current_user, require_internal
from autobots.api.settings import Settings
from autobots.api.settings_routes import current_workspace, require_owner
from autobots.application.backups import backup_status
from autobots.application.catalog_check import OPERATIONS_SECONDS, check_catalog
from autobots.application.job_activity import delayed_occurrences, job_hours
from autobots.application.operation_values import disk_bytes, loopback_only, stored_bytes
from autobots.application.operations import (
    Condition,
    ProbeTimes,
    QueueCounts,
    applied_migrations,
    checkpoint_adapter,
    database_conditions,
    is_ready,
    live_workers,
    queue_condition,
    queue_counts,
    worker_condition,
)
from autobots.application.provider_settings import ProviderSettings, read_route_qualifications
from autobots.application.readiness import first_blocking, installation_conditions
from autobots.application.retention import (
    RetentionPolicy,
    apply_retention,
    read_policy,
    write_policy,
)
from autobots.application.run_projection import public_text
from autobots.application.schema_release import SHIPPED_MIGRATIONS
from autobots.contracts.operations import (
    DelayedOccurrence,
    JobHour,
    JobsChart,
    LocalStatus,
    MemberReadiness,
    OperationCondition,
    OperationValues,
    QueueStatus,
    RestoreRecord,
    RetentionApplied,
    RetentionSettings,
    RetentionSummary,
    ServiceReadiness,
)
from autobots.contracts.settings import RouteQualification
from autobots.logs import remote_tracing_disabled

router = APIRouter(prefix="/v1", dependencies=[Depends(require_internal)])
Owner = Annotated[UUID, Depends(require_owner)]
User = Annotated[UUID, Depends(current_user)]


def probe_times(request: Request) -> ProbeTimes:
    """This process's readiness probe window, made on first use."""
    probes = getattr(request.app.state, "probe_times", None)
    if probes is None:
        probes = ProbeTimes()
        request.app.state.probe_times = probes
    return probes


def process_settings(request: Request) -> Settings:
    """What the entry point read from the environment once, at start (PAPI-10)."""
    settings: Settings = request.app.state.settings
    return settings


async def _installation_conditions(request: Request) -> list[Condition]:
    return await installation_conditions(
        request.app.state.pool,
        getattr(request.app.state, "object_store", None),
        process_settings(request).readiness,
        probe_times(request),
    )


async def require_ready(request: Request) -> None:
    """Admission stops when required persistence is unhealthy (LM-07), before any job can exist.
    A due routine waits on the same gate in the worker (Decision 0023 E2)."""
    if first_blocking(await _installation_conditions(request)) is not None:
        raise ApiError(503, "not_ready", "Local services aren't ready, so nothing was started.")


def _restore_records(items: list[dict[str, Any]]) -> list[RestoreRecord]:
    """A line of the right shape with a bad value is skipped too, so the page still answers."""
    records = []
    for item in items:
        try:
            records.append(RestoreRecord.model_validate(item))
        except ValueError:
            continue
    return records


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
    delayed: list[DelayedOccurrence] = []
    qualifications: list[RouteQualification] = []
    workers: int | None = None
    migrations: int | None = None
    storage_used: int | None = None
    if database_up:
        workspace_id = await current_workspace(request, user_id, x_autobots_workspace)
        if await request.app.state.membership.role_in(user_id, workspace_id) != "owner":
            raise ApiError(403, "owner_required", "Only the workspace owner can see this.")
        async with request_pool(request).connection() as connection:
            counts = await queue_counts(connection, workspace_id)
            conditions.append(queue_condition(counts))
            conditions.append(await worker_condition(connection, counts))
            policy = await read_policy(connection, workspace_id)
            delayed = [
                DelayedOccurrence(
                    routine=public_text(row[0]),
                    occurrence_time=row[1],
                    status=row[2],
                    reason=row[3],
                )
                for row in await delayed_occurrences(connection, workspace_id)
            ]
            qualifications = await read_route_qualifications(connection)
            workers = await live_workers(connection)
            migrations = await applied_migrations(connection)
            storage_used = await stored_bytes(connection, workspace_id)
        queue = QueueStatus(
            queued=counts.queued,
            claimed=counts.claimed,
            expired_leases=counts.expired_leases,
            oldest_queued_seconds=counts.oldest_queued_seconds,
        )
        retention = RetentionSettings(run_days=policy.run_days, receipt_days=policy.receipt_days)
    catalog = await check_catalog(
        getattr(getattr(request.app.state, "provider_context", None), "fetch_catalog", None),
        OPERATIONS_SECONDS,
    )
    settings = process_settings(request)
    backups = await backup_status(settings.backup_dir, datetime.now(UTC))
    disk = disk_bytes(settings.readiness.data_root)
    probes = probe_times(request)
    return LocalStatus(
        schema_version=1,
        ready=is_ready(conditions),
        scope="workspace" if database_up else "installation",
        # The live environment on purpose: it shows whether tracing is off in this process now,
        # after forbid_remote_tracing changed it at start.
        remote_tracing="disabled" if remote_tracing_disabled(os.environ) else "enabled",
        conditions=[
            OperationCondition(name=item.name, state=item.state, code=item.code)  # type: ignore[arg-type]  # a str that pydantic validates against the field's Literal
            for item in conditions
        ],
        queue=queue,
        retention=retention,
        backup_age_hours=backups.age_hours,
        openrouter=catalog.status,
        delayed_schedules=delayed,
        restores=_restore_records(backups.restores),
        route_qualifications=qualifications,
        values=OperationValues(
            database_p95_ms=probes.p95(),
            database_probes=probes.count(),
            applied_migrations=migrations,
            shipped_migrations=SHIPPED_MIGRATIONS,
            storage_bytes=storage_used,
            disk_free_bytes=disk[0] if disk else None,
            disk_total_bytes=disk[1] if disk else None,
            leased_jobs=queue.claimed if queue else None,
            queued_jobs=queue.queued if queue else None,
            checkpoint_adapter=checkpoint_adapter(),
            catalog_fetch_ms=catalog.milliseconds,
            loopback_only=loopback_only(),
            workers=workers,
        ),
    )


@router.get("/operations/jobs", operation_id="getJobsChart", response_model=JobsChart)
async def get_jobs_chart(request: Request, workspace_id: Owner) -> JobsChart:
    """PRD-Studio OP-03: the workspace's jobs per hour over 24 hours, by outcome. Counts only."""
    async with request_pool(request).connection() as connection:
        zone, hours = await job_hours(connection, workspace_id)
    return JobsChart(
        schema_version=1,
        timezone=zone,
        hours=[
            JobHour(
                starts_at=item.starts_at.astimezone(UTC),
                hour=item.hour,
                succeeded=item.succeeded,
                waited=item.waited,
                failed=item.failed,
                in_progress=item.in_progress,
            )
            for item in hours
        ],
    )


@router.get("/retention", operation_id="getRetentionSummary", response_model=RetentionSummary)
async def get_retention_summary(
    request: Request,
    user_id: User,
    workspace_id: Annotated[UUID, Depends(current_workspace)],
) -> RetentionSummary:
    """PRD-Studio SE-06: read-only for any member. Only the owner changes it, on Operations."""
    role = await request.app.state.membership.role_in(user_id, workspace_id)
    async with request_pool(request).connection() as connection:
        policy = await read_policy(connection, workspace_id)
    return RetentionSummary(
        schema_version=1,
        run_days=policy.run_days,
        receipt_days=policy.receipt_days,
        viewer_role="owner" if role == "owner" else "member",
    )


@router.put("/operations/retention", operation_id="setRetention", response_model=RetentionSettings)
async def put_retention(
    body: RetentionSettings, request: Request, workspace_id: Owner, user_id: User
) -> RetentionSettings:
    async with request_pool(request).connection() as connection:
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
    dependencies=[Depends(require_ready)],
    response_model=RetentionApplied,
)
async def post_retention_apply(request: Request, workspace_id: Owner) -> RetentionApplied:
    async with request_pool(request).connection() as connection:
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


@router.get("/readiness", operation_id="getReadiness", response_model=MemberReadiness)
async def get_readiness(
    request: Request,
    user_id: Annotated[UUID, Depends(current_user)],
    x_autobots_workspace: Annotated[UUID | None, Header()] = None,
) -> MemberReadiness:
    """PRD-Studio SH-04 and HM-05: any member's view, with states and codes only.

    The workspace is the chosen one, verified, or else the session's first, as the shell's footer
    shows it. A user with no workspace is refused.
    """
    workspaces = await request.app.state.membership.workspaces_for(user_id)
    if x_autobots_workspace is not None and x_autobots_workspace not in workspaces:
        raise ApiError(403, "forbidden", "This workspace is not available.")
    if not workspaces:
        raise ApiError(403, "forbidden", "This workspace is not available.")
    workspace_id = x_autobots_workspace or sorted(workspaces)[0]
    database, schema, *_rest = await database_conditions(
        request.app.state.pool, probe_times(request)
    )
    database_up = database.state == "ok" and schema.state == "ok"
    services = [ServiceReadiness(name="api", state="ready", code="api_ready")]
    if not database_up:
        services.append(ServiceReadiness(name="worker", state="unknown", code="database_unready"))
        services.append(ServiceReadiness(name="database", state="not_ready", code=database.code))
        services.append(
            ServiceReadiness(name="openrouter", state="unknown", code="database_unready")
        )
        return MemberReadiness(schema_version=1, ready=False, services=services)
    async with request_pool(request).connection() as connection:
        worker = await worker_condition(connection, QueueCounts(0, 0, 0, 0))
        context = request.app.state.provider_context
        auth = (
            await ProviderSettings(connection, context).auth_status(workspace_id)
            if context is not None
            else "unavailable"
        )
    services.append(
        ServiceReadiness(
            name="worker", state="ready" if worker.state == "ok" else "not_ready", code=worker.code
        )
    )
    services.append(ServiceReadiness(name="database", state="ready", code="database_ready"))
    services.append(
        ServiceReadiness(
            name="openrouter",
            state="ready" if auth == "configured" else "not_ready",
            code=f"auth_{auth}",
        )
    )
    return MemberReadiness(
        schema_version=1,
        ready=all(item.state == "ready" for item in services),
        services=services,
    )
