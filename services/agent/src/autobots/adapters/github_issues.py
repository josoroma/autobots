"""The first consequential connector, Decision 0007: one operation on one configured repository.

The repository is server configuration, so a model can't choose it, and the token is read for each
attempt and kept nowhere. GitHub has no idempotency key for this call, so each issue has a marker
with its operation ID, and an uncertain outcome is settled by reading the repository's issues back.
"""

import asyncio
import os
import re
from collections.abc import Mapping, Sequence
from typing import Any

import httpx

from autobots.application.tool_gateway import (
    NotDelivered,
    ToolContext,
    ToolDefinition,
    ToolFailed,
)
from autobots.contracts.tools import CreateGithubIssueInput, CreateGithubIssueOutput
from autobots.domain.tools import OperationClass

API_URL = "https://api.github.com"
REPOSITORY_VARIABLE = "GITHUB_REPOSITORY"
TOKEN_VARIABLE = "GITHUB_TOKEN"
TOOL_ID = "create_github_issue"
_REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
# GitHub answered, and nothing was created. Anything else unclear stays uncertain.
_REFUSED = frozenset({400, 401, 403, 404, 410, 422, 429})
_REQUEST_SECONDS = 15.0
_READBACK_ISSUES = 100
# The issue list can lag a create: a live run read it at once and missed the new issue.
# "Not delivered" lets the gateway send again, so it's only said after these waits. They stay well
# inside the tool's timeout, and running out of that time records an unknown outcome, which never
# sends again.
READBACK_SETTLE_SECONDS = (1.0, 2.0, 4.0, 8.0)


class UnclearReply(Exception):
    """The destination's reply doesn't say whether the issue exists."""


def marker(operation_id: str | None) -> str:
    return f"<!-- autobots-operation:{operation_id} -->"


def _output(issue: Mapping[str, Any]) -> CreateGithubIssueOutput:
    return CreateGithubIssueOutput(number=int(issue["number"]), url=str(issue["html_url"]))


def github_issue_tool(
    transport: httpx.AsyncBaseTransport | None = None,
    environ: Mapping[str, str] = os.environ,
    settle_seconds: Sequence[float] = READBACK_SETTLE_SECONDS,
) -> ToolDefinition:
    def review_target(_arguments: Any) -> str | None:
        """Server configuration only, so a reviewer sees where it goes whatever a model asked."""
        repository = environ.get(REPOSITORY_VARIABLE, "")
        return f"GitHub repository {repository}" if _REPOSITORY.fullmatch(repository) else None

    def target() -> tuple[str, str]:
        repository = environ.get(REPOSITORY_VARIABLE, "")
        token = environ.get(TOKEN_VARIABLE, "")
        if not token or not _REPOSITORY.fullmatch(repository):
            raise ToolFailed("connector_not_configured")
        return repository, token

    def client(token: str) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=API_URL,
            transport=transport,
            timeout=_REQUEST_SECONDS,
            follow_redirects=False,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )

    async def create(
        arguments: CreateGithubIssueInput, context: ToolContext
    ) -> CreateGithubIssueOutput:
        repository, token = target()
        body = f"{arguments.body}\n\n{marker(context.operation_id)}"
        async with client(token) as http:
            try:
                reply = await http.post(
                    f"/repos/{repository}/issues", json={"title": arguments.title, "body": body}
                )
            except (httpx.ConnectError, httpx.ConnectTimeout):
                # The connection never opened, so nothing reached GitHub.
                raise ToolFailed("destination_unreachable") from None
        if reply.status_code in _REFUSED:
            raise ToolFailed(f"github_refused_{reply.status_code}")
        if reply.status_code != 201:
            raise UnclearReply(reply.status_code)
        return _output(reply.json())

    async def readback(_: CreateGithubIssueInput, context: ToolContext) -> CreateGithubIssueOutput:
        """Reads the list, which lags less than search, and gives a new issue time to appear."""
        repository, token = target()
        expected = marker(context.operation_id)
        async with client(token) as http:
            for wait in (0.0, *settle_seconds):
                await asyncio.sleep(wait)
                reply = await http.get(
                    f"/repos/{repository}/issues",
                    params={
                        "state": "all",
                        "sort": "created",
                        "direction": "desc",
                        "per_page": _READBACK_ISSUES,
                    },
                )
                if reply.status_code != 200:
                    raise UnclearReply(reply.status_code)
                for issue in reply.json():
                    if expected in (issue.get("body") or ""):
                        return _output(issue)
        raise NotDelivered

    return ToolDefinition(
        tool_id=TOOL_ID,
        version=1,
        description=(
            "Create an issue in the one GitHub repository this workspace configured. "
            "Each call waits for a person's approval."
        ),
        input_model=CreateGithubIssueInput,
        output_model=CreateGithubIssueOutput,
        operation_class=OperationClass.CONSEQUENTIAL_EXTERNAL_WRITE,
        handler=create,
        timeout_seconds=30.0,
        reconcile=readback,
        resource_target=review_target,
    )


GITHUB_ISSUE = github_issue_tool()
