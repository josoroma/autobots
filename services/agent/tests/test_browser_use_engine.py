"""US-17.3 offline: browse_goal on browser-use in the isolated box, Decision 0035 Y5 to Y9, Y15
and Y16.

The engine per call, the limits per engine, version 2 beside version 1, the guard on the box's model
requests, the outcome judged from the worker's own observations, the guard's navigation log, the
browser-use container's Docker arguments and browser-use's own qualification. Nothing here starts a
container, opens a socket or calls a model: the live cases are tests/db/checks/browser_use_check.py.
"""

import asyncio
import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from pydantic import ValidationError

from autobots.adapters import browser_qualification, browser_use_box
from autobots.adapters.browser_cdp import RequestGuard
from autobots.adapters.browser_executor import BrowserExecutor, ModelLink
from autobots.adapters.browser_page import CdpPage
from autobots.adapters.browser_qualification import (
    BROWSER_USE,
    BROWSER_USE_FINGERPRINTED,
    FINGERPRINT_LABEL,
    IMAGES,
    REQUIRED_BROWSER_USE_CASES,
    REQUIRED_CASES,
    browser_use_fingerprint,
    browser_use_qualified,
    fingerprint_digest,
    images_fingerprint,
    parse_labels,
)
from autobots.adapters.browser_use_box import (
    BoxCall,
    BoxReport,
    BoxWatch,
    browse_in_box,
    guarded,
    notices_refusal,
    outcome,
    parse_report,
)
from autobots.adapters.model_endpoint import EndpointRefused, Reply
from autobots.application import browsing_tool
from autobots.application.browsing_loop import BrowseOutcome
from autobots.application.browsing_tool import Limits, browse_tools, resolved_limits
from autobots.application.loop_admission import active_middleware
from autobots.application.tool_definitions import ToolContext, ToolFailed, ToolScope
from autobots.contracts.browsing import BrowseGoalInput, BrowseGoalV2Input
from autobots.domain.models import ModelRoute
from autobots.domain.tools import EXPERT_TOOLS
from sql_fakes import RuledConnection

ROOT = Path(__file__).resolve().parents[3]
ROUTE = ModelRoute("researcher", "openrouter_sol", "openai/gpt-6.1-sol", 1000)
ARGS = {
    "task": "Read the guide",
    "start_url": "https://en.wikivoyage.org/",
    "allowed_domains": ["en.wikivoyage.org"],
}


# Limits and versions (Y9, Y15, Decision 0029 F13).


def test_an_unnamed_limit_is_its_engines_default_and_a_named_one_is_capped() -> None:
    plain = BrowseGoalV2Input.model_validate(ARGS)
    assert resolved_limits(plain, on_browser_use=True) == Limits(25, 300)
    assert resolved_limits(plain, on_browser_use=False) == Limits(10, 120)
    most = BrowseGoalV2Input.model_validate({**ARGS, "max_steps": 40, "max_seconds": 600})
    assert resolved_limits(most, on_browser_use=True) == Limits(40, 600)
    assert resolved_limits(most, on_browser_use=False) == Limits(20, 300)
    first = BrowseGoalInput.model_validate(ARGS)
    assert resolved_limits(first, on_browser_use=True) == Limits(10, 120)


@pytest.mark.parametrize(
    "change", [{"max_steps": 41}, {"max_seconds": 601}, {"max_seconds": 9}, {"max_steps": 0}]
)
def test_version_2_refuses_past_browser_uses_ceilings(change: dict[str, int]) -> None:
    with pytest.raises(ValidationError):
        BrowseGoalV2Input.model_validate({**ARGS, **change})


def test_version_1_keeps_the_loops_ceilings() -> None:
    with pytest.raises(ValidationError):
        BrowseGoalInput.model_validate({**ARGS, "max_steps": 21})
    with pytest.raises(ValidationError):
        BrowseGoalInput.model_validate({**ARGS, "max_seconds": 301})


