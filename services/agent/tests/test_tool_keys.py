"""US-14.17 offline: the Tavily and Jina keys' order, availability view and per-attempt use."""

import asyncio
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import pytest

from autobots.adapters.tavily import tavily_tools
from autobots.application.provider_settings import InvalidKey
from autobots.application.tool_catalog import tool_catalog
from autobots.application.tool_gateway import ToolContext, ToolFailed, ToolScope
from autobots.application.tool_key_settings import ToolKeySettings
from autobots.application.tool_keys import (
    ToolKeyMissing,
    environment_key,
    key_sources,
    resolve_tool_key,
)
from autobots.contracts.web_tools import TavilySearchInput
from autobots.domain.tool_catalog import KeyRequirement

TAVILY = KeyRequirement("tavily", ("TAVILY_API_KEY",))


def config(tmp_path: Path, files: dict[str, str]) -> dict[str, str]:
    for name, text in files.items():
        (tmp_path / name).write_text(text)
    return {"AUTOBOTS_CONFIG_ROOT": str(tmp_path), "NODE_ENV": "development"}


def test_the_process_environment_wins_over_every_env_file(tmp_path: Path) -> None:
    environ = config(tmp_path, {".env": "TAVILY_API_KEY=tvly-fixtureLowest01"})
    assert environment_key(
        "TAVILY_API_KEY", {**environ, "TAVILY_API_KEY": " tvly-fixtureProcess1 "}
    ) == ("tvly-fixtureProcess1")


@pytest.mark.parametrize(
    ("files", "expected"),
    [
        (
            {
                ".env.development.local": "TAVILY_API_KEY=tvly-fixtureModeLocal",
                ".env.local": "TAVILY_API_KEY=tvly-fixtureLocal001",
                ".env.development": "TAVILY_API_KEY=tvly-fixtureMode0001",
                ".env": "TAVILY_API_KEY=tvly-fixtureLowest01",
            },
            "tvly-fixtureModeLocal",
        ),
        (
            {
                ".env.development.local": "TAVILY_API_KEY=   ",
                ".env.local": "TAVILY_API_KEY=",
                ".env": "TAVILY_API_KEY=tvly-fixtureLowest01",
            },
            "tvly-fixtureLowest01",
        ),
        ({".env": "OTHER=1"}, None),
    ],
)
def test_env_files_follow_mp03_order_and_blank_values_are_skipped(
    tmp_path: Path, files: dict[str, str], expected: str | None
) -> None:
    environ = config(tmp_path, files)
    assert environment_key("TAVILY_API_KEY", {**environ, "TAVILY_API_KEY": "  "}) == expected


