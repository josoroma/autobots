"""What a query returns (refactor plan R-54, XTYP-04, PDOM-08). SQL migrations own the schema.

Each row is one statement's select list: its fields are the columns' aliases, so the application
builds it by column name (application/sql.py) and a missing, extra or duplicate column raises. A
field holds the stored value as psycopg reads it, such as a status as text. A row is never a public
response: the read that selects it maps it explicitly, converting a vocabulary there.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

# A run's views (application/run_projection)


@dataclass(frozen=True, slots=True, kw_only=True)
class RunRow:
    """A run as its views read it, with the ledger's figures (Decision 0029 F10) and the sequence
    its event cursor starts from."""

    id: UUID
    workspace_id: UUID
    parent_run_id: UUID | None
    status: str
    created_at: datetime
    updated_at: datetime
    charged_micro_usd: int
    reserved_micro_usd: int
    limit_micro_usd: int
    lease_generation: int
    checkpoint_thread_id: str | None
    version: int
    event_sequence: int


@dataclass(frozen=True, slots=True, kw_only=True)
class RunEventRow:
    sequence: int
    payload: object
    occurred_at: datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class TaskTimeRow:
    task_id: str
    started_at: datetime
    finished_at: datetime | None
    wall_seconds: int


@dataclass(frozen=True, slots=True, kw_only=True)
class VerificationRow:
    passed: bool
    unmet: list[str]
    checks: int


@dataclass(frozen=True, slots=True, kw_only=True)
class AssignmentViewRow:
    id: UUID
    child_run_id: UUID
    expert: str
    status: str
    outcome: str | None


@dataclass(frozen=True, slots=True, kw_only=True)
class ExpertBindingRow:
    name: str
    version: int
    allowed_tools: dict[str, int]
    role_bindings: dict[str, str] | None
    frozen_bindings: dict[str, str] | None


@dataclass(frozen=True, slots=True, kw_only=True)
class RunUsageRow:
    model_calls: int
    tool_dispatches: int
    repairs: int
    plan_revisions: int
    stop_reason: str | None


@dataclass(frozen=True, slots=True, kw_only=True)
class RunGroupCountRow:
    total: int
    active: int
    needs_you: int
    finished: int


@dataclass(frozen=True, slots=True, kw_only=True)
class RunListRow:
    id: UUID
    parent_run_id: UUID | None
    status: str
    goal_summary: str
    created_at: datetime
    updated_at: datetime
    label_kind: str
    label: str | None
    stop_reason: str | None
    tasks_total: int
    tasks_complete: int
    profiles: list[str]
    charged_micro_usd: int
    reserved_micro_usd: int
    unreported: bool
    limit_micro_usd: int


@dataclass(frozen=True, slots=True, kw_only=True)
class InspectedRunRow:
    goal_summary: str
    policy_snapshot: object
    thread_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ModelCallRow:
    id: UUID
    run_id: UUID
    role: str
    attempt: int
    status: str
    profile: str
    wire_id: str
    upstream_provider: str | None
    input_tokens: int | None
    output_tokens: int | None
    reasoning_tokens: int | None
    charged_micro_usd: int | None
    reserved_micro_usd: int
    finish_reason: str | None
    failure_class: str | None
    created_at: datetime
    reconciled: bool
    charge_source_unknown: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class ToolAttemptRow:
    operation_id: str
    tool_id: str
    tool_version: int
    status: str
    failure_code: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class CheckpointRow:
    checkpoint_id: str
    parent_checkpoint_id: str | None
    step: int | None
    source: str | None


@dataclass(frozen=True, slots=True, kw_only=True)
class PlanEvidenceRow:
    task_id: str
    evidence: list[dict[str, object]] | None
    summary: str


# Runs, jobs and leases (application/runs.py, application/worker_leases.py)


@dataclass(frozen=True, slots=True, kw_only=True)
class LockedJobRow:
    status: str
    generation: int | None
    lease_live: bool | None


@dataclass(frozen=True, slots=True, kw_only=True)
class OpenAssignmentRow:
    id: UUID
    child_run_id: UUID
    status: str


# Approvals (application/approvals.py)


@dataclass(frozen=True, slots=True, kw_only=True)
class RequesterRow:
    started_by: UUID | None
    expert_id: UUID | None
    expert_version: int | None


@dataclass(frozen=True, slots=True, kw_only=True)
class ApprovalGateRow:
    id: UUID
    status: str
    scope_hash: str
    expired: bool
    consumed: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class ReceiptStateRow:
    status: str
    reconciled_at: datetime | None
    failure_code: str | None


@dataclass(frozen=True, slots=True, kw_only=True)
class DueApprovalRow:
    id: UUID
    run_id: UUID
    workspace_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class ApprovalDecisionRow:
    run_id: UUID
    status: str
    argument_hash: str
    expired: bool
    arguments: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ApprovalListRow:
    """A request as the inbox lists it, with its run's goal, the plan task its call served and who
    decided it (PRD-Studio AP-01 and AP-02)."""

    id: UUID
    run_id: UUID
    tool_id: str
    tool_version: int
    operation_class: str
    argument_hash: str
    arguments: str
    status: str
    expires_at: datetime
    policy_reason: str | None
    resource_target: str | None
    requested_by: UUID | None
    requested_by_agent: dict[str, Any] | None
    scope_snapshot: dict[str, Any] | None
    policy_version: str | None
    policy_rule: str | None
    expert_name: str | None
    run_goal: str | None
    task_title: str | None
    decided_at: datetime | None
    decided_by: UUID | None
    decided_by_name: str | None
    arguments_bytes: int
    review_detail: dict[str, Any] | None


# Workflows (application/workflows.py, application/workflow_executions.py)


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkflowRow:
    id: UUID
    name: str
    latest_version: int
    description: str | None


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkflowVersionRow:
    workflow_id: UUID
    version: int
    graph_hash: str
    source: str
    graph: dict[str, Any]
    block_versions: dict[str, str]


@dataclass(frozen=True, slots=True, kw_only=True)
class DraftRow:
    """A saved draft. Its graph is whatever JSON object the draft table's check admitted."""

    workflow_id: UUID
    graph: object
    saved_at: datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class PublishedVersionRow:
    graph: dict[str, Any]
    graph_hash: str
    block_versions: dict[str, str]
    name: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionRow:
    """An execution with its run's status, the instance in progress and whether a person's
    approval is pending, read in one statement so they agree."""

    workflow_id: UUID
    workflow_version: int
    graph_hash: str
    block_versions: dict[str, str]
    run_id: UUID
    run_status: str
    stop_reason: str | None
    graph: dict[str, Any]
    current_instance: str | None
    approval_pending: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class NodeInstanceRow:
    instance_key: str
    node_id: str
    iteration: int | None
    status: str
    error_code: str | None


