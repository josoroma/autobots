"""What every GitHub tool shares: one resolution and one client per call, one read mapping, and a
named table of the statuses that prove a write wrote nothing (refactor plan R-62: PADP-04, PADP-05,
PADP-06 and PADP-19). Fake transports only.
"""

import asyncio
from collections.abc import Awaitable, Mapping
from uuid import UUID, uuid4

import httpx
import pytest

from autobots.adapters import github_connector
from autobots.adapters.github_connector import (
    GIT_WRITE_REFUSED,
    ISSUE_WRITE_REFUSED,
    PULL_WRITE_REFUSED,
    READ_REFUSED,
    REQUEST_SECONDS,
    github_read_code,
)
from autobots.adapters.github_issues import github_issue_tool
from autobots.adapters.github_pulls import GITHUB_PULL_REQUEST
from autobots.adapters.github_reads import GITHUB_READ_TOOLS, github_read_tools
from autobots.application import tool_keys
from autobots.application.sql import SqlConnection
from autobots.application.tool_definitions import ToolContext, ToolFailed, ToolScope
from sql_fakes import ScriptedConnection

REPOSITORY = "owner/configured"
ENV = {"GITHUB_REPOSITORY": REPOSITORY, "GITHUB_TOKEN": "github_pat_fixture0001"}
CONTEXT = ToolContext(ScriptedConnection(), ToolScope(uuid4(), uuid4(), 1, {}), "op-1")


@pytest.mark.parametrize("status", sorted(READ_REFUSED))
def test_a_read_refused_for_the_request_or_the_token_names_its_status(status: int) -> None:
    assert github_read_code(status) == f"github_refused_{status}"


@pytest.mark.parametrize("status", [302, 405, 500, 502, 503, 504, 599])
def test_any_other_read_failure_is_github_unavailable(status: int) -> None:
    assert github_read_code(status) == "github_unavailable"


def test_an_empty_repositorys_conflict_on_a_read_is_a_refusal_not_an_outage() -> None:
    assert github_read_code(409) == "github_refused_409"


def test_each_write_class_names_the_statuses_that_prove_nothing_was_written() -> None:
    """Only Git data counts a conflict as nothing written, and a pull request create doesn't count
    a 422, which GitHub also answers when that pull request already exists."""
    assert ISSUE_WRITE_REFUSED == frozenset({400, 401, 403, 404, 410, 422, 429})
    assert GIT_WRITE_REFUSED == ISSUE_WRITE_REFUSED | {409}
    assert PULL_WRITE_REFUSED == GIT_WRITE_REFUSED - {422}
    for table in (ISSUE_WRITE_REFUSED, GIT_WRITE_REFUSED, PULL_WRITE_REFUSED):
        assert not any(status >= 500 for status in table)


def test_the_request_bound_fits_inside_each_github_tools_timeout() -> None:
    """A request's timeout is named beside the tool timeouts it must fit inside (PADP-05)."""
    tools = [github_issue_tool(), GITHUB_PULL_REQUEST, *GITHUB_READ_TOOLS]
    assert all(REQUEST_SECONDS < tool.timeout_seconds for tool in tools)


def test_the_approval_records_the_target_resolver_and_nothing_else() -> None:
    """Both GitHub writes record what the resolver returns, so neither keeps a second, unused
    label from the arguments (PADP-19)."""
    for tool in (github_issue_tool(), GITHUB_PULL_REQUEST):
        assert tool.approval.target_resolver is not None
        assert tool.approval.resource_target(object()) is None


def settled[T](awaitable: Awaitable[T]) -> T:
    """Runs a tool's handler, readback or resolver, which are typed as plain awaitables."""

    async def wait() -> T:
        return await awaitable

    return asyncio.run(wait())


def test_one_call_resolves_its_repository_and_token_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """A workflow listing reads each failed run's jobs from the repository it listed (PADP-06)."""
    resolved: list[tuple[UUID | None, str]] = []
    real = tool_keys.attempt_value

    async def counted(
        connection: SqlConnection | None,
        workspace: UUID | None,
        item: tool_keys.Item,
        environ: Mapping[str, str],
    ) -> str | None:
        resolved.append((workspace, item.name))
        return await real(connection, workspace, item, environ)

    monkeypatch.setattr(tool_keys, "attempt_value", counted)
    paths: list[str] = []

    def github(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path.endswith("/jobs"):
            return httpx.Response(200, json={"jobs": []})
        failed = [{"id": number, "conclusion": "failure"} for number in range(3)]
        return httpx.Response(200, json={"workflow_runs": failed})

    tool = {tool.tool_id: tool for tool in github_read_tools(httpx.MockTransport(github), ENV)}[
        "github_list_workflow_runs"
    ]
    arguments = tool.input_model.model_validate({})
    settled(tool.handler(arguments, CONTEXT))
    assert len(paths) == 4 and all(path.startswith(f"/repos/{REPOSITORY}/") for path in paths)
    workspace = CONTEXT.scope.workspace_id
    assert resolved == [(workspace, "github_repository"), (workspace, "github_token")]


def test_an_attempt_without_a_valid_repository_sends_nothing() -> None:
    sent: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200)

    connector = github_connector.GithubConnector(
        httpx.MockTransport(record),
        {"GITHUB_REPOSITORY": "https://evil.example/o/r", "GITHUB_TOKEN": "github_pat_fixture0001"},
    )

    async def attempt() -> None:
        async with connector.attempt(CONTEXT):
            pass

    with pytest.raises(ToolFailed, match=r"^connector_not_configured$"):
        asyncio.run(attempt())
    assert sent == []