def test_both_versions_are_registered_and_new_grants_take_version_2() -> None:
    first, second = browse_tools(None, qualified=lambda: True)
    assert (first.version, first.input_model, first.timeout_seconds) == (1, BrowseGoalInput, 390)
    assert (second.version, second.input_model, second.timeout_seconds) == (
        2,
        BrowseGoalV2Input,
        690,
    )
    assert EXPERT_TOOLS["browse_goal"] == 2


def test_an_approval_shows_the_loops_limits_since_only_a_loop_call_waits() -> None:
    _, second = browse_tools(None, qualified=lambda: True)
    assert second.approval is not None and second.approval.resource_target is not None
    most = BrowseGoalV2Input.model_validate({**ARGS, "max_steps": 40, "max_seconds": 600})
    plain = BrowseGoalV2Input.model_validate(ARGS)
    shown = [second.approval.resource_target(args) or "" for args in (most, plain)]
    assert shown[0].endswith("up to 20 steps and 300 s")
    assert shown[1].endswith("up to 10 steps and 120 s")


# The engine per call (Y15).


def yolo(on: bool) -> RuledConnection:
    return RuledConnection(
        ("browsing_yolo", [(on,)]),
        ("browse_domains", [{"domains": '["en.wikivoyage.org"]'}]),
        ("", []),
    )


class LoopExecutor:
    """Enough of an executor for the loop's path, which the fakes below drive."""

    def __init__(self) -> None:
        self.stopped = 0

    async def start(self, *args: object) -> object:
        class Session:
            async def websocket_url(self) -> str:
                return "ws://fake"

        return Session()

    async def sweep(self, alive: object) -> list[str]:
        return []

    async def watch(self, session: object, alive: object, seconds: float) -> str:
        await asyncio.sleep(3600)
        return "removed"

    async def stop(self, session: object) -> None:
        self.stopped += 1


def engine_call(
    monkeypatch: pytest.MonkeyPatch, *, on: bool, ready: bool, args: Mapping[str, Any]
) -> tuple[str, dict[str, Any]]:
    """Which engine a version 2 call ran on, and the limits it was given."""
    seen: dict[str, Any] = {}

    async def in_box(executor: object, call: BoxCall, **_: object) -> BrowseOutcome:
        seen.update(engine="browser_use", steps=call.max_steps, seconds=call.max_seconds)
        return BrowseOutcome("Done.", ("https://en.wikivoyage.org/",), 1, 2, "done")

    async def loop(page: object, step: object, **kwargs: object) -> BrowseOutcome:
        seen.update(engine="loop", steps=kwargs["max_steps"], seconds=kwargs["max_seconds"])
        return BrowseOutcome("Read.", (), 1, 1, "done")

    class Cdp:
        @classmethod
        async def connect(cls, url: str) -> "Cdp":
            return cls()

        async def close(self) -> None:
            return None

    class Guard:
        def __init__(self, cdp: object) -> None:
            pass

        async def start(self) -> None:
            return None

    async def opened(cdp: object, settle: float) -> object:
        return object()

    monkeypatch.setattr(browsing_tool, "browse_in_box", in_box)
    monkeypatch.setattr(browsing_tool, "browse", loop)
    monkeypatch.setattr(browsing_tool, "Cdp", Cdp)
    monkeypatch.setattr(browsing_tool, "RequestGuard", Guard)
    monkeypatch.setattr(CdpPage, "open", opened)
    runtime = browsing_tool.BrowsingRuntime(
        LoopExecutor(),  # type: ignore[arg-type]  # a fake BrowserExecutor
        Model(),
        ROUTE,
        settle=0,
        browser_use=lambda: ready,
    )
    tool = browsing_tool.browse_tool(runtime, qualified=lambda: True, version=2)
    scope = ToolScope(uuid4(), uuid4(), 1, {"browse_goal": 2})

    async def go() -> object:
        with active_middleware(object()):  # type: ignore[arg-type]  # the fakes never admit
            return await tool.handler(
                BrowseGoalV2Input.model_validate(args), ToolContext(yolo(on), scope, None)
            )

    asyncio.run(go())
    return seen.pop("engine"), seen