def test_a_relative_configuration_root_is_never_read(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("TAVILY_API_KEY=tvly-fixtureLowest01")
    assert environment_key("TAVILY_API_KEY", {"AUTOBOTS_CONFIG_ROOT": "relative"}) is None


def test_without_a_database_or_any_value_the_key_is_missing() -> None:
    async def resolve() -> str:
        return await resolve_tool_key(None, uuid4(), TAVILY, {})

    with pytest.raises(ToolKeyMissing) as raised:
        asyncio.run(resolve())
    assert raised.value.code == "tavily_key_missing"


class Cursor:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self.rows = rows

    async def fetchall(self) -> list[tuple[Any, ...]]:
        return self.rows


class Saved:
    """A connection whose workspace saved a Tavily key, and nothing else."""

    async def execute(self, query: str, params: Any = None) -> Cursor:
        if "tool_key_settings" in query:
            return Cursor([])
        assert "provider_credentials" in query
        return Cursor([("tavily",)])


def test_the_availability_view_names_sources_and_never_holds_a_value(tmp_path: Path) -> None:
    environ = {
        **config(tmp_path, {".env": "JINA_API_KEY=jina_fixtureDotenv001"}),
        "TAVILY_API_KEY": "tvly-fixtureProcess1",
    }
    view = asyncio.run(key_sources(Saved(), uuid4(), environ))
    assert view.sources == {"TAVILY_API_KEY": "settings", "JINA_API_KEY": "environment"}
    assert "fixture" not in json.dumps(dict(view)).replace("autobots-config", "")
    tools = {tool.tool_id: tool for tool in tool_catalog(view).tools}
    for tool_id, source in (("tavily_search", "settings"), ("search_web", "environment")):
        requirement = tools[tool_id].key_requirement
        assert tools[tool_id].availability == "available"
        assert requirement is not None and requirement.source == source


def test_a_missing_key_has_no_source_in_the_catalog() -> None:
    tools = {tool.tool_id: tool for tool in tool_catalog({}).tools}
    requirement = tools["tavily_search"].key_requirement
    assert tools["tavily_search"].availability == "key_missing"
    assert requirement is not None and requirement.source is None


def call(environ: dict[str, str]) -> tuple[list[str], str | None]:
    seen: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers["Authorization"])
        return httpx.Response(200, json={"results": []})

    async def resolve(host: str, _: int) -> list[str]:
        return ["93.184.215.14"]

    search = next(
        tool
        for tool in tavily_tools(httpx.MockTransport(handle), environ=environ, resolver=resolve)
        if tool.tool_id == "tavily_search"
    )
    scope = ToolScope(uuid4(), uuid4(), 1, {"tavily_search": 1})

    async def go() -> str | None:
        try:
            await search.handler(TavilySearchInput(query="colones"), ToolContext(None, scope, None))
        except ToolFailed as failed:
            return str(failed)
        return None

    return seen, asyncio.run(go())


def test_the_adapter_resolves_inside_the_attempt_and_sends_the_key_only_as_its_header(
    tmp_path: Path,
) -> None:
    environ = config(tmp_path, {".env": "TAVILY_API_KEY=tvly-fixtureDotenv001"})
    assert call(environ) == (["Bearer tvly-fixtureDotenv001"], None)
    (tmp_path / ".env").write_text("TAVILY_API_KEY=tvly-fixtureRotated01")
    assert call(environ) == (["Bearer tvly-fixtureRotated01"], None)
    assert call({}) == ([], "tavily_key_missing")


class Untouched:
    async def execute(self, *_: Any) -> None:
        raise AssertionError("a malformed key must be refused before the database")


@pytest.mark.parametrize("draft", ["short", "has a space", "tvly-ünicode-key"])
def test_a_malformed_key_is_refused_by_shape_alone(draft: str) -> None:
    settings = ToolKeySettings(Untouched(), Path("/nonexistent/master.key"), {})
    with pytest.raises(InvalidKey):
        asyncio.run(settings.save(uuid4(), "tavily", draft, 0))


class Transaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *_: Any) -> None:
        return None


class Recorded:
    """Accepts the save's SQL and keeps it, so a test can see what was written."""

    def __init__(self) -> None:
        self.writes: list[tuple[str, Any]] = []

    def transaction(self) -> Transaction:
        return Transaction()

    async def execute(self, query: str, params: Any = None) -> Any:
        self.writes.append((query, params))

        class Row:
            async def fetchone(self) -> tuple[int, ...] | None:
                return (
                    (0,) if "select version from app_private.tool_key_settings" in query else None
                )

        return Row()


def test_saving_seals_the_key_and_opens_no_connection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import socket

    def refuse(*_: Any, **__: Any) -> None:
        raise AssertionError("saving a key must make no network request")

    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(httpx.AsyncClient, "send", refuse)
    connection = Recorded()
    settings = ToolKeySettings(connection, tmp_path / "secrets/master.key", {})
    asyncio.run(settings.save(uuid4(), "tavily", "tvly-fixtureSealed0001", 0))
    inserted = [
        params
        for query, params in connection.writes
        if "insert into" in query and "provider_credentials" in query
    ]
    assert len(inserted) == 1 and inserted[0][3] == "tavily"
    assert all("tvly-fixtureSealed0001" not in repr(params) for _, params in connection.writes)


