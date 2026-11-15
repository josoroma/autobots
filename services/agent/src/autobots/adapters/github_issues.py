"""The first consequential connector, Decision 0007: one operation on one configured repository.

The repository is server configuration, so a model can't choose it, and the token is read for each
attempt and kept nowhere (github_connector). GitHub has no idempotency key for this call, so each
issue has a marker with its operation ID, and an uncertain outcome is settled by reading the
repository's issues back.
"""

import asyncio
import os
from collections.abc import Mapping, Sequence
from functools import partial

import httpx
from pydantic import RootModel

from autobots.adapters.github_connector import (
    API_URL,
    GITHUB_KEY,
    ISSUE_WRITE_REFUSED,
    REPOSITORY_VARIABLE,
    TOKEN_VARIABLE,
    GithubConnector,
    marker,
)
from autobots.adapters.provider_http import ProviderReply
from autobots.application.tool_gateway import (
    ApprovalPolicy,
    NotDelivered,
    ToolContext,
    ToolDefinition,
)
from autobots.contracts.tools import (
    CreateGithubIssueInput,
    CreateGithubIssueOutput,
    CreateGithubIssueV2Input,
)
from autobots.domain.tool_catalog import ToolGroup, ToolProvider
from autobots.domain.tools import OperationClass

# API_URL, REPOSITORY_VARIABLE, TOKEN_VARIABLE and marker are imported from here by tests/db,
# tests/qualification and scripts/qualify_github_connector.py.
__all__ = [
    "API_URL",
    "GITHUB_ISSUE",
    "GITHUB_ISSUE_V2",
    "READBACK_SETTLE_SECONDS",
    "REPOSITORY_VARIABLE",
    "TOKEN_VARIABLE",
    "TOOL_ID",
    "github_issue_tool",
    "marker",
]

TOOL_ID = "create_github_issue"
_READBACK_ISSUES = 100
# The issue list can lag a create: a live run read it at once and missed the new issue.
# "Not delivered" lets the gateway send again, so it's only said after these waits. They stay well
# inside the tool's timeout, and running out of that time records an unknown outcome, which never
# sends again.
READBACK_SETTLE_SECONDS = (1.0, 2.0, 4.0, 8.0)

IssueInput = CreateGithubIssueInput | CreateGithubIssueV2Input


class _Issue(ProviderReply):
    number: int
    html_url: str
    body: str | None = None

    def output(self) -> CreateGithubIssueOutput:
        return CreateGithubIssueOutput(number=self.number, url=self.html_url)


class _Issues(RootModel[list[_Issue]]):
    pass


async def create_issue(
    github: GithubConnector, arguments: IssueInput, context: ToolContext
) -> CreateGithubIssueOutput:
    payload: dict[str, object] = {
        "title": arguments.title,
        "body": f"{arguments.body}\n\n{marker(context.operation_id)}",
    }
    labels = arguments.labels if isinstance(arguments, CreateGithubIssueV2Input) else None
    if labels:
        payload["labels"] = list(labels)
    async with github.attempt(context) as api:
        issue = await api.create(api.repo("/issues"), payload, _Issue, ISSUE_WRITE_REFUSED)
    return issue.output()


async def find_issue(
    github: GithubConnector,
    settle_seconds: Sequence[float],
    _: IssueInput,
    context: ToolContext,
) -> CreateGithubIssueOutput:
    """Reads the list, which lags less than search, and gives a new issue time to appear."""
    expected = marker(context.operation_id)
    params: dict[str, str | int] = {
        "state": "all",
        "sort": "created",
        "direction": "desc",
        "per_page": _READBACK_ISSUES,
    }
    async with github.attempt(context) as api:
        for wait in (0.0, *settle_seconds):
            await asyncio.sleep(wait)
            issues = await api.settle(api.repo("/issues"), _Issues, params)
            for issue in issues.root:
                if expected in (issue.body or ""):
                    return issue.output()
    raise NotDelivered


def github_issue_tool(
    transport: httpx.AsyncBaseTransport | None = None,
    environ: Mapping[str, str] = os.environ,
    settle_seconds: Sequence[float] = READBACK_SETTLE_SECONDS,
    version: int = 1,
) -> ToolDefinition:
    """Version 2 (PRD-Studio GH-05) adds up to 10 labels. Version 1 is unchanged and stays
    registered, so a run whose grants pinned it keeps calling it."""
    github = GithubConnector(transport, environ)
    labelled = version == 2
    return ToolDefinition(
        tool_id=TOOL_ID,
        title="Create GitHub issue",
        group=ToolGroup.CONNECTORS,
        provider=ToolProvider.GITHUB,
        network=True,
        key_requirement=GITHUB_KEY,
        public_input_fields=("title", "labels") if labelled else ("title",),
        public_output_fields=("number", "url"),
        version=version,
        description=(
            "Create an issue, optionally with up to 10 labels, in the one GitHub repository this "
            "workspace configured. Each call waits for a person's approval."
            if labelled
            else "Create an issue in the one GitHub repository this workspace configured. "
            "Each call waits for a person's approval."
        ),
        input_model=CreateGithubIssueV2Input if labelled else CreateGithubIssueInput,
        output_model=CreateGithubIssueOutput,
        operation_class=OperationClass.CONSEQUENTIAL_EXTERNAL_WRITE,
        handler=partial(create_issue, github),
        timeout_seconds=30.0,
        reconcile=partial(find_issue, github, settle_seconds),
        # The approval records the repository resolved for the workspace (Decision 0025 V7).
        approval=ApprovalPolicy(target_resolver=github.approval_label),
    )


GITHUB_ISSUE = github_issue_tool()
GITHUB_ISSUE_V2 = github_issue_tool(version=2)
