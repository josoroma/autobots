"""Inputs and outputs of the GitHub tools, PRD-Studio GH-01 to GH-06.

None names a repository: the one configured repository is server configuration (Decision 0007,
widened by Decision 0022 D6). Every input is bounded.
"""

import re
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from autobots.contracts.primitives import TOOL_CONTRACT, UtcInput
from autobots.contracts.tool_fields import CommitPath, IssueBody, IssueTitle, RepoPath


class CreateGithubIssueInput(BaseModel):
    """No field names a repository: that's server configuration, by Decision 0007."""

    model_config = TOOL_CONTRACT

    title: IssueTitle
    body: IssueBody


class CreateGithubIssueOutput(BaseModel):
    model_config = TOOL_CONTRACT

    number: int
    url: str


GithubLabel = Annotated[str, Field(min_length=1, max_length=50)]


class CreateGithubIssueV2Input(BaseModel):
    """PRD-Studio GH-05: version 1's fields, and up to 10 labels. Still no repository."""

    model_config = TOOL_CONTRACT

    title: IssueTitle
    body: IssueBody
    labels: list[GithubLabel] = Field(default_factory=list, max_length=10)


GithubBranch = Annotated[str, Field(min_length=1, max_length=255, pattern=r"^[A-Za-z0-9._/-]+$")]
GithubLimit = Annotated[int, Field(ge=1, le=100)]
# Qualifiers that would widen a search past the configured repository are refused.
_SEARCH_SCOPE = re.compile(r"(?i)(^|\s)-?(repo|org|user|owner)\s*:")


class GithubListPullRequestsInput(BaseModel):
    model_config = TOOL_CONTRACT

    state: Literal["open", "closed", "merged"] = "open"
    base: GithubBranch | None = None
    since: UtcInput | None = None
    limit: GithubLimit = 30


class GithubPullRequest(BaseModel):
    model_config = TOOL_CONTRACT

    number: int
    title: str
    author: str | None
    # GitHub's own text, as v1's output schema states it.
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
    since: UtcInput | None = None
    limit: GithubLimit = 20


class GithubFailingJob(BaseModel):
    model_config = TOOL_CONTRACT

    name: str
    failed_steps: list[str]


class GithubWorkflowRun(BaseModel):
    model_config = TOOL_CONTRACT

    id: int
    conclusion: str | None
    # GitHub's own text, as v1's output schema states it.
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

    path: RepoPath
    ref: GithubBranch | None = None


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

    path: CommitPath
    content: str = Field(max_length=MAX_PULL_REQUEST_BYTES)


class GithubOpenPullRequestInput(BaseModel):
    """PRD-Studio GH-06: up to 20 files and 1 MiB in all, and no repository."""

    model_config = TOOL_CONTRACT

    title: IssueTitle
    body: IssueBody = ""
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
