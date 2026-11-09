"""Versioned input and output contracts for the narrow tool set."""

import re
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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


GithubLabel = Annotated[str, Field(min_length=1, max_length=50)]


class CreateGithubIssueV2Input(BaseModel):
    """PRD-Studio GH-05: version 1's fields, and up to 10 labels. Still no repository."""

    model_config = TOOL_CONTRACT

    title: str = Field(min_length=1, max_length=256)
    body: str = Field(max_length=60_000)
    labels: list[GithubLabel] = Field(default_factory=list, max_length=10)


# PRD-Studio GH-01 to GH-04. Every input is bounded, and none names a repository: the one configured
# repository is server configuration (Decision 0022 D6).
GithubBranch = Annotated[str, Field(min_length=1, max_length=255, pattern=r"^[A-Za-z0-9._/-]+$")]
GithubLimit = Annotated[int, Field(ge=1, le=100)]
# Qualifiers that would widen a search past the configured repository are refused.
_SEARCH_SCOPE = re.compile(r"(?i)(^|\s)-?(repo|org|user|owner)\s*:")


class GithubListPullRequestsInput(BaseModel):
    model_config = TOOL_CONTRACT

    state: Literal["open", "closed", "merged"] = "open"
    base: GithubBranch | None = None
    since: datetime | None = None
    limit: GithubLimit = 30


class GithubPullRequest(BaseModel):
    model_config = TOOL_CONTRACT

    number: int
    title: str
    author: str | None
    merged_at: str | None
    labels: list[str]
    url: str


class GithubListPullRequestsOutput(BaseModel):
    model_config = TOOL_CONTRACT

    pull_requests: list[GithubPullRequest]


class GithubListWorkflowRunsInput(BaseModel):
    model_config = TOOL_CONTRACT

    workflow: str | None = Field(
        default=None, min_length=1, max_length=100, pattern=r"^[A-Za-z0-9._-]+\.ya?ml$"
    )
    branch: GithubBranch | None = None
    status: Literal["failure", "success"] | None = None
    since: datetime | None = None
    limit: GithubLimit = 20


class GithubFailingJob(BaseModel):
    model_config = TOOL_CONTRACT

    name: str
    failed_steps: list[str]


class GithubWorkflowRun(BaseModel):
    model_config = TOOL_CONTRACT

    id: int
    conclusion: str | None
    created_at: str | None
    updated_at: str | None
    head_sha: str
    failing_jobs: list[GithubFailingJob]


class GithubListWorkflowRunsOutput(BaseModel):
    model_config = TOOL_CONTRACT

    runs: list[GithubWorkflowRun]


class GithubSearchIssuesInput(BaseModel):
    model_config = TOOL_CONTRACT

    query: str = Field(min_length=1, max_length=256)
    state: Literal["open", "closed"] | None = None

    @field_validator("query")
    @classmethod
    def _within_the_repository(cls, query: str) -> str:
        if _SEARCH_SCOPE.search(query):
            raise ValueError("the search can't name another repository, owner or organization")
        return query


class GithubIssue(BaseModel):
    model_config = TOOL_CONTRACT

    number: int
    title: str
    state: str
    labels: list[str]
    url: str


class GithubSearchIssuesOutput(BaseModel):
    model_config = TOOL_CONTRACT

    issues: list[GithubIssue]


class GithubReadFileInput(BaseModel):
    model_config = TOOL_CONTRACT

    path: str = Field(min_length=1, max_length=500, pattern=r"^[A-Za-z0-9._/ -]+$")
    ref: GithubBranch | None = None

    @field_validator("path")
    @classmethod
    def _inside_the_repository(cls, path: str) -> str:
        if path.startswith("/") or ".." in path.split("/"):
            raise ValueError("a path is relative to the repository and can't climb out of it")
        return path


class GithubReadFileOutput(BaseModel):
    """`content` reaches the model only. A tool use and run screens keep its SHA and size."""

    model_config = TOOL_CONTRACT

    path: str
    ref: str | None
    sha: str
    size: int
    content: str


MAX_PULL_REQUEST_BYTES = 1_048_576


