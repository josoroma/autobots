"""Four read-only GitHub tools on the one configured repository, PRD-Studio GH-01 to GH-04.

Like the issue connector (Decision 0007, widened by Decision 0022 D6), the repository is server
configuration and the token is read for each attempt, once for the whole call (github_connector).
No input names a repository, and the issue search is pinned to it. Nothing here writes, so a call
needs no approval and has no receipt.
"""

import os
from collections.abc import Mapping
from datetime import datetime
from functools import partial
from typing import Annotated, TypedDict
from urllib.parse import quote

import httpx
from pydantic import RootModel

from autobots.adapters.github_connector import (
    GITHUB_KEY,
    ContentReply,
    GithubConnector,
    file_text,
)
from autobots.adapters.provider_http import Objects, ProviderReply, Text
from autobots.application.tool_definitions import ToolContext, ToolDefinition, ToolFailed
from autobots.contracts.tools import (
    GithubFailingJob,
    GithubIssue,
    GithubListPullRequestsInput,
    GithubListPullRequestsOutput,
    GithubListWorkflowRunsInput,
    GithubListWorkflowRunsOutput,
    GithubPullRequest,
    GithubReadFileInput,
    GithubReadFileOutput,
    GithubSearchIssuesInput,
    GithubSearchIssuesOutput,
    GithubWorkflowRun,
)
from autobots.domain.tool_catalog import KeyRequirement, ToolGroup, ToolProvider
from autobots.domain.tools import OperationClass

MAX_FILE_BYTES = 1_048_576
# Each failed run's jobs are one more request, so only the newest few are read.
FAILED_RUNS_WITH_JOBS = 10


class _Label(ProviderReply):
    name: Text = ""


class _User(ProviderReply):
    login: str | None = None


class _Labelled(ProviderReply):
    labels: Annotated[list[_Label] | None, Objects] = None

    def label_names(self) -> list[str]:
        return [label.name for label in self.labels or () if label.name]


class _Pull(_Labelled):
    number: int
    title: Text = ""
    user: _User | None = None
    merged_at: str | None = None
    updated_at: str | None = None
    html_url: Text = ""


class _Pulls(RootModel[list[_Pull]]):
    pass


class _Run(ProviderReply):
    id: int
    conclusion: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    head_sha: Text = ""


class _Runs(ProviderReply):
    workflow_runs: list[_Run] | None = None


class _Step(ProviderReply):
    name: Text = ""
    conclusion: str | None = None


class _Job(ProviderReply):
    name: Text = ""
    conclusion: str | None = None
    steps: list[_Step] | None = None


class _Jobs(ProviderReply):
    jobs: list[_Job] | None = None


class _Issue(_Labelled):
    number: int
    title: Text = ""
    state: Text = ""
    html_url: Text = ""


class _Search(ProviderReply):
    items: list[_Issue] | None = None


def _after(value: str | None, since: datetime | None) -> bool:
    if since is None or value is None:
        return True
    return datetime.fromisoformat(value.replace("Z", "+00:00")) >= since


async def list_pull_requests(
    github: GithubConnector, arguments: GithubListPullRequestsInput, context: ToolContext
) -> GithubListPullRequestsOutput:
    # GitHub's own states are open and closed. Merged is a closed one with a merge time.
    params: dict[str, str | int] = {
        "state": "closed" if arguments.state == "merged" else arguments.state,
        "sort": "updated",
        "direction": "desc",
        "per_page": arguments.limit,
    }
    if arguments.base is not None:
        params["base"] = arguments.base
    async with github.attempt(context) as api:
        found = await api.read(api.repo("/pulls"), _Pulls, params)
    listed = [
        GithubPullRequest(
            number=item.number,
            title=item.title,
            author=item.user.login if item.user is not None else None,
            merged_at=item.merged_at,
            labels=item.label_names(),
            url=item.html_url,
        )
        for item in found.root
        if (arguments.state != "merged" or item.merged_at)
        and _after(item.updated_at, arguments.since)
    ]
    return GithubListPullRequestsOutput(pull_requests=listed[: arguments.limit])


def _failing(jobs: _Jobs) -> list[GithubFailingJob]:
    return [
        GithubFailingJob(
            name=job.name,
            failed_steps=[step.name for step in job.steps or () if step.conclusion == "failure"],
        )
        for job in jobs.jobs or ()
        if job.conclusion == "failure"
    ]


async def list_workflow_runs(
    github: GithubConnector, arguments: GithubListWorkflowRunsInput, context: ToolContext
) -> GithubListWorkflowRunsOutput:
    params: dict[str, str | int] = {"per_page": arguments.limit}
    if arguments.branch is not None:
        params["branch"] = arguments.branch
    if arguments.status is not None:
        params["status"] = arguments.status
    if arguments.since is not None:
        params["created"] = f">={arguments.since.date().isoformat()}"
    path = (
        f"/actions/workflows/{quote(arguments.workflow)}/runs"
        if arguments.workflow is not None
        else "/actions/runs"
    )
    runs = []
    # Every request of the call goes to the one repository resolved for it (PADP-06).
    async with github.attempt(context) as api:
        found = (await api.read(api.repo(path), _Runs, params)).workflow_runs or []
        with_jobs = 0
        for item in found[: arguments.limit]:
            failing: list[GithubFailingJob] = []
            if item.conclusion == "failure" and with_jobs < FAILED_RUNS_WITH_JOBS:
                with_jobs += 1
                failing = _failing(await api.read(api.repo(f"/actions/runs/{item.id}/jobs"), _Jobs))
            runs.append(
                GithubWorkflowRun(
                    id=item.id,
                    conclusion=item.conclusion,
                    created_at=item.created_at,
                    updated_at=item.updated_at,
                    head_sha=item.head_sha,
                    failing_jobs=failing,
                )
            )
    return GithubListWorkflowRunsOutput(runs=runs)


