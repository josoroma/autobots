"""Four read-only GitHub tools on the one configured repository, PRD-Studio GH-01 to GH-04.

Like the issue connector (Decision 0007, widened by Decision 0022 D6), the repository is server
configuration and the token is read for each attempt. No input names a repository, and the issue
search is pinned to it. Nothing here writes, so a call needs no approval and has no receipt.
"""

import base64
import binascii
import os
from collections.abc import Mapping
from datetime import datetime
from typing import Any
from urllib.parse import quote

import httpx

from autobots.adapters.github_issues import GITHUB_KEY, attempt_target, github_client
from autobots.application.tool_gateway import ToolContext, ToolDefinition, ToolFailed
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
from autobots.domain.tool_catalog import ToolGroup, ToolProvider
from autobots.domain.tools import OperationClass

MAX_FILE_BYTES = 1_048_576
# Each failed run's jobs are one more request, so only the newest few are read.
FAILED_RUNS_WITH_JOBS = 10
_REFUSED = frozenset({401, 403, 404, 410, 422, 429})


def _labels(item: Mapping[str, Any]) -> list[str]:
    return [str(label.get("name")) for label in item.get("labels") or () if label.get("name")]


def _after(value: str | None, since: datetime | None) -> bool:
    if since is None or value is None:
        return True
    return datetime.fromisoformat(value.replace("Z", "+00:00")) >= since


def _checked(reply: httpx.Response) -> Any:
    if reply.status_code in _REFUSED:
        raise ToolFailed(f"github_refused_{reply.status_code}")
    if reply.status_code != 200:
        raise ToolFailed("github_unavailable")
    return reply.json()


