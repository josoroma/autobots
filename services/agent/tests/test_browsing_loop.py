"""US-14.14 offline: the browsing loop's actions, limits and model path, with a scripted model."""

import asyncio
import gc
from collections.abc import Callable
from typing import Any

import pytest
from langchain_core.messages import AIMessage, BaseMessage

from autobots.adapters.loop_middleware import AdmittedModel
from autobots.application.browsing_loop import (
    ACTION_TOOLS,
    Link,
    PageView,
    action_of,
    admitted_steps,
    bare,
    browse,
)
from autobots.application.loop_admission import admitted_scope
from autobots.application.loop_policy import LoopStopped, UnadmittedModelCall

SITE = {
    "https://example.com/": PageView(
        url="https://example.com/",
        title="Example Domain",
        text="This domain is for use in examples.",
        links=(
            Link(text="More information", url="https://www.iana.org/help/example-domains"),
            Link(text="Elsewhere", url="https://evil.test/steal?token=1"),
        ),
    ),
    "https://www.iana.org/help/example-domains": PageView(
        url="https://www.iana.org/help/example-domains?ref=x#top",
        title="Example Domains",
        text="Reserved by RFC 2606.",
    ),
}


class Pages:
    def __init__(self) -> None:
        self.at = ""
        self.opened: list[str] = []
        self.scrolls = 0

    async def view(self) -> PageView:
        return SITE[self.at]

    async def go(self, url: str) -> None:
        self.opened.append(url)
        self.at = url

    async def scroll(self) -> None:
        self.scrolls += 1


def act(name: str, **args: Any) -> AIMessage:
    return AIMessage(
        content="",
        response_metadata={"finish_reason": "tool_calls"},
        tool_calls=[{"name": name, "args": args, "id": f"c-{name}", "type": "tool_call"}],
    )


class Steps:
    def __init__(self, *replies: AIMessage) -> None:
        self.replies = list(replies)
        self.seen: list[list[BaseMessage]] = []

    async def __call__(self, messages: list[BaseMessage]) -> AIMessage:
        self.seen.append(messages)
        return self.replies.pop(0)


def allowed(url: str) -> bool:
    host = url.split("/")[2] if url.startswith("https://") else ""
    return host in {"example.com", "www.iana.org"}


def run(steps: Steps, pages: Pages | None = None, **limits: Any) -> Any:
    return asyncio.run(
        browse(
            pages or Pages(),
            steps,
            task="What is example.com for?",
            start_url="https://example.com/",
            permitted=allowed,
            max_steps=limits.get("max_steps", 10),
            max_seconds=limits.get("max_seconds", 120),
            clock=limits.get("clock", lambda: 0.0),
        )
    )


def test_three_steps_read_follow_a_link_and_finish() -> None:
    pages = Pages()
    steps = Steps(
        act("scroll", notes="examples"),
        act("open_link", number=1, notes="IANA reserves it"),
        act("finish", summary="Reserved for documentation by IANA."),
    )
    outcome = run(steps, pages)
    assert outcome.stopped == "done"
    assert outcome.summary == "Reserved for documentation by IANA."
    assert (outcome.steps, outcome.model_calls, pages.scrolls) == (3, 3, 1)
    assert outcome.visited == ("https://example.com/", "https://www.iana.org/help/example-domains")
    page_text = steps.seen[0][-1].content
    assert "<third_party_page>" in page_text and "[1] More information" in page_text


@pytest.mark.parametrize(
    "reply",
    [
        AIMessage(content="I think it is for examples."),
        act("hover", target="x"),
        act("open_link", number=0),
        act("open_link", number=9),
        act("go_to", url="https://example.com/", surprise=True),
        AIMessage(
            content="",
            tool_calls=[
                {"name": "scroll", "args": {}, "id": "a", "type": "tool_call"},
                {"name": "scroll", "args": {}, "id": "b", "type": "tool_call"},
            ],
        ),
        AIMessage(
            content="",
            invalid_tool_calls=[
                {
                    "name": "scroll",
                    "args": "{",
                    "id": "a",
                    "error": "bad",
                    "type": "invalid_tool_call",
                }
            ],
        ),
    ],
)
def test_anything_but_one_valid_action_ends_the_call_with_no_further_step(reply: AIMessage) -> None:
    steps = Steps(reply, act("finish", summary="never asked"))
    outcome = run(steps)
    assert outcome.stopped == "invalid_action"
    assert len(steps.seen) == 1 and len(steps.replies) == 1


@pytest.mark.parametrize(
    "reply",
    [
        act("open_link", number=2),
        act("go_to", url="https://evil.test/"),
        act("go_to", url="http://example.com/x"),
    ],
)
def test_a_refused_navigation_ends_the_call_and_opens_nothing(reply: AIMessage) -> None:
    pages = Pages()
    steps = Steps(act("scroll", notes="so far"), reply, act("finish", summary="never asked"))
    outcome = run(steps, pages)
    assert outcome.stopped == "refused_action"
    assert pages.opened == ["https://example.com/"]
    assert outcome.summary == "so far" and outcome.steps == 2 and len(steps.replies) == 1


def test_step_and_time_limits_stop_the_call() -> None:
    steps = Steps(*[act("scroll") for _ in range(5)])
    assert run(steps, max_steps=2).stopped == "max_steps"
    assert len(steps.seen) == 2
    ticks = iter([0.0, 0.0, 5.0, 11.0])
    timed = Steps(*[act("scroll") for _ in range(5)])
    outcome = run(timed, max_seconds=10, clock=lambda: next(ticks))
    assert (outcome.stopped, outcome.steps) == ("max_seconds", 2)


def test_visited_urls_drop_query_and_fragment() -> None:
    assert bare("https://a.example/p?q=1#f") == "https://a.example/p"


