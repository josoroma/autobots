"""US-20.2 offline: a check that clears by itself, Decision 0038 Z5 and Z7 to Z10.

Which hosts each session may reach, which checks are the page, a widget or a person's, the wait
before admission, and what browser-use is told. Nothing here starts a container, opens a socket or
calls a model: the live cases are tests/db/checks/stealth_check.py.
"""

import asyncio
import importlib.util
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from autobots.adapters import browser_cdp
from autobots.adapters.browser_cdp import CHALLENGE_HOSTS, Patience, RequestGuard, bot_check_host
from autobots.adapters.browser_executor import BrowserExecutor, ExecutorUnavailable, Stealth
from autobots.adapters.browser_use_box import BoxCall, BoxReport, BoxWatch, guarded, outcome
from autobots.adapters.model_endpoint import EndpointRefused, Reply
from autobots.application import browsing_tool
from autobots.application.browsing_loop import BrowseOutcome
from autobots.application.loop_admission import active_middleware
from autobots.application.tool_definitions import ToolContext, ToolFailed, ToolScope
from autobots.contracts.browsing import BrowseGoalV2Input
from sql_fakes import RuledConnection

ROOT = Path(__file__).resolve().parents[3]
CHL_PAGE = "https://shop.test/cdn-cgi/challenge-platform/h/b/orchestrate/chl_page/v1"
WIDGET = "https://challenges.cloudflare.com/cdn-cgi/challenge-platform/h/b/turnstile/if/ov2"
WIDGET_SCRIPT = (
    "https://challenges.cloudflare.com/cdn-cgi/challenge-platform/h/b/orchestrate/chl_api"
)
DATADOME = "https://geo.captcha-delivery.com/captcha/?initialCid=x"
SORRY = "https://www.google.com/sorry/index?continue=x"
PERSON = (
    "https://www.google.com/recaptcha/api2/anchor?k=x&size=normal",
    "https://www.google.com/recaptcha/enterprise/bframe?k=x",
    "https://newassets.hcaptcha.com/captcha/v1/x/static/hcaptcha.html",
    "https://client-api.arkoselabs.com/fc/gt2/",
)


class Sent:
    """Records the commands a guard sends, and answers what its start reads."""

    def __init__(self) -> None:
        self.commands: list[tuple[str, dict[str, Any] | None, str | None]] = []
        self.handlers: list[Any] = []

    async def send(
        self, method: str, params: dict[str, Any] | None = None, session: str | None = None
    ) -> dict[str, Any]:
        self.commands.append((method, params, session))
        if method == "Target.getTargets":
            return {"result": {"targetInfos": [{"type": "page", "targetId": "main"}]}}
        if method == "Target.attachToTarget":
            return {"result": {"sessionId": "page"}}
        return {"result": {}}


