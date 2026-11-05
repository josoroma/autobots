"""Requests and responses for run admission and commands."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from autobots.contracts.plans import InputDocument, RequiredArtifact
from autobots.contracts.primitives import STRICT_CONTRACT, Identifier, MicroUsd
from autobots.domain.runs import RunStatus


class RunRequest(BaseModel):
    """Not strict, since a UUID arrives here as a JSON string."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    continues_run_id: Identifier | None = None
    session_id: Identifier | None = None
    expert_id: Identifier | None = None
    expert_version: int | None = Field(default=None, ge=1)
    goal_text: str = Field(min_length=1, max_length=20000)
    limit_micro_usd: MicroUsd = 1_000_000
    acceptance_criteria: list[str] = Field(default_factory=list, max_length=20)
    required_artifacts: list[RequiredArtifact] = Field(default_factory=list, max_length=20)
    input_documents: list[InputDocument] = Field(default_factory=list, max_length=10)


class RunAccepted(BaseModel):
    """Not strict, since it is built from database values. It is validated as it is built."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1]
    run_id: Identifier
    version: int
    status: RunStatus
    replayed: bool


class RunCommandRequest(BaseModel):
    model_config = STRICT_CONTRACT

    expected_version: int = Field(ge=1)


class RunInputRequest(BaseModel):
    model_config = STRICT_CONTRACT

    expected_version: int = Field(ge=1)
    value: str = Field(min_length=1, max_length=20000)


class EffectEvidence(BaseModel):
    """What the destination's own records show. This is a person's report, kept as evidence."""

    model_config = STRICT_CONTRACT

    outcome: Literal["delivered", "not_delivered"]
    evidence: str = Field(min_length=1, max_length=2000)


class ModelCallReconciliation(BaseModel):
    """What the provider reported, from its own records. A charge is never invented."""

    model_config = STRICT_CONTRACT

    charged_micro_usd: int = Field(ge=0)


class ReconciliationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1]
    reconciled_calls: int


class RunCommandResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1]
    run_id: Identifier
    version: int
    status: RunStatus
    changed: bool
