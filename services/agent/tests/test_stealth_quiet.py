"""US-20.3 offline: quiet on the page and its pace, Decision 0038 Z11 and Z12.

What a step records of what it pressed or typed into, the highlights, the pace on both engines, and
one stealth browse of a site at a time. Nothing here starts a container, opens a socket or calls a
model: the live cases are tests/db/checks/stealth_check.py, and the turn across connections is
tests/db/checks/browse_turn_check.py.
"""

import asyncio
import json
from collections.abc import Awaitable, Callable, Mapping
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from autobots.adapters import browser_cdp
from autobots.adapters.browser_cdp import (
    NEXT,
    STEPS_WORLD,
    TOUCHES,
    WATCH,
    Cdp,
    RequestGuard,
    Touch,
    touched,
)
from autobots.adapters.browser_use_box import BoxWatch, _Steps, guarded
from autobots.adapters.model_endpoint import Reply
from autobots.application import browse_turns, browsing_tool
from autobots.application.browse_turns import Pace, SiteBusy, TurnLost, site_of, turn
from autobots.application.browsing_loop import BrowseOutcome
from autobots.application.loop_admission import active_middleware
from autobots.application.tool_definitions import ToolContext, ToolScope
from autobots.contracts.browse_steps import BrowseTouch
from autobots.contracts.browsing import BrowseGoalV2Input
from sql_fakes import RuledConnection

PRESSED = ["pressed", "button", "Show transcript"]


# What a step records (Z11).


def test_a_pages_answer_is_read_as_bounded_data() -> None:
    assert touched(json.dumps(["typed", "k" * 90, "l" * 200])) == Touch("typed", "k" * 40, "l" * 80)
    assert touched(json.dumps(PRESSED)) == Touch("pressed", "button", "Show transcript")
    for odd in ("", "null", "{}", "nonsense", '["deleted","a","b"]', '["pressed"]', "7", None):
        assert touched(odd) is None


class Page:
    """A DevTools connection whose one page answers each poll from what its world noted."""

    def __init__(self, *answers: object) -> None:
        self.commands: list[tuple[str, dict[str, Any]]] = []
        self.handlers: list[Any] = []
        self.answers = list(answers)
        self.fails = False

    async def send(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        session: str | None = None,
        seconds: float | None = 30,
    ) -> dict[str, Any]:
        self.commands.append((method, params or {}))
        if method == "Target.getTargets":
            return {"result": {"targetInfos": [{"type": "page", "targetId": "main"}]}}
        if method == "Target.attachToTarget":
            return {"result": {"sessionId": "page"}}
        if method == "Page.createIsolatedWorld":
            return {} if self.fails else {"result": {"executionContextId": 7}}
        if method == "Runtime.evaluate":
            assert seconds is None
            if not self.answers:
                # The page was left: its world is gone.
                return {"error": {"message": "Inspected target navigated or closed"}}
            return {"result": {"result": {"value": self.answers.pop(0)}}}
        return {"result": {}}

    def sent(self, method: str) -> list[dict[str, Any]]:
        return [params for name, params in self.commands if name == method]


async def guard_of(page: Page, watches: bool = True) -> RequestGuard:
    guard = RequestGuard(page, submits=True, watches=watches)  # type: ignore[arg-type]  # a fake CDP sender
    await guard.start()
    return guard


async def committed(guard: RequestGuard, url: str = "https://a.test/", **frame: str) -> None:
    params = {"frame": {"id": "main", "url": url, **frame}}
    await guard._event({"method": "Page.frameNavigated", "sessionId": "page", "params": params})
    await asyncio.gather(*guard.listening)


@pytest.mark.asyncio
async def test_presses_are_awaited_in_a_world_of_their_own_and_only_on_the_stealth_browser() -> (
    None
):
    page = Page(json.dumps(PRESSED), json.dumps(["typed", "text input", "Search"]))
    guard = await guard_of(page)
    assert page.sent("Page.addScriptToEvaluateOnNewDocument") == [
        {"source": WATCH, "worldName": STEPS_WORLD}
    ]
    await committed(guard)
    assert page.sent("Page.createIsolatedWorld") == [{"frameId": "main", "worldName": STEPS_WORLD}]
    polls = page.sent("Runtime.evaluate")
    assert all(poll["contextId"] == 7 and poll["expression"] == NEXT for poll in polls)
    assert all(poll["awaitPromise"] for poll in polls) and len(polls) >= TOUCHES
    assert sorted(touch.label for touch in guard.touched) == ["Search", "Show transcript"]
    # Runtime.enable and a binding are signs a page could read, so nothing here sends one.
    assert not page.sent("Runtime.enable") and not page.sent("Runtime.addBinding")

    quiet = Page(json.dumps(PRESSED))
    boxed = await guard_of(quiet, watches=False)
    await committed(boxed)
    assert boxed.touched == [] and not quiet.sent("Page.addScriptToEvaluateOnNewDocument")
    assert not quiet.sent("Page.createIsolatedWorld")