class Clock:
    """A clock the fake sleep moves, so a wait takes no time."""

    def __init__(self) -> None:
        self.now = 100.0
        self.at: dict[float, Any] = {}

    def __call__(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.now += seconds
        for moment in sorted(self.at):
            if moment <= self.now:
                await self.at.pop(moment)()


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    ticking = Clock()
    monkeypatch.setattr(browser_cdp, "asyncio", SimpleNamespace(sleep=ticking.sleep))
    return ticking


PATIENT = Patience()


async def guard_of(patience: Patience | None = PATIENT, clock: Clock | None = None) -> RequestGuard:
    guard = RequestGuard(Sent(), submits=True, patience=patience)  # type: ignore[arg-type]  # a fake CDP sender
    if clock is not None:
        guard.clock = clock
    await guard.start()
    return guard


async def request(
    guard: RequestGuard, url: str, kind: str = "Document", frame: str = "child"
) -> str:
    params = {
        "requestId": "r",
        "request": {"method": "GET", "url": url, "headers": {}},
        "resourceType": kind,
        "frameId": frame,
    }
    await guard._event({"method": "Fetch.requestPaused", "sessionId": "page", "params": params})
    sent = guard.cdp
    assert isinstance(sent, Sent)
    return sent.commands[-1][0]


async def committed(guard: RequestGuard, url: str, **frame: str) -> None:
    params = {"frame": {"id": "main", "url": url, **frame}}
    await guard._event({"method": "Page.frameNavigated", "sessionId": "page", "params": params})


# Challenge hosts, as parts of a page only (Z7).


@pytest.mark.parametrize("host", [*CHALLENGE_HOSTS, "geo.captcha-delivery.com", "js.datadome.co"])
@pytest.mark.asyncio
async def test_a_challenge_host_loads_as_a_part_and_never_as_a_page(host: str) -> None:
    guard = await guard_of()
    assert await request(guard, f"https://{host}/x.js", "Script") == "Fetch.continueRequest"
    assert await request(guard, f"https://{host}/x", "Document") == "Fetch.continueRequest"
    assert guard.refusals() == 0
    assert await request(guard, f"https://{host}/x", frame="main") == "Fetch.failRequest"
    assert guard.refusals() == 1


@pytest.mark.parametrize("host", ["notdatadome.co", "datadome.co.evil.test", "shop.test"])
@pytest.mark.asyncio
async def test_no_other_host_is_taken_for_one(host: str) -> None:
    guard = await guard_of()
    assert await request(guard, f"https://{host}/", frame="main") == "Fetch.continueRequest"


@pytest.mark.asyncio
async def test_the_boxs_guard_bars_no_page_and_keeps_its_own_rule() -> None:
    guard = await guard_of(None)
    assert await request(guard, f"https://{CHALLENGE_HOSTS[2]}/", frame="main") == (
        "Fetch.continueRequest"
    )
    assert guard.refusals() == 0 and guard.bot_checks == []
    for url in (WIDGET, CHL_PAGE, DATADOME):
        before = len(guard.bot_checks)
        await request(guard, url)
        assert len(guard.bot_checks) == before + 1 and bot_check_host(url, "Document")
    assert not guard.checking


def test_the_list_is_the_decisions_and_only_a_session_given_it_reaches_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert CHALLENGE_HOSTS == ("challenges.cloudflare.com", "captcha-delivery.com", "datadome.co")
    calls: list[tuple[str, ...]] = []

    async def docker(self: BrowserExecutor, *arguments: str, check: bool = True) -> str:
        calls.append(arguments)
        return "127.0.0.1:5555" if arguments[0] == "port" else ""

    async def ready(self: BrowserExecutor, session: object, seconds: float = 20.0) -> None:
        return None

    monkeypatch.setattr(BrowserExecutor, "_docker", docker)
    monkeypatch.setattr(BrowserExecutor, "_ready", ready)

    def hosts(stealth: Stealth | None) -> str:
        calls.clear()
        asyncio.run(BrowserExecutor(environ={}).start("r", 1, ("example.com",), stealth=stealth))
        proxy = next(call for call in calls if call[:2] == ("run", "-d"))
        return next(part for part in proxy if part.startswith("AUTOBOTS_ALLOWED_HOSTS="))

    assert hosts(None).endswith("=example.com") and hosts(Stealth()).endswith("=example.com")
    assert hosts(Stealth("UTC", CHALLENGE_HOSTS)).endswith(
        "=example.com,challenges.cloudflare.com,captcha-delivery.com,datadome.co"
    )


@pytest.mark.parametrize(
    ("on", "browser", "reached"),
    [
        (True, "stealth", CHALLENGE_HOSTS),
        (False, "stealth", ()),
        (True, "box", None),
        (False, "box", None),
    ],
)
def test_only_browser_use_on_the_stealth_browser_is_given_the_list(
    monkeypatch: pytest.MonkeyPatch, on: bool, browser: str, reached: tuple[str, ...] | None
) -> None:
    given: list[Stealth | None] = []
    called: list[BoxCall] = []

    class Executor:
        async def start(self, *_: object, stealth: Stealth | None = None) -> object:
            given.append(stealth)
            raise ExecutorUnavailable("a fake that starts nothing")

        async def sweep(self, alive: object) -> list[str]:
            return []

    async def in_box(box: object, call: BoxCall, *, start: Any, **_: object) -> BrowseOutcome:  # noqa: ANN401 - the tool's own start
        called.append(call)
        await start(None)
        raise AssertionError("the fake executor starts nothing")

    monkeypatch.setattr(browsing_tool, "browse_in_box", in_box)
    runtime = browsing_tool.BrowsingRuntime(
        Executor(),  # type: ignore[arg-type]  # a fake BrowserExecutor
        object(),
        "route",  # type: ignore[arg-type]  # never dispatched
        browser_use=lambda: True,
        stealth=lambda: True,
    )
    connection = RuledConnection(
        ("pg_try_advisory_lock", [(True,)]),
        ("browsing_yolo", [(on,)]),
        ("browse_domains", [{"domains": '["a.test"]'}]),
        ("v.config ->> 'browser'", [{"browser": browser, "timezone": "UTC"}]),
        ("", []),
    )
    args = {"task": "Read", "start_url": "https://a.test/", "allowed_domains": ["a.test"]}
    tool = browsing_tool.browse_tool(runtime, qualified=lambda: True, version=2)
    scope = ToolScope(uuid4(), uuid4(), 1, {"browse_goal": 2})

    async def go() -> None:
        with active_middleware(object()):  # type: ignore[arg-type]  # the fakes never admit
            await tool.handler(
                BrowseGoalV2Input.model_validate(args), ToolContext(connection, scope, None)
            )

    with pytest.raises(ToolFailed, match="executor_unavailable"):
        asyncio.run(go())
    assert [s and s.challenge_hosts for s in given] == [reached]
    if called:
        stealth = called[0].stealth
        assert (stealth and stealth.challenge_hosts) == reached
        assert called[0].spec().get("stealth") is (True if browser == "stealth" else None)
        assert called[0].spec()["allowed_domains"] == ["a.test"]


# Which checks are which (Z8, Z9).


@pytest.mark.parametrize("url", [CHL_PAGE, DATADOME, SORRY])
@pytest.mark.asyncio
async def test_a_check_that_is_the_page_is_waited_for_and_not_yet_a_bot_check(url: str) -> None:
    guard = await guard_of()
    await request(guard, url, "Script" if url == CHL_PAGE else "Document")
    assert guard.checking and guard.bot_checks == []


@pytest.mark.parametrize("url", PERSON)
@pytest.mark.asyncio
async def test_a_check_that_asks_a_person_is_a_bot_check_at_first_sight(url: str) -> None:
    guard = await guard_of()
    await request(guard, url)
    assert len(guard.bot_checks) == 1 and not guard.checking


@pytest.mark.parametrize(
    ("url", "kind"),
    [
        (WIDGET, "Document"),
        (WIDGET_SCRIPT, "Script"),
        ("https://challenges.cloudflare.com/turnstile/v0/api.js", "Script"),
        ("https://shop.test/cdn-cgi/challenge-platform/scripts/jsd/main.js", "Script"),
        ("https://www.google.com/recaptcha/api2/anchor?k=x&size=invisible", "Document"),
        ("https://js.hcaptcha.com/1/api.js", "Script"),
    ],
)
@pytest.mark.asyncio
async def test_a_widget_that_needs_nobody_is_no_check(url: str, kind: str) -> None:
    guard = await guard_of()
    await request(guard, url, kind)
    assert guard.bot_checks == [] and not guard.checking


# The wait (Z8).


@pytest.mark.asyncio
async def test_a_check_that_clears_lets_the_browse_go_on(clock: Clock) -> None:
    guard = await guard_of(clock=clock)
    await committed(guard, "https://shop.test/")
    await request(guard, CHL_PAGE, "Script")

    async def clears() -> None:
        await committed(guard, "https://shop.test/?ok")

    clock.at[105.0] = clears
    await guard.settle()
    assert guard.bot_checks == [] and not guard.checking and guard.since is None
    assert 107.0 <= clock.now < 110.0


@pytest.mark.asyncio
async def test_a_check_that_stays_is_a_bot_check_when_its_time_is_up(clock: Clock) -> None:
    guard = await guard_of(clock=clock)
    await request(guard, CHL_PAGE, "Script")
    await guard.settle()
    assert guard.bot_checks == ["shop.test"] and 120.0 <= clock.now < 121.0


@pytest.mark.asyncio
async def test_a_check_that_comes_back_gets_no_more_time(clock: Clock) -> None:
    guard = await guard_of(clock=clock)
    await request(guard, CHL_PAGE, "Script")

    async def again() -> None:
        await committed(guard, "https://shop.test/?again")
        await request(guard, CHL_PAGE, "Script")

    for moment in (105.0, 110.0, 115.0):
        clock.at[moment] = again
    await guard.settle()
    assert guard.bot_checks == ["shop.test"] and 120.0 <= clock.now < 121.0


@pytest.mark.asyncio
async def test_a_page_that_never_committed_clears_nothing(clock: Clock) -> None:
    """The proxy refuses a "sorry" page's host, so it lands on an error page."""
    guard = await guard_of(clock=clock)
    await request(guard, SORRY, frame="main")
    await committed(guard, "chrome-error://chromewebdata/", unreachableUrl=SORRY)
    await guard.settle()
    assert guard.bot_checks == ["www.google.com"]


@pytest.mark.asyncio
async def test_a_second_check_after_one_cleared_gets_its_own_time(clock: Clock) -> None:
    guard = await guard_of(clock=clock)
    await request(guard, CHL_PAGE, "Script")
    await committed(guard, "https://shop.test/?ok")
    await guard.settle()
    began = clock.now
    await request(guard, CHL_PAGE, "Script")
    await guard.settle()
    assert guard.bot_checks == ["shop.test"] and 20.0 <= clock.now - began < 21.0


@pytest.mark.asyncio
async def test_with_no_check_and_on_the_box_nothing_waits(clock: Clock) -> None:
    for patience in (Patience(), None):
        guard = await guard_of(patience, clock)
        await committed(guard, "https://shop.test/")
        await guard.settle()
    assert clock.now == 100.0


def ask(watch: BoxWatch) -> tuple[str, int]:
    answered: list[Mapping[str, Any]] = []

    async def answer(body: Mapping[str, Any]) -> Reply:
        answered.append(body)
        return Reply({"object": "chat.completion"})

    async def once() -> str:
        try:
            await guarded(answer, watch)({"messages": []})
        except EndpointRefused as refused:
            return refused.code
        return "admitted"

    return asyncio.run(once()), len(answered)


def test_the_next_model_request_waits_before_admission() -> None:
    seen: list[str] = []
    stays = [False]

    async def settle() -> None:
        seen.append("waited")
        stays[0] = len(seen) > 1

    watch = BoxWatch(max_calls=5, refused=lambda: False, bot_check=lambda: stays[0], settle=settle)
    assert ask(watch) == ("admitted", 1) and seen == ["waited"]
    assert ask(watch) == ("bot_check", 0) and watch.model_calls == 1
    # A browse that has ended waits for nothing more.
    assert ask(watch) == ("bot_check", 0) and len(seen) == 2


def test_a_check_still_showing_at_the_end_is_a_bot_check() -> None:
    watch = BoxWatch(max_calls=5, refused=lambda: False)
    watch.model_calls = 1
    ended = outcome(
        BoxReport("completed", "Read.", 1), watch, refused=False, visited=(), bot_check=True
    )
    assert ended.stopped == "bot_check"


# What browser-use is told (Z10).


def runner_task(
    spec: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> tuple[str, dict[str, Any]]:
    """The task and options services/browser-use/runner.py gives browser-use, which isn't installed
    here."""
    made: list[tuple[str, dict[str, Any]]] = []

    class Agent:
        def __init__(self, task: str, **options: Any) -> None:  # noqa: ANN401 - browser-use's own options
            made.append((task, options))

        async def run(self, **_: object) -> object:
            return SimpleNamespace(status="completed", text="", steps=1, output=None)

    fake = ModuleType("browser_use")

    def anything(*_: object, **__: object) -> None:
        return None

    for name, value in (("Agent", Agent), ("Browser", anything), ("ChatOpenAI", anything)):
        setattr(fake, name, value)
    ai = ModuleType("pydantic_ai")
    ai.StructuredDict = dict  # type: ignore[attr-defined]  # a fake module
    monkeypatch.setitem(sys.modules, "browser_use", fake)
    monkeypatch.setitem(sys.modules, "pydantic_ai", ai)
    base: dict[str, Any] = {
        "start_url": "https://a.test/",
        "allowed_domains": ["a.test"],
        "task": "Read",
    }
    base |= {"base_url": "http://p", "cdp_url": "http://c", "max_steps": 1, "max_seconds": 10}
    monkeypatch.setenv("AUTOBOTS_BROWSE_SPEC", json.dumps({**base, **spec}))
    path = ROOT / "services/browser-use/runner.py"
    loaded = importlib.util.spec_from_file_location("browse_runner", path)
    assert loaded is not None and loaded.loader is not None
    module = importlib.util.module_from_spec(loaded)
    loaded.loader.exec_module(module)
    assert asyncio.run(module.main()) == 0
    return made[0]


def test_browser_use_is_told_never_to_answer_a_check_on_the_stealth_browser(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task, options = runner_task({"stealth": True}, monkeypatch)
    assert "Never press, type into or answer a CAPTCHA" in task
    assert options["use_vision"] is False and options["judge"] is False
    # Decision 0038 Z11: nothing is drawn on the stealth page, and the box keeps its highlights.
    assert options["highlight_actions"] is False
    task, options = runner_task({}, monkeypatch)
    assert "CAPTCHA" not in task and options["highlight_actions"] is True