def github_read_tools(  # noqa: C901 - baseline 2026-11-14, shrink only (STD-06)
    transport: httpx.AsyncBaseTransport | None = None,
    environ: Mapping[str, str] = os.environ,
) -> tuple[ToolDefinition, ...]:
    async def get(context: ToolContext, path: str, params: Mapping[str, Any] | None = None) -> Any:
        repository, token = await attempt_target(context, environ)
        async with github_client(token, transport) as http:
            try:
                reply = await http.get(path.format(repository=repository), params=params)
            except httpx.HTTPError:
                raise ToolFailed("destination_unreachable") from None
        return _checked(reply)

    async def pull_requests(
        arguments: GithubListPullRequestsInput, context: ToolContext
    ) -> GithubListPullRequestsOutput:
        # GitHub's own states are open and closed. Merged is a closed one with a merge time.
        params: dict[str, Any] = {
            "state": "closed" if arguments.state == "merged" else arguments.state,
            "sort": "updated",
            "direction": "desc",
            "per_page": arguments.limit,
        }
        if arguments.base is not None:
            params["base"] = arguments.base
        found = await get(context, "/repos/{repository}/pulls", params)
        listed = [
            GithubPullRequest(
                number=int(item["number"]),
                title=str(item.get("title") or ""),
                author=(item.get("user") or {}).get("login"),
                merged_at=item.get("merged_at"),
                labels=_labels(item),
                url=str(item.get("html_url") or ""),
            )
            for item in found
            if (arguments.state != "merged" or item.get("merged_at"))
            and _after(item.get("updated_at"), arguments.since)
        ]
        return GithubListPullRequestsOutput(pull_requests=listed[: arguments.limit])

    async def workflow_runs(
        arguments: GithubListWorkflowRunsInput, context: ToolContext
    ) -> GithubListWorkflowRunsOutput:
        params: dict[str, Any] = {"per_page": arguments.limit}
        if arguments.branch is not None:
            params["branch"] = arguments.branch
        if arguments.status is not None:
            params["status"] = arguments.status
        if arguments.since is not None:
            params["created"] = f">={arguments.since.date().isoformat()}"
        path = (
            f"/repos/{{repository}}/actions/workflows/{quote(arguments.workflow)}/runs"
            if arguments.workflow is not None
            else "/repos/{repository}/actions/runs"
        )
        found = (await get(context, path, params)).get("workflow_runs") or []
        runs = []
        with_jobs = 0
        for item in found[: arguments.limit]:
            failing: list[GithubFailingJob] = []
            if item.get("conclusion") == "failure" and with_jobs < FAILED_RUNS_WITH_JOBS:
                with_jobs += 1
                jobs = (
                    await get(context, f"/repos/{{repository}}/actions/runs/{int(item['id'])}/jobs")
                ).get("jobs") or []
                failing = [
                    GithubFailingJob(
                        name=str(job.get("name") or ""),
                        failed_steps=[
                            str(step.get("name") or "")
                            for step in job.get("steps") or ()
                            if step.get("conclusion") == "failure"
                        ],
                    )
                    for job in jobs
                    if job.get("conclusion") == "failure"
                ]
            runs.append(
                GithubWorkflowRun(
                    id=int(item["id"]),
                    conclusion=item.get("conclusion"),
                    created_at=item.get("created_at"),
                    updated_at=item.get("updated_at"),
                    head_sha=str(item.get("head_sha") or ""),
                    failing_jobs=failing,
                )
            )
        return GithubListWorkflowRunsOutput(runs=runs)

    async def search_issues(
        arguments: GithubSearchIssuesInput, context: ToolContext
    ) -> GithubSearchIssuesOutput:
        repository, _token = await attempt_target(context, environ)
        # The repository is added here, after the model's text, which can't name another one.
        qualifiers = [f"repo:{repository}", "is:issue"]
        if arguments.state is not None:
            qualifiers.append(f"state:{arguments.state}")
        found = await get(
            context,
            "/search/issues",
            {"q": f"{arguments.query} {' '.join(qualifiers)}", "per_page": 50},
        )
        return GithubSearchIssuesOutput(
            issues=[
                GithubIssue(
                    number=int(item["number"]),
                    title=str(item.get("title") or ""),
                    state=str(item.get("state") or ""),
                    labels=_labels(item),
                    url=str(item.get("html_url") or ""),
                )
                for item in found.get("items") or ()
            ]
        )

    async def read_file(
        arguments: GithubReadFileInput, context: ToolContext
    ) -> GithubReadFileOutput:
        params = {"ref": arguments.ref} if arguments.ref is not None else None
        found = await get(
            context, f"/repos/{{repository}}/contents/{quote(arguments.path)}", params
        )
        if not isinstance(found, dict) or found.get("type") != "file":
            raise ToolFailed("github_path_not_a_file")
        size = int(found.get("size") or 0)
        if size > MAX_FILE_BYTES:
            raise ToolFailed("github_file_too_large")
        try:
            raw = base64.b64decode(str(found.get("content") or ""), validate=False)
            content = raw.decode("utf-8")
        except (binascii.Error, UnicodeDecodeError):
            raise ToolFailed("github_file_not_text") from None
        if len(raw) > MAX_FILE_BYTES:
            raise ToolFailed("github_file_too_large")
        return GithubReadFileOutput(
            path=arguments.path,
            ref=arguments.ref,
            sha=str(found.get("sha") or ""),
            size=size,
            content=content,
        )

    common: dict[str, Any] = {
        "group": ToolGroup.CONNECTORS,
        "provider": ToolProvider.GITHUB,
        "network": True,
        "key_requirement": GITHUB_KEY,
        "operation_class": OperationClass.READ_ONLY,
        "timeout_seconds": 30.0,
        "retries": 1,
        "version": 1,
    }
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
            handler=pull_requests,
            public_input_fields=("state", "base", "since", "limit"),
            public_output_fields=("pull_requests",),
            **common,
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
            handler=workflow_runs,
            public_input_fields=("workflow", "branch", "status", "since", "limit"),
            public_output_fields=("runs",),
            **common,
        ),
        ToolDefinition(
            tool_id="github_search_issues",
            title="Search issues",
            description=(
                "Search issues in the configured GitHub repository only, by text and state."
            ),
            input_model=GithubSearchIssuesInput,
            output_model=GithubSearchIssuesOutput,
            handler=search_issues,
            public_input_fields=("query", "state"),
            public_output_fields=("issues",),
            **common,
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
            handler=read_file,
            max_output_bytes=MAX_FILE_BYTES + 100_000,
            public_input_fields=("path", "ref"),
            # Content stays private: a tool use keeps its SHA and size, and the output's digest.
            public_output_fields=("path", "ref", "sha", "size"),
            **common,
        ),
    )


GITHUB_READ_TOOLS = github_read_tools()
