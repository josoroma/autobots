"""US-20.1 offline: an Expert's browser and the stealth browser in the box, Decision 0038 Z1 to Z6
and Z13.

The Expert's choice and the bytes it keeps, the session's Docker arguments, which Expert version and
time zone are read, the refusal before any container, either engine on the Expert's browser, the
browser's own user agent, and the stealth browser's own qualification. Nothing here starts a
container, opens a socket or calls a model: the live cases are tests/db/checks/stealth_check.py.
"""

import asyncio
import json
from collections.abc import Awaitable, Callable, Mapping
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from pydantic import ValidationError

from autobots.adapters.browser_cdp import CHALLENGE_HOSTS, RequestGuard
from autobots.adapters.browser_executor import BrowserExecutor, BrowserSession, Stealth
from autobots.adapters.browser_page import CdpPage
from autobots.adapters.browser_qualification import (
    FINGERPRINT_LABEL,
    IMAGES,
    REQUIRED_CASES,
    REQUIRED_STEALTH_CASES,
    STEALTH,
    STEALTH_FINGERPRINTED,
    fingerprint_digest,
    images_fingerprint,
    parse_labels,
    stealth_fingerprint,
    stealth_qualified,
)
from autobots.adapters.browser_use_box import BoxCall
from autobots.application import browsing_tool
from autobots.application.browsing_loop import BrowseOutcome
from autobots.application.browsing_settings import ExpertBrowser, expert_browser
from autobots.application.experts import expert_record, expert_view_config
from autobots.application.loop_admission import active_middleware
from autobots.application.tool_definitions import ToolContext, ToolFailed, ToolScope
from autobots.contracts.browsing import BrowseGoalV2Input
from autobots.contracts.experts import ExpertConfig, ExpertConfigView
from autobots.domain.models import ModelRoute
from autobots.persistence.records import read_expert_config
from sql_fakes import RuledConnection

ROOT = Path(__file__).resolve().parents[3]
ROUTE = ModelRoute("researcher", "openrouter_sol", "openai/gpt-6.1-sol", 1000)
ARGS = {
    "task": "Read the guide",
    "start_url": "https://en.wikivoyage.org/",
    "allowed_domains": ["en.wikivoyage.org"],
}
Reader = Callable[[tuple[str, ...]], Mapping[str, str | None]]


# The Expert's choice (Z1).


def test_an_expert_on_the_box_keeps_the_bytes_it_always_had() -> None:
    plain = ExpertConfig(tools=["browse_goal"])
    named = ExpertConfig.model_validate({"tools": ["browse_goal"], "browser": "box"})
    assert plain == named
    for config in (plain, named):
        assert "browser" not in config.model_dump(mode="json")
        assert "browser" not in expert_record(config).document()
        assert "browser" not in json.loads(expert_record(config).stored())
        assert "browser" not in expert_view_config(expert_record(config)).model_dump(mode="json")
    old = read_expert_config({"purpose": "Saved before", "tools": ["browse_goal"]})
    assert old.browser == "box" and expert_view_config(old).browser == "box"


def test_an_expert_set_to_stealth_stores_and_shows_it() -> None:
    record = expert_record(ExpertConfig(tools=["browse_goal"], browser="stealth"))
    assert record.document()["browser"] == "stealth"
    assert read_expert_config(record.document()).browser == "stealth"
    assert expert_view_config(record) == ExpertConfigView(tools=["browse_goal"], browser="stealth")


@pytest.mark.parametrize("value", ["cloud", "", "STEALTH", None])
def test_no_other_browser_can_be_named(value: object) -> None:
    with pytest.raises(ValidationError):
        ExpertConfig.model_validate({"browser": value})


def test_no_input_of_any_version_names_a_browser() -> None:
    for tool in browsing_tool.browse_tools(None, qualified=lambda: True):
        schema = json.dumps(tool.input_model.model_json_schema())
        assert "browser" not in schema and "stealth" not in schema


def read_browser(browser: str | None, timezone: str) -> ExpertBrowser:
    rows = [{"browser": browser, "timezone": timezone}]
    return asyncio.run(expert_browser(RuledConnection(("v.config ->> 'browser'", rows)), uuid4()))


