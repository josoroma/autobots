"""The second consequential GitHub connector, PRD-Studio GH-06 and Decision 0022 D6, D7 and D15.

A person approves each pull request with every file's diff against the base branch's head, which
the approval binds. The connector creates `autobots/<operation_id>`, commits only the named paths on
that head, and opens the pull request with the operation ID as a marker. If the head moved, it stops
with base_moved and the request returns to pending with a diff against the new head. A retry
reads the branch and its open pull request back first, so a lost reply never opens a second one.
Merging is not offered.
"""

import difflib
import os
from collections.abc import Mapping
from functools import partial
from urllib.parse import quote

import httpx
from pydantic import RootModel

from autobots.adapters.github_connector import (
    GIT_WRITE_REFUSED,
    GITHUB_KEY,
    PULL_WRITE_REFUSED,
    ContentReply,
    GithubApi,
    GithubConnector,
    RefReply,
    Sha,
    file_text,
    marker,
)
from autobots.adapters.provider_http import ProviderReply, Text, UnclearReply
from autobots.application.tool_definitions import (
    ApprovalPolicy,
    NotDelivered,
    ToolContext,
    ToolDefinition,
    ToolFailed,
)
from autobots.contracts.tools import (
    GithubOpenPullRequestInput,
    GithubOpenPullRequestOutput,
)
from autobots.domain.tool_catalog import ToolGroup, ToolProvider
from autobots.domain.tools import OperationClass

TOOL_ID = "github_open_pull_request"
BRANCH_PREFIX = "autobots/"


class _Commit(ProviderReply):
    tree: Sha


class _Head(ProviderReply):
    ref: Text = ""
    sha: Text = ""


class _Pull(ProviderReply):
    number: int
    html_url: str
    head: _Head = _Head()


class _Pulls(RootModel[list[_Pull]]):
    pass


def branch_for(operation_id: str | None) -> str:
    return f"{BRANCH_PREFIX}{operation_id}"


def _unified(path: str, before: str | None, after: str) -> tuple[str, str]:
    if before == after:
        return "unchanged", ""
    lines = difflib.unified_diff(
        (before or "").splitlines(keepends=True),
        after.splitlines(keepends=True),
        fromfile="/dev/null" if before is None else f"a/{path}",
        tofile=f"b/{path}",
    )
    return ("added" if before is None else "modified"), "".join(lines)


async def head_of(api: GithubApi, branch: str) -> str | None:
    """The branch's head commit, or None when there is no such branch."""
    found = await api.find(api.repo(f"/git/ref/heads/{quote(branch)}"), RefReply)
    return None if found is None else found.target.sha


async def content_at(api: GithubApi, path: str, sha: str) -> str | None:
    """A file's text at a commit, or None when the path isn't there."""
    found = await api.find(api.repo(f"/contents/{quote(path)}"), ContentReply, {"ref": sha})
    return None if found is None else file_text(found.file())[1]


async def detail_against(
    api: GithubApi, arguments: GithubOpenPullRequestInput
) -> dict[str, object]:
    """What a reviewer approves: each file's diff against the base branch's head."""
    base_sha = await head_of(api, arguments.base)
    if base_sha is None:
        raise ToolFailed("github_base_not_found")
    files = []
    for item in arguments.files:
        change, diff = _unified(item.path, await content_at(api, item.path, base_sha), item.content)
        files.append({"path": item.path, "change": change, "diff": diff})
    return {"base_branch": arguments.base, "base_sha": base_sha, "files": files}


async def review_detail(
    github: GithubConnector, arguments: GithubOpenPullRequestInput, context: ToolContext
) -> dict[str, object]:
    """Before any approval: reads only, so nothing is written for an unapproved call."""
    async with github.attempt(context) as api:
        return await detail_against(api, arguments)


def approved_base(context: ToolContext) -> tuple[str, str]:
    """This attempt's operation and the base head its approval bound (PRD-Studio GH-06), as the
    gateway handed them over (XMOD-02)."""
    operation_id, approved = context.operation_id, context.approval
    if operation_id is None or approved is None or approved.review_detail is None:
        raise ToolFailed("review_detail_missing")
    return operation_id, str(approved.review_detail["base_sha"])


async def open_pull(api: GithubApi, branch: str) -> GithubOpenPullRequestOutput | None:
    """The open pull request from `branch`, if one exists. A reply that doesn't say stays unknown,
    since it decides whether one is opened."""
    owner = api.repository.split("/")[0]
    found = await api.settle(
        api.repo("/pulls"), _Pulls, {"head": f"{owner}:{branch}", "state": "open"}
    )
    for pull in found.root:
        if pull.head.ref == branch:
            return GithubOpenPullRequestOutput(
                number=pull.number, url=pull.html_url, branch=branch, head_sha=pull.head.sha
            )
    return None


