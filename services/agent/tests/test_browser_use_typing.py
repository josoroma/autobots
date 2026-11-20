"""US-17.4 offline: pressing, typing and submitting under YOLO, bot checks, typed results and step
screenshots, Decision 0035 Y5, Y10, Y11, Y12, Y16 and Y19.

Nothing here starts a container, opens a socket or calls a model. The live cases are in
tests/db/checks/browser_use_check.py, and the steps' rows and routes in browse_steps_check.py.
"""

import asyncio
import base64
import json
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import uuid4

import pytest
from pydantic import ValidationError

from autobots.adapters.browser_cdp import RequestGuard, bot_check_host
from autobots.adapters.browser_use_box import BoxReport, BoxWatch, _Steps, guarded, outcome
from autobots.adapters.model_endpoint import EndpointRefused, Reply
from autobots.adapters.object_storage import _scoped
from autobots.application import browsing_tool
from autobots.application.browse_steps import page_of, screenshot_path
from autobots.application.browsing_loop import BrowseOutcome
from autobots.application.tool_definitions import ToolContext, ToolFailed, ToolScope
from autobots.contracts.browsing import BrowseGoalV3Input

ARGS = {"task": "Search", "start_url": "https://a.test/", "allowed_domains": ["a.test"]}
SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "flights": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"url": {"type": "string"}, "note": {"type": "string"}},
                "required": ["url"],
            },
        }
    },
    "required": ["flights"],
    "x-link-fields": ["flights[].url"],
}


class Sent:
    """Records what a guard sends, in place of a DevTools connection."""

    def __init__(self, reply: dict[str, Any] | None = None) -> None:
        self.commands: list[tuple[str, str | None]] = []
        self.handlers: list[object] = []
        self.reply = reply or {}

    async def send(
        self, method: str, params: object = None, session: str | None = None
    ) -> dict[str, Any]:
        self.commands.append((method, session))
        return self.reply


async def paused(
    guard: RequestGuard, method: str, url: str, body: bool = False, kind: str = "Document"
) -> str:
    sent = guard.cdp
    assert isinstance(sent, Sent)
    request = {"method": method, "url": url, "hasPostData": body}
    params = {"requestId": "r", "request": request, "resourceType": kind}
    await guard._event({"method": "Fetch.requestPaused", "sessionId": "s", "params": params})
    return sent.commands[-1][0]


# Submits (Y5).


@pytest.mark.parametrize(
    ("submits", "method", "url", "body", "answer"),
    [
        (True, "POST", "https://a.test/search", True, "Fetch.continueRequest"),
        (True, "OPTIONS", "https://a.test/api", False, "Fetch.continueRequest"),
        (True, "GET", "https://a.test/?q=x", False, "Fetch.continueRequest"),
        (True, "PUT", "https://a.test/item", True, "Fetch.failRequest"),
        (True, "DELETE", "https://a.test/item", False, "Fetch.failRequest"),
        (True, "POST", "data:text/plain,x", True, "Fetch.failRequest"),
        (True, "POST", "http://a.test/form", True, "Fetch.failRequest"),
        (False, "POST", "https://a.test/search", True, "Fetch.failRequest"),
    ],
)
@pytest.mark.asyncio
async def test_only_a_browser_use_guard_lets_submits_through_on_https(
    submits: bool, method: str, url: str, body: bool, answer: str
) -> None:
    guard = RequestGuard(Sent(), submits=submits)  # type: ignore[arg-type]  # a fake CDP sender
    assert await paused(guard, method, url, body) == answer


@pytest.mark.asyncio
async def test_a_form_submission_is_recorded_as_host_and_path_only() -> None:
    guard = RequestGuard(Sent(), submits=True)  # type: ignore[arg-type]  # a fake CDP sender
    attach = {"sessionId": "p1", "targetInfo": {"type": "page"}}
    await guard._event({"method": "Target.attachedToTarget", "params": attach})
    for reason, url in (
        ("formSubmissionGet", "https://A.test/search?q=secret#top"),
        ("formSubmissionPost", "https://a.test/login"),
        ("linkClicked", "https://a.test/about"),
    ):
        params = {"frameId": "f", "reason": reason, "url": url, "disposition": "currentTab"}
        await guard._event(
            {"method": "Page.frameRequestedNavigation", "sessionId": "p1", "params": params}
        )
    other = {"reason": "formSubmissionGet", "url": "https://a.test/elsewhere"}
    await guard._event(
        {"method": "Page.frameRequestedNavigation", "sessionId": "x", "params": other}
    )
    assert guard.submitted == ["a.test/search", "a.test/login"]
    assert all("secret" not in entry for entry in guard.submitted)


