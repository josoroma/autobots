"""US-14.12 offline: browse_goal's registration, catalog entry, grants, input limits and handler."""

import asyncio
from typing import Any
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage
from pydantic import ValidationError

from autobots.adapters.browser_page import CdpPage
from autobots.adapters.tool_registry import catalog, catalog_registry
from autobots.application import browsing_tool
from autobots.application.browsing_loop import Link, PageView
from autobots.application.loop_admission import active_middleware
from autobots.application.loop_policy import LoopStopped
from autobots.application.tool_definitions import ToolContext, ToolFailed, ToolRegistry, ToolScope
from autobots.contracts.browsing import BrowseGoalInput

TC_03_PROVIDERS = {"autobots", "tavily", "jina", "yahoo_finance", "world_bank", "github"}
CATALOG = catalog()
ARGS = {
    "task": "What is example.com for?",
    "start_url": "https://example.com/",
    "allowed_domains": ["example.com", "iana.org"],
}


def qualified(state: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(browsing_tool, "executor_ready", lambda *_, **__: state)


def browse_descriptor() -> Any:
    return next(item for item in CATALOG.descriptors({}) if item.tool_id == "browse_goal")


def test_unqualified_it_is_planned_disabled_and_unregistered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    qualified(False, monkeypatch)
    item = browse_descriptor()
    assert (item.availability, item.availability_reason) == (
        "disabled_by_policy",
        "isolated_executor_not_qualified",
    )
    assert (item.provider, item.registered, item.grantable_to) == ("autobots", False, [])
    assert catalog_registry().get("browse_goal", 1) is None
    assert {tool.provider for tool in CATALOG.catalog({}).tools} <= TC_03_PROVIDERS


def test_qualified_it_is_registered_expert_only_metered_and_always_approved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    qualified(True, monkeypatch)
    item = browse_descriptor()
    assert (item.availability, item.registered, item.grantable_to) == (
        "available",
        True,
        ["expert"],
    )
    assert (item.operation_class, item.provider, item.group) == (
        "arbitrary_execution",
        "autobots",
        "browsing",
    )
    assert (item.cost_class, item.approval) == ("metered_provider", "always")
    public = {(field.direction, field.path) for field in item.fields if field.public}
    assert public == {
        ("input", "start_url"),
        ("input", "allowed_domains"),
        ("input", "max_steps"),
        ("output", "stopped"),
        ("output", "steps"),
        ("output", "visited_count"),
    }


def test_the_registry_refuses_arbitrary_execution_whose_executor_isnt_qualified() -> None:
    with pytest.raises(ValueError, match="arbitrary execution"):
        ToolRegistry().register(browsing_tool.browse_tool(None, qualified=lambda: False))
    registry = ToolRegistry()
    registry.register(browsing_tool.browse_tool(None, qualified=lambda: True))
    assert registry.get("browse_goal", 1) is not None


def test_browsing_needs_the_owners_switch_as_well_as_a_report(tmp_path: Any) -> None:
    assert browsing_tool.executor_ready(tmp_path, {"AUTOBOTS_BROWSER_EXECUTOR": "enabled"}) is False
    assert browsing_tool.executor_ready(browsing_tool.REPOSITORY, {}) is False


@pytest.mark.parametrize("state", [False, True])
def test_an_expert_grant_follows_qualification(
    state: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    from autobots.application.experts import ExpertRefused, validate_config
    from autobots.contracts.experts import ExpertConfig

    qualified(state, monkeypatch)
    config = ExpertConfig(tools=["browse_goal"])
    if state:
        validate_config(config, CATALOG, {})
    else:
        with pytest.raises(ExpertRefused, match="expert_tool_unavailable"):
            validate_config(config, CATALOG, {})


@pytest.mark.parametrize(
    "change",
    [
        {"start_url": "https://evil.test/"},
        {"start_url": "http://example.com/"},
        {"start_url": "https://user:pw@example.com/"},
        {"allowed_domains": ["Example.com"]},
        {"allowed_domains": ["example.com", "example.com"]},
        {"allowed_domains": []},
        {"allowed_domains": [f"d{n}.example" for n in range(11)]},
        {"max_steps": 21},
        {"max_seconds": 301},
        {"max_seconds": 9},
        {"task": ""},
        {"password": "x"},
    ],
)
def test_inputs_past_their_ceilings_are_refused(change: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        BrowseGoalInput.model_validate({**ARGS, **change})


def test_a_subdomain_of_an_allowed_domain_is_inside_it() -> None:
    assert browsing_tool.permitted("https://www.iana.org/help", ["iana.org"])
    assert not browsing_tool.permitted("https://notiana.org/", ["iana.org"])
    assert not browsing_tool.permitted("http://www.iana.org/", ["iana.org"])


class Executor:
    def __init__(self) -> None:
        self.started: list[Any] = []
        self.stopped: list[Any] = []

    async def start(self, run_id: str, generation: int, hosts: tuple[str, ...]) -> Any:
        self.started.append((run_id, generation, hosts))

        class Session:
            async def websocket_url(self) -> str:
                return "ws://fake"

        return Session()

    async def sweep(self, alive: Any) -> list[str]:
        self.swept = True
        return []

    async def watch(self, session: Any, alive: Any, seconds: float) -> str:
        await asyncio.sleep(3600)
        return "removed"

    async def stop(self, session: Any) -> None:
        self.stopped.append(session)


class Page:
    def __init__(self) -> None:
        self.at = ""

    async def view(self) -> PageView:
        return PageView(
            url=self.at + "?q=secret",
            title="Example",
            text="x",
            links=(Link(text="More", url="https://www.iana.org/"),),
        )

    async def go(self, url: str) -> None:
        self.at = url

    async def scroll(self) -> None:
        return None


class Delegate:
    def bind_tools(self, tools: Any, **_: Any) -> "Delegate":
        return self


class Middleware:
    def __init__(self, replies: list[Any]) -> None:
        self.replies = replies

    async def admitted(self, request: Any, handler: Any, route: Any) -> Any:
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return type("R", (), {"result": [reply]})(), True


def act(name: str, **args: Any) -> AIMessage:
    return AIMessage(
        content="", tool_calls=[{"name": name, "args": args, "id": "c", "type": "tool_call"}]
    )


def call(replies: list[Any], monkeypatch: pytest.MonkeyPatch) -> tuple[Any, Executor]:
    executor = Executor()

    class Cdp:
        @classmethod
        async def connect(cls, url: str) -> "Cdp":
            return cls()

        async def close(self) -> None:
            return None

    class Guard:
        def __init__(self, cdp: Any) -> None:
            pass

        async def start(self) -> None:
            return None

    async def opened(cdp: Any, settle: float) -> Page:
        return Page()

    monkeypatch.setattr(browsing_tool, "Cdp", Cdp)
    monkeypatch.setattr(browsing_tool, "RequestGuard", Guard)
    monkeypatch.setattr(CdpPage, "open", opened)
    runtime = browsing_tool.BrowsingRuntime(
        executor,  # type: ignore[arg-type]
        Delegate(),
        "route",  # type: ignore[arg-type]
        settle=0,
    )
    tool = browsing_tool.browse_tool(runtime, qualified=lambda: True)
    scope = ToolScope(uuid4(), uuid4(), 3, {"browse_goal": 1})

    async def go() -> Any:
        try:
            with active_middleware(Middleware(replies)):
                return await tool.handler(
                    BrowseGoalInput.model_validate(ARGS), ToolContext(None, scope, None)
                )
        except ToolFailed as failed:
            return str(failed)

    return asyncio.run(go()), executor


def test_a_call_starts_one_session_for_its_domains_and_always_removes_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output, executor = call(
        [act("open_link", number=1), act("finish", summary="IANA reserves it.")], monkeypatch
    )
    assert output.stopped == "done" and output.summary == "IANA reserves it."
    assert output.visited == ["https://example.com/", "https://www.iana.org/"]
    assert (output.visited_count, output.steps, output.model_calls) == (2, 2, 2)
    assert (output.source, output.truncated) == ("third_party", False)
    assert executor.started[0][1:] == (3, ("example.com", "iana.org")) and executor.swept
    assert len(executor.stopped) == 1


def test_a_stop_inside_the_loop_is_reported_and_still_removes_the_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output, executor = call([LoopStopped("budget_exceeded")], monkeypatch)
    assert output == "budget_exceeded" and len(executor.stopped) == 1


def test_no_runtime_or_no_loop_fails_before_any_container() -> None:
    tool = browsing_tool.browse_tool(None, qualified=lambda: True)
    scope = ToolScope(uuid4(), uuid4(), 1, {"browse_goal": 1})

    async def go() -> str:
        try:
            await tool.handler(BrowseGoalInput.model_validate(ARGS), ToolContext(None, scope, None))
        except ToolFailed as failed:
            return str(failed)
        return "ran"

    assert asyncio.run(go()) == "browsing_unavailable"
