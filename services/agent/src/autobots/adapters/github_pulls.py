"""The second consequential GitHub connector, PRD-Studio GH-06 and Decision 0022 D6, D7 and D15.

A person approves each pull request with every file's diff against the base branch's head, which
the approval binds. The connector creates `autobots/<operation_id>`, commits only the named paths on
that head, and opens the pull request with the operation ID as a marker. If the head moved, it stops
with base_moved and the request returns to pending with a diff against the new head. A retry
reads the branch and its open pull request back first, so a lost reply never opens a second one.
Merging is not offered.
"""

import base64
import difflib
import json
import os
from collections.abc import Mapping
from typing import Any
from urllib.parse import quote

import httpx

from autobots.adapters.github_issues import (
    GITHUB_KEY,
    TARGET_PREFIX,
    approval_target,
    attempt_target,
    github_client,
    marker,
)
from autobots.application.runs import append_event
from autobots.application.tool_gateway import (
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
_REFUSED = frozenset({400, 401, 403, 404, 409, 410, 422, 429})


class UnclearReply(Exception):
    """GitHub's reply doesn't say whether the write happened."""


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


def github_pull_request_tool(
    transport: httpx.AsyncBaseTransport | None = None,
    environ: Mapping[str, str] = os.environ,
) -> ToolDefinition:
    async def read(http: httpx.AsyncClient, path: str, params: Any = None) -> httpx.Response:
        try:
            return await http.get(path, params=params)
        except httpx.HTTPError:
            raise ToolFailed("destination_unreachable") from None

    async def head_of(http: httpx.AsyncClient, repository: str, branch: str) -> str | None:
        reply = await read(http, f"/repos/{repository}/git/ref/heads/{quote(branch)}")
        if reply.status_code == 404:
            return None
        if reply.status_code != 200:
            raise ToolFailed(f"github_refused_{reply.status_code}")
        return str(reply.json()["object"]["sha"])

    async def content_at(
        http: httpx.AsyncClient, repository: str, path: str, sha: str
    ) -> str | None:
        reply = await read(http, f"/repos/{repository}/contents/{quote(path)}", {"ref": sha})
        if reply.status_code == 404:
            return None
        if reply.status_code != 200:
            raise ToolFailed(f"github_refused_{reply.status_code}")
        found = reply.json()
        if not isinstance(found, dict) or found.get("type") != "file":
            raise ToolFailed("github_path_not_a_file")
        try:
            return base64.b64decode(str(found.get("content") or "")).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            raise ToolFailed("github_file_not_text") from None

    async def detail_against(
        http: httpx.AsyncClient, repository: str, arguments: GithubOpenPullRequestInput
    ) -> dict[str, Any]:
        base_sha = await head_of(http, repository, arguments.base)
        if base_sha is None:
            raise ToolFailed("github_base_not_found")
        files = []
        for item in arguments.files:
            change, diff = _unified(
                item.path, await content_at(http, repository, item.path, base_sha), item.content
            )
            files.append({"path": item.path, "change": change, "diff": diff})
        return {"base_branch": arguments.base, "base_sha": base_sha, "files": files}

    async def review(arguments: GithubOpenPullRequestInput, context: ToolContext) -> dict[str, Any]:
        """Before any approval: reads only, so nothing is written for an unapproved call."""
        repository, token = await attempt_target(context, environ)
        async with github_client(token, transport) as http:
            return await detail_against(http, repository, arguments)

    async def approved_detail(context: ToolContext) -> dict[str, Any]:
        cursor = await context.connection.execute(
            "select review_detail from public.approval_requests where operation_id = %s "
            "and status = 'approved'",
            (context.operation_id,),
        )
        row = await cursor.fetchone()
        if row is None or row[0] is None:
            raise ToolFailed("review_detail_missing")
        detail: dict[str, Any] = row[0]
        return detail

    async def return_to_review(context: ToolContext, detail: dict[str, Any]) -> None:
        """D15: nothing was sent, so this attempt is settled, and the request goes back to a person
        with the diff against the new head. Its next approval sends against that head."""
        await context.connection.execute(
            "update app_private.tool_receipts set reconciled_at = now() where operation_id = %s",
            (context.operation_id,),
        )
        cursor = await context.connection.execute(
            "update public.approval_requests set status = 'pending', decided_by = null, "
            "decided_at = null, review_detail = %s, "
            "expires_at = clock_timestamp() + interval '1 day' "
            "where operation_id = %s returning id, run_id",
            (json.dumps(detail), context.operation_id),
        )
        row = await cursor.fetchone()
        if row is not None:
            await append_event(
                context.connection,
                row[1],
                {"type": "approval.requested", "approval_id": str(row[0]), "tool_id": TOOL_ID},
            )

    async def existing(
        http: httpx.AsyncClient, repository: str, branch: str
    ) -> GithubOpenPullRequestOutput | None:
        owner = repository.split("/")[0]
        reply = await read(
            http, f"/repos/{repository}/pulls", {"head": f"{owner}:{branch}", "state": "open"}
        )
        if reply.status_code != 200:
            raise UnclearReply(reply.status_code)
        for pull in reply.json():
            if (pull.get("head") or {}).get("ref") == branch:
                return GithubOpenPullRequestOutput(
                    number=int(pull["number"]),
                    url=str(pull["html_url"]),
                    branch=branch,
                    head_sha=str((pull.get("head") or {}).get("sha") or ""),
                )
        return None

    async def write(http: httpx.AsyncClient, path: str, payload: dict[str, Any]) -> Any:
        try:
            reply = await http.post(path, json=payload)
        except (httpx.ConnectError, httpx.ConnectTimeout):
            raise ToolFailed("destination_unreachable") from None
        if reply.status_code in _REFUSED:
            raise ToolFailed(f"github_refused_{reply.status_code}")
        if reply.status_code != 201:
            raise UnclearReply(reply.status_code)
        return reply.json()

    async def open_pull_request(
        arguments: GithubOpenPullRequestInput, context: ToolContext
    ) -> GithubOpenPullRequestOutput:
        repository, token = await attempt_target(context, environ)
        approved = await approved_detail(context)
        branch = branch_for(context.operation_id)
        async with github_client(token, transport) as http:
            head = await head_of(http, repository, arguments.base)
            if head != approved["base_sha"]:
                if head is not None:
                    await return_to_review(
                        context, await detail_against(http, repository, arguments)
                    )
                raise ToolFailed("base_moved")
            commit = await head_of(http, repository, branch)
            if commit is None:
                base_commit = await read(http, f"/repos/{repository}/git/commits/{head}")
                if base_commit.status_code != 200:
                    raise ToolFailed(f"github_refused_{base_commit.status_code}")
                tree = await write(
                    http,
                    f"/repos/{repository}/git/trees",
                    {
                        "base_tree": base_commit.json()["tree"]["sha"],
                        "tree": [
                            {
                                "path": item.path,
                                "mode": "100644",
                                "type": "blob",
                                "content": item.content,
                            }
                            for item in arguments.files
                        ],
                    },
                )
                made = await write(
                    http,
                    f"/repos/{repository}/git/commits",
                    {"message": arguments.title, "tree": tree["sha"], "parents": [head]},
                )
                commit = str(made["sha"])
                await write(
                    http,
                    f"/repos/{repository}/git/refs",
                    {"ref": f"refs/heads/{branch}", "sha": commit},
                )
            found = await existing(http, repository, branch)
            if found is not None:
                return found
            pull = await write(
                http,
                f"/repos/{repository}/pulls",
                {
                    "title": arguments.title,
                    "head": branch,
                    "base": arguments.base,
                    "body": f"{arguments.body}\n\n{marker(context.operation_id)}",
                },
            )
        return GithubOpenPullRequestOutput(
            number=int(pull["number"]), url=str(pull["html_url"]), branch=branch, head_sha=commit
        )

    async def readback(
        _: GithubOpenPullRequestInput, context: ToolContext
    ) -> GithubOpenPullRequestOutput:
        """The branch, then any open pull request from it. Neither means nothing was opened."""
        repository, token = await attempt_target(context, environ)
        branch = branch_for(context.operation_id)
        async with github_client(token, transport) as http:
            found = await existing(http, repository, branch)
        if found is not None:
            return found
        raise NotDelivered

    def review_target(_arguments: Any) -> str | None:
        repository = environ.get("GITHUB_REPOSITORY", "")
        return f"{TARGET_PREFIX}{repository}" if repository else None

    async def resolve_target(arguments: Any, context: ToolContext) -> str:
        return await approval_target(arguments, context, environ)

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
        handler=open_pull_request,
        reconcile=readback,
        review_detail=review,
        resource_target=review_target,
        target_resolver=resolve_target,
        timeout_seconds=60.0,
        max_output_bytes=10_000,
        public_input_fields=("title", "base"),
        public_output_fields=("number", "url", "branch", "head_sha"),
    )


GITHUB_PULL_REQUEST = github_pull_request_tool()