def test_a_yolo_call_runs_on_browser_use_with_its_default_limits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine, limits = engine_call(monkeypatch, on=True, ready=True, args=ARGS)
    assert (engine, limits) == ("browser_use", {"steps": 25, "seconds": 300})


def test_a_yolo_call_may_name_browser_uses_ceilings(monkeypatch: pytest.MonkeyPatch) -> None:
    args = {**ARGS, "max_steps": 40, "max_seconds": 600}
    engine, limits = engine_call(monkeypatch, on=True, ready=True, args=args)
    assert (engine, limits) == ("browser_use", {"steps": 40, "seconds": 600})


@pytest.mark.parametrize(("on", "ready"), [(False, True), (True, False), (False, False)])
def test_otherwise_the_call_runs_on_the_loop_capped_at_its_limits(
    monkeypatch: pytest.MonkeyPatch, on: bool, ready: bool
) -> None:
    args = {**ARGS, "max_steps": 40, "max_seconds": 600}
    engine, limits = engine_call(monkeypatch, on=on, ready=ready, args=args)
    assert (engine, limits) == ("loop", {"steps": 20, "seconds": 300})


# The guard on the box's model requests (Decision 0018, a refused action ends the call).


def request(*results: str) -> dict[str, Any]:
    """A chat completion request whose last step returned `results`."""
    history: list[dict[str, Any]] = [
        {"role": "system", "content": "Browse."},
        {"role": "user", "content": "Go"},
        {"role": "assistant", "content": None, "tool_calls": []},
        {
            "role": "tool",
            "tool_call_id": "c0",
            "content": '["blocked: x.test is not in allowed_domains"]',
        },
        {"role": "assistant", "content": None, "tool_calls": []},
    ]
    return {
        "messages": history
        + [{"role": "tool", "tool_call_id": "c1", "content": r} for r in results]
    }


class Answers:
    def __init__(self, failure: EndpointRefused | None = None) -> None:
        self.bodies: list[Mapping[str, Any]] = []
        self.failure = failure

    async def __call__(self, body: Mapping[str, Any]) -> Reply:
        self.bodies.append(body)
        if self.failure is not None:
            raise self.failure
        return Reply({"object": "chat.completion"})


def ask(answer: Callable[[Mapping[str, Any]], Any], body: Mapping[str, Any]) -> str:
    try:
        asyncio.run(answer(body))
    except EndpointRefused as refused:
        return refused.code
    return "answered"


def test_only_the_last_steps_results_are_read_for_a_refusal() -> None:
    assert not notices_refusal(request('["ok"]'))
    assert notices_refusal(
        request('["PermissionError: blocked: x.test is not in allowed_domains"]')
    )
    assert notices_refusal(request('["[download started: a.bin]"]'))
    assert notices_refusal(request("[\"blocked: 'file:///etc' is a file: URL or has no host\"]"))


def test_a_refused_navigation_or_download_refuses_the_next_request_before_admission() -> None:
    answers, refused = Answers(), [False]
    watch = BoxWatch(max_calls=5, refused=lambda: refused[0])
    answer = guarded(answers, watch)
    assert ask(answer, request('["ok"]')) == "answered"
    refused[0] = True
    assert ask(answer, request('["ok"]')) == "refused_action"
    refused[0] = False
    assert ask(answer, request('["ok"]')) == "refused_action"
    assert (len(answers.bodies), watch.model_calls, watch.stopped) == (1, 1, "refused_action")


