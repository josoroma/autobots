"""US-15.14: the four GitHub read tools on a fake transport only. No request reaches GitHub."""

import asyncio
import base64
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError

from autobots.adapters.github_connector import GITHUB_KEY, TOKEN_SCOPES
from autobots.adapters.github_reads import MAX_FILE_BYTES, github_read_tools
from autobots.application.tool_definitions import ToolContext, ToolFailed, ToolScope
from autobots.contracts.github_tools import GithubListPullRequestsInput, GithubListWorkflowRunsInput
from autobots.domain.tool_catalog import ToolAvailability, key_availability
from sql_fakes import ScriptedConnection

REPOSITORY = "owner/configured"
ENV = {"GITHUB_REPOSITORY": REPOSITORY, "GITHUB_TOKEN": "fake-token-for-tests"}
CONTEXT = ToolContext(
    connection=ScriptedConnection(), scope=ToolScope(uuid4(), uuid4(), 1, {}), operation_id=None
)


class FakeGithub:
    def __init__(self, file_size: int = 12) -> None:
        self.requests: list[httpx.Request] = []
        self.file_size = file_size

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if path.endswith("/pulls"):
            return httpx.Response(
                200,
                json=[
                    {
                        "number": 7,
                        "title": "Fix the flaky test",
                        "user": {"login": "ada"},
                        "merged_at": "2026-11-07T10:00:00Z",
                        "updated_at": "2026-11-07T10:00:00Z",
                        "labels": [{"name": "ci"}],
                        "html_url": f"https://github.com/{REPOSITORY}/pull/7",
                    },
                    {
                        "number": 8,
                        "title": "Closed unmerged",
                        "user": {"login": "bo"},
                        "merged_at": None,
                        "updated_at": "2026-11-07T11:00:00Z",
                        "labels": [],
                        "html_url": f"https://github.com/{REPOSITORY}/pull/8",
                    },
                ],
            )
        if path.endswith("/jobs"):
            return httpx.Response(
                200,
                json={
                    "jobs": [
                        {
                            "name": "tests",
                            "conclusion": "failure",
                            "steps": [
                                {"name": "Install", "conclusion": "success"},
                                {"name": "Run pytest", "conclusion": "failure"},
                            ],
                        },
                        {"name": "lint", "conclusion": "success", "steps": []},
                    ]
                },
            )
        if path.endswith("/runs"):
            return httpx.Response(
                200,
                json={
                    "workflow_runs": [
                        {
                            "id": 99,
                            "conclusion": "failure",
                            "created_at": "2026-11-07T09:00:00Z",
                            "updated_at": "2026-11-07T09:05:00Z",
                            "head_sha": "abc123",
                        }
                    ]
                },
            )
        if path == "/search/issues":
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "number": 3,
                            "title": "Login fails",
                            "state": "open",
                            "labels": [{"name": "bug"}],
                            "html_url": f"https://github.com/{REPOSITORY}/issues/3",
                        }
                    ]
                },
            )
        if "/contents/" in path:
            content = base64.b64encode(b"print('hi')\n").decode()
            return httpx.Response(
                200,
                json={
                    "type": "file",
                    "size": self.file_size,
                    "sha": "f1le5ha",
                    "content": "" if self.file_size > MAX_FILE_BYTES else content,
                },
            )
        return httpx.Response(599)


def tools(github: FakeGithub, environ: dict[str, str] = ENV) -> dict[str, Any]:
    return {tool.tool_id: tool for tool in github_read_tools(httpx.MockTransport(github), environ)}


def call(github: FakeGithub, tool_id: str, arguments: dict[str, Any]) -> Any:
    tool = tools(github)[tool_id]
    return asyncio.run(tool.handler(tool.input_model.model_validate(arguments), CONTEXT))


def test_each_read_returns_its_fields_from_the_configured_repository_only() -> None:
    github = FakeGithub()
    merged = call(github, "github_list_pull_requests", {"state": "merged", "limit": 10})
    assert [item.model_dump() for item in merged.pull_requests] == [
        {
            "number": 7,
            "title": "Fix the flaky test",
            "author": "ada",
            "merged_at": "2026-11-07T10:00:00Z",
            "labels": ["ci"],
            "url": f"https://github.com/{REPOSITORY}/pull/7",
        }
    ]
    runs = call(github, "github_list_workflow_runs", {"workflow": "ci.yml", "status": "failure"})
    run = runs.runs[0]
    assert (run.id, run.conclusion, run.head_sha, run.created_at, run.updated_at) == (
        99,
        "failure",
        "abc123",
        "2026-11-07T09:00:00Z",
        "2026-11-07T09:05:00Z",
    )
    assert [job.model_dump() for job in run.failing_jobs] == [
        {"name": "tests", "failed_steps": ["Run pytest"]}
    ]
    issues = call(github, "github_search_issues", {"query": "login", "state": "open"})
    assert [item.model_dump() for item in issues.issues] == [
        {
            "number": 3,
            "title": "Login fails",
            "state": "open",
            "labels": ["bug"],
            "url": f"https://github.com/{REPOSITORY}/issues/3",
        }
    ]
    read = call(github, "github_read_file", {"path": "src/app.py", "ref": "main"})
    assert (read.path, read.ref, read.sha, read.size, read.content) == (
        "src/app.py",
        "main",
        "f1le5ha",
        12,
        "print('hi')\n",
    )
    for request in github.requests:
        assert request.url.host == "api.github.com"
        assert request.url.path.startswith(f"/repos/{REPOSITORY}/") or (
            request.url.path == "/search/issues"
        )
        assert request.method == "GET"
    search = next(r for r in github.requests if r.url.path == "/search/issues")
    assert parse_qs(urlparse(str(search.url)).query)["q"] == [
        f"login repo:{REPOSITORY} is:issue state:open"
    ]


