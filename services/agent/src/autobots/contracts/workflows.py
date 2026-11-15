"""Workflow IR and API contracts, PRD 7.3 and 11.2."""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from autobots.contracts.plans import InputDocument
from autobots.contracts.primitives import Identifier

VIEW = ConfigDict(extra="forbid", frozen=True)


class WorkflowNode(BaseModel):
    model_config = VIEW

    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,60}$")
    block: str = Field(max_length=40)
    version: int
    config: dict[str, Any] = Field(default_factory=dict)
    # IR version 2 (PRD-Studio WF-06): what this step does, shown in lists and previews.
    label: str | None = Field(default=None, min_length=1, max_length=80)


class WorkflowLink(BaseModel):
    model_config = VIEW

    source: str
    source_port: str
    target: str
    target_port: str


class WorkflowGraph(BaseModel):
    model_config = VIEW

    nodes: list[WorkflowNode] = Field(default_factory=list, max_length=200)
    links: list[WorkflowLink] = Field(default_factory=list, max_length=1000)
    # Absent means version 1. A graph whose nodes carry labels is stored at version 2.
    ir_version: Literal[1, 2] | None = None


class WorkflowErrorView(BaseModel):
    model_config = VIEW

    code: str
    node: str | None
    port: str | None


class WorkflowValidation(BaseModel):
    model_config = VIEW

    schema_version: Literal[1]
    valid: bool
    errors: list[WorkflowErrorView]
    graph_hash: str | None


class WorkflowCreate(BaseModel):
    model_config = VIEW

    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, min_length=1, max_length=500)


class WorkflowDescription(BaseModel):
    """PRD-Studio WF-06: replaces the description. None removes it."""

    model_config = VIEW

    description: str | None = Field(min_length=1, max_length=500)


class WorkflowPublish(BaseModel):
    model_config = VIEW

    expected_version: int = Field(ge=0)
    graph: WorkflowGraph
    source: Literal["user", "model_proposal"] = "user"


class WorkflowVersionView(BaseModel):
    model_config = VIEW

    version: int
    graph_hash: str
    source: str
    graph: WorkflowGraph
    block_versions: dict[str, str]


class WorkflowDraftView(BaseModel):
    """PRD-Studio WF-02: the one saved draft beside the published versions. Nothing runs it."""

    model_config = VIEW

    graph: WorkflowGraph
    saved_at: str


class WorkflowDraftSave(BaseModel):
    model_config = VIEW

    graph: WorkflowGraph


class WorkflowDraftPublish(BaseModel):
    model_config = VIEW

    expected_version: int = Field(ge=0)


class WorkflowExecutionSummary(BaseModel):
    """PRD-Studio WF-04: one execution's version, state, ledger spend and duration. Spend is an
    estimate while a reservation is held or a charge was never reported."""

    model_config = VIEW

    id: Identifier
    run_id: Identifier
    version: int
    status: str
    charged_micro_usd: int
    reserved_micro_usd: int
    unreported: bool
    started_at: str
    # Until the run ends, None.
    duration_seconds: int | None


class WorkflowExecutionList(BaseModel):
    model_config = VIEW

    schema_version: Literal[1]
    executions: list[WorkflowExecutionSummary]


class WorkflowStepView(BaseModel):
    """WF-03: one step of a version, in the order it runs."""

    model_config = VIEW

    id: str
    block: str
    label: str | None
    expert_id: Identifier | None
    expert_name: str | None
    # The executor's canonical model for an agent step, as a run started now would resolve it.
    model: str | None
    tools: list[str]
    approval: bool


class WorkflowPreview(BaseModel):
    model_config = VIEW

    schema_version: Literal[1]
    version: int | Literal["draft"]
    steps: list[WorkflowStepView]


class WorkflowView(BaseModel):
    model_config = VIEW

    schema_version: Literal[1]
    id: Identifier
    name: str
    description: str | None
    latest_version: int
    versions: list[WorkflowVersionView]
    draft: WorkflowDraftView | None
    # A draft is stored that WorkflowGraph refuses, as one written through PostgREST can be; `draft`
    # is then None, and saving replaces it (R-56, SQLI-13).
    draft_unreadable: bool
    # WF-01, from the latest published version: its Experts in step order and its step count.
    experts: list[str]
    step_count: int
    last_execution: WorkflowExecutionSummary | None
    run_count: int


class WorkflowList(BaseModel):
    model_config = VIEW

    schema_version: Literal[1]
    workflows: list[WorkflowView]


class BlockView(BaseModel):
    model_config = VIEW

    block: str
    version: int
    inputs: list[str]
    outputs: list[str]


class BlockCatalog(BaseModel):
    model_config = VIEW

    schema_version: Literal[1]
    blocks: list[BlockView]


class InstanceView(BaseModel):
    model_config = VIEW

    key: str
    node_id: str
    iteration: int | None
    status: str
    error_code: str | None


class EmissionView(BaseModel):
    model_config = VIEW

    instance_key: str
    port: str
    sequence: int
    value: str


class ExecutionView(BaseModel):
    """Read from saved rows, so looking at it can't start or repeat anything."""

    model_config = VIEW

    schema_version: Literal[1]
    id: Identifier
    workflow_id: Identifier
    workflow_version: int
    graph_hash: str
    block_versions: dict[str, str]
    run_id: Identifier
    run_status: str
    stop_reason: str | None
    instances: list[InstanceView]
    emissions: list[EmissionView]


class ExecutionCreate(BaseModel):
    model_config = VIEW

    # "draft" is accepted here only to be refused with `draft_not_runnable` (WF-02).
    version: Annotated[int, Field(ge=1)] | Literal["draft"]
    inputs: dict[str, Any] = Field(default_factory=dict)
    documents: list[InputDocument] = Field(default_factory=list, max_length=10)
    # WF-05 and Decision 0022 D11: US$0.25 to US$5.00 in US$0.25 steps, within today's cap.
    budget_micro_usd: int | None = Field(default=None, ge=0)


class ExecutionBinding(BaseModel):
    model_config = VIEW

    schema_version: Literal[1]
    id: Identifier
    run_id: Identifier
    workflow_id: Identifier
    workflow_version: int
    graph_hash: str
    block_versions: dict[str, str]