class GithubFileChange(BaseModel):
    """A file's full new content. Only named paths are committed."""

    model_config = TOOL_CONTRACT

    path: str = Field(min_length=1, max_length=500, pattern=r"^[A-Za-z0-9._/ -]+$")
    content: str = Field(max_length=MAX_PULL_REQUEST_BYTES)

    @field_validator("path")
    @classmethod
    def _inside_the_repository(cls, path: str) -> str:
        if path.startswith("/") or ".." in path.split("/") or path.startswith(".git/"):
            raise ValueError("a path is relative to the repository and can't climb out of it")
        return path


class GithubOpenPullRequestInput(BaseModel):
    """PRD-Studio GH-06: up to 20 files and 1 MiB in all, and no repository."""

    model_config = TOOL_CONTRACT

    title: str = Field(min_length=1, max_length=256)
    body: str = Field(default="", max_length=60_000)
    base: GithubBranch
    files: list[GithubFileChange] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def _bounded(self) -> "GithubOpenPullRequestInput":
        if sum(len(item.content.encode()) for item in self.files) > MAX_PULL_REQUEST_BYTES:
            raise ValueError("the changes are more than 1 MiB in all")
        if len({item.path for item in self.files}) != len(self.files):
            raise ValueError("each path appears once")
        return self


class GithubOpenPullRequestOutput(BaseModel):
    model_config = TOOL_CONTRACT

    number: int
    url: str
    branch: str
    head_sha: str


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
    "automation",
]
ToolProviderName = Literal["autobots", "tavily", "jina", "yahoo_finance", "world_bank", "github"]
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
    side_effects: Literal["none", "internal_write", "external_write", "arbitrary"]
    network: bool
    cost_class: Literal["free_local", "metered_provider"]
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


# US-14.9, PRD-Tool-Catalog "File tools". Text only; content never becomes a public field.
TextMediaType = Literal["text/plain", "text/markdown", "application/json", "text/csv"]


class ReadRunFileV2Input(BaseModel):
    model_config = TOOL_CONTRACT

    path: str = Field(min_length=1, max_length=500)
    offset: int = Field(default=0, ge=0, description="The first line to return, from 0.")
    limit: int | None = Field(
        default=None, ge=1, le=20_000, description="How many lines. Left out, to the end."
    )


class ReadRunFileV2Output(BaseModel):
    model_config = TOOL_CONTRACT

    path: str
    version: int
    media_type: str
    sha256: str
    content: str
    offset: int
    total_lines: int
    truncated: bool


class ReadCsvInput(BaseModel):
    model_config = TOOL_CONTRACT

    path: str = Field(min_length=1, max_length=500)
    delimiter: Literal[",", ";", "\t", "|"] = ","
    has_header: bool = True
    max_rows: int = Field(default=100, ge=1, le=500)
    columns: list[str] = Field(default_factory=list, max_length=50)


class CsvColumn(BaseModel):
    model_config = TOOL_CONTRACT

    name: str
    inferred_type: Literal["integer", "number", "boolean", "date", "string", "empty"]


class ReadCsvOutput(BaseModel):
    model_config = TOOL_CONTRACT

    path: str
    version: int
    columns: list[CsvColumn]
    rows: list[list[str]]
    row_count: int
    truncated: bool


class StoreRemoteFileInput(BaseModel):
    model_config = TOOL_CONTRACT

    url: str = Field(min_length=1, max_length=2048)
    path: str = Field(min_length=1, max_length=500, pattern=r"^outputs/")


class StoreRemoteFileOutput(BaseModel):
    model_config = TOOL_CONTRACT

    path: str
    version: int
    sha256: str
    size_bytes: int
    media_type: TextMediaType


class GrantedTo(BaseModel):
    """An Expert or a published workflow that grants a tool, with the version that does."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    name: str
    version: int


class ToolGrants(BaseModel):
    """PRD-Studio TL-02: latest Expert versions, and published workflows through agent steps."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1]
    tool_id: str
    experts: list[GrantedTo]
    workflows: list[GrantedTo]
