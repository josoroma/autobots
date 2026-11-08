"""The initial public slice. Lease, checkpoint and credential fields are deliberately absent."""

from typing import Any, Literal

from pydantic import BaseModel, Field

from autobots.contracts.primitives import (
    STRICT_CONTRACT,
    Identifier,
    MicroUsd,
    Sequence,
    UtcTimestamp,
)
from autobots.domain.runs import RunStatus


class BudgetCounters(BaseModel):
    model_config = STRICT_CONTRACT

    spent_micro_usd: MicroUsd
    reserved_micro_usd: MicroUsd
    limit_micro_usd: MicroUsd


class RunSummary(BaseModel):
    model_config = STRICT_CONTRACT

    schema_version: Literal[1]
    version: int = Field(ge=1)
    id: Identifier
    workspace_id: Identifier
    parent_run_id: Identifier | None
    status: RunStatus
    created_at: UtcTimestamp
    updated_at: UtcTimestamp
    budget: BudgetCounters


class RunStatusChanged(BaseModel):
    model_config = STRICT_CONTRACT

    type: Literal["run.status_changed"]
    previous: RunStatus
    current: RunStatus


class ArtifactPublished(BaseModel):
    model_config = STRICT_CONTRACT

    type: Literal["artifact.published"]
    artifact_id: Identifier
    name: str
    sha256: str


class ArtifactMissing(BaseModel):
    model_config = STRICT_CONTRACT

    type: Literal["artifact.missing"]
    artifact_id: Identifier
    name: str


class ApprovalRequested(BaseModel):
    model_config = STRICT_CONTRACT

    type: Literal["approval.requested"]
    approval_id: Identifier
    tool_id: str


class ApprovalDecided(BaseModel):
    model_config = STRICT_CONTRACT

    type: Literal["approval.decided"]
    approval_id: Identifier
    decision: Literal["approved", "rejected", "expired"]


class EffectReconciled(BaseModel):
    model_config = STRICT_CONTRACT

    type: Literal["effect.reconciled"]
    operation_id: str
    outcome: Literal["delivered", "not_delivered"]


class ToolUseStarted(BaseModel):
    """Identifiers only. Public fields come from the tool-use listing, never the stream (TU-03)."""

    model_config = STRICT_CONTRACT

    type: Literal["tool.use.started"]
    tool_use_id: Sequence
    tool_id: str
    tool_version: int | None
    group: str | None
    task_id: str | None


class ToolUseCompleted(BaseModel):
    model_config = STRICT_CONTRACT

    type: Literal["tool.use.completed"]
    tool_use_id: Sequence
    tool_id: str
    tool_version: int | None
    outcome: Literal["succeeded", "failed", "unknown", "denied"]
    code: str | None
    duration_ms: int = Field(ge=0)
    operation_id: str | None


class ResultTextDelta(BaseModel):
    """US-15.24, PRD-Studio ST-01: result text while it's written. Ephemeral and coalesced: it is
    only ever sent live and never stored, and the stored artifact is what counts. `segment` numbers
    each result file a run writes; `offset` is where in that file's text this piece begins."""

    model_config = STRICT_CONTRACT

    type: Literal["result.text.delta"]
    segment: int = Field(ge=1)
    offset: int = Field(ge=0)
    text: str = Field(min_length=1, max_length=2000)


class RunEvent(BaseModel):
    """The sanitized public envelope from SP-011. Payloads are typed, so nothing raw can pass."""

    model_config = STRICT_CONTRACT

    schema_version: Literal[1]
    run_id: Identifier
    sequence: Sequence
    causal_ids: list[Identifier]
    occurred_at: UtcTimestamp
    payload: (
        RunStatusChanged
        | ArtifactPublished
        | ArtifactMissing
        | ApprovalRequested
        | ApprovalDecided
        | EffectReconciled
        | ToolUseStarted
        | ToolUseCompleted
        | ResultTextDelta
    )


class ErrorResponse(BaseModel):
    model_config = STRICT_CONTRACT

    code: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=2000)


class ToolUseView(BaseModel):
    """One dispatch: when, why (the plan task), for what (public fields, digests, sizes), how."""

    model_config = STRICT_CONTRACT

    id: Sequence
    run_id: Identifier
    sequence_in_run: int
    tool_id: str
    tool_version: int | None
    group: str | None
    provider: str | None
    plan_version: int | None
    task_id: str | None
    task_title: str | None
    requested_at: UtcTimestamp
    finished_at: UtcTimestamp | None
    duration_ms: int | None
    outcome: Literal["succeeded", "failed", "unknown", "denied"] | None
    code: str | None
    input_public: dict[str, Any]
    output_public: dict[str, Any] | None
    input_digest: str
    output_bytes: int | None
    operation_id: str | None
    provider_units: float | None
    # The workflow node instance that made it, when one did (TV-02).
    instance_key: str | None


class ToolUseList(BaseModel):
    model_config = STRICT_CONTRACT

    schema_version: Literal[1]
    run_id: Identifier
    uses: list[ToolUseView]
    next_cursor: int | None