@pytest.mark.asyncio
async def test_a_page_that_cannot_be_read_loses_only_its_touches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(browser_cdp, "POLL_SECONDS", 0)
    lost, absent = Page(), Page(*[None] * 200)
    lost.fails = True
    for page in (lost, absent, Page(*["nonsense"] * 3)):
        guard = await guard_of(page)
        await committed(guard)
        assert guard.touched == []
    # A world whose script never came is asked a few times, then left alone.
    assert len(absent.sent("Runtime.evaluate")) <= TOUCHES * 6


@pytest.mark.asyncio
async def test_each_new_page_is_watched_and_an_error_page_is_not() -> None:
    page = Page()
    guard = await guard_of(page)
    await committed(guard)
    await committed(guard, "https://a.test/next")
    await committed(guard, "chrome-error://x/", unreachableUrl="https://b.test/")
    assert len(page.sent("Page.createIsolatedWorld")) == 2
    # Nothing is asked of a page while it is being left.
    params = {
        "requestId": "r",
        "request": {"method": "GET", "url": "https://a.test/third", "headers": {}},
        "resourceType": "Document",
        "frameId": "main",
    }
    before = len(page.sent("Runtime.evaluate"))
    await guard._event({"method": "Fetch.requestPaused", "sessionId": "page", "params": params})
    assert len(page.sent("Runtime.evaluate")) == before


@pytest.mark.asyncio
async def test_a_late_reply_to_a_command_that_timed_out_never_stops_the_reader() -> None:
    """Its future is done, and setting a result on it would end the connection's reader."""

    class Socket:
        def __init__(self) -> None:
            self.lines: asyncio.Queue[str] = asyncio.Queue()

        async def send(self, text: str) -> None:
            return None

        def __aiter__(self) -> "Socket":
            return self

        async def __anext__(self) -> str:
            return await self.lines.get()

        async def close(self) -> None:
            return None

    socket = Socket()
    cdp = Cdp(socket)  # type: ignore[arg-type]  # a fake socket
    with pytest.raises(TimeoutError):
        await cdp.send("Runtime.evaluate", seconds=0.01)
    await socket.lines.put(json.dumps({"id": 1, "result": {"late": True}}))
    second = asyncio.ensure_future(cdp.send("Page.enable"))
    await asyncio.sleep(0)
    await socket.lines.put(json.dumps({"id": 2, "result": {}}))
    assert (await second)["id"] == 2
    await cdp.close()


@pytest.mark.asyncio
async def test_a_step_records_the_first_ten_touches_and_the_next_starts_afresh() -> None:
    page = Page()
    guard = await guard_of(page)
    guard.touched = [Touch("pressed", "button", str(n)) for n in range(8)] * 2
    recorded: list[tuple[BrowseTouch, ...]] = []

    async def sink(
        step: int,
        shown: str | None,
        image: bytes | None,
        submits: tuple[str, ...],
        touched: tuple[BrowseTouch, ...],
    ) -> None:
        recorded.append(touched)

    steps = _Steps(page, guard, sink)  # type: ignore[arg-type]  # a fake CDP sender
    await steps.take()
    await steps.take()
    assert [len(touched) for touched in recorded] == [10, 0]
    assert [touch.label for touch in recorded[0]] == [str(n) for n in (*range(8), 0, 1)]


# The pace (Z12).