async def commit_files(
    api: GithubApi, arguments: GithubOpenPullRequestInput, base: str, branch: str
) -> str:
    """The named files committed on `base` and pushed as `branch`: a tree, a commit, then the ref.
    A refused write fails before the next, and an unclear one stays unknown."""
    base_commit = await api.read(api.repo(f"/git/commits/{base}"), _Commit)
    tree = await api.create(
        api.repo("/git/trees"),
        {
            "base_tree": base_commit.tree.sha,
            "tree": [
                {"path": item.path, "mode": "100644", "type": "blob", "content": item.content}
                for item in arguments.files
            ],
        },
        Sha,
        GIT_WRITE_REFUSED,
    )
    made = await api.create(
        api.repo("/git/commits"),
        {"message": arguments.title, "tree": tree.sha, "parents": [base]},
        Sha,
        GIT_WRITE_REFUSED,
    )
    await api.create_only(
        api.repo("/git/refs"), {"ref": f"refs/heads/{branch}", "sha": made.sha}, GIT_WRITE_REFUSED
    )
    return made.sha


async def open_pull_request(
    github: GithubConnector, arguments: GithubOpenPullRequestInput, context: ToolContext
) -> GithubOpenPullRequestOutput:
    operation_id, approved_sha = approved_base(context)
    branch = branch_for(operation_id)
    async with github.attempt(context) as api:
        head = await head_of(api, arguments.base)
        if head != approved_sha:
            if head is not None:
                # A person approves again, against the new head (Decision 0022 D15). The run
                # keeps running and waits once the call is tried again (Decision 0028 E1).
                await context.return_to_review(TOOL_ID, await detail_against(api, arguments))
            raise ToolFailed("base_moved")
        commit = await head_of(api, branch)
        if commit is None:
            commit = await commit_files(api, arguments, head, branch)
        found = await open_pull(api, branch)
        if found is not None:
            return found
        try:
            pull = await api.create(
                api.repo("/pulls"),
                {
                    "title": arguments.title,
                    "head": branch,
                    "base": arguments.base,
                    "body": f"{arguments.body}\n\n{marker(context.operation_id)}",
                },
                _Pull,
                PULL_WRITE_REFUSED,
            )
        except UnclearReply as unclear:
            # GitHub answers 422 when this branch's pull request already exists, so it is read
            # back. One that doesn't show yet leaves the outcome unknown for the readback.
            if unclear.status_code != 422:
                raise
            existing = await open_pull(api, branch)
            if existing is None:
                raise
            return existing
    return GithubOpenPullRequestOutput(
        number=pull.number, url=pull.html_url, branch=branch, head_sha=commit
    )


async def find_pull_request(
    github: GithubConnector, _: GithubOpenPullRequestInput, context: ToolContext
) -> GithubOpenPullRequestOutput:
    """The branch's open pull request. None open means nothing was opened."""
    async with github.attempt(context) as api:
        found = await open_pull(api, branch_for(context.operation_id))
    if found is not None:
        return found
    raise NotDelivered


def github_pull_request_tool(
    transport: httpx.AsyncBaseTransport | None = None,
    environ: Mapping[str, str] = os.environ,
) -> ToolDefinition:
    github = GithubConnector(transport, environ)
    return ToolDefinition(
        tool_id=TOOL_ID,
        version=1,
        title="Open pull request",
        description=(
            "Propose a pull request in the configured GitHub repository: a title, body, base "
            "branch and up to 20 files' full new content, 1 MiB in all. A person approves it "
            "with each file's diff. It's never merged."
        ),
        group=ToolGroup.CONNECTORS,
        provider=ToolProvider.GITHUB,
        network=True,
        key_requirement=GITHUB_KEY,
        operation_class=OperationClass.CONSEQUENTIAL_EXTERNAL_WRITE,
        input_model=GithubOpenPullRequestInput,
        output_model=GithubOpenPullRequestOutput,
        handler=partial(open_pull_request, github),
        reconcile=partial(find_pull_request, github),
        # The approval records the repository resolved for the workspace (Decision 0025 V7).
        approval=ApprovalPolicy(
            review_detail=partial(review_detail, github), target_resolver=github.approval_label
        ),
        timeout_seconds=60.0,
        max_output_bytes=10_000,
        public_input_fields=("title", "base"),
        public_output_fields=("number", "url", "branch", "head_sha"),
    )


GITHUB_PULL_REQUEST = github_pull_request_tool()
