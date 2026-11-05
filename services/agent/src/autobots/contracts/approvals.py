"""Approval views and decisions, PRD 9.2."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from autobots.contracts.primitives import Identifier

VIEW = ConfigDict(extra="forbid", frozen=True)


class ApprovalView(BaseModel):
    """What a reviewer decides on. The hash they saw comes back with the decision."""

    model_config = VIEW

    id: Identifier
    run_id: Identifier
    tool_id: str
    tool_version: int
    operation_class: str
    argument_hash: str
    arguments: str
    arguments_truncated: bool
    status: str
    expires_at: str


class ApprovalList(BaseModel):
    model_config = VIEW

    schema_version: Literal[1]
    approvals: list[ApprovalView]


class ApprovalDecision(BaseModel):
    model_config = VIEW

    decision: Literal["approve", "reject"]
    argument_hash: str = Field(min_length=64, max_length=64)


class ApprovalResult(BaseModel):
    model_config = VIEW

    schema_version: Literal[1]
    approval_id: Identifier
    status: str
    replayed: bool
