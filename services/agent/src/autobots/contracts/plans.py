"""The admitted goal and the plan a model may propose, SP-011 and PRD 8.1."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from autobots.contracts.tools import TOOL_CONTRACT

MAX_INPUT_BYTES = 1_048_576
InputMediaType = Literal["text/plain", "text/markdown", "application/json", "text/csv"]


class InputDocument(BaseModel):
    """A controlled document given at admission, or a file attached to a goal (FI-01). Tools can
    read it and can't change it. Text only, at most 1 MiB."""

    model_config = TOOL_CONTRACT

    path: str = Field(pattern=r"^inputs/[A-Za-z0-9._-]{1,200}$")
    content: str = Field(max_length=MAX_INPUT_BYTES)
    media_type: InputMediaType = "text/plain"

    @field_validator("content")
    @classmethod
    def _bounded_bytes(cls, value: str) -> str:
        if len(value.encode()) > MAX_INPUT_BYTES:
            raise ValueError("an input document is at most 1 MiB")
        return value


class RequiredArtifact(BaseModel):
    """A deterministic check of the bytes, decided at admission."""

    model_config = TOOL_CONTRACT

    name: str = Field(min_length=1, max_length=200)
    must_contain: list[str] = Field(default_factory=list, max_length=20)


class GoalSpec(BaseModel):
    """Set at admission, and never changed by a plan."""

    model_config = TOOL_CONTRACT

    objective: str
    original_request: str
    criteria: dict[str, str]
    allowed_tools: dict[str, int]
    allowed_paths: list[str]
    required_artifacts: list[RequiredArtifact] = Field(default_factory=list)
    instructions: str = ""


class PlanTask(BaseModel):
    model_config = TOOL_CONTRACT

    id: str = Field(pattern=r"^[a-z0-9_-]{1,40}$")
    title: str = Field(min_length=1, max_length=300)
    depends_on: list[str] = Field(default_factory=list, max_length=30)
    criteria: list[str] = Field(
        default_factory=list,
        max_length=20,
        description="IDs of the goal's criteria this task covers, exactly as listed, such as c1. "
        "Never a criterion's text.",
    )
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

    kind: Literal["artifact", "receipt"] = Field(
        description="artifact for a file this run saved, receipt for a tool's recorded effect."
    )
    reference: str = Field(
        min_length=1,
        max_length=500,
        description=(
            "For artifact, the file's exact path as save_artifact returned it, such as "
            "outputs/report.md, with no version, hash or other text added. For receipt, the "
            "operation_id from that tool's reply."
        ),
    )


class CompleteTask(BaseModel):
    model_config = TOOL_CONTRACT

    task_id: str = Field(min_length=1, max_length=40)
    evidence: list[Evidence] = Field(min_length=1, max_length=20)
    summary: str = Field(min_length=1, max_length=2000)


class TaskCompleted(BaseModel):
    model_config = TOOL_CONTRACT

    task_id: str
    remaining: list[str]