def test_every_action_is_a_strict_tool_and_nothing_writes() -> None:
    names = {tool["function"]["name"] for tool in ACTION_TOOLS}
    assert names == {"open_link", "go_to", "scroll", "finish"}
    assert all(
        tool["function"]["parameters"]["additionalProperties"] is False for tool in ACTION_TOOLS
    )
    assert action_of(act("finish", summary="x")) is not None


class Delegate:
    """Stands in for the attempt model, recording what reached it."""

    def __init__(self) -> None:
        self.bound: list[Any] = []
        self.calls = 0

    def bind_tools(self, tools: Any, **options: Any) -> "Delegate":
        self.bound.append((tools, options))
        return self

    async def ainvoke(self, messages: Any, stop: Any = None, **_: Any) -> AIMessage:
        self.calls += 1
        return act("finish", summary="ok")


class Middleware:
    def __init__(self, complete: bool = True) -> None:
        self.routes: list[Any] = []
        self.requests: list[Any] = []
        self.complete = complete

    async def admitted(self, request: Any, handler: Callable[[Any], Any], route: Any) -> Any:
        self.routes.append(route)
        self.requests.append(request)
        with admitted_scope():
            return await handler(request), self.complete


def test_a_step_goes_through_admission_on_the_given_route_with_tools_required() -> None:
    delegate, middleware = Delegate(), Middleware()
    step = admitted_steps(middleware, delegate, "researcher-route")  # type: ignore[arg-type]
    message = asyncio.run(step([]))
    assert message.tool_calls[0]["name"] == "finish"
    assert middleware.routes == ["researcher-route"]
    assert delegate.bound[0][1] == {"tool_choice": "any"}
    assert list(middleware.requests[0].tools) == ACTION_TOOLS


def test_an_unadmitted_call_never_reaches_the_model() -> None:
    delegate = Delegate()

    async def outside() -> str:
        # No traceback is kept, so no model outlives this test (see test_environment).
        model = AdmittedModel(delegate=delegate).bind_tools(ACTION_TOOLS, tool_choice="any")
        try:
            await model.ainvoke([])
        except UnadmittedModelCall:
            return "unadmitted"
        return "answered"

    assert asyncio.run(outside()) == "unadmitted"
    assert delegate.calls == 0
    gc.collect()


def test_a_cut_off_reply_stops_the_loop() -> None:
    async def cut_off() -> str:
        step = admitted_steps(Middleware(complete=False), Delegate(), "route")  # type: ignore[arg-type]
        try:
            await step([])
        except LoopStopped as stopped:
            return stopped.code
        return "continued"

    assert asyncio.run(cut_off()) == "incomplete_output"
    gc.collect()


class FakeCdp:
    """Answers the DevTools commands the page sends, recording them."""

    def __init__(self, text: str) -> None:
        self.sent: list[tuple[str, Any, Any]] = []
        self.text = text

    async def send(self, method: str, params: Any = None, session: Any = None) -> Any:
        self.sent.append((method, params, session))
        if method == "Target.getTargets":
            return {"result": {"targetInfos": [{"type": "page", "targetId": "t1"}]}}
        if method == "Target.attachToTarget":
            return {"result": {"sessionId": "s1"}}
        if method == "Runtime.evaluate":
            links = [{"text": "More", "url": "https://www.iana.org/"}, "junk"]
            value = {"url": "https://example.com/", "title": "Example", "text": self.text}
            return {"result": {"result": {"value": {**value, "links": links}}}}
        return {"result": {}}


def test_the_cdp_page_reads_text_and_links_and_scrolls_its_window() -> None:
    from autobots.adapters.browser_page import READER, CdpPage
    from autobots.application.browsing_loop import TEXT_CHARS

    cdp = FakeCdp("a" * TEXT_CHARS + "b" * 10)

    async def scenario() -> tuple[PageView, PageView]:
        page = await CdpPage.open(cdp, settle=0)  # type: ignore[arg-type]
        await page.go("https://example.com/")
        first = await page.view()
        await page.scroll()
        return first, await page.view()

    first, scrolled = asyncio.run(scenario())
    assert first.title == "Example" and first.links == (
        Link(text="More", url="https://www.iana.org/"),
    )
    assert set(first.text) == {"a"} and scrolled.text.endswith("b" * 10)
    methods = [method for method, _, _ in cdp.sent]
    assert methods == [
        "Target.getTargets",
        "Target.attachToTarget",
        "Page.navigate",
        "Runtime.evaluate",
        "Runtime.evaluate",
    ]
    # The only script is the fixed reader: nothing the model wrote is evaluated.
    assert all(
        params["expression"] == READER
        for method, params, _ in cdp.sent
        if method == "Runtime.evaluate"
    )


@pytest.mark.parametrize("name", ["type_text", "submit_form", "fill", "sign_in", "download"])
def test_a_typing_or_submission_attempt_is_a_refused_action(name: str) -> None:
    steps = Steps(
        act("scroll", notes="read so far"), act(name, text="x"), act("finish", summary="no")
    )
    outcome = run(steps)
    assert (outcome.stopped, outcome.summary, len(steps.seen)) == (
        "refused_action",
        "read so far",
        2,
    )


def test_a_navigation_the_browser_refuses_ends_the_call() -> None:
    from autobots.application.browsing_loop import NavigationRefused

    class Refusing(Pages):
        async def go(self, url: str) -> None:
            if "iana" in url:
                raise NavigationRefused("navigation_refused")
            await super().go(url)

    steps = Steps(act("open_link", number=1), act("finish", summary="no"))
    outcome = run(steps, Refusing())
    assert (outcome.stopped, outcome.visited, len(steps.seen)) == (
        "refused_action",
        ("https://example.com/",),
        1,
    )