# Bot checks (Y10, Y16).


@pytest.mark.parametrize(
    ("url", "kind", "host"),
    [
        (
            "https://www.google.com/recaptcha/api2/anchor?k=x&size=normal",
            "Document",
            "www.google.com",
        ),
        ("https://www.google.com/recaptcha/api2/anchor?k=x&size=invisible", "Document", None),
        ("https://www.google.com/recaptcha/enterprise/bframe?k=x", "Document", "www.google.com"),
        ("https://www.google.com/recaptcha/api.js", "Script", None),
        (
            "https://newassets.hcaptcha.com/captcha/v1/x/static/hcaptcha.html",
            "Document",
            "newassets.hcaptcha.com",
        ),
        ("https://js.hcaptcha.com/1/api.js", "Script", None),
        (
            "https://shop.test/cdn-cgi/challenge-platform/h/b/orchestrate/chl_page/v1",
            "Script",
            "shop.test",
        ),
        ("https://shop.test/cdn-cgi/challenge-platform/scripts/jsd/main.js", "Script", None),
        (
            "https://challenges.cloudflare.com/cdn-cgi/challenge-platform/turnstile",
            "Document",
            "challenges.cloudflare.com",
        ),
        (
            "https://geo.captcha-delivery.com/captcha/?initialCid=x",
            "Document",
            "geo.captcha-delivery.com",
        ),
        ("https://client-api.arkoselabs.com/fc/gt2/", "Document", "client-api.arkoselabs.com"),
        ("https://www.google.com/sorry/index?continue=x", None, "www.google.com"),
        ("https://www.google.com/search?q=sorry", None, None),
        ("https://a.test/sorry/", None, None),
    ],
)
def test_a_bot_check_is_recognised_from_the_page_itself(
    url: str, kind: str | None, host: str | None
) -> None:
    assert bot_check_host(url, kind) == host


@pytest.mark.asyncio
async def test_the_guard_notes_bot_checks_in_requests_and_top_frames() -> None:
    guard = RequestGuard(Sent(), submits=True)  # type: ignore[arg-type]  # a fake CDP sender
    await paused(guard, "GET", "https://www.google.com/recaptcha/api2/bframe?k=x")
    attach = {"sessionId": "p1", "targetInfo": {"type": "page"}}
    await guard._event({"method": "Target.attachedToTarget", "params": attach})
    frame = {"frame": {"id": "a", "url": "https://www.google.com/sorry/index?q=1"}}
    await guard._event({"method": "Page.frameNavigated", "sessionId": "p1", "params": frame})
    assert guard.bot_checks == ["www.google.com", "www.google.com"] and guard.latest == "p1"


def ask(answer: Callable[[dict[str, Any]], Awaitable[Reply]], body: dict[str, Any]) -> str:
    async def once() -> None:
        await answer(body)

    try:
        asyncio.run(once())
    except EndpointRefused as refused:
        return refused.code
    return "answered"


def body() -> dict[str, Any]:
    return {"messages": [{"role": "user", "content": "go"}]}


def test_a_bot_check_refuses_the_next_request_before_admission_and_outranks_a_refusal() -> None:
    answered: list[object] = []

    async def answer(request: object) -> Reply:
        answered.append(request)
        return Reply({})

    watch = BoxWatch(max_calls=5, refused=lambda: True, bot_check=lambda: True)
    assert ask(guarded(answer, watch), body()) == "bot_check"
    assert answered == [] and watch.stopped == "bot_check"