@dataclass(frozen=True, slots=True, kw_only=True)
class EmissionRow:
    instance_key: str
    port: str
    sequence: int
    value: str


# Routines (application/routines.py)


@dataclass(frozen=True, slots=True, kw_only=True)
class RoutineRow:
    id: UUID
    name: str
    enabled: bool
    latest_version: int


@dataclass(frozen=True, slots=True, kw_only=True)
class OccurrenceRow:
    occurrence_time: datetime
    routine_version: int
    status: str
    reason: str | None
    run_id: UUID | None


@dataclass(frozen=True, slots=True, kw_only=True)
class RoutineOccurrenceRow(OccurrenceRow):
    """An occurrence read with others of several routines at once."""

    routine_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class RoutineConfigRow:
    routine_id: UUID
    config: dict[str, Any]


@dataclass(frozen=True, slots=True, kw_only=True)
class DueRoutineRow:
    workspace_id: UUID
    latest_version: int
    evaluated_until: datetime


# The tool gateway (application/tool_gateway.py)


@dataclass(frozen=True, slots=True, kw_only=True)
class OwnershipRow:
    run_status: str
    job_status: str
    generation: int | None
    lease_live: bool | None


# Run files (application/run_files.py)


@dataclass(frozen=True, slots=True, kw_only=True)
class RunFileRow:
    version: int
    sha256: str
    content: str
    media_type: str


# Improvements (application/improvements.py)


@dataclass(frozen=True, slots=True, kw_only=True)
class CandidateCheckRow:
    content: str
    evidence: list[dict[str, Any]]
    regression_cases: list[dict[str, Any]]
    status: str


