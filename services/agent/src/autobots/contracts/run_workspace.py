"""What the run workspace may see. Built by code from typed records, never from graph state."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel

from autobots.contracts.artifacts import ArtifactSummary
from autobots.contracts.primitives import MAX_SAFE_INTEGER, Identifier, UtcTimestamp
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


# The named frames of `GET /v1/runs/{run_id}/events/stream`, which stays out of the OpenAPI paths
# (XTYP-07). `run` carries a stored RunEvent with its sequence as the replay id, `live` a
# result.text.delta with no id, `cursor` a StreamCursor, `gap` a StreamGap, and `end` an empty body.
StreamFrameName = Literal["run", "live", "cursor", "gap", "end"]
# A stream position: the API's `after` query takes any of these, and JavaScript holds each exactly.
StreamPosition = Annotated[int, Field(ge=0, le=MAX_SAFE_INTEGER)]


class StreamFrame(RootModel[StreamFrameName]):
    """A frame's name, exported so the browser listens for exactly these."""


class StreamCursor(BaseModel):
    """The newest sequence the stream has covered, so a reconnect resumes after it."""

    model_config = VIEW

    cursor: StreamPosition


class StreamGap(BaseModel):
    """Retained events can't fill the range after `after`, so the client reads a snapshot
    (SP-011)."""

    model_config = VIEW

    after: StreamPosition


# The run commands a person sends from a run's page (SP-010). Workers' commands and the input and
# approval commands, which have their own screens, are not among them.
UserRunCommand = Literal["pause", "resume", "cancel"]


class CriterionView(BaseModel):
    model_config = VIEW

    id: str
    text: str


class TaskView(BaseModel):
    """One plan task. `marker` is RN-04's done, current or to-do: the current task is the earliest
    open task that has started (RN-05). Times are database times the worker recorded on its fenced
    path. `wall_seconds` runs from start to finish, or to now for an open task that has started.
    `tools` are the tools uses served it, in first-use order, planning tools excepted."""

    model_config = VIEW

    id: str
    title: str
    status: Literal["open", "complete"]
    marker: Literal["done", "current", "to_do"]
    criteria: list[str]
    evidence_summary: str | None
    started_at: UtcTimestamp | None
    finished_at: UtcTimestamp | None
    wall_seconds: int | None
    tools: list[str]


class PlanSummary(BaseModel):
    model_config = VIEW

    version: int
    revision_reason: str | None
    tasks: list[TaskView]
    current_task_id: str | None


class UsageSummary(BaseModel):
    model_config = VIEW

    model_calls: int
    tool_dispatches: int
    repairs: int
    plan_revisions: int
    input_tokens: int
    output_tokens: int


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
    # Returned with a verdict, so one based on an earlier attempt can't settle a later one.
    generation: int


class RunBudgets(BaseModel):
    """MP-07's limits this run works under. Spend is on the run itself."""

    model_config = VIEW

    context_tokens: int
    max_output_tokens_per_call: int


class FrozenBinding(BaseModel):
    """One role's binding as this run froze it at admission, which later settings don't change."""

    model_config = VIEW

    role: str
    profile: str
    canonical_id: str
    wire_id: str
    # Which step of MP-01's order chose it. None for a run admitted before sources were recorded.
    source: (
        Literal["run_override", "workspace_override", "workspace_default", "builtin_default"] | None
    )


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
    role_map: list[FrozenBinding]
    budgets: RunBudgets
    # A goal run of its own that has finished. A child or a workflow's run isn't one.
    can_continue: bool
    # What a person may send this run now, in this order, as SP-010's next_status allows it. Any
    # member of the workspace may send these, so it is the same for an owner and a member.
    allowed_commands: list[UserRunCommand]
    # Decision 0017 Q4: metered tool calls made in this run's root tree, of what one tree may make.
    metered_tool_calls: int
    metered_tool_call_limit: int


RunListGroup = Literal["all", "active", "needs_you", "finished"]


class RunListItem(BaseModel):
    """One run's facts for the list (PRD-Studio RN-01). Spend is from the ledger: `charged` is
    reported or entered, `reserved` is held for calls not yet settled, and `unreported` marks a call
    whose charge was never reported. Either of the last two makes the amount an estimate."""

    model_config = VIEW

    id: Identifier
    parent_run_id: Identifier | None
    status: RunStatus
    goal_summary: str
    created_at: UtcTimestamp
    updated_at: UtcTimestamp
    label_kind: Literal["goal", "expert", "session", "workflow"]
    label: str | None
    stop_reason: str | None
    tasks_complete: int
    tasks_total: int
    profiles: list[str]
    charged_micro_usd: int
    reserved_micro_usd: int
    unreported: bool
    limit_micro_usd: int


class RunGroupCounts(BaseModel):
    model_config = VIEW

    all: int
    active: int
    needs_you: int
    finished: int


class RunList(BaseModel):
    """A page of a workspace's runs, newest first, with server counts per status group.

    `total` counts the selected group under the same filters. `next_cursor` continues the list
    after this page's last row, and `has_more` says that more rows exist.
    """

    model_config = VIEW

    schema_version: Literal[1]
    runs: list[RunListItem]
    has_more: bool
    next_cursor: str | None
    total: int
    counts: RunGroupCounts


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
    # What the provider reported, and the most this call could have cost. Never added together.
    reported_micro_usd: int | None
    estimated_micro_usd: int
    # The owner entered this charge. A late report from the provider doesn't count.
    reconciled: bool
    # The call was lost, so an owner's charge is all that's known of it.
    outcome_unknown: bool
    # Reconciled before the source was recorded, so nothing is claimed either way.
    charge_source_unknown: bool
    finish_reason: str | None
    failure_class: str | None
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


class EvidenceView(BaseModel):
    """What a completed task cited. The artifact, if it names one, is what to link."""

    model_config = VIEW

    task_id: str
    kind: str
    reference: str
    summary: str
    artifact_id: Identifier | None


class RunInspector(BaseModel):
    model_config = VIEW

    schema_version: Literal[1]
    run: RunSummary
    goal_summary: str
    model_calls: list[ModelCallView]
    tool_attempts: list[ToolAttemptView]
    checkpoints: list[CheckpointView]
    checkpoints_truncated: bool
    evidence: list[EvidenceView]
