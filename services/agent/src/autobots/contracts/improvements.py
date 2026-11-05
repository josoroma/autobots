"""Improvement proposals, PRD 8.5. A proposal has no field that could change a grant or a model."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from autobots.contracts.primitives import Identifier
from autobots.contracts.tools import TOOL_CONTRACT

VIEW = ConfigDict(extra="forbid", frozen=True)


class EvidenceRef(BaseModel):
    model_config = TOOL_CONTRACT

    kind: Literal["run", "artifact"]
    id: str = Field(min_length=36, max_length=36)


class RegressionCase(BaseModel):
    """A query that must find the content once it's in place, and text it must not lose."""

    model_config = TOOL_CONTRACT

    must_contain: str = Field(min_length=1, max_length=500)


class ImprovementProposal(BaseModel):
    model_config = TOOL_CONTRACT

    kind: Literal["memory", "skill"]
    key: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,99}$")
    content: str = Field(min_length=1, max_length=20000)
    evidence: list[EvidenceRef] = Field(default_factory=list, max_length=20)
    regression_cases: list[RegressionCase] = Field(default_factory=list, max_length=20)


class ProposalAccepted(BaseModel):
    model_config = TOOL_CONTRACT

    candidate_id: str
    status: str


class CandidateView(BaseModel):
    model_config = VIEW

    id: Identifier
    kind: str
    key: str
    content: str
    status: str
    regression_results: dict[str, object] | None


class CandidateList(BaseModel):
    model_config = VIEW

    schema_version: Literal[1]
    candidates: list[CandidateView]


class CandidateDecision(BaseModel):
    model_config = VIEW

    decision: Literal["promote", "reject"]


class KnowledgeHead(BaseModel):
    model_config = VIEW

    schema_version: Literal[1]
    kind: str
    key: str
    active_version: int


class RollbackRequest(BaseModel):
    model_config = VIEW

    kind: Literal["memory", "skill"]
    key: str
    to_version: int = Field(ge=1)
