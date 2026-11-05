"""What the run workspace may see. Built by code from typed records, never from graph state."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from autobots.contracts.artifacts import ArtifactSummary
from autobots.contracts.primitives import Identifier
from autobots.contracts.runs import RunEvent, RunSummary

VIEW = ConfigDict(extra="forbid", frozen=True)


class EventPage(BaseModel):
    """`gap` means retained events can't fill the range, so the client needs a snapshot."""

    model_config = VIEW

    schema_version: Literal[1]
    run_id: Identifier
    events: list[RunEvent]
    next_cursor: int
    gap: bool


class CriterionView(BaseModel):
    model_config = VIEW

    id: str
    text: str


class TaskView(BaseModel):
    model_config = VIEW

    id: str
    title: str
    status: Literal["open", "complete"]
    criteria: list[str]
    evidence_summary: str | None


class PlanSummary(BaseModel):
    model_config = VIEW

    version: int
    revision_reason: str | None
    tasks: list[TaskView]


class UsageSummary(BaseModel):
    model_config = VIEW

    model_calls: int
    tool_dispatches: int
    repairs: int
    plan_revisions: int


class VerificationSummary(BaseModel):
    model_config = VIEW

    passed: bool
    unmet: list[str]
    checks: int


class OutstandingSummary(BaseModel):
    """Known unknowns. These stay visible, even on a finished run."""

    model_config = VIEW

    uncertain_calls: int
    unknown_effects: int
    unreported_charges: int


class RunWorkspace(BaseModel):
    model_config = VIEW

    schema_version: Literal[1]
    run: RunSummary
    objective: str | None
    criteria: list[CriterionView]
    plan: PlanSummary | None
    artifacts: list[ArtifactSummary]
    usage: UsageSummary
    stop_reason: str | None
    verification: VerificationSummary | None
    outstanding: OutstandingSummary
    cursor: int
