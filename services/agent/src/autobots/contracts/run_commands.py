"""Requests and responses for run admission and commands."""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from autobots.contracts.plans import InputDocument, RequiredArtifact
from autobots.contracts.primitives import (
    LAX_CONTRACT,
    STRICT_CONTRACT,
    Identifier,
    MicroUsd,
    Version,
)
from autobots.domain.models import ModelProfileId
from autobots.domain.runs import RunStatus


class RunRequest(BaseModel):
    # Lax, since a UUID arrives here as a JSON string. Money and versions are strict values.

    model_config = LAX_CONTRACT

    continues_run_id: Identifier | None = None
    session_id: Identifier | None = None
    expert_id: Identifier | None = None
    expert_version: Version | None = None
    # Left out, a continued run repeats the earlier run's stored goal. Otherwise required.
    goal_text: str | None = Field(default=None, min_length=1, max_length=20000)
    limit_micro_usd: MicroUsd = 1_000_000
    # A person's chosen budget, Decision 0022 D11: US$0.25 to US$5.00 in US$0.25 steps and not
    # above what's left of the daily cap. It becomes the run's frozen limit. Not with a limit.
    budget_micro_usd: MicroUsd | None = None
    # One approved model for this run alone. An unknown value is refused, and no run starts.
    run_profile: ModelProfileId | None = None
    acceptance_criteria: list[str] = Field(default_factory=list, max_length=20)
    required_artifacts: list[RequiredArtifact] = Field(default_factory=list, max_length=20)
    input_documents: list[InputDocument] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def _has_a_goal(self) -> "RunRequest":
        if self.goal_text is None and self.continues_run_id is None:
            raise ValueError("goal_text is required unless continuing a run")
        return self


class RunAccepted(BaseModel):
    # Not strict, since it is built from database values. It is validated as it is built.

    model_config = LAX_CONTRACT

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


# What a person found at the destination. Reconciliation takes the same values (PTOL-15).
EffectOutcome = Literal["delivered", "not_delivered"]


class EffectEvidence(BaseModel):
    """What the destination's own records show. This is a person's report, kept as evidence."""

    model_config = STRICT_CONTRACT

    outcome: EffectOutcome
    evidence: str = Field(min_length=1, max_length=2000)
    generation: int


class ModelCallReconciliation(BaseModel):
    """What the provider reported, from its own records. A charge is never invented."""

    model_config = STRICT_CONTRACT

    charged_micro_usd: MicroUsd


class ReconciliationResult(BaseModel):
    model_config = LAX_CONTRACT

    schema_version: Literal[1]
    reconciled_calls: int


class RunCommandResult(BaseModel):
    model_config = LAX_CONTRACT

    schema_version: Literal[1]
    run_id: Identifier
    version: int
    status: RunStatus
    changed: bool
