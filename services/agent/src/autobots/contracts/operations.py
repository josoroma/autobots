"""Local Operations, SP-018: conditions and counts only. No address, path, identifier or secret."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

VIEW = ConfigDict(extra="forbid", frozen=True)
Name = Literal["database", "schema", "hold", "adapter", "storage", "disk", "queue", "worker"]


class OperationCondition(BaseModel):
    model_config = VIEW

    name: Name
    state: Literal["ok", "degraded", "unavailable"]
    code: str


class QueueStatus(BaseModel):
    """This workspace's jobs."""

    model_config = VIEW

    queued: int = Field(ge=0)
    claimed: int = Field(ge=0)
    expired_leases: int = Field(ge=0)
    oldest_queued_seconds: int = Field(ge=0)


class RetentionSettings(BaseModel):
    """A null window keeps everything. Keys must outlive the run content they can answer for."""

    model_config = VIEW

    run_days: int | None = Field(default=None, ge=1, le=36500)
    receipt_days: int | None = Field(default=None, ge=1, le=36500)

    @model_validator(mode="after")
    def keys_outlive_content(self) -> "RetentionSettings":
        if self.receipt_days is None:
            return self
        if self.run_days is None:
            raise ValueError("receipt_days needs run_days: content kept for good keeps its keys")
        if self.receipt_days < self.run_days:
            raise ValueError("receipt_days can't be shorter than run_days")
        return self


class LocalStatus(BaseModel):
    """`scope` is `installation` when the database is down, as no workspace can be verified."""

    model_config = VIEW

    schema_version: Literal[1]
    ready: bool
    scope: Literal["workspace", "installation"]
    remote_tracing: Literal["disabled", "enabled"]
    conditions: list[OperationCondition]
    queue: QueueStatus | None
    retention: RetentionSettings | None
    backup_age_hours: int | None = Field(ge=0)


class RetentionApplied(BaseModel):
    model_config = VIEW

    schema_version: Literal[1]
    purged_runs: int = Field(ge=0)
    refused: dict[str, int]
    keys_expired: int = Field(ge=0)
    objects_removed: int = Field(ge=0)
    objects_pending: int = Field(ge=0)