def test_browser_uses_own_refusal_refuses_the_next_request_too() -> None:
    answers = Answers()
    watch = BoxWatch(max_calls=5, refused=lambda: False)
    blocked = request('["PermissionError: blocked: www.iana.org is not in allowed_domains (x)"]')
    assert ask(guarded(answers, watch), blocked) == "refused_action"
    assert answers.bodies == [] and watch.stopped == "refused_action"


def test_an_admission_refusal_is_kept_with_its_code() -> None:
    watch = BoxWatch(max_calls=5, refused=lambda: False)
    answer = guarded(Answers(EndpointRefused(403, "budget_exhausted")), watch)
    assert ask(answer, request('["ok"]')) == "budget_exhausted"
    assert (watch.refusal, watch.model_calls) == ("budget_exhausted", 0)


def test_past_its_steps_and_one_delivery_turn_a_request_is_refused() -> None:
    answers = Answers()
    watch = BoxWatch(max_calls=2, refused=lambda: False)
    answer = guarded(answers, watch)
    codes = [ask(answer, request('["ok"]')) for _ in range(3)]
    assert codes == ["answered", "answered", "max_steps"] and len(answers.bodies) == 2


# The outcome (Y5, AB-03).


def test_the_report_is_the_last_json_line_and_untrusted() -> None:
    printed = 'noise\n{"status": "completed", "text": "Done.", "steps": 3}\n'
    assert parse_report(printed) == BoxReport("completed", "Done.", 3)
    assert parse_report('{"status": "timeout", "text": 5, "steps": -2}') == BoxReport(
        "timeout", "", 0
    )
    assert parse_report("") is None and parse_report("[1, 2]") is None
    long = parse_report(json.dumps({"status": "completed", "text": "x" * 30_000}))
    assert long is not None and len(long.text) == 20_000


@pytest.mark.parametrize(
    ("status", "stopped"),
    [("completed", "done"), ("max_steps", "max_steps"), ("timeout", "max_seconds")],
)
def test_browser_uses_status_maps_onto_the_same_stop_reasons(status: str, stopped: str) -> None:
    watch = BoxWatch(max_calls=26, refused=lambda: False, model_calls=4)
    result = outcome(
        BoxReport(status, "Done.", 9), watch, refused=False, visited=("https://a.test/",)
    )
    assert result == BrowseOutcome("Done.", ("https://a.test/",), 4, 4, stopped)  # type: ignore[arg-type]  # a Stopped literal


def test_steps_never_exceed_the_calls_limit_or_the_model_calls() -> None:
    watch = BoxWatch(max_calls=3, refused=lambda: False, model_calls=3)
    assert outcome(BoxReport("max_steps", "", 3), watch, refused=False, visited=()).steps == 2
    watch = BoxWatch(max_calls=26, refused=lambda: False, model_calls=1)
    assert outcome(BoxReport("completed", "", 7), watch, refused=False, visited=()).steps == 1


def test_a_refused_action_or_the_workers_cap_wins_over_the_boxs_report() -> None:
    watch = BoxWatch(max_calls=26, refused=lambda: False, model_calls=2)
    report = BoxReport("completed", "Done.", 2)
    assert outcome(report, watch, refused=True, visited=()).stopped == "refused_action"
    watch.stopped = "max_steps"
    assert outcome(report, watch, refused=False, visited=()).stopped == "max_steps"


@pytest.mark.parametrize(
    ("report", "refusal", "code"),
    [
        (BoxReport("error", "", 1), "budget_exhausted", "budget_exhausted"),
        (BoxReport("error", "", 1), None, "browser_use_failed"),
        (None, None, "browser_use_failed"),
        (BoxReport("cancelled", "", 1), None, "browser_use_failed"),
    ],
)
def test_an_admission_refusal_or_a_failed_run_fails_the_call(
    report: BoxReport | None, refusal: str | None, code: str
) -> None:
    watch = BoxWatch(max_calls=26, refused=lambda: False, refusal=refusal)
    with pytest.raises(ToolFailed, match=code):
        outcome(report, watch, refused=False, visited=())