def test_a_bot_check_stops_the_outcome_and_submits_and_the_result_reach_it() -> None:
    watch = BoxWatch(max_calls=26, refused=lambda: False, model_calls=3)
    report = BoxReport("completed", "Done.", 3, {"flights": []})
    stopped = outcome(
        report, watch, refused=True, visited=(), bot_check=True, submits=("a.test/s",)
    )
    assert (stopped.stopped, stopped.submits) == ("bot_check", ("a.test/s",))
    done = outcome(report, watch, refused=False, visited=(), submits=("a.test/s",))
    assert (done.stopped, done.result, done.submits) == ("done", {"flights": []}, ("a.test/s",))


def test_before_runs_ahead_of_each_request_refused_ones_included() -> None:
    calls: list[int] = []

    async def before() -> None:
        calls.append(len(calls) + 1)

    async def answer(request: object) -> Reply:
        return Reply({})

    watch = BoxWatch(max_calls=2, refused=lambda: False)
    proxied = guarded(answer, watch, before)
    codes = [ask(proxied, body()) for _ in range(3)]
    assert calls == [1, 2, 3] and codes == ["answered", "answered", "max_steps"]


# Version 3 and the typed result (Y12, Y19).


def test_version_3_takes_a_valid_schema_of_at_most_8_kb_with_link_paths() -> None:
    assert (
        BrowseGoalV3Input.model_validate({**ARGS, "output_schema": SCHEMA}).output_schema == SCHEMA
    )
    assert BrowseGoalV3Input.model_validate(ARGS).output_schema is None


@pytest.mark.parametrize(
    "schema",
    [
        {"type": 5},
        {"type": "object", "description": "x" * 9000},
        {"type": "object", "x-link-fields": "url"},
        {"type": "object", "x-link-fields": ["flights[].url?q"]},
        {"type": "object", "x-link-fields": [f"f{n}" for n in range(21)]},
    ],
)
def test_version_3_refuses_a_schema_that_is_invalid_large_or_badly_linked(
    schema: dict[str, Any],
) -> None:
    with pytest.raises(ValidationError):
        BrowseGoalV3Input.model_validate({**ARGS, "output_schema": schema})


def finished(result: object, stopped: str = "done", submits: tuple[str, ...] = ()) -> BrowseOutcome:
    return BrowseOutcome("Found.", ("https://a.test/",), 2, 2, stopped, result, submits)  # type: ignore[arg-type]  # a stop reason literal


def test_a_typed_result_keeps_queries_only_in_link_fields_and_visited_stays_bare() -> None:
    args = BrowseGoalV3Input.model_validate({**ARGS, "output_schema": SCHEMA})
    result = {
        "flights": [{"url": "https://a.test/buy?id=7#seat", "note": "https://a.test/n?q=secret"}]
    }
    output = browsing_tool._typed_output(finished(result, submits=("a.test/search",)), args)
    assert output.stopped == "done" and output.visited == ["https://a.test/"]
    assert output.result == {
        "flights": [{"url": "https://a.test/buy?id=7#seat", "note": "https://a.test/n"}]
    }
    assert output.submits == ["a.test/search"]


def test_a_result_that_doesnt_validate_stops_invalid_action_with_no_result() -> None:
    args = BrowseGoalV3Input.model_validate({**ARGS, "output_schema": SCHEMA})
    output = browsing_tool._typed_output(finished({"flights": [{"note": "no url"}]}), args)
    assert (output.stopped, output.result) == ("invalid_action", None)
    stopped = browsing_tool._typed_output(finished({"flights": []}, "max_steps"), args)
    assert (stopped.stopped, stopped.result) == ("max_steps", None)
    plain = browsing_tool._typed_output(
        finished({"flights": []}), BrowseGoalV3Input.model_validate(ARGS)
    )
    assert (plain.stopped, plain.result) == ("done", None)


def test_versions_1_and_2_fail_a_bot_check_with_its_code_and_version_3_reports_it() -> None:
    with pytest.raises(ToolFailed, match="bot_check"):
        browsing_tool._output(finished(None, "bot_check"))
    args = BrowseGoalV3Input.model_validate(ARGS)
    assert browsing_tool._typed_output(finished(None, "bot_check"), args).stopped == "bot_check"


