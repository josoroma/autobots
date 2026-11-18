"""The tool catalog's public view, PRD-Tool-Catalog TC-02 to TC-05, and the grants API
(PRD-Studio TL-02). Names of keys, never their values.

The vocabularies are Literals, so the strict descriptors take the catalog's strings, and each
equals its domain enum (domain/tool_catalog.py, domain/tools.py), which
tests/test_contract_vocabularies.py holds them to (PDOM-06).
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

from autobots.contracts.primitives import LAX_CONTRACT, STRICT_CONTRACT, Identifier

ToolGroupName = Literal[
    "planning",
    "general",
    "web_search",
    "web_extraction",
    "web_crawling",
    "files",
    "market_data",
    "browsing",
    "code",
    "connectors",
    "delegation",
    "learning",
    "automation",
]
ToolProviderName = Literal[
    "autobots", "tavily", "jina", "serpapi", "yahoo_finance", "world_bank", "github"
]
OperationClassName = Literal[
    "pure",
    "read_only",
    "reversible_internal_write",
    "consequential_external_write",
    "arbitrary_execution",
]
AvailabilityName = Literal["available", "key_missing", "disabled_by_policy", "not_qualified"]
GrantSiteName = Literal["goal", "expert", "workflow_node", "coordinator"]
SideEffectName = Literal["none", "internal_write", "external_write", "arbitrary"]
CostClassName = Literal["free_local", "metered_provider"]


class FieldDescriptor(BaseModel):
    model_config = STRICT_CONTRACT

    path: str
    direction: Literal["input", "output"]
    type: str
    required: bool
    description: str | None
    constraints: dict[str, Any]
    public: bool


class KeyRequirementView(BaseModel):
    model_config = STRICT_CONTRACT

    credential: str
    variables: list[str]
    # What the credential must be allowed to do, for the repair to name. Never a value.
    scopes: list[str]
    # Where this workspace's key comes from (PK-05), and null while it has none. Never a value.
    source: Literal["settings", "environment"] | None


class ToolLimits(BaseModel):
    model_config = STRICT_CONTRACT

    timeout_seconds: float
    retries: int
    max_output_bytes: int


class ToolGuideView(BaseModel):
    """Decision 0026 G1: what a tool does, when to use it and why. Describes, never grants."""

    model_config = STRICT_CONTRACT

    what: str = Field(min_length=1)
    when: str = Field(min_length=1)
    why: str = Field(min_length=1)


class ToolDescriptor(BaseModel):
    model_config = STRICT_CONTRACT

    tool_id: str = Field(pattern=r"^[a-z][a-z0-9_]{2,63}$")
    version: int = Field(ge=1)
    title: str
    description: str
    guide: ToolGuideView
    group: ToolGroupName
    provider: ToolProviderName
    operation_class: OperationClassName
    side_effects: SideEffectName
    network: bool
    cost_class: CostClassName
    cost_note: str | None
    key_requirement: KeyRequirementView | None
    # Decision 0026 C9: `by_action` when only some of a tool's actions wait for a person.
    approval: Literal["never", "always", "by_action"]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    fields: list[FieldDescriptor]
    limits: ToolLimits | None
    grantable_to: list[GrantSiteName]
    registered: bool
    availability: AvailabilityName
    availability_reason: str | None


class ToolGroupDescriptor(BaseModel):
    model_config = STRICT_CONTRACT

    group: ToolGroupName
    title: str
    description: str
    tool_ids: list[str]


class ToolCatalog(BaseModel):
    model_config = STRICT_CONTRACT

    schema_version: Literal[1]
    catalog_digest: str
    groups: list[ToolGroupDescriptor]
    tools: list[ToolDescriptor]


class ToolVersions(BaseModel):
    model_config = STRICT_CONTRACT

    tool_id: str
    versions: list[ToolDescriptor]


class GrantedTo(BaseModel):
    """An Expert or a published workflow that grants a tool, with the version that does."""

    model_config = LAX_CONTRACT

    id: Identifier
    name: str
    version: int


class ToolGrants(BaseModel):
    """PRD-Studio TL-02: latest Expert versions, and published workflows through agent steps."""

    model_config = LAX_CONTRACT

    schema_version: Literal[1]
    tool_id: str
    experts: list[GrantedTo]
    workflows: list[GrantedTo]