def test_the_browser_and_time_zone_are_the_runs_expert_versions_and_workspaces() -> None:
    assert read_browser("stealth", "America/Costa_Rica") == ExpertBrowser(
        "stealth", "America/Costa_Rica"
    )
    assert read_browser(None, "UTC") == ExpertBrowser("box", "UTC")
    assert read_browser("else", "").timezone == "UTC"
    for unknown in ("Nowhere/Land", "../../etc/passwd", "America/Costa_Rica\n-e X=1"):
        assert read_browser("stealth", unknown) == ExpertBrowser("stealth", "UTC")
    empty = RuledConnection(("v.config ->> 'browser'", []))
    assert asyncio.run(expert_browser(empty, uuid4())) == ExpertBrowser("box", "UTC")


# The session (Z2 to Z4).


def started(monkeypatch: pytest.MonkeyPatch, stealth: Stealth | None) -> tuple[Any, Any]:
    calls: list[tuple[str, ...]] = []

    async def docker(self: BrowserExecutor, *arguments: str, check: bool = True) -> str:
        calls.append(arguments)
        return "127.0.0.1:5555" if arguments[0] == "port" else ""

    async def ready(self: BrowserExecutor, session: object, seconds: float = 20.0) -> None:
        return None

    monkeypatch.setattr(BrowserExecutor, "_docker", docker)
    monkeypatch.setattr(BrowserExecutor, "_ready", ready)
    environ = {"OPENROUTER_API_KEY": "sk-or-x", "PATH": "/bin", "TZ": "Europe/Paris"}
    session = asyncio.run(
        BrowserExecutor(environ=environ).start("run", 1, ("example.com",), stealth=stealth)
    )
    run = {call[3]: call for call in calls if call[:2] == ("run", "-d")}
    return session, {name.rsplit("-", 1)[1]: call for name, call in run.items()}


def test_a_stealth_session_differs_from_the_boxs_only_in_image_time_zone_and_process_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    box_session, box = started(monkeypatch, None)
    session, stealth = started(monkeypatch, Stealth("America/Costa_Rica"))
    assert (box_session.pids, session.pids) == (256, 512)
    assert stealth["browser"][-1] == STEALTH.tag == "autobots-browser-stealth:local"
    assert box["browser"][-1] == "autobots-browser:local"

    def shape(call: tuple[str, ...], name: str) -> list[str]:
        return [part.replace(name, "NAME") for part in call[:-1]]

    ours = shape(stealth["browser"], session.name)
    index = ours.index("TZ=America/Costa_Rica")
    del ours[index - 1 : index + 1]
    ours[ours.index("512")] = "256"
    assert ours == shape(box["browser"], box_session.name)
    # The sidecar is the box's own, and nothing of the worker's environment crossed.
    cap = stealth["proxy"].index("--pids-limit")
    assert stealth["proxy"][cap + 1] == "256"
    assert not any("sk-or-x" in part or "Europe" in part for part in stealth["browser"])


@pytest.mark.parametrize(("pids", "count", "refused"), [(512, "300", 0), (256, "255", 1)])
def test_a_count_is_held_at_its_own_sessions_cap(
    monkeypatch: pytest.MonkeyPatch, pids: int, count: str, refused: int
) -> None:
    async def run(
        self: BrowserExecutor, *arguments: str, seconds: float = 60.0
    ) -> tuple[int, bytes, bytes]:
        return 0, count.encode() if arguments[0] == "stats" else b"max 0\noom_kill 0\n", b""

    monkeypatch.setattr(BrowserExecutor, "_run", run)
    session = BrowserSession("n", "t", 1, "run", 1, pids)
    assert asyncio.run(BrowserExecutor(environ={}).cap_events(session)) == (0, refused)


# The call (Z1, Z5, Z6).


class Model:
    """An attempt model the fakes never dispatch."""

    def bind_tools(self, tools: object, **_: object) -> "Model":
        return self


class Executor:
    """Records each session's browser, and stands in for the container."""

    def __init__(self) -> None:
        self.started: list[Stealth | None] = []

    async def start(self, *args: object, stealth: Stealth | None = None) -> object:
        self.started.append(stealth)

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
        return None