def test_version_3_publishes_its_submits_and_never_its_result() -> None:
    third = browsing_tool.browse_tool(None, qualified=lambda: True, version=3)
    assert "submits" in third.public_output_fields and "result" not in third.public_output_fields
    assert "output_schema" not in third.public_input_fields


# One screenshot per step (Y11, Y16).


def test_each_step_is_pictured_once_with_only_its_new_submits() -> None:
    picture = base64.b64encode(b"jpeg-bytes").decode()
    sent = Sent({"result": {"data": picture}})
    guard = RequestGuard(sent, submits=True)  # type: ignore[arg-type]  # a fake CDP sender
    guard.pages.add("p1")
    guard.latest = "p1"
    recorded: list[tuple[int, str | None, bytes | None, tuple[str, ...]]] = []

    async def sink(
        step: int, page: str | None, image: bytes | None, submits: tuple[str, ...]
    ) -> None:
        recorded.append((step, page, image, submits))

    steps = _Steps(sent, guard, sink)  # type: ignore[arg-type]  # a fake CDP sender

    async def go() -> None:
        guard.navigated.append("https://a.test/")
        guard.submitted.append("a.test/search")
        await steps.take()
        await steps.take()
        sent.reply = {}
        await steps.take()

    asyncio.run(go())
    assert recorded == [
        (1, "https://a.test/", b"jpeg-bytes", ("a.test/search",)),
        (2, "https://a.test/", b"jpeg-bytes", ()),
        (3, "https://a.test/", None, ()),
    ]
    assert sent.commands[0] == ("Page.captureScreenshot", "p1")


def test_a_page_is_kept_as_host_and_path_and_its_screenshot_under_the_run() -> None:
    assert page_of("https://A.test/search?q=secret#x") == "a.test/search"
    assert page_of("chrome-error://chromewebdata/") is None and page_of(None) is None
    scope = ToolScope(uuid4(), uuid4(), 1, {})
    assert screenshot_path(scope, 7, 2) == f"{scope.workspace_id}/{scope.run_id}/browse-7-2.jpg"
    _scoped(screenshot_path(scope, 7, 2))


class Store:
    def __init__(self, fails: bool = False) -> None:
        self.put_calls: list[tuple[str, int, str]] = []
        self.fails = fails

    async def put(self, path: str, content: bytes, media_type: str) -> bool:
        if self.fails:
            raise OSError("storage down")
        self.put_calls.append((path, len(content), media_type))
        return True


class Recording:
    """A connection that records each statement and its parameters."""

    def __init__(self) -> None:
        self.statements: list[tuple[str, tuple[object, ...]]] = []

    async def execute(self, sql: str, params: tuple[object, ...] = ()) -> None:
        self.statements.append((sql, params))


@pytest.mark.parametrize("fails", [False, True])
def test_a_steps_screenshot_is_stored_privately_and_a_failure_keeps_the_row(fails: bool) -> None:
    store, connection = Store(fails), Recording()
    runtime = browsing_tool.BrowsingRuntime(object(), object(), object(), store=store)  # type: ignore[arg-type]  # fakes the sink never calls
    scope = ToolScope(uuid4(), uuid4(), 1, {})
    sink = browsing_tool._step_sink(runtime, ToolContext(connection, scope, None, None, 41))  # type: ignore[arg-type]  # a recording connection
    assert sink is not None

    async def record() -> None:
        await sink(1, "https://a.test/s?q=secret", b"jpeg", ("a.test/s",))

    asyncio.run(record())
    ((sql, params),) = connection.statements
    assert "insert into app_private.browse_steps" in sql and params[:5] == (
        41,
        scope.run_id,
        scope.workspace_id,
        1,
        "a.test/s",
    )
    assert json.loads(str(params[5])) == ["a.test/s"]
    if fails:
        assert params[6:] == (None, None, None) and store.put_calls == []
    else:
        assert params[6] == screenshot_path(scope, 41, 1) and params[7] == 4
        assert store.put_calls == [(screenshot_path(scope, 41, 1), 4, "image/jpeg")]
    assert browsing_tool._step_sink(runtime, ToolContext(connection, scope, None)) is None  # type: ignore[arg-type]  # a recording connection