# One browse in the box, with a fake endpoint, CDP, guard and executor.


class Endpoint:
    """The model endpoint without a socket: the fake executor calls its answer directly."""

    last: "Endpoint | None" = None

    def __init__(self, answer: Callable[[Mapping[str, Any]], Any]) -> None:
        self.answer, self.port, self.token = answer, 4321, "box-token"
        Endpoint.last = self

    async def __aenter__(self) -> "Endpoint":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None


class Guard:
    last: "Guard | None" = None

    def __init__(self, cdp: object) -> None:
        self.navigated: list[str] = []
        self.failed: list[str] = []
        Guard.last = self

    async def start(self) -> None:
        return None

    def refusals(self) -> int:
        return len(self.failed)


class BoxExecutor:
    def __init__(
        self, steps: list[Callable[[Guard], None]], watched: str | None = None, late: bool = False
    ) -> None:
        self.steps, self.watched, self.late = steps, watched, late
        self.ran: list[tuple[dict[str, Any], float]] = []
        self.stopped = 0

    async def run_browser_use(self, session: object, spec: dict[str, Any], seconds: float) -> str:
        self.ran.append((spec, seconds))
        assert Endpoint.last is not None and Guard.last is not None
        answered = 0
        for step in self.steps:
            step(Guard.last)
            try:
                await Endpoint.last.answer(request('["ok"]'))
                answered += 1
            except EndpointRefused:
                return json.dumps({"status": "error", "text": "", "steps": answered})
        if self.watched and self.late:
            return json.dumps({"status": "error", "text": "", "steps": answered})
        if self.watched:
            await asyncio.sleep(0.05)
            return ""
        return json.dumps({"status": "completed", "text": "Read it.", "steps": answered})

    async def watch(self, session: object, alive: object, seconds: float) -> str:
        if self.watched and self.late:
            await asyncio.sleep(0.2)
            return self.watched
        if self.watched:
            return self.watched
        await asyncio.sleep(3600)
        return "removed"

    async def stop(self, session: object) -> None:
        self.stopped += 1


class Admitting:
    def __init__(self) -> None:
        self.calls = 0

    async def admitted(self, request: object, handler: object, route: object) -> object:
        self.calls += 1
        return type("R", (), {"result": [_reply()]})(), True


def _reply() -> object:
    from langchain_core.messages import AIMessage

    return AIMessage(
        content="", tool_calls=[{"name": "finish", "args": {}, "id": "c", "type": "tool_call"}]
    )


class Model:
    def bind_tools(self, tools: object, **_: object) -> "Model":
        return self


def in_box(
    monkeypatch: pytest.MonkeyPatch, executor: BoxExecutor
) -> tuple[BrowseOutcome | str, list[ModelLink], Admitting]:
    class Cdp:
        @classmethod
        async def connect(cls, url: str) -> "Cdp":
            return cls()

        async def close(self) -> None:
            return None

    monkeypatch.setattr(browser_use_box, "ModelEndpoint", Endpoint)
    monkeypatch.setattr(browser_use_box, "RequestGuard", Guard)
    monkeypatch.setattr(browser_use_box, "Cdp", Cdp)
    links: list[ModelLink] = []
    admitting = Admitting()

    async def start(link: ModelLink) -> object:
        links.append(link)

        class Session:
            async def websocket_url(self) -> str:
                return "ws://fake"

        return Session()

    async def alive() -> bool:
        return True

    call = BoxCall("Read", "https://a.test/", ("a.test",), 3, 300, 60)

    async def go() -> BrowseOutcome | str:
        try:
            return await browse_in_box(
                executor,  # type: ignore[arg-type]  # a fake BrowserExecutor
                call,
                start=start,  # type: ignore[arg-type]  # starts a fake session
                alive=alive,
                middleware=admitting,  # type: ignore[arg-type]  # a fake admission
                model=Model(),
                route=ROUTE,
                visited=lambda navigated: browsing_tool.visited_urls(navigated, ["a.test"]),
            )
        except ToolFailed as failed:
            return str(failed)

    return asyncio.run(go()), links, admitting


