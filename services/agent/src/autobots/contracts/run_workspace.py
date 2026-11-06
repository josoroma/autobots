"""What the run workspace may see. Built by code from typed records, never from graph state."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from autobots.contracts.artifacts import ArtifactSummary
from autobots.contracts.primitives import Identifier, UtcTimestamp
from autobots.contracts.runs import RunEvent, RunSummary
from autobots.domain.runs import RunStatus

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


class ExpertBinding(BaseModel):
    """What this run was given. It can't use anything that isn't listed here."""

    model_config = VIEW

    name: str
    version: int
    tools: list[str]
    role_bindings: dict[str, str]


class AssignmentView(BaseModel):
    model_config = VIEW

    id: Identifier
    child_run_id: Identifier
    expert: str
    status: Literal["open", "finished"]
    outcome: str | None


class UnknownEffect(BaseModel):
    model_config = VIEW

    operation_id: str
    tool_id: str
    tool_version: int


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
    expert: ExpertBinding | None
    assignments: list[AssignmentView]
    outstanding: OutstandingSummary
    unknown_operations: list[UnknownEffect]
    cursor: int


class RunListItem(BaseModel):
    model_config = VIEW

    id: Identifier
    parent_run_id: Identifier | None
    status: RunStatus
    goal_summary: str
    created_at: UtcTimestamp


class RunList(BaseModel):
    """The newest of a workspace's runs. `has_more` says older ones aren't in this page."""

    model_config = VIEW

    schema_version: Literal[1]
    runs: list[RunListItem]
    has_more: bool


class ModelCallView(BaseModel):
    """One attempt's facts. Its partial output and any reasoning stay out of this view."""

    model_config = VIEW

    id: Identifier
    run_id: Identifier
    role: str
    attempt: int
    status: str
    provider: Literal["openrouter"]
    profile: str
    canonical_id: str
    wire_id: str
    upstream_provider: str
    input_tokens: int | None
    output_tokens: int | None
    reasoning_tokens: int | None
    created_at: UtcTimestamp


class ToolAttemptView(BaseModel):
    """What a tool operation did. Its arguments and result stay out of this view."""

    model_config = VIEW

    operation_id: str
    tool_id: str
    tool_version: int
    status: str
    failure_code: str | None
    created_at: UtcTimestamp


class CheckpointView(BaseModel):
    """That a checkpoint exists, and where. Never what it holds."""

    model_config = VIEW

    checkpoint_id: str
    parent_checkpoint_id: str | None
    step: int | None
    source: str | None


class RunInspector(BaseModel):
    model_config = VIEW

    schema_version: Literal[1]
    run: RunSummary
    goal_summary: str
    model_calls: list[ModelCallView]
    tool_attempts: list[ToolAttemptView]
    checkpoints: list[CheckpointView]
    checkpoints_truncated: bool
