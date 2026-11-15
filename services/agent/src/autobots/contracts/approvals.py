"""Approval views and decisions, PRD 9.2."""

from typing import Literal, get_args

from pydantic import BaseModel, Field

from autobots.contracts.primitives import LAX_CONTRACT, Identifier, UtcTimestamp
from autobots.domain.effects import ApprovalStatus

# A person's answer to a request. The decision command takes the same values (PTOL-15).
ApprovalVerdict = Literal["approve", "reject"]
# The rule that held a call, as approval_requests.policy_rule stores it: a consequential write, a
# tool that always asks, or a call its tool marked (Decision 0026 C3, migration 53's CHECK).
PolicyRuleName = Literal["consequential_external_write", "tool_marked", "action_marked"]
POLICY_RULES: tuple[PolicyRuleName, ...] = get_args(PolicyRuleName)


class ApprovalRequester(BaseModel):
    """Who asked, Decision 0015. Only the Expert's ID and version were stored with the request."""

    model_config = LAX_CONTRACT

    # The person who started the run. Empty when no person did, or the run predates this record.
    person_id: Identifier | None
    person_is_viewer: bool
    agent: Literal["expert", "coordinator"]
    expert_id: Identifier | None
    expert_version: int | None
    # Read when the view loads, so a rename since the request shows the current name.
    expert_name: str | None


class ApprovalScope(BaseModel):
    """The grants the request was made under. They hash to the scope it's checked against."""

    model_config = LAX_CONTRACT

    tools: dict[str, int]
    paths: list[str]


class ApprovalFileDiff(BaseModel):
    model_config = LAX_CONTRACT

    path: str
    change: Literal["added", "modified", "unchanged"]
    diff: str


class ApprovalReviewDetail(BaseModel):
    """PRD-Studio GH-06: each file's diff against the base branch's head, which the approval
    binds. A moved head stops the call with base_moved."""

    model_config = LAX_CONTRACT

    base_branch: str
    base_sha: str
    files: list[ApprovalFileDiff]


class ApprovalView(BaseModel):
    """What a reviewer decides on. The hash they saw comes back with the decision."""

    model_config = LAX_CONTRACT

    id: Identifier
    run_id: Identifier
    tool_id: str
    tool_version: int
    operation_class: str
    argument_hash: str
    arguments: str
    arguments_truncated: bool
    # approval_requests.status, which a check constraint holds to ApprovalStatus.
    status: ApprovalStatus
    expires_at: UtcTimestamp
    # Empty on a request saved before these were recorded. They're never filled in afterward.
    policy_reason: str | None
    resource_target: str | None
    # Empty on a request saved before US-13.1, and never filled in afterward.
    requester: ApprovalRequester | None
    scope_snapshot: ApprovalScope | None
    policy_version: str | None
    policy_rule: PolicyRuleName | None
    # PRD-Studio AP-02 and AP-03. Empty when the run, task or decision isn't recorded.
    run_goal: str | None
    task_title: str | None
    decided_at: UtcTimestamp | None
    decided_by: Literal["you", "member"] | None
    decided_by_name: str | None
    arguments_bytes: int
    review_detail: ApprovalReviewDetail | None = None


class ApprovalCounts(BaseModel):
    model_config = LAX_CONTRACT

    waiting: int
    decided: int


class ApprovalList(BaseModel):
    model_config = LAX_CONTRACT

    schema_version: Literal[1]
    approvals: list[ApprovalView]
    counts: ApprovalCounts


class PendingApprovals(BaseModel):
    """The sidebar badge's number (PRD-Studio SH-03), counted on the server."""

    model_config = LAX_CONTRACT

    schema_version: Literal[1]
    pending: int


class ApprovalDecision(BaseModel):
    model_config = LAX_CONTRACT

    decision: ApprovalVerdict
    argument_hash: str = Field(min_length=64, max_length=64)


class ApprovalResult(BaseModel):
    model_config = LAX_CONTRACT

    schema_version: Literal[1]
    approval_id: Identifier
    status: ApprovalStatus
    replayed: bool
