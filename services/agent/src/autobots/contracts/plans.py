"""The admitted goal and the plan a model may propose, SP-011 and PRD 8.1."""

from typing import Literal

from pydantic import BaseModel, Field

from autobots.contracts.tools import TOOL_CONTRACT


class GoalSpec(BaseModel):
    """Set at admission, and never changed by a plan."""

    model_config = TOOL_CONTRACT

    objective: str
    original_request: str
    criteria: dict[str, str]
    allowed_tools: dict[str, int]
    allowed_paths: list[str]


class PlanTask(BaseModel):
    model_config = TOOL_CONTRACT

    id: str = Field(pattern=r"^[a-z0-9_-]{1,40}$")
    title: str = Field(min_length=1, max_length=300)
    depends_on: list[str] = Field(default_factory=list, max_length=30)
    criteria: list[str] = Field(default_factory=list, max_length=20)
    tools: list[str] = Field(default_factory=list, max_length=20)
    expected_evidence: str = Field(min_length=1, max_length=500)


class PlanProposal(BaseModel):
    model_config = TOOL_CONTRACT

    tasks: list[PlanTask] = Field(min_length=1, max_length=30)
    revision_reason: str | None = Field(default=None, max_length=1000)


class PlanCommitted(BaseModel):
    model_config = TOOL_CONTRACT

    version: int
    tasks: list[str]


class Evidence(BaseModel):
    model_config = TOOL_CONTRACT

    kind: Literal["artifact", "receipt"]
    reference: str = Field(min_length=1, max_length=500)


class CompleteTask(BaseModel):
    model_config = TOOL_CONTRACT

    task_id: str = Field(min_length=1, max_length=40)
    evidence: list[Evidence] = Field(min_length=1, max_length=20)
    summary: str = Field(min_length=1, max_length=2000)


class TaskCompleted(BaseModel):
    model_config = TOOL_CONTRACT

    task_id: str
    remaining: list[str]
