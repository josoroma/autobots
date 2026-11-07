"""Improvement proposals, PRD 8.5. A proposal has no field that could change a grant or a model."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from autobots.contracts.primitives import Identifier, MicroUsd
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


class ReplayRunView(BaseModel):
    model_config = VIEW

    run_id: Identifier
    goal_text: str
    status: str


class ReplayView(BaseModel):
    """The latest held-out replay, Decision 0016. Its state is read from its runs."""

    model_config = VIEW

    id: Identifier
    state: Literal["running", "passed", "failed"]
    runs: list[ReplayRunView]


class CandidateView(BaseModel):
    model_config = VIEW

    id: Identifier
    kind: str
    key: str
    content: str
    status: str
    regression_results: dict[str, object] | None
    # Promotion needs this to have passed. None means no replay was requested.
    replay: ReplayView | None


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
    active_version: int | None


class RollbackRequest(BaseModel):
    model_config = VIEW

    kind: Literal["memory", "skill"]
    key: str
    # 0 means no active version, to undo a first promotion.
    to_version: int = Field(ge=0)


class RegressionRun(BaseModel):
    """The reviewer's own checks. A proposal's suggested cases aren't counted.

    Optional since US-13.2: a case can fail a proposal, and only a held-out replay passes one.
    """

    model_config = VIEW

    cases: list[RegressionCase] = Field(default_factory=list, max_length=20)


class HeldOutTask(BaseModel):
    """A goal the owner wrote, with what it must meet. It must not be one the proposal came from."""

    model_config = VIEW

    goal_text: str = Field(min_length=1, max_length=2000)
    criteria: list[str] = Field(min_length=1, max_length=10)


class ReplayRequest(BaseModel):
    """Each task is a run with the proposal applied, spending up to the limit, Decision 0016."""

    model_config = VIEW

    tasks: list[HeldOutTask] = Field(min_length=1, max_length=10)
    limit_micro_usd: MicroUsd = Field(ge=1)