@dataclass(frozen=True, slots=True, kw_only=True)
class CandidateDecisionRow:
    kind: str
    key: str
    content: str
    status: str
    evidence: list[dict[str, Any]]
    source: dict[str, Any] | None


@dataclass(frozen=True, slots=True, kw_only=True)
class CandidateRow:
    id: UUID
    kind: str
    key: str
    content: str
    status: str
    regression_results: dict[str, object] | None


@dataclass(frozen=True, slots=True, kw_only=True)
class ReplayRunRow:
    candidate_id: UUID
    replay_id: UUID
    run_id: UUID
    goal_text: str
    status: str


# Model admission (application/model_admission.py)


@dataclass(frozen=True, slots=True, kw_only=True)
class LedgerUsageRow:
    active: int
    workspace_micro_usd: int
    root_micro_usd: int


@dataclass(frozen=True, slots=True, kw_only=True)
class SpendLimitsRow:
    run_limit_micro_usd: int
    daily_limit_micro_usd: int
    slots: int


# Experts (application/experts.py)


@dataclass(frozen=True, slots=True, kw_only=True)
class ExpertRow:
    id: UUID
    name: str
    latest_version: int


@dataclass(frozen=True, slots=True, kw_only=True)
class ExpertVersionRow:
    expert_id: UUID
    version: int
    config: dict[str, Any]


@dataclass(frozen=True, slots=True, kw_only=True)
class ExpertRunsRow:
    expert_id: UUID
    run_count: int
    last_run_at: datetime | None


@dataclass(frozen=True, slots=True, kw_only=True)
class RouteOptionRow:
    """A pinned Expert version a session may route to, with its Expert's name."""

    expert_id: UUID
    version: int
    name: str
    config: dict[str, Any]


# Provider settings (application/provider_settings.py)


@dataclass(frozen=True, slots=True, kw_only=True)
class RouteQualificationRow:
    profile: str
    canonical_id: str
    status: str
    qualified_on: date | None
    configuration: str | None
    limits: str | None


# Local Operations (application/operations.py)


@dataclass(frozen=True, slots=True, kw_only=True)
class QueueCountRow:
    queued: int
    claimed: int
    expired_leases: int
    oldest_queued_seconds: int


# Search (application/search.py)


@dataclass(frozen=True, slots=True, kw_only=True)
class RunHitRow:
    id: UUID
    goal_summary: str
    status: str


# Profiles (application/profiles.py)


@dataclass(frozen=True, slots=True, kw_only=True)
class SessionWorkspaceRow:
    id: UUID
    name: str
    role: str
    timezone: str


# Assignments (application/assignments.py)


@dataclass(frozen=True, slots=True, kw_only=True)
class DelegatingRunRow:
    session_id: UUID | None
    policy_snapshot: dict[str, Any]
    limit_micro_usd: int
    parent_depth: int


@dataclass(frozen=True, slots=True, kw_only=True)
class AssignmentRecordRow:
    id: UUID
    child_run_id: UUID
    status: str
    result: dict[str, Any] | None


# Tool uses (application/tool_uses.py)


@dataclass(frozen=True, slots=True, kw_only=True)
class ToolUseRow:
    id: int
    run_id: UUID
    sequence_in_run: int
    tool_id: str
    tool_version: int | None
    tool_group: str | None
    provider: str | None
    plan_version: int | None
    task_id: str | None
    task_title: str | None
    requested_at: datetime
    finished_at: datetime | None
    duration_ms: int | None
    outcome: str | None
    code: str | None
    input_public: dict[str, Any] | None
    output_public: dict[str, Any] | None
    input_digest: str
    output_bytes: int | None
    operation_id: str | None
    # numeric in the database (migration 38), so psycopg returns a Decimal.
    provider_units: Decimal | None
    instance_key: str | None


# Artifacts (application/artifacts.py, application/artifact_tool.py)


@dataclass(frozen=True, slots=True, kw_only=True)
class ArtifactObjectRow:
    id: UUID
    name: str
    object_path: str
    sha256: str
    status: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ArtifactRow:
    """An artifact a run's pages list. Its storage path is never selected."""

    id: UUID
    run_id: UUID
    name: str
    media_type: str
    size_bytes: int
    sha256: str
    status: str