class Ticking:
    def __init__(self) -> None:
        self.now = 50.0
        self.slept: list[float] = []

    def __call__(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


@pytest.mark.asyncio
async def test_steps_are_at_least_two_seconds_apart_and_a_slow_one_waits_for_nothing() -> None:
    clock = Ticking()
    pace = Pace(clock=clock, sleep=clock.sleep)
    await pace()
    clock.now += 0.5
    await pace()
    clock.now += 9.0
    await pace()
    assert clock.slept == [1.5]


def test_browser_use_and_the_loop_both_keep_it() -> None:
    calls: list[str] = []

    async def pace() -> None:
        calls.append("pace")

    async def answer(body: Mapping[str, Any]) -> Reply:
        calls.append("answer")
        return Reply({})

    watch = BoxWatch(max_calls=5, refused=lambda: False, pace=pace)

    async def once() -> None:
        await guarded(answer, watch)({"messages": []})

    asyncio.run(once())

    async def step(messages: list[Any]) -> Any:  # noqa: ANN401 - a step's reply
        calls.append("step")
        return None

    asyncio.run(browsing_tool._paced(step, pace)([]))  # type: ignore[arg-type]  # a fake pace
    assert calls == ["pace", "answer", "pace", "step"]


# One browse of a site at a time (Z12).


@pytest.mark.parametrize(
    ("domain", "site"),
    [
        ("example.com", "example.com"),
        ("a.b.Example.com.", "example.com"),
        ("bccr.fi.cr", "bccr.fi.cr"),
        ("www.bccr.fi.cr", "bccr.fi.cr"),
        ("www.gollo.co.cr", "gollo.co.cr"),
        ("en.wikivoyage.org", "wikivoyage.org"),
        ("localhost", "localhost"),
    ],
)
def test_a_domains_site_is_its_registrable_part(domain: str, site: str) -> None:
    assert site_of(domain) == site


class Locks:
    """Enough of a connection for the turn: which advisory locks another session holds."""

    def __init__(self, held: set[str]) -> None:
        self.held = held
        self.freed: list[str] = []

    async def execute(self, query: str, params: Any = None, /) -> Any:  # noqa: ANN401 - a cursor
        site = str(params[0])
        if "unlock" in query:
            self.freed.append(site)
            self.held.discard(site)
            return SimpleNamespace()
        taken = site not in self.held
        if taken:
            self.held.add(site)

        async def fetchone() -> tuple[bool]:
            return (taken,)

        async def fetchall() -> list[tuple[bool]]:
            return [(taken,)]

        return SimpleNamespace(fetchone=fetchone, fetchall=fetchall, description=[])


async def alive() -> bool:
    return True


async def dead() -> bool:
    return False


def waiting(
    held: set[str],
    domains: list[str],
    seconds: float,
    living: Callable[[], Awaitable[bool]] = alive,
) -> tuple[str, float, Locks]:
    locks, clock = Locks(held), Ticking()

    async def go() -> str:
        try:
            async with turn(
                locks,  # type: ignore[arg-type]  # a fake connection
                domains,
                seconds,
                living,
                clock=clock,
                sleep=clock.sleep,
            ):
                return "taken"
        except (SiteBusy, TurnLost) as refused:
            return type(refused).__name__

    return asyncio.run(go()), clock.now - 50.0, locks


def test_a_free_site_is_taken_at_once_and_freed_after() -> None:
    result, waited, locks = waiting(set(), ["b.example.com", "a.example.com", "x.org"], 30)
    assert (result, waited) == ("taken", 0.0)
    assert locks.freed == ["browse-site:x.org", "browse-site:example.com"]
    assert locks.held == set() and browse_turns._HELD == set()


def test_a_site_another_browse_holds_is_waited_for_until_time_is_up() -> None:
    result, waited, locks = waiting({"browse-site:example.com"}, ["www.example.com"], 30)
    assert result == "SiteBusy" and 30.0 <= waited < 32.0
    assert locks.freed == [] and browse_turns._HELD == set()


def test_one_site_taken_is_freed_when_the_next_never_comes() -> None:
    result, _, locks = waiting({"browse-site:z.org"}, ["a.org", "z.org"], 5)
    assert result == "SiteBusy" and locks.freed == ["browse-site:a.org"]


def test_a_browse_whose_attempt_ended_stops_waiting() -> None:
    result, waited, _ = waiting({"browse-site:example.com"}, ["example.com"], 300, dead)
    assert (result, waited) == ("TurnLost", 0.0)


def test_two_calls_of_one_attempt_take_turns_though_they_share_a_connection() -> None:
    """Postgres lets one session take its own advisory lock twice."""

    class Reentrant(Locks):
        async def execute(self, query: str, params: Any = None, /) -> Any:  # noqa: ANN401 - a cursor
            if "unlock" not in query:
                self.held.clear()
            return await super().execute(query, params)

    async def go() -> list[str]:
        locks, order = Reentrant(set()), []

        async def call(name: str) -> None:
            async with turn(
                locks,  # type: ignore[arg-type]  # a fake connection
                ["example.com"],
                30,
                alive,
                sleep=lambda _: asyncio.sleep(0),
            ):
                order.append(f"{name} in")
                await asyncio.sleep(0.01)
                order.append(f"{name} out")

        await asyncio.gather(call("a"), call("b"))
        return order

    assert asyncio.run(go()) == ["a in", "a out", "b in", "b out"]


def test_a_failed_take_holds_nothing() -> None:
    class Broken(Locks):
        async def execute(self, query: str, params: Any = None, /) -> Any:  # noqa: ANN401 - a cursor
            raise ConnectionError("gone")

    async def go() -> None:
        async with turn(Broken(set()), ["example.com"], 5, alive):  # type: ignore[arg-type]  # a fake connection
            raise AssertionError("never taken")

    with pytest.raises(ConnectionError):
        asyncio.run(go())
    assert browse_turns._HELD == set()


# The call (Z12).


def call(
    monkeypatch: pytest.MonkeyPatch, browser: str, waits: float | Exception
) -> tuple[str, list[Any]]:
    """How a YOLO call ends when its turn waits, and what its browse was given."""
    seen: list[Any] = []

    class Turn:
        def __init__(self, connection: object, domains: object, seconds: float, *_: object) -> None:
            seen.append(("turn", list(domains), seconds))  # type: ignore[call-overload]  # a list of domains

        async def __aenter__(self) -> float:
            if isinstance(waits, Exception):
                raise waits
            return waits

        async def __aexit__(self, *_: object) -> None:
            return None

    async def on_browser_use(*args: Any) -> BrowseOutcome:  # noqa: ANN401 - the tool's own arguments
        seen.append(("browse", args[4].seconds))
        return BrowseOutcome("Read.", (), 1, 1, "done")

    async def sweep(*_: object) -> None:
        return None

    monkeypatch.setattr(browsing_tool, "turn", Turn)
    monkeypatch.setattr(browsing_tool, "_on_browser_use", on_browser_use)
    monkeypatch.setattr(browsing_tool, "_sweep", sweep)
    runtime = browsing_tool.BrowsingRuntime(
        object(),  # type: ignore[arg-type]  # never started
        object(),
        "route",  # type: ignore[arg-type]  # never dispatched
        browser_use=lambda: True,
        stealth=lambda: True,
    )
    connection = RuledConnection(
        ("browsing_yolo", [(True,)]),
        ("browse_domains", [{"domains": '["a.test"]'}]),
        ("v.config ->> 'browser'", [{"browser": browser, "timezone": "UTC"}]),
        ("", []),
    )
    args = {"task": "Read", "start_url": "https://a.test/", "allowed_domains": ["a.test"]}
    tool = browsing_tool.browse_tool(runtime, qualified=lambda: True, version=2)
    scope = ToolScope(uuid4(), uuid4(), 1, {"browse_goal": 2})

    async def go() -> Any:  # noqa: ANN401 - the tool's output
        with active_middleware(object()):  # type: ignore[arg-type]  # the fakes never admit
            return await tool.handler(
                BrowseGoalV2Input.model_validate(args), ToolContext(connection, scope, None)
            )

    return asyncio.run(go()).stopped, seen


def test_a_stealth_browse_waits_its_turn_within_its_own_time_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert call(monkeypatch, "stealth", 40.0) == (
        "done",
        [("turn", ["a.test"], 300), ("browse", 260)],
    )
    assert call(monkeypatch, "stealth", SiteBusy("a.test")) == (
        "max_seconds",
        [("turn", ["a.test"], 300)],
    )
    assert call(monkeypatch, "stealth", TurnLost("a.test"))[0] == "cancelled"


def test_a_box_browse_takes_no_turn(monkeypatch: pytest.MonkeyPatch) -> None:
    assert call(monkeypatch, "box", SiteBusy("a.test")) == ("done", [("browse", 300)])