async def search_issues(
    github: GithubConnector, arguments: GithubSearchIssuesInput, context: ToolContext
) -> GithubSearchIssuesOutput:
    async with github.attempt(context) as api:
        # The repository is added here, after the model's text, which can't name another one.
        qualifiers = [f"repo:{api.repository}", "is:issue"]
        if arguments.state is not None:
            qualifiers.append(f"state:{arguments.state}")
        found = await api.read(
            "/search/issues",
            _Search,
            {"q": f"{arguments.query} {' '.join(qualifiers)}", "per_page": 50},
        )
    return GithubSearchIssuesOutput(
        issues=[
            GithubIssue(
                number=item.number,
                title=item.title,
                state=item.state,
                labels=item.label_names(),
                url=item.html_url,
            )
            for item in found.items or ()
        ]
    )


async def read_file(
    github: GithubConnector, arguments: GithubReadFileInput, context: ToolContext
) -> GithubReadFileOutput:
    params = {"ref": arguments.ref} if arguments.ref is not None else None
    async with github.attempt(context) as api:
        found = await api.read(api.repo(f"/contents/{quote(arguments.path)}"), ContentReply, params)
    entry = found.file()
    size = entry.size or 0
    if size > MAX_FILE_BYTES:
        raise ToolFailed("github_file_too_large")
    raw, content = file_text(entry)
    if len(raw) > MAX_FILE_BYTES:
        raise ToolFailed("github_file_too_large")
    return GithubReadFileOutput(
        path=arguments.path, ref=arguments.ref, sha=entry.sha, size=size, content=content
    )


class _ReadTraits(TypedDict):
    """What the four read tools share. Typed, so each definition is checked field by field."""

    group: ToolGroup
    provider: ToolProvider
    network: bool
    key_requirement: KeyRequirement
    operation_class: OperationClass
    timeout_seconds: float
    retries: int
    version: int


_READS = _ReadTraits(
    group=ToolGroup.CONNECTORS,
    provider=ToolProvider.GITHUB,
    network=True,
    key_requirement=GITHUB_KEY,
    operation_class=OperationClass.READ_ONLY,
    timeout_seconds=30.0,
    retries=1,
    version=1,
)


def github_read_tools(
    transport: httpx.AsyncBaseTransport | None = None,
    environ: Mapping[str, str] = os.environ,
) -> tuple[ToolDefinition, ...]:
    github = GithubConnector(transport, environ)
    return (
        ToolDefinition(
            tool_id="github_list_pull_requests",
            title="List pull requests",
            description=(
                "List pull requests in the configured GitHub repository by state (open, closed "
                "or merged), base branch and a since time, up to 100."
            ),
            input_model=GithubListPullRequestsInput,
            output_model=GithubListPullRequestsOutput,
            handler=partial(list_pull_requests, github),
            public_input_fields=("state", "base", "since", "limit"),
            public_output_fields=("pull_requests",),
            **_READS,
        ),
        ToolDefinition(
            tool_id="github_list_workflow_runs",
            title="List workflow runs",
            description=(
                "List GitHub Actions runs in the configured repository, by workflow file, branch, "
                "status and a since time, with each failed run's failing jobs and steps."
            ),
            input_model=GithubListWorkflowRunsInput,
            output_model=GithubListWorkflowRunsOutput,
            handler=partial(list_workflow_runs, github),
            public_input_fields=("workflow", "branch", "status", "since", "limit"),
            public_output_fields=("runs",),
            **_READS,
        ),
        ToolDefinition(
            tool_id="github_search_issues",
            title="Search issues",
            description=(
                "Search issues in the configured GitHub repository only, by text and state."
            ),
            input_model=GithubSearchIssuesInput,
            output_model=GithubSearchIssuesOutput,
            handler=partial(search_issues, github),
            public_input_fields=("query", "state"),
            public_output_fields=("issues",),
            **_READS,
        ),
        ToolDefinition(
            tool_id="github_read_file",
            title="Read repository file",
            description=(
                "Read a text file of up to 1 MiB from the configured GitHub repository, at a "
                "branch, tag or commit. Its content is never shown on run screens."
            ),
            input_model=GithubReadFileInput,
            output_model=GithubReadFileOutput,
            handler=partial(read_file, github),
            max_output_bytes=MAX_FILE_BYTES + 100_000,
            public_input_fields=("path", "ref"),
            # Content stays private: a tool use keeps its SHA and size, and the output's digest.
            public_output_fields=("path", "ref", "sha", "size"),
            **_READS,
        ),
    )


GITHUB_READ_TOOLS = github_read_tools()