def browse_call(
    monkeypatch: pytest.MonkeyPatch, *, on: bool, browser: str | None, qualified: bool = True
) -> tuple[str, Executor]:
    """The engine a call ran on, with browser-use qualified, and the executor it used."""
    engine: list[str] = []
    executor = Executor()

    async def in_box(
        box: object, call: BoxCall, *, start: Callable[[None], Awaitable[object]], **_: object
    ) -> BrowseOutcome:
        engine.append("browser_use")
        await start(None)
        return BrowseOutcome("Done.", (), 1, 1, "done")

    async def loop(page: object, step: object, **_: object) -> BrowseOutcome:
        engine.append("loop")
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
        executor,  # type: ignore[arg-type]  # a fake BrowserExecutor
        Model(),
        ROUTE,
        settle=0,
        browser_use=lambda: True,
        stealth=lambda: qualified,
    )
    connection = RuledConnection(
        ("browsing_yolo", [(on,)]),
        ("browse_domains", [{"domains": '["en.wikivoyage.org"]'}]),
        ("v.config ->> 'browser'", [{"browser": browser, "timezone": "America/Costa_Rica"}]),
        ("", []),
    )
    tool = browsing_tool.browse_tool(runtime, qualified=lambda: True, version=2)
    scope = ToolScope(uuid4(), uuid4(), 1, {"browse_goal": 2})

    async def go() -> None:
        with active_middleware(object()):  # type: ignore[arg-type]  # the fakes never admit
            await tool.handler(
                BrowseGoalV2Input.model_validate(ARGS), ToolContext(connection, scope, None)
            )

    try:
        asyncio.run(go())
    except ToolFailed as failed:
        return str(failed), executor
    return engine[0], executor


@pytest.mark.parametrize(
    ("on", "engine", "hosts"),
    [(True, "browser_use", CHALLENGE_HOSTS), (False, "loop", ())],
)
def test_either_engine_drives_the_experts_browser(
    monkeypatch: pytest.MonkeyPatch, on: bool, engine: str, hosts: tuple[str, ...]
) -> None:
    ran, executor = browse_call(monkeypatch, on=on, browser="stealth")
    assert ran == engine and executor.started == [Stealth("America/Costa_Rica", hosts)]
    ran, executor = browse_call(monkeypatch, on=on, browser=None)
    assert ran == engine and executor.started == [None]


@pytest.mark.parametrize("on", [True, False])
def test_a_stealth_call_is_refused_before_any_container_while_it_is_not_qualified(
    monkeypatch: pytest.MonkeyPatch, on: bool
) -> None:
    ran, executor = browse_call(monkeypatch, on=on, browser="stealth", qualified=False)
    assert ran == "stealth_browser_unqualified" and executor.started == []
    # The box's own calls never ask.
    ran, executor = browse_call(monkeypatch, on=on, browser="box", qualified=False)
    assert executor.started == [None]


def shown(on: bool, browser: str | None) -> Mapping[str, Any]:
    connection = RuledConnection(
        ("browsing_yolo", [(on,)]),
        ("v.config ->> 'browser'", [{"browser": browser, "timezone": "UTC"}]),
    )
    tool = browsing_tool.browse_tool(None, qualified=lambda: True, version=3)
    assert tool.public_context is not None
    scope = ToolScope(uuid4(), uuid4(), 1, {"browse_goal": 3})
    return asyncio.run(tool.public_context(ToolContext(connection, scope, None)))  # type: ignore[arg-type]  # an awaitable coroutine


def test_the_tool_row_names_the_stealth_browser_and_only_that_one() -> None:
    assert shown(True, "stealth") == {"typing": "on", "browser": "stealth"}
    assert shown(False, "stealth") == {"browser": "stealth"}
    assert shown(True, None) == {"typing": "on"} and shown(False, "box") == {}


# The browser's own user agent (Z13).

OWN = "Mozilla/5.0 (X11; Linux x86_64) Chrome/158.0.0.0 Safari/537.36"


class Sent:
    """Records the commands a guard sends, and answers what its start reads."""

    def __init__(self) -> None:
        self.commands: list[tuple[str, dict[str, Any] | None, str | None]] = []
        self.handlers: list[Any] = []

    async def send(
        self, method: str, params: dict[str, Any] | None = None, session: str | None = None
    ) -> dict[str, Any]:
        self.commands.append((method, params, session))
        if method == "Browser.getVersion":
            return {"result": {"userAgent": OWN}}
        if method == "Target.getTargets":
            return {"result": {"targetInfos": [{"type": "page", "targetId": "main"}]}}
        if method == "Target.attachToTarget":
            return {"result": {"sessionId": "page"}}
        return {"result": {}}


def paused(
    guard_headers: dict[str, str], frame: str = "main", kind: str = "Document"
) -> tuple[str, RequestGuard]:
    sent = Sent()
    guard = RequestGuard(sent, submits=True)  # type: ignore[arg-type]  # a fake CDP sender
    request = {"method": "GET", "url": "https://example.com/", "headers": guard_headers}
    params = {"requestId": "r", "request": request, "resourceType": kind, "frameId": frame}

    async def go() -> None:
        await guard.start()
        await guard._event({"method": "Fetch.requestPaused", "sessionId": "page", "params": params})

    asyncio.run(go())
    return sent.commands[-1][0], guard


