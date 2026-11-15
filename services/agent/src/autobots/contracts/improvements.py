"""Improvement proposals, PRD 8.5. A proposal has no field that could change a grant or a model."""

from typing import Literal

from pydantic import BaseModel, Field

from autobots.contracts.primitives import LAX_CONTRACT, TOOL_CONTRACT, Count, Identifier, MicroUsd
from autobots.domain.runs import RunStatus

# What a proposal changes. improvement_candidates.kind and knowledge_versions.kind hold to it by
# check constraints (tests/test_contract_vocabularies.py).
KnowledgeKind = Literal["memory", "skill"]
# improvement_candidates.status, as its check constraint allows.
CandidateStatus = Literal[
    "proposed", "regression_failed", "regression_passed", "rejected", "promoted"
]


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

    kind: KnowledgeKind
    key: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,99}$")
    content: str = Field(min_length=1, max_length=20000)
    evidence: list[EvidenceRef] = Field(default_factory=list, max_length=20)
    regression_cases: list[RegressionCase] = Field(default_factory=list, max_length=20)


class ProposalAccepted(BaseModel):
    model_config = TOOL_CONTRACT

    candidate_id: str
    status: str


class ReplayRunView(BaseModel):
    model_config = LAX_CONTRACT

    run_id: Identifier
    goal_text: str
    status: RunStatus


class ReplayView(BaseModel):
    """The latest held-out replay, Decision 0016. Its state is read from its runs."""

    model_config = LAX_CONTRACT

    id: Identifier
    state: Literal["running", "passed", "failed"]
    runs: list[ReplayRunView]


class CandidateView(BaseModel):
    model_config = LAX_CONTRACT

    id: Identifier
    kind: KnowledgeKind
    key: str
    content: str
    status: CandidateStatus
    regression_results: dict[str, object] | None
    # Promotion needs this to have passed. None means no replay was requested.
    replay: ReplayView | None


class CandidateList(BaseModel):
    model_config = LAX_CONTRACT

    schema_version: Literal[1]
    candidates: list[CandidateView]


class CandidateDecision(BaseModel):
    model_config = LAX_CONTRACT

    decision: Literal["promote", "reject"]


class KnowledgeHead(BaseModel):
    model_config = LAX_CONTRACT

    schema_version: Literal[1]
    kind: KnowledgeKind
    key: str
    active_version: int | None


class RollbackRequest(BaseModel):
    model_config = LAX_CONTRACT

    kind: KnowledgeKind
    key: str
    # 0 means no active version, to undo a first promotion.
    to_version: Count


class RegressionRun(BaseModel):
    """The reviewer's own checks. A proposal's suggested cases aren't counted.

    Optional since US-13.2: a case can fail a proposal, and only a held-out replay passes one.
    """

    model_config = LAX_CONTRACT

    cases: list[RegressionCase] = Field(default_factory=list, max_length=20)


class HeldOutTask(BaseModel):
    """A goal the owner wrote, with what it must meet. It must not be one the proposal came from."""

    model_config = LAX_CONTRACT

    goal_text: str = Field(min_length=1, max_length=2000)
    criteria: list[str] = Field(min_length=1, max_length=10)


class ReplayRequest(BaseModel):
    """Each task is a run with the proposal applied, spending up to the limit, Decision 0016."""

    model_config = LAX_CONTRACT

    tasks: list[HeldOutTask] = Field(min_length=1, max_length=10)
    limit_micro_usd: MicroUsd = Field(ge=1)
