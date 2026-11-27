"""Local Operations. It has to answer with the database down, so a signed-in user is enough then."""

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request

from autobots.api.dependencies import (
    CurrentUser,
    MemberWorkspace,
    OwnerWorkspace,
    installation_conditions_of,
    is_owner,
    operations_workspace,
    probe_times,
    readiness_workspace,
    require_ready,
)
from autobots.api.model_source_routes import local_health
from autobots.api.pool import Pool
from autobots.api.resources import app_resources, request_pool
from autobots.api.security import app_settings, require_internal
from autobots.application.backups import BackupStatus, backup_status
from autobots.application.catalog_check import OPERATIONS_SECONDS, CatalogCheck, check_catalog
from autobots.application.job_activity import delayed_occurrences, delayed_view, job_hours
from autobots.application.model_policy import read_model_policy
from autobots.application.model_source import offered_local_profiles
from autobots.application.operation_values import disk_bytes, loopback_only, stored_bytes
from autobots.application.operations import (
    Condition,
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
from autobots.application.provider_settings import (
    ProviderSettings,
    read_route_qualifications,
    workspace_model_source,
)
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
from autobots.domain.models import ModelProfileId, ModelSource
from autobots.logs import remote_tracing_disabled

router = APIRouter(prefix="/v1", dependencies=[Depends(require_internal)])


def _restore_records(items: list[dict[str, Any]]) -> list[RestoreRecord]:
    """A line of the right shape with a bad value is skipped too, so the page still answers."""
    records = []
    for item in items:
        try:
            records.append(RestoreRecord.model_validate(item))
        except ValueError:
            continue
    return records


def _database_up(conditions: list[Condition]) -> bool:
    """The database and its schema both answer, found by name, whatever their place in the list."""
    states = {item.name: item.state for item in conditions}
    return states.get("database") == "ok" and states.get("schema") == "ok"


@dataclass(frozen=True)
class _WorkspaceOperations:
    """What Operations reads for the owner's workspace, on one connection."""

    conditions: tuple[Condition, Condition]
    queue: QueueStatus
    retention: RetentionSettings
    delayed: list[DelayedOccurrence]
    qualifications: list[RouteQualification]
    workers: int
    migrations: int | None
    storage_used: int
    source: ModelSource = ModelSource.OPENROUTER


async def _workspace_operations(pool: Pool, workspace_id: UUID) -> _WorkspaceOperations:
    async with pool.connection() as connection:
        counts = await queue_counts(connection, workspace_id)
        queue = queue_condition(counts)
        worker = await worker_condition(connection, counts)
        policy = await read_policy(connection, workspace_id)
        delayed = [
            delayed_view(row, public_text(row.name))
            for row in await delayed_occurrences(connection, workspace_id)
        ]
        qualifications = await read_route_qualifications(connection)
        workers = await live_workers(connection)
        migrations = await applied_migrations(connection)
        storage_used = await stored_bytes(connection, workspace_id)
        source = await workspace_model_source(connection, workspace_id)
    return _WorkspaceOperations(
        conditions=(queue, worker),
        queue=QueueStatus(
            queued=counts.queued,
            claimed=counts.claimed,
            expired_leases=counts.expired_leases,
            oldest_queued_seconds=counts.oldest_queued_seconds,
        ),
        retention=RetentionSettings(run_days=policy.run_days, receipt_days=policy.receipt_days),
        delayed=delayed,
        qualifications=qualifications,
        workers=workers,
        migrations=migrations,
        storage_used=storage_used,
        source=source,
    )


@dataclass(frozen=True)
class _ProcessFacts:
    """What this process knows of itself and its host when the page asks."""

    disk: tuple[int, int] | None
    probe_p95_ms: int | None
    probes: int
    remote_tracing_off: bool
    loopback_only: bool | None
    checkpoint_adapter: str


def _local_status(
    conditions: list[Condition],
    workspace: _WorkspaceOperations | None,
    catalog: CatalogCheck,
    backups: BackupStatus,
    process: _ProcessFacts,
) -> LocalStatus:
    """Decision 0022 D5's values from what was read. No workspace means the database is down."""
    shown: list[Condition] = [*conditions, *(workspace.conditions if workspace else ())]
    queue = workspace.queue if workspace else None
    return LocalStatus(
        schema_version=1,
        ready=is_ready(shown),
        scope="workspace" if workspace else "installation",
        remote_tracing="disabled" if process.remote_tracing_off else "enabled",
        conditions=[
            OperationCondition(name=item.name, state=item.state, code=item.code) for item in shown
        ],
        queue=queue,
        retention=workspace.retention if workspace else None,
        backup_age_hours=backups.age_hours,
        openrouter=catalog.status,
        delayed_schedules=workspace.delayed if workspace else [],
        restores=_restore_records(backups.restores),
        route_qualifications=workspace.qualifications if workspace else [],
        values=OperationValues(
            database_p95_ms=process.probe_p95_ms,
            database_probes=process.probes,
            applied_migrations=workspace.migrations if workspace else None,
            shipped_migrations=SHIPPED_MIGRATIONS,
            storage_bytes=workspace.storage_used if workspace else None,
            disk_free_bytes=process.disk[0] if process.disk else None,
            disk_total_bytes=process.disk[1] if process.disk else None,
            leased_jobs=queue.claimed if queue else None,
            queued_jobs=queue.queued if queue else None,
            checkpoint_adapter=process.checkpoint_adapter,
            catalog_fetch_ms=catalog.milliseconds,
            loopback_only=process.loopback_only,
            workers=workspace.workers if workspace else None,
        ),
    )


@router.get("/operations/local-status", operation_id="getLocalStatus", response_model=LocalStatus)
async def get_local_status(
    request: Request,
    user_id: CurrentUser,
    x_autobots_workspace: Annotated[UUID | None, Header()] = None,
) -> LocalStatus:
    conditions = await installation_conditions_of(request)
    workspace_id = await operations_workspace(
        request, user_id, x_autobots_workspace, database_up=_database_up(conditions)
    )
    workspace = (
        None
        if workspace_id is None
        else await _workspace_operations(request_pool(request), workspace_id)
    )
    context = app_resources(request).provider_context
    # On Local nothing is sent to OpenRouter, its catalog included (Decision 0041 A13).
    local = workspace is not None and workspace.source is ModelSource.LOCAL
    catalog = await check_catalog(
        None if context is None or local else context.fetch_catalog, OPERATIONS_SECONDS
    )
    settings = app_settings(request)
    backups = await backup_status(settings.backup_dir, datetime.now(UTC))
    probes = probe_times(request)
    process = _ProcessFacts(
        disk=disk_bytes(settings.readiness.data_root),
        probe_p95_ms=probes.p95(),
        probes=probes.count(),
        # The live environment on purpose: it shows whether tracing is off in this process now,
        # after forbid_remote_tracing changed it at start.
        remote_tracing_off=remote_tracing_disabled(os.environ),
        loopback_only=loopback_only(),
        checkpoint_adapter=checkpoint_adapter(),
    )
    return _local_status(conditions, workspace, catalog, backups, process)


@router.get("/operations/jobs", operation_id="getJobsChart", response_model=JobsChart)
async def get_jobs_chart(request: Request, workspace_id: OwnerWorkspace) -> JobsChart:
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
    user_id: CurrentUser,
    workspace_id: MemberWorkspace,
) -> RetentionSummary:
    """PRD-Studio SE-06: read-only for any member. Only the owner changes it, on Operations."""
    owner = await is_owner(request, user_id, workspace_id)
    async with request_pool(request).connection() as connection:
        policy = await read_policy(connection, workspace_id)
    return RetentionSummary(
        schema_version=1,
        run_days=policy.run_days,
        receipt_days=policy.receipt_days,
        viewer_role="owner" if owner else "member",
    )