@pytest.mark.parametrize("headers", [{"User-Agent": OWN}, {"user-agent": OWN}, {}])
def test_a_request_under_the_browsers_own_user_agent_goes_on(headers: dict[str, str]) -> None:
    answer, guard = paused(headers)
    assert answer == "Fetch.continueRequest" and guard.refusals() == 0


@pytest.mark.parametrize("name", ["User-Agent", "user-agent"])
def test_a_navigation_under_another_user_agent_is_refused_and_ends_the_call(name: str) -> None:
    answer, guard = paused({name: "Mozilla/5.0 Fake/1"})
    assert answer == "Fetch.failRequest" and guard.refusals() == 1


@pytest.mark.parametrize(("frame", "kind"), [("child", "Document"), ("main", "XHR")])
def test_a_pages_own_request_under_one_is_refused_without_ending_the_call(
    frame: str, kind: str
) -> None:
    answer, guard = paused({"User-Agent": "Fake/1"}, frame=frame, kind=kind)
    assert answer == "Fetch.failRequest" and guard.refusals() == 0 and len(guard.refused) == 1


# Qualified apart (Z6).


def passing(path: Path, cases: tuple[str, ...], key: str, fingerprint: Mapping[str, str]) -> Path:
    path.write_text(
        json.dumps(
            {
                "status": "passed",
                "cases": [{"id": case, "status": "passed"} for case in cases],
                key: dict(fingerprint),
            }
        )
    )
    return path


def labels(executor: str, own: str | None) -> Reader:
    def read(tags: tuple[str, ...]) -> Mapping[str, str | None]:
        lines = [
            json.dumps({FINGERPRINT_LABEL: own if tag == STEALTH.tag else executor}) for tag in tags
        ]
        return parse_labels("\n".join(lines), tags)

    return read


def test_the_stealth_browser_is_qualified_only_on_top_of_the_executor_and_its_own_check(
    tmp_path: Path,
) -> None:
    base, own = images_fingerprint(ROOT), stealth_fingerprint(ROOT)
    executor = passing(tmp_path / "e.json", REQUIRED_CASES, "executor_fingerprint", base)
    report = passing(tmp_path / "s.json", REQUIRED_STEALTH_CASES, "stealth_fingerprint", own)
    good = labels(fingerprint_digest(base), fingerprint_digest(own))

    def qualified(read: Reader = good, report: Path = report, executor: Path = executor) -> bool:
        return stealth_qualified(ROOT, report, read, executor_report=executor)

    assert qualified()
    for missing in (REQUIRED_STEALTH_CASES[:-1], REQUIRED_STEALTH_CASES[1:]):
        short = passing(tmp_path / "m.json", missing, "stealth_fingerprint", own)
        assert not qualified(report=short)
    stale = passing(tmp_path / "o.json", REQUIRED_STEALTH_CASES, "stealth_fingerprint", base)
    assert not qualified(report=stale) and not qualified(report=tmp_path / "absent.json")
    for label in (None, "0" * 64, fingerprint_digest(base)):
        assert not qualified(labels(fingerprint_digest(base), label))
    unqualified = passing(tmp_path / "u.json", REQUIRED_CASES[1:], "executor_fingerprint", base)
    assert not qualified(executor=unqualified)


def test_the_stealth_image_is_apart_and_built_only_from_its_fingerprinted_files() -> None:
    assert STEALTH not in IMAGES
    assert set(REQUIRED_CASES) < set(REQUIRED_STEALTH_CASES)
    lines = (ROOT / STEALTH.dockerfile).read_text().splitlines()
    copied = [
        source
        for line in lines
        if line.startswith("COPY ") and "--from=" not in line
        for source in line.split()[1:-1]
    ]
    ignore = (ROOT / STEALTH.ignore_file).read_text().splitlines()
    kept = [line for line in ignore if line and not line.startswith("#")]
    assert sorted(kept) == sorted(["*", *(f"!{source}" for source in copied)])
    inputs = (STEALTH.dockerfile, STEALTH.ignore_file, *(f"{STEALTH.context}/{s}" for s in copied))
    assert set(inputs) <= set(STEALTH_FINGERPRINTED)
    assert len(set(STEALTH_FINGERPRINTED)) == len(STEALTH_FINGERPRINTED)