@pytest.mark.parametrize(
    ("tool_id", "arguments"),
    [
        ("github_list_pull_requests", {"repository": "other/repo"}),
        ("github_list_pull_requests", {"state": "draft"}),
        ("github_list_pull_requests", {"limit": 101}),
        ("github_list_workflow_runs", {"status": "cancelled"}),
        ("github_list_workflow_runs", {"limit": 101}),
        ("github_search_issues", {"query": "bug", "repository": "other/repo"}),
        ("github_search_issues", {"query": "bug repo:other/repo"}),
        ("github_search_issues", {"query": "bug org:elsewhere"}),
        ("github_read_file", {"path": "../secrets"}),
        ("github_read_file", {"path": "/etc/passwd"}),
    ],
)
def test_a_repository_or_an_out_of_bounds_input_is_refused_before_any_request(
    tool_id: str, arguments: dict[str, Any]
) -> None:
    github = FakeGithub()
    with pytest.raises(ValidationError):
        tools(github)[tool_id].input_model.model_validate(arguments)
    assert github.requests == []


@pytest.mark.parametrize(
    ("since", "numbers"),
    [
        ("2026-11-07", [7, 8]),
        ("2026-11-07T09:30:00", [7, 8]),
        ("2026-11-07T10:30:00", [8]),
        ("2026-11-07T12:30:00+02:00", [8]),
        ("2026-11-07T10:30:00Z", [8]),
    ],
)
def test_a_since_without_an_offset_is_read_as_utc(since: str, numbers: list[int]) -> None:
    """A date-only or offset-less `since` is UTC, and one with an offset compares as the same
    instant, so the filter answers instead of failing (PADP-17, PDOM-03)."""
    listed = call(FakeGithub(), "github_list_pull_requests", {"state": "closed", "since": since})
    assert [item.number for item in listed.pull_requests] == numbers


@pytest.mark.parametrize("model", [GithubListPullRequestsInput, GithubListWorkflowRunsInput])
def test_a_since_is_held_in_utc(
    model: type[GithubListPullRequestsInput] | type[GithubListWorkflowRunsInput],
) -> None:
    naive = model.model_validate({"since": "2026-11-07T10:30:00"}).since
    assert naive == datetime(2026, 11, 7, 10, 30, tzinfo=UTC)
    assert naive is not None and naive.tzinfo is UTC
    offset = model.model_validate({"since": "2026-11-07T01:00:00+02:00"}).since
    assert offset == datetime(2026, 11, 6, 23, 0, tzinfo=UTC)
    assert offset is not None and offset.tzinfo is UTC


def test_a_workflow_run_filter_takes_the_utc_date() -> None:
    github = FakeGithub()
    call(github, "github_list_workflow_runs", {"since": "2026-11-07T01:00:00+02:00"})
    call(github, "github_list_workflow_runs", {"since": "2026-11-07"})
    created = [
        parse_qs(urlparse(str(request.url)).query)["created"]
        for request in github.requests
        if request.url.path.endswith("/actions/runs")
    ]
    assert created == [[">=2026-11-06"], [">=2026-11-07"]]


def test_no_tool_schema_offers_a_repository_input() -> None:
    for tool in tools(FakeGithub()).values():
        properties = tool.input_model.model_json_schema().get("properties", {})
        assert not any(word in name for name in properties for word in ("repo", "owner", "org")), (
            tool.tool_id
        )


def test_a_file_over_one_mebibyte_fails_with_a_typed_code() -> None:
    github = FakeGithub(file_size=MAX_FILE_BYTES + 1)
    with pytest.raises(ToolFailed) as failed:
        call(github, "github_read_file", {"path": "big.bin"})
    assert str(failed.value) == "github_file_too_large"


def test_its_content_is_never_a_public_field() -> None:
    read_file = tools(FakeGithub())["github_read_file"]
    assert "content" not in read_file.public_output_fields
    assert {"sha", "size"} <= set(read_file.public_output_fields)


@pytest.mark.parametrize(
    "environ",
    [{"GITHUB_REPOSITORY": REPOSITORY}, {"GITHUB_TOKEN": "fake-token-for-tests"}, {}],
)
def test_each_tool_is_key_missing_until_both_variables_are_set(environ: dict[str, str]) -> None:
    for tool in tools(FakeGithub(), environ).values():
        assert key_availability(tool.key_requirement, environ) == (
            ToolAvailability.KEY_MISSING,
            "github_key_missing",
        )
    assert GITHUB_KEY.variables == ("GITHUB_REPOSITORY", "GITHUB_TOKEN")
    assert "Pull requests: read and write" in TOKEN_SCOPES
    assert key_availability(GITHUB_KEY, ENV) == (ToolAvailability.AVAILABLE, None)
