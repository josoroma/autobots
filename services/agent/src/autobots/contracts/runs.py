"""The initial public slice. Lease, checkpoint and credential fields are deliberately absent."""

from typing import Literal

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


class RunEvent(BaseModel):
    """The sanitized public envelope from SP-011. Payloads are typed, so nothing raw can pass."""

    model_config = STRICT_CONTRACT

    schema_version: Literal[1]
    run_id: Identifier
    sequence: Sequence
    causal_ids: list[Identifier]
    occurred_at: UtcTimestamp
    payload: RunStatusChanged


class ErrorResponse(BaseModel):
    model_config = STRICT_CONTRACT

    code: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=2000)
