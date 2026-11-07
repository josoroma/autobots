"""Versioned input and output contracts for the narrow tool set."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from autobots.contracts.primitives import STRICT_CONTRACT

TOOL_CONTRACT = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
MAX_FILE_CHARACTERS = 256_000


class CalculateInput(BaseModel):
    model_config = TOOL_CONTRACT

    operation: Literal["sum", "mean", "min", "max"]
    values: list[float] = Field(min_length=1, max_length=1000)


class CalculateOutput(BaseModel):
    model_config = TOOL_CONTRACT

    result: float


class ReadRunFileInput(BaseModel):
    model_config = TOOL_CONTRACT

    path: str = Field(min_length=1, max_length=500)


class ReadRunFileOutput(BaseModel):
    model_config = TOOL_CONTRACT

    path: str
    version: int
    content: str
    sha256: str


class CreateGithubIssueInput(BaseModel):
    """No field names a repository: that's server configuration, by Decision 0007."""

    model_config = TOOL_CONTRACT

    title: str = Field(min_length=1, max_length=256)
    body: str = Field(max_length=60_000)


class CreateGithubIssueOutput(BaseModel):
    model_config = TOOL_CONTRACT

    number: int
    url: str


class SaveArtifactInput(BaseModel):
    model_config = TOOL_CONTRACT

    path: str = Field(min_length=1, max_length=500)
    content: str = Field(max_length=MAX_FILE_CHARACTERS)
    media_type: Literal["text/plain", "text/markdown", "application/json"] = "text/markdown"


class SaveArtifactOutput(BaseModel):
    model_config = TOOL_CONTRACT

    path: str
    version: int
    sha256: str


# The catalog's public view, PRD-Tool-Catalog TC-02 to TC-05. Names of keys, never their values.
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
]
ToolProviderName = Literal[
    "autobots", "tavily", "jina", "yahoo_finance", "world_bank", "github", "browser_use"
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
    source: Literal["environment"]


class ToolLimits(BaseModel):
    model_config = STRICT_CONTRACT

    timeout_seconds: float
    retries: int
    max_output_bytes: int


class ToolDescriptor(BaseModel):
    model_config = STRICT_CONTRACT

    tool_id: str = Field(pattern=r"^[a-z][a-z0-9_]{2,63}$")
    version: int = Field(ge=1)
    title: str
    description: str
    group: ToolGroupName
    provider: ToolProviderName
    operation_class: OperationClassName
    side_effects: Literal["none", "internal_write", "external_write", "arbitrary"]
    network: bool
    cost_class: Literal["free_local", "metered_provider"]
    cost_note: str | None
    key_requirement: KeyRequirementView | None
    approval: Literal["never", "always"]
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
