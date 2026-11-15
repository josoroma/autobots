"""The GitHub connector over a fake transport. The gateway is in tests/db/connector_check.py."""

import asyncio
import importlib.util
import json
import sys
from collections.abc import Awaitable
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError

from autobots.adapters.github_connector import REPOSITORY_VARIABLE, TOKEN_VARIABLE, marker
from autobots.adapters.github_issues import READBACK_SETTLE_SECONDS, github_issue_tool
from autobots.adapters.provider_http import UnclearReply
from autobots.application.tool_definitions import NotDelivered, ToolContext, ToolFailed, ToolScope
from autobots.contracts.tools import CreateGithubIssueInput
from autobots.domain.tools import EXPERT_TOOLS, LOOP_TOOL_GRANTS, OperationClass

REPOSITORY = "owner/throwaway"
TOKEN = "arranged-connector-token"
ENV = {REPOSITORY_VARIABLE: REPOSITORY, TOKEN_VARIABLE: TOKEN}
ARGUMENTS = CreateGithubIssueInput(title="A title", body="A body")
OPERATION = "operation-1"
REPO_ROOT = Path(__file__).resolve().parents[3]


class FakeGithub:
    def __init__(self, status: int = 201) -> None:
        self.status = status
        self.requests: list[httpx.Request] = []
        self.issues: list[dict[str, Any]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.method == "GET":
            return httpx.Response(200 if self.status == 201 else self.status, json=self.issues)
        if self.status != 201:
            return httpx.Response(self.status, json={"message": "arranged"})
        number = len(self.issues) + 1
        issue = {
            **json.loads(request.content),
            "number": number,
            "html_url": f"https://github.com/{REPOSITORY}/issues/{number}",
        }
        self.issues.append(issue)
        return httpx.Response(201, json=issue)


def context(operation: str = OPERATION) -> ToolContext:
    return ToolContext(None, ToolScope(uuid4(), uuid4(), 1, {}), operation)


def tool(
    handler: Any, environ: dict[str, str] | None = None, settle: tuple[float, ...] = ()
) -> Any:
    return github_issue_tool(
        httpx.MockTransport(handler), ENV if environ is None else environ, settle
    )


def create(handler: Any, environ: dict[str, str] | None = None) -> Any:
    return asyncio.run(tool(handler, environ).handler(ARGUMENTS, context()))


def read_back(handler: Any, operation: str = OPERATION) -> Any:
    reconcile = tool(handler).reconcile
    assert reconcile is not None
    return asyncio.run(reconcile(ARGUMENTS, context(operation)))


def test_the_tool_is_consequential_and_never_retried() -> None:
    definition = tool(FakeGithub())
    assert definition.operation_class is OperationClass.CONSEQUENTIAL_EXTERNAL_WRITE
    assert definition.retries == 0
    assert definition.safe_to_repeat is False
    assert definition.reconcile is not None


def test_an_owner_grants_it_and_a_plain_goal_does_not_get_it() -> None:
    # New grants get version 2, with labels (US-15.14). Version 1 stays registered.
    assert EXPERT_TOOLS[definition_id()] == 2
    assert definition_id() not in LOOP_TOOL_GRANTS


def definition_id() -> str:
    return str(tool(FakeGithub()).tool_id)


def test_a_call_goes_only_to_the_configured_repository_with_its_marker() -> None:
    github = FakeGithub()
    output = create(github)
    assert output.number == 1
    assert output.url.endswith(f"{REPOSITORY}/issues/1")
    request = github.requests[0]
    assert request.method == "POST"
    assert str(request.url) == f"https://api.github.com/repos/{REPOSITORY}/issues"
    assert request.headers["authorization"] == f"Bearer {TOKEN}"
    sent = json.loads(request.content)
    assert sent["title"] == "A title"
    assert sent["body"].startswith("A body")
    assert marker(OPERATION) in sent["body"]


def test_the_output_holds_no_token() -> None:
    assert TOKEN not in create(FakeGithub()).model_dump_json()


@pytest.mark.parametrize("field", ["repository", "repo", "owner", "assignees", "url", "token"])
def test_no_argument_can_choose_a_destination(field: str) -> None:
    with pytest.raises(ValidationError):
        CreateGithubIssueInput.model_validate({"title": "t", "body": "b", field: "other/repo"})


@pytest.mark.parametrize(
    "environ",
    [
        {},
        {REPOSITORY_VARIABLE: REPOSITORY},
        {TOKEN_VARIABLE: TOKEN},
        {REPOSITORY_VARIABLE: "../../elsewhere", TOKEN_VARIABLE: TOKEN},
        {REPOSITORY_VARIABLE: "https://evil.example/owner/repo", TOKEN_VARIABLE: TOKEN},
        {REPOSITORY_VARIABLE: REPOSITORY, TOKEN_VARIABLE: ""},
    ],
)
def test_missing_or_bad_configuration_sends_nothing(environ: dict[str, str]) -> None:
    github = FakeGithub()
    with pytest.raises(ToolFailed, match="connector_not_configured"):
        create(github, environ)
    assert github.requests == []


@pytest.mark.parametrize("status", [400, 401, 403, 404, 410, 422, 429])
def test_a_clear_refusal_is_a_failure_that_created_nothing(status: int) -> None:
    with pytest.raises(ToolFailed, match=f"github_refused_{status}"):
        create(FakeGithub(status))


@pytest.mark.parametrize("status", [200, 202, 301, 500, 502, 503])
def test_an_unclear_reply_stays_uncertain(status: int) -> None:
    with pytest.raises(UnclearReply):
        create(FakeGithub(status))


def test_a_connection_that_never_opened_is_a_clean_failure() -> None:
    def refuse(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("arranged")

    with pytest.raises(ToolFailed, match="destination_unreachable"):
        create(refuse)


def test_a_lost_reply_stays_uncertain() -> None:
    """The request went out, so the issue may exist. Only a readback can say."""

    def lose(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadError("arranged")

    with pytest.raises(httpx.ReadError):
        create(lose)


def test_a_redirect_is_not_followed() -> None:
    def redirect(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api.github.com"
        return httpx.Response(302, headers={"location": "https://evil.example/issues"})

    with pytest.raises(UnclearReply):
        create(redirect)


def test_a_readback_finds_the_issue_by_its_marker() -> None:
    github = FakeGithub()
    created = create(github)
    found = read_back(github)
    assert found == created
    assert sum(request.method == "POST" for request in github.requests) == 1


def test_a_readback_of_another_operation_finds_nothing() -> None:
    github = FakeGithub()
    create(github)
    with pytest.raises(NotDelivered):
        read_back(github, "another-operation")


def test_a_readback_copes_with_an_issue_with_no_body() -> None:
    github = FakeGithub()
    github.issues.append({"number": 9, "html_url": "x", "body": None})
    with pytest.raises(NotDelivered):
        read_back(github)


class LaggingGithub(FakeGithub):
    """Hides issues from the first reads, as the live list did right after a create."""

    def __init__(self, hidden_reads: int) -> None:
        super().__init__()
        self.hidden_reads = hidden_reads

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and self.hidden_reads:
            self.hidden_reads -= 1
            self.requests.append(request)
            return httpx.Response(200, json=[])
        return super().__call__(request)


def settled_read_back(github: FakeGithub, operation: str = OPERATION) -> Any:
    reconcile = tool(github, settle=(0.0, 0.0)).reconcile
    assert reconcile is not None
    return asyncio.run(reconcile(ARGUMENTS, context(operation)))


def test_a_readback_waits_for_a_list_that_lags_the_create() -> None:
    github = LaggingGithub(hidden_reads=2)
    created = create(github)
    assert settled_read_back(github) == created
    assert sum(request.method == "GET" for request in github.requests) == 3
    assert sum(request.method == "POST" for request in github.requests) == 1


def test_not_delivered_is_only_said_after_every_wait() -> None:
    github = LaggingGithub(hidden_reads=3)
    create(github)
    with pytest.raises(NotDelivered):
        settled_read_back(github)
    assert sum(request.method == "GET" for request in github.requests) == 3


def test_a_failed_read_during_the_waits_stays_uncertain() -> None:
    github = FakeGithub(500)
    with pytest.raises(UnclearReply):
        settled_read_back(github)
    assert sum(request.method == "GET" for request in github.requests) == 1


def test_the_waits_fit_inside_the_tools_timeout() -> None:
    """Running out of time records an unknown outcome, so the waits must usually finish first."""
    assert sum(READBACK_SETTLE_SECONDS) < tool(FakeGithub()).timeout_seconds


def test_a_failed_readback_says_nothing_about_delivery() -> None:
    with pytest.raises(UnclearReply):
        read_back(FakeGithub(500))


def qualifier() -> Any:
    path = REPO_ROOT / "scripts/qualify_github_connector.py"
    spec = importlib.util.spec_from_file_location("qualify_github_connector", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("scopes", "private", "refusal"),
    [
        ("repo", True, "broad"),
        ("repo, workflow", True, "broad"),
        ("", False, "public"),
        (None, False, "public"),
    ],
)
def test_the_live_qualifier_refuses_an_unsafe_target(
    scopes: str | None, private: bool, refusal: str
) -> None:
    assert refusal in qualifier().unsafe_target(scopes, private)


@pytest.mark.parametrize("scopes", ["", None])
def test_the_live_qualifier_accepts_a_limited_token_on_a_private_repository(
    scopes: str | None,
) -> None:
    assert qualifier().unsafe_target(scopes, True) == ""


def test_the_qualifier_reports_a_failed_readback_and_still_closes_the_issue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The first live run ended in a traceback here, with no report."""
    methods: list[str] = []

    def github(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        if request.method == "POST":
            return httpx.Response(
                201, json={"number": 1, "html_url": f"https://github.com/{REPOSITORY}/issues/1"}
            )
        if request.url.path.endswith("/issues"):
            return httpx.Response(200, json=[])
        if request.method == "PATCH":
            return httpx.Response(200, json={})
        if request.url.path.endswith("/issues/1"):
            return httpx.Response(200, json={"body": marker("unused")})
        return httpx.Response(200, json={"private": True})

    real_client = httpx.AsyncClient

    def faked(**options: Any) -> httpx.AsyncClient:
        return real_client(**{**options, "transport": httpx.MockTransport(github)})

    async def no_wait(_: float) -> None:
        return None

    monkeypatch.setattr(httpx, "AsyncClient", faked)
    monkeypatch.setattr(asyncio, "sleep", no_wait)
    code, report = asyncio.run(qualifier().qualify(REPOSITORY, TOKEN))
    assert code == 1
    assert report["failed"]
    assert TOKEN not in json.dumps(report)
    assert methods[-1] == "PATCH"


def test_a_reviewer_sees_the_configured_repository_and_not_a_models_choice() -> None:
    """The approval records the repository resolved for the workspace, whatever a model asked
    (Decision 0025 V7). Without a token there is nothing to approve."""
    configured = github_issue_tool(environ={"GITHUB_REPOSITORY": "owner/name", **TOKEN_ONLY})
    resolve = configured.approval.target_resolver
    assert resolve is not None
    assert settled(resolve(object(), context())) == "GitHub repository owner/name"
    unset = github_issue_tool(environ={"GITHUB_REPOSITORY": "owner/name"}).approval
    assert unset.target_resolver is not None
    with pytest.raises(ToolFailed, match="connector_not_configured"):
        settled(unset.target_resolver(object(), context()))
    assert configured.approval.resource_target(object()) is None


TOKEN_ONLY = {TOKEN_VARIABLE: TOKEN}


def settled[T](awaitable: Awaitable[T]) -> T:
    """Runs a tool's handler, readback or resolver, which are typed as plain awaitables."""

    async def wait() -> T:
        return await awaitable

    return asyncio.run(wait())


def test_a_created_issue_that_cant_be_read_stays_uncertain() -> None:
    """GitHub answered 201, so the issue may exist. Only a readback can say."""

    def created(_: httpx.Request) -> httpx.Response:
        return httpx.Response(201, text="not json")

    with pytest.raises(UnclearReply) as unclear:
        create(created)
    assert unclear.value.detail == "github_unclear_201"


def test_a_readback_that_gets_no_reply_stays_unknown_with_its_reason() -> None:
    def lose(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadError("arranged")

    with pytest.raises(UnclearReply) as unclear:
        read_back(lose)
    assert unclear.value.detail == "github_unclear_unreachable"