class Approvals:
    """A receipt table and an approval table, as `_target_unchanged` reads them."""

    def __init__(self, receipt: str | None, recorded: str | None) -> None:
        self.receipt, self.recorded = receipt, recorded

    async def execute(self, query: str, params: Any = None) -> Any:
        row = (
            (self.receipt,)
            if "tool_receipts" in query and self.receipt
            else ((self.recorded,) if "approval_requests" in query else None)
        )

        class One:
            async def fetchone(self) -> Any:
                return row

        return One()


@pytest.mark.parametrize(
    ("receipt", "recorded", "now", "runs"),
    [
        (None, "GitHub repository owner/a", "GitHub repository owner/a", True),
        (None, "GitHub repository owner/a", "GitHub repository owner/b", False),
        (None, None, "GitHub repository owner/a", False),
        (None, "", "GitHub repository owner/a", False),
        ("failed", "GitHub repository owner/a", "GitHub repository owner/b", False),
        ("succeeded", "GitHub repository owner/a", "GitHub repository owner/b", True),
    ],
)
def test_an_approved_write_runs_only_against_its_recorded_target(
    receipt: str | None, recorded: str | None, now: str, runs: bool
) -> None:
    """Decision 0025 V7 and V8. An empty recorded target fails closed. One already sent is left
    to its receipt, and its readback uses the recorded repository."""
    from autobots.application.tool_gateway import _target_unchanged

    assert asyncio.run(_target_unchanged(Approvals(receipt, recorded), "op", now)) is runs


def test_a_write_uses_the_repository_its_approval_recorded() -> None:
    from autobots.adapters.github_issues import attempt_target

    class Recorded(Approvals):
        async def execute(self, query: str, params: Any = None) -> Any:
            if "tool_key_settings" in query or "provider_credentials" in query:

                class Nothing:
                    async def fetchone(self) -> None:
                        return None

                return Nothing()
            return await super().execute(query, params)

    scope = ToolScope(uuid4(), uuid4(), 1, {"create_github_issue": 1})
    context = ToolContext(Recorded(None, "GitHub repository owner/approved"), scope, "op")
    environ = {"GITHUB_REPOSITORY": "owner/now", "GITHUB_TOKEN": "github_pat_fixture0001"}
    assert asyncio.run(attempt_target(context, environ)) == (
        "owner/approved",
        "github_pat_fixture0001",
    )


@pytest.mark.parametrize(
    ("name", "value", "accepted"),
    [
        ("github_repository", "owner/name", True),
        ("github_repository", " owner/name ", True),
        ("github_repository", "owner", False),
        ("github_repository", "../owner/name", False),
        ("github_repository", "https://github.com/owner/name", False),
        ("browser_executor", "enabled", True),
        ("browser_executor", "disabled", True),
        ("browser_executor", "Enabled", False),
        ("browser_executor", "true", False),
        ("github_token", "github_pat_fixture0001", True),
        ("github_token", "short", False),
    ],
)
def test_each_item_has_its_own_check(name: str, value: str, accepted: bool) -> None:
    from autobots.application.tool_key_settings import checked
    from autobots.application.tool_keys import ITEMS

    if accepted:
        assert checked(ITEMS[name], value) == value.strip() or ITEMS[name].secret
    else:
        with pytest.raises(InvalidKey):
            checked(ITEMS[name], value)


def test_the_view_holds_values_and_markers_and_a_saved_switch_wins(tmp_path: Path) -> None:
    class Both:
        async def execute(self, query: str, params: Any = None) -> Cursor:
            if "tool_key_settings" in query:
                return Cursor(
                    [("browser_executor", "disabled"), ("github_repository", "owner/saved")]
                )
            return Cursor([("github",)])

    environ = {"AUTOBOTS_BROWSER_EXECUTOR": "enabled", "GITHUB_REPOSITORY": "owner/env"}
    view = asyncio.run(key_sources(Both(), uuid4(), environ))
    assert view["AUTOBOTS_BROWSER_EXECUTOR"] == "disabled"
    assert view["GITHUB_REPOSITORY"] == "owner/saved"
    assert view["GITHUB_TOKEN"] == "<settings>"
    assert view.sources["AUTOBOTS_BROWSER_EXECUTOR"] == "settings"