@dataclass(frozen=True, slots=True, kw_only=True)
class StoredArtifactRow:
    name: str
    media_type: str
    object_path: str
    sha256: str
    status: str


@dataclass(frozen=True, slots=True, kw_only=True)
class PublishedArtifactRow:
    id: UUID
    name: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True, slots=True, kw_only=True)
class ClaimableJobRow:
    run_id: UUID
    workspace_id: UUID
    status: str
    version: int


# The workflow runner (application/workflow_runner.py)


@dataclass(frozen=True, slots=True, kw_only=True)
class EmittedValueRow:
    instance_key: str
    port: str
    sequence: int
    value: object


@dataclass(frozen=True, slots=True, kw_only=True)
class RunExecutionRow:
    id: UUID
    inputs: dict[str, Any]
    graph: dict[str, Any]


# Recovery and reconciliation (application/recovery.py, application/reconciliation.py)


@dataclass(frozen=True, slots=True, kw_only=True)
class ObligationRow:
    kind: str
    detail: str


@dataclass(frozen=True, slots=True, kw_only=True)
class UnknownOperationRow:
    operation_id: str
    tool_id: str
    tool_version: int
    generation: int


# Job activity (application/job_activity.py)


@dataclass(frozen=True, slots=True, kw_only=True)
class DelayedOccurrenceRow:
    name: str
    occurrence_time: datetime
    status: str
    reason: str | None


@dataclass(frozen=True, slots=True, kw_only=True)
class JobHourRow:
    starts_at: datetime
    hour: str
    succeeded: int
    waited: int
    failed: int
    in_progress: int


# The model policy (application/model_policy.py)


@dataclass(frozen=True, slots=True, kw_only=True)
class ModelPolicyRow:
    version: int
    default_profile: str | None
    role_overrides: dict[str, str] | None


# Run usage (application/run_usage.py)


@dataclass(frozen=True, slots=True, kw_only=True)
class UsageCountRow:
    model_calls: int
    tool_dispatches: int
    repairs: int
    plan_revisions: int
    children: int
    stop_reason: str | None


# The workflow overview (application/workflow_overview.py)


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionSummaryRow:
    id: UUID
    run_id: UUID
    workflow_version: int
    status: str
    started_at: datetime
    run_updated_at: datetime
    run_created_at: datetime
    charged_micro_usd: int
    reserved_micro_usd: int
    unreported: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class LatestExecutionRow(ExecutionSummaryRow):
    """A workflow's latest execution, read with others of several workflows at once."""

    workflow_id: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkflowRunCountRow:
    workflow_id: UUID
    runs: int


@dataclass(frozen=True, slots=True, kw_only=True)
class ExpertConfigRow:
    id: str
    name: str
    config: dict[str, Any]


# Memory (application/memory.py, application/memory_tools.py)


@dataclass(frozen=True, slots=True, kw_only=True)
class MemoryHitRow:
    id: UUID
    title: str
    headline: str
    source: dict[str, Any]
    created_at: datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class FileHitRow:
    run_id: UUID
    path: str
    version: int
    sha256: str
    headline: str
    created_at: datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class ReplayProposalRow:
    id: UUID
    key: str
    content: str


@dataclass(frozen=True, slots=True, kw_only=True)
class OffloadRow:
    tool_name: str
    content: str
    sha256: str


# Compaction (application/compaction.py)


@dataclass(frozen=True, slots=True, kw_only=True)
class RunSummaryRow:
    covers: int
    summary: str
    sources: list[str]


# Verification and tool grants (application/verification.py, application/tool_grants.py)


@dataclass(frozen=True, slots=True, kw_only=True)
class NamedArtifactRow:
    name: str
    id: UUID
    status: str


@dataclass(frozen=True, slots=True, kw_only=True)
class GrantedToRow:
    id: UUID
    name: str
    latest_version: int


# Credentials (application/credentials/store.py)


@dataclass(frozen=True, slots=True, kw_only=True)
class SealedCredentialRow:
    """An active credential as stored: sealed, so nothing here is a usable key."""

    credential_id: UUID
    version: int
    ciphertext: bytes
    nonce: bytes
    tag: bytes


@dataclass(frozen=True, slots=True, kw_only=True)
class ProviderSettingsRow:
    version: int
    auth_status: str
    validated_at: datetime | None
