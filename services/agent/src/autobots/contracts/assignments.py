"""What a parent asks of a specialist, and the concise result it gets back."""

from pydantic import BaseModel, Field

from autobots.contracts.primitives import TOOL_CONTRACT


class AssignSpecialist(BaseModel):
    model_config = TOOL_CONTRACT

    expert_id: str = Field(min_length=36, max_length=36)
    goal: str = Field(min_length=1, max_length=5000)
    criteria: list[str] = Field(default_factory=list, max_length=20)
    # A request for less than the Expert has. Asking for more than the parent holds is refused.
    tools: list[str] | None = Field(default=None, max_length=20)


class AssignmentResult(BaseModel):
    """Raw intermediate work stays in the child run. Only references come back."""

    model_config = TOOL_CONTRACT

    assignment_id: str
    child_run_id: str
    outcome: str
    code: str | None
    run_status: str | None
    completed: list[str]
    remaining: list[str]
    artifact_ids: list[str]