def visit(url: str) -> Callable[[Guard], None]:
    return lambda guard: guard.navigated.append(url)


def test_a_browse_in_the_box_is_judged_from_the_workers_own_log(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executor = BoxExecutor([visit("https://a.test/x?q=1#f"), visit("https://b.test/")])
    result, links, admitting = in_box(monkeypatch, executor)
    assert result == BrowseOutcome("Read it.", ("https://a.test/x",), 2, 2, "done")
    assert links == [ModelLink(4321, "box-token")] and admitting.calls == 2
    spec, seconds = executor.ran[0]
    assert (spec["max_steps"], spec["max_seconds"], seconds) == (3, 300, 360)
    assert "cdp_url" not in spec and executor.stopped == 1


def test_a_navigation_that_landed_on_an_error_page_ends_the_browse_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    refused = BoxExecutor(
        [visit("https://a.test/"), lambda guard: guard.failed.append("https://a.test/x")]
    )
    result, _, admitting = in_box(monkeypatch, refused)
    assert isinstance(result, BrowseOutcome)
    assert (result.stopped, result.model_calls, admitting.calls) == ("refused_action", 1, 1)
    assert refused.stopped == 1


def test_a_session_whose_attempt_ended_reports_cancelled(monkeypatch: pytest.MonkeyPatch) -> None:
    result, _, _ = in_box(monkeypatch, BoxExecutor([], watched="attempt_ended"))
    assert isinstance(result, BrowseOutcome) and result.stopped == "cancelled"
    result, _, _ = in_box(monkeypatch, BoxExecutor([], watched="memory_cap"))
    assert result == "browser_memory_cap"
    # The box's run returns first, having lost its browser, while the watcher is still removing it.
    result, _, _ = in_box(monkeypatch, BoxExecutor([], watched="attempt_ended", late=True))
    assert isinstance(result, BrowseOutcome) and result.stopped == "cancelled"


# The guard's navigation log (Decision 0035 Y5).


class Sent:
    def __init__(self) -> None:
        self.commands: list[tuple[str, str | None]] = []
        self.handlers: list[Any] = []

    async def send(
        self, method: str, params: object = None, session: str | None = None
    ) -> dict[str, Any]:
        self.commands.append((method, session))
        return {}


@pytest.mark.asyncio
async def test_the_guard_logs_each_pages_top_frame_navigations_and_downloads() -> None:
    sent = Sent()
    guard = RequestGuard(sent)  # type: ignore[arg-type]  # a fake CDP sender
    attach = {"sessionId": "p1", "targetInfo": {"type": "page"}}
    await guard._event({"method": "Target.attachedToTarget", "params": attach})
    frame = {"sessionId": "f1", "targetInfo": {"type": "iframe"}}
    await guard._event({"method": "Target.attachedToTarget", "params": frame})
    assert ("Page.enable", "p1") in sent.commands and ("Page.enable", "f1") not in sent.commands
    events = [
        ("p1", {"frame": {"id": "a", "url": "https://a.test/"}}),
        ("p1", {"frame": {"id": "b", "parentId": "a", "url": "https://ads.test/"}}),
        (
            "p1",
            {
                "frame": {
                    "id": "a",
                    "url": "chrome-error://chromewebdata/",
                    "unreachableUrl": "https://a.test/x",
                }
            },
        ),
        ("f1", {"frame": {"id": "c", "url": "https://c.test/"}}),
    ]
    for session, params in events:
        await guard._event(
            {"method": "Page.frameNavigated", "sessionId": session, "params": params}
        )
    await guard._event(
        {"method": "Browser.downloadWillBegin", "params": {"url": "https://a.test/f"}}
    )
    assert (guard.navigated, guard.failed, guard.downloads) == (
        ["https://a.test/"],
        ["https://a.test/x"],
        1,
    )
    assert guard.refusals() == 2


# The browser-use container (BX-01, Y8).


@pytest.mark.asyncio
async def test_the_browser_use_container_is_hardened_and_holds_nothing_of_the_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runs: list[tuple[str, ...]] = []

    async def docker(self: BrowserExecutor, *arguments: str, check: bool = True) -> str:
        return "172.20.0.3\n" if arguments[0] == "inspect" else ""

    async def run(
        self: BrowserExecutor, *arguments: str, seconds: float = 60.0
    ) -> tuple[int, bytes, bytes]:
        runs.append(arguments)
        return 0, b'{"status": "completed", "text": "x", "steps": 1}\n', b"step 1: print(secret)"

    monkeypatch.setattr(BrowserExecutor, "_docker", docker)
    monkeypatch.setattr(BrowserExecutor, "_run", run)
    executor = BrowserExecutor(environ={"OPENROUTER_API_KEY": "sk-or-x", "PATH": "/bin"})
    session = type("S", (), {"name": "autobots-browser-abc", "run_id": "r", "generation": 2})()
    printed = await executor.run_browser_use(session, {"task": "t"}, seconds=360)
    (arguments,) = runs
    assert printed.startswith('{"status": "completed"') and "secret" not in printed
    assert arguments[:4] == ("run", "--rm", "--name", "autobots-browser-abc-use")
    for flag in ("--read-only", "--cap-drop=ALL", "no-new-privileges", "--pids-limit"):
        assert flag in arguments
    assert arguments[arguments.index("--network") + 1] == "autobots-browser-abc-net"
    assert arguments[arguments.index("--memory") + 1] == "1g" and arguments[-1] == BROWSER_USE.tag
    assert "autobots.browser.session=autobots-browser-abc" in arguments
    spec = json.loads(
        next(a for a in arguments if a.startswith("AUTOBOTS_BROWSE_SPEC=")).split("=", 1)[1]
    )
    assert spec == {
        "task": "t",
        "cdp_url": "http://172.20.0.3:9222",
        "base_url": "http://proxy:9300/v1",
    }
    assert not any(
        "sk-or" in part or "OPENROUTER" in part or "host.docker.internal" in part
        for part in arguments
    )


@pytest.mark.asyncio
async def test_a_browser_use_container_past_its_time_is_removed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    removed: list[tuple[str, ...]] = []

    async def docker(self: BrowserExecutor, *arguments: str, check: bool = True) -> str:
        removed.append(arguments)
        return "172.20.0.3" if arguments[0] == "inspect" else ""

    async def run(
        self: BrowserExecutor, *arguments: str, seconds: float = 60.0
    ) -> tuple[int, bytes, bytes]:
        return -1, b"", b"timed out"

    monkeypatch.setattr(BrowserExecutor, "_docker", docker)
    monkeypatch.setattr(BrowserExecutor, "_run", run)
    session = type("S", (), {"name": "autobots-browser-abc", "run_id": "r", "generation": 2})()
    assert await BrowserExecutor(environ={}).run_browser_use(session, {}, seconds=1) == ""
    assert ("rm", "-f", "autobots-browser-abc-use") in removed
    removed.clear()
    await BrowserExecutor(environ={}).remove("autobots-browser-abc")
    assert removed[0][:3] == ("rm", "-f", "autobots-browser-abc-use")


# browser-use's own qualification (Y8, the reversal).


def passing(path: Path, required: tuple[str, ...], key: str, fingerprint: object) -> Path:
    path.write_text(
        json.dumps(
            {
                "status": "passed",
                key: fingerprint,
                "cases": [{"id": case, "status": "passed"} for case in required],
            }
        )
    )
    return path


Reader = Callable[[tuple[str, ...]], Mapping[str, str | None]]


def labels(
    executor: str | None, browser_use: str | None
) -> Callable[[tuple[str, ...]], Mapping[str, str | None]]:
    def read(tags: tuple[str, ...]) -> Mapping[str, str | None]:
        values = [browser_use if tag == BROWSER_USE.tag else executor for tag in tags]
        text = "".join(
            json.dumps(None if v is None else {FINGERPRINT_LABEL: v}) + "\n" for v in values
        )
        return parse_labels(text, tags)

    return read


def test_browser_use_is_qualified_only_on_top_of_the_executor_and_its_own_check(
    tmp_path: Path,
) -> None:
    executor_fingerprint, own = images_fingerprint(ROOT), browser_use_fingerprint(ROOT)
    executor = passing(
        tmp_path / "e.json", REQUIRED_CASES, "executor_fingerprint", executor_fingerprint
    )
    report = passing(
        tmp_path / "b.json", REQUIRED_BROWSER_USE_CASES, "browser_use_fingerprint", own
    )
    good = labels(fingerprint_digest(executor_fingerprint), fingerprint_digest(own))

    def qualified(read: Reader = good, report: Path = report, executor: Path = executor) -> bool:
        return browser_use_qualified(ROOT, report, read, executor_report=executor)

    assert qualified()
    missing = passing(
        tmp_path / "m.json", REQUIRED_BROWSER_USE_CASES[1:], "browser_use_fingerprint", own
    )
    stale = passing(
        tmp_path / "s.json",
        REQUIRED_BROWSER_USE_CASES,
        "browser_use_fingerprint",
        executor_fingerprint,
    )
    assert not qualified(report=missing) and not qualified(report=stale)
    assert not qualified(report=tmp_path / "absent.json")
    assert not qualified(labels(fingerprint_digest(executor_fingerprint), None))
    assert not qualified(labels(fingerprint_digest(executor_fingerprint), "0" * 64))
    unqualified = passing(
        tmp_path / "u.json", REQUIRED_CASES[1:], "executor_fingerprint", executor_fingerprint
    )
    assert not qualified(executor=unqualified)


def test_removing_the_browser_use_image_leaves_the_executor_qualified(tmp_path: Path) -> None:
    fingerprint = images_fingerprint(ROOT)
    executor = passing(tmp_path / "e.json", REQUIRED_CASES, "executor_fingerprint", fingerprint)
    read = labels(fingerprint_digest(fingerprint), None)
    assert browser_qualification.executor_qualified(ROOT, executor, read)
    assert BROWSER_USE not in IMAGES


def test_browser_uses_image_is_built_only_from_its_fingerprinted_files() -> None:
    lines = (ROOT / BROWSER_USE.dockerfile).read_text().splitlines()
    copied = [
        source
        for line in lines
        if line.startswith("COPY ") and "--from=" not in line
        for source in line.split()[1:-1]
    ]
    ignore = (ROOT / BROWSER_USE.ignore_file).read_text().splitlines()
    kept = [line for line in ignore if line and not line.startswith("#")]
    assert sorted(kept) == sorted(["*", *(f"!{source}" for source in copied)])
    inputs = (
        BROWSER_USE.dockerfile,
        BROWSER_USE.ignore_file,
        *(f"{BROWSER_USE.context}/{s}" for s in copied),
    )
    assert set(inputs) <= set(BROWSER_USE_FINGERPRINTED)
    assert len(set(BROWSER_USE_FINGERPRINTED)) == len(BROWSER_USE_FINGERPRINTED)
    assert sorted(browser_use_fingerprint(ROOT)) == sorted(BROWSER_USE_FINGERPRINTED)
    from_lines = [line for line in lines if line.startswith("FROM ")]
    assert len(from_lines) == 2 and all("@sha256:" in line for line in from_lines)
