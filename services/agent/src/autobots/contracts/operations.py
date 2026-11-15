"""Local Operations, SP-018: conditions and counts only. No address, path, identifier or secret."""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from autobots.contracts.primitives import LAX_CONTRACT, Count, UtcTimestamp
from autobots.contracts.settings import RouteQualification

Name = Literal["database", "schema", "hold", "adapter", "storage", "disk", "queue", "worker"]


class OperationCondition(BaseModel):
    model_config = LAX_CONTRACT

    name: Name
    state: Literal["ok", "degraded", "unavailable"]
    code: str


class QueueStatus(BaseModel):
    """This workspace's jobs."""

    model_config = LAX_CONTRACT

    queued: int = Field(ge=0)
    claimed: int = Field(ge=0)
    expired_leases: int = Field(ge=0)
    oldest_queued_seconds: int = Field(ge=0)


class RetentionSettings(BaseModel):
    """A null window keeps everything. Keys must outlive the run content they can answer for."""

    model_config = LAX_CONTRACT

    run_days: Count | None = Field(default=None, ge=1, le=36500)
    receipt_days: Count | None = Field(default=None, ge=1, le=36500)

    @model_validator(mode="after")
    def keys_outlive_content(self) -> "RetentionSettings":
        if self.receipt_days is None:
            return self
        if self.run_days is None:
            raise ValueError("receipt_days needs run_days: content kept for good keeps its keys")
        if self.receipt_days < self.run_days:
            raise ValueError("receipt_days can't be shorter than run_days")
        return self


class RetentionSummary(BaseModel):
    """PRD-Studio SE-06: the workspace's retention windows, which any member may read, and the
    reader's own role, so a page offers Operations to the owner only. Nothing here changes them."""

    model_config = LAX_CONTRACT

    schema_version: Literal[1]
    run_days: int | None = Field(ge=1)
    receipt_days: int | None = Field(ge=1)
    viewer_role: Literal["owner", "member"]


class DelayedOccurrence(BaseModel):
    """A routine occurrence that didn't run at its time, and the code for why."""

    model_config = LAX_CONTRACT

    routine: str
    occurrence_time: UtcTimestamp
    status: Literal["missed", "skipped_overlap", "blocked"]
    reason: str | None


class RestoreRecord(BaseModel):
    """One restore drill: when, and what its verification found. Never which instance or where."""

    model_config = LAX_CONTRACT

    at: UtcTimestamp
    result: Literal["passed", "failed", "not_verified"]
    checks_passed: int | None = Field(ge=0)
    checks_total: int | None = Field(ge=0)


class OperationValues(BaseModel):
    """Decision 0022 D5's measured values, and nothing more: numbers, a release name and a flag.
    No path, address, identifier or secret. Each is null when it can't be measured."""

    model_config = LAX_CONTRACT

    # The p95 of the last readiness probes' database answer times, and how many probes it covers.
    database_p95_ms: int | None = Field(ge=0)
    database_probes: int = Field(ge=0)
    applied_migrations: int | None = Field(ge=0)
    # Decision 0023 E2: how many migrations this release ships, to read the applied count against.
    shipped_migrations: int = Field(ge=0)
    # This workspace's published artifact bytes in Storage.
    storage_bytes: int | None = Field(ge=0)
    disk_free_bytes: int | None = Field(ge=0)
    disk_total_bytes: int | None = Field(ge=0)
    leased_jobs: int | None = Field(ge=0)
    queued_jobs: int | None = Field(ge=0)
    checkpoint_adapter: str = Field(pattern=r"^[a-z0-9-]+ [0-9A-Za-z.+-]+$")
    # How long this page load's catalog check took to answer.
    catalog_fetch_ms: int | None = Field(ge=0)
    # Whether every TCP socket the API listens on is bound to loopback.
    loopback_only: bool | None
    workers: int | None = Field(ge=0)


class LocalStatus(BaseModel):
    """`scope` is `installation` when the database is down, as no workspace can be verified."""

    model_config = LAX_CONTRACT

    schema_version: Literal[1]
    ready: bool
    scope: Literal["workspace", "installation"]
    remote_tracing: Literal["disabled", "enabled"]
    conditions: list[OperationCondition]
    queue: QueueStatus | None
    retention: RetentionSettings | None
    backup_age_hours: int | None = Field(ge=0)
    openrouter: Literal["available", "unavailable", "unknown"]
    delayed_schedules: list[DelayedOccurrence]
    restores: list[RestoreRecord]
    route_qualifications: list[RouteQualification]
    values: OperationValues


class JobHour(BaseModel):
    """One hour of the workspace's jobs (PRD-Studio OP-03, Decision 0022 D14). Counts only."""

    model_config = LAX_CONTRACT

    starts_at: UtcTimestamp
    # The hour's start in the workspace's timezone, as 14:00.
    hour: str = Field(pattern=r"^[0-2][0-9]:00$")
    succeeded: int = Field(ge=0)
    waited: int = Field(ge=0)
    failed: int = Field(ge=0)
    in_progress: int = Field(ge=0)


class JobsChart(BaseModel):
    """The last 24 hours, oldest first, in the workspace's timezone. No identifier, no goal text."""

    model_config = LAX_CONTRACT

    schema_version: Literal[1]
    timezone: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_+/-]+$")
    hours: list[JobHour] = Field(min_length=1, max_length=25)


class RetentionApplied(BaseModel):
    model_config = LAX_CONTRACT

    schema_version: Literal[1]
    purged_runs: int = Field(ge=0)
    refused: dict[str, int]
    keys_expired: int = Field(ge=0)
    objects_removed: int = Field(ge=0)
    objects_pending: int = Field(ge=0)


ServiceName = Literal["api", "worker", "database", "openrouter"]


class ServiceReadiness(BaseModel):
    """One service's readiness for members (PRD-Studio SH-04): a state and a code, nothing more."""

    model_config = LAX_CONTRACT

    name: ServiceName
    state: Literal["ready", "not_ready", "unknown"]
    code: str


class MemberReadiness(BaseModel):
    """Readiness any member may read. No counts, no paths, no identifiers, no secrets."""

    model_config = LAX_CONTRACT

    schema_version: Literal[1]
    ready: bool
    services: list[ServiceReadiness]
