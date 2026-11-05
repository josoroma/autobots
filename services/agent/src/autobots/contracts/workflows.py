"""Workflow IR and API contracts, PRD 7.3 and 11.2."""

from typing import Any, Literal

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


class WorkflowView(BaseModel):
    model_config = VIEW

    schema_version: Literal[1]
    id: Identifier
    name: str
    latest_version: int
    versions: list[WorkflowVersionView]


class WorkflowList(BaseModel):
    model_config = VIEW

    schema_version: Literal[1]
    workflows: list[WorkflowView]


class ExecutionCreate(BaseModel):
    model_config = VIEW

    version: int = Field(ge=1)
    inputs: dict[str, Any] = Field(default_factory=dict)
    documents: list[InputDocument] = Field(default_factory=list, max_length=10)


class ExecutionBinding(BaseModel):
    model_config = VIEW

    schema_version: Literal[1]
    id: Identifier
    run_id: Identifier
    workflow_id: Identifier
    workflow_version: int
    graph_hash: str
    block_versions: dict[str, str]