@router.put("/operations/retention", operation_id="setRetention", response_model=RetentionSettings)
async def put_retention(
    body: RetentionSettings, request: Request, workspace_id: OwnerWorkspace, user_id: CurrentUser
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
async def post_retention_apply(request: Request, workspace_id: OwnerWorkspace) -> RetentionApplied:
    async with request_pool(request).connection() as connection:
        report = await apply_retention(
            connection, app_resources(request).object_store, workspace_id
        )
    return RetentionApplied(
        schema_version=1,
        purged_runs=report.purged_runs,
        refused=report.refused,
        keys_expired=report.keys_expired,
        objects_removed=report.objects_removed,
        objects_pending=report.objects_pending,
    )


async def _local_model_service(
    request: Request, chosen: str | None, offered: list[ModelProfileId]
) -> ServiceReadiness:
    """On Local, the model service is the owner's llama-server, from its model ID check alone, so
    Home never waits on a hash and nothing reaches OpenRouter (Decision 0041 A13)."""
    profile = ModelProfileId(chosen) if chosen is not None else (offered[0] if offered else None)
    if profile is None:
        return ServiceReadiness(name="local_model", state="not_ready", code="local_not_offered")
    health = await local_health(app_resources(request), profile, with_digest=False)
    return ServiceReadiness(
        name="local_model",
        state="ready" if health.status == "ready" else "not_ready",
        code=f"local_{health.status}",
    )


@router.get("/readiness", operation_id="getReadiness", response_model=MemberReadiness)
async def get_readiness(
    request: Request,
    user_id: CurrentUser,
    x_autobots_workspace: Annotated[UUID | None, Header()] = None,
) -> MemberReadiness:
    """PRD-Studio SH-04 and HM-05: any member's view, with states and codes only.

    The workspace is the chosen one, verified, or else the session's first, as the shell's footer
    shows it. A user with no workspace is refused.
    """
    workspace_id = await readiness_workspace(request, user_id, x_autobots_workspace)
    database, schema, *_rest = await database_conditions(
        app_resources(request).pool, probe_times(request)
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
        stored = await read_model_policy(connection, workspace_id)
        context = app_resources(request).provider_context
        auth = (
            await ProviderSettings(connection, context).auth_status(workspace_id)
            if context is not None and stored.model_source is ModelSource.OPENROUTER
            else "unavailable"
        )
        offered = sorted(await offered_local_profiles(connection))
    services.append(
        ServiceReadiness(
            name="worker", state="ready" if worker.state == "ok" else "not_ready", code=worker.code
        )
    )
    services.append(ServiceReadiness(name="database", state="ready", code="database_ready"))
    if stored.model_source is ModelSource.LOCAL:
        services.append(await _local_model_service(request, stored.local_profile, offered))
    else:
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
