"""US-14.17 offline: the Keys & vars order, availability view and per-attempt use. One resolver
over every item keeps Decisions 0024 and 0025's order, and a nonblank, unusable higher source never
falls through to a lower one (PTOL-12, model-gateway rule)."""

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import pytest

from autobots.adapters import github_connector, jina, tavily
from autobots.adapters.tavily import tavily_tools
from autobots.adapters.tool_registry import catalog
from autobots.application import tool_keys
from autobots.application.provider_settings import InvalidKey
from autobots.application.sql import SqlParams
from autobots.application.tool_definitions import ToolContext, ToolFailed, ToolScope
from autobots.application.tool_key_settings import ToolKeySettings, checked
from autobots.application.tool_keys import (
    ENVIRONMENT,
    ITEMS,
    NOTHING_SAVED,
    SETTINGS,
    Item,
    Resolved,
    ToolKeyUnavailable,
    attempt_value,
    environment_key,
    key_sources,
    resolve,
)
from autobots.contracts.web_tools import TavilySearchInput
from sql_fakes import ScriptedConnection, ScriptedRows

CATALOG = catalog()


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


@pytest.mark.asyncio
async def test_without_a_database_or_any_value_the_key_is_missing() -> None:
    context = ToolContext(ScriptedConnection(), ToolScope(uuid4(), uuid4(), 1, {}), None)
    with pytest.raises(ToolFailed, match=r"^tavily_key_missing$"):
        await context.key("tavily", {})
    assert await attempt_value(None, uuid4(), ITEMS["tavily"], {}) is None


class Saved(ScriptedConnection):
    """A connection whose workspace saved a Tavily key, and nothing else."""

    async def execute(self, query: str, params: SqlParams | None = None, /) -> ScriptedRows:
        if "tool_key_settings" in query:
            return ScriptedRows([])
        assert "provider_credentials" in query
        return ScriptedRows([("tavily",)])


@pytest.mark.asyncio
async def test_the_availability_view_names_sources_and_never_holds_a_value(tmp_path: Path) -> None:
    environ = {
        **config(tmp_path, {".env": "JINA_API_KEY=jina_fixtureDotenv001"}),
        "TAVILY_API_KEY": "tvly-fixtureProcess1",
    }
    view = await key_sources(Saved(), uuid4(), environ)
    assert view.sources == {"TAVILY_API_KEY": "settings", "JINA_API_KEY": "environment"}
    assert "fixture" not in json.dumps(dict(view)).replace("autobots-config", "")
    tools = {tool.tool_id: tool for tool in CATALOG.catalog(view).tools}
    for tool_id, source in (("tavily_search", "settings"), ("search_web", "environment")):
        requirement = tools[tool_id].key_requirement
        assert tools[tool_id].availability == "available"
        assert requirement is not None and requirement.source == source


def test_a_missing_key_has_no_source_in_the_catalog() -> None:
    tools = {tool.tool_id: tool for tool in CATALOG.catalog({}).tools}
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
            await search.handler(
                TavilySearchInput(query="colones"), ToolContext(ScriptedConnection(), scope, None)
            )
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


class Untouched(ScriptedConnection):
    async def execute(self, query: str, _params: SqlParams | None = None, /) -> ScriptedRows:
        raise AssertionError("a malformed key must be refused before the database")


@pytest.mark.parametrize("draft", ["short", "has a space", "tvly-ünicode-key"])
@pytest.mark.asyncio
async def test_a_malformed_key_is_refused_by_shape_alone(draft: str) -> None:
    settings = ToolKeySettings(Untouched(), Path("/nonexistent/master.key"), {})
    with pytest.raises(InvalidKey):
        await settings.save(uuid4(), "tavily", draft, 0)


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


@pytest.mark.asyncio
async def test_saving_seals_the_key_and_opens_no_connection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import socket

    def refuse(*_: Any, **__: Any) -> None:
        raise AssertionError("saving a key must make no network request")

    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(httpx.AsyncClient, "send", refuse)
    connection = Recorded()
    settings = ToolKeySettings(connection, tmp_path / "secrets/master.key", {})
    await settings.save(uuid4(), "tavily", "tvly-fixtureSealed0001", 0)
    inserted = [
        params
        for query, params in connection.writes
        if "insert into" in query and "provider_credentials" in query
    ]
    assert len(inserted) == 1 and inserted[0][3] == "tavily"
    assert all("tvly-fixtureSealed0001" not in repr(params) for _, params in connection.writes)


class Approvals:
    """A receipt table and an approval table: the receipt's status, as `_target_unchanged` reads
    it, and the approved request's target and review detail."""

    def __init__(self, receipt: str | None, recorded: str | None) -> None:
        self.receipt, self.recorded = receipt, recorded

    async def execute(self, query: str, params: SqlParams | None = None, /) -> ScriptedRows:
        row = (
            (self.receipt,)
            if "tool_receipts" in query and self.receipt
            else ((self.recorded, None) if "approval_requests" in query else None)
        )
        return ScriptedRows([] if row is None else [row])

    @contextlib.asynccontextmanager
    async def transaction(self) -> AsyncIterator[None]:
        yield


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
@pytest.mark.asyncio
async def test_an_approved_write_runs_only_against_its_recorded_target(
    receipt: str | None, recorded: str | None, now: str, runs: bool
) -> None:
    """Decision 0025 V7 and V8. An empty recorded target fails closed. One already sent is left
    to its receipt, and its readback uses the recorded repository."""
    from autobots.application.approvals import ApprovedRequest
    from autobots.application.tool_gateway import _target_unchanged

    approval = ApprovedRequest(recorded, None)
    assert await _target_unchanged(Approvals(receipt, None), "op", approval, now) is runs


@pytest.mark.asyncio
async def test_a_write_uses_the_repository_its_approval_recorded() -> None:
    """The gateway hands the attempt what was approved, and the adapter reads its repository from
    there, never from the database (XMOD-02)."""
    from autobots.adapters.github_connector import attempt_credentials
    from autobots.application.approvals import ApprovedRequest

    class Recorded(Approvals):
        async def execute(self, query: str, params: SqlParams | None = None, /) -> ScriptedRows:
            if "tool_key_settings" in query or "provider_credentials" in query:
                return ScriptedRows()
            return await super().execute(query, params)

    scope = ToolScope(uuid4(), uuid4(), 1, {"create_github_issue": 1})
    approval = ApprovedRequest("GitHub repository owner/approved", None)
    context = ToolContext(Recorded(None, None), scope, "op", approval)
    environ = {"GITHUB_REPOSITORY": "owner/now", "GITHUB_TOKEN": "github_pat_fixture0001"}
    assert await attempt_credentials(context, environ) == (
        "owner/approved",
        "github_pat_fixture0001",
    )


@pytest.mark.parametrize(
    ("name", "value", "saved"),
    [
        ("github_repository", "owner/name", "owner/name"),
        ("github_repository", " owner/name ", "owner/name"),
        ("browser_executor", "enabled", "enabled"),
        ("browser_executor", "disabled", "disabled"),
        # A secret is saved as it was given.
        ("github_token", "github_pat_fixture0001", "github_pat_fixture0001"),
    ],
)
def test_each_item_saves_what_its_check_accepts(name: str, value: str, saved: str) -> None:
    """The exact value saved, for secrets too, where the either-or this replaced passed whatever the
    check returned (PTST-17)."""
    assert checked(ITEMS[name], value) == saved


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("github_repository", "owner"),
        ("github_repository", "../owner/name"),
        ("github_repository", "https://github.com/owner/name"),
        ("browser_executor", "Enabled"),
        ("browser_executor", "true"),
        ("github_token", "short"),
    ],
)
def test_each_item_refuses_what_its_check_refuses(name: str, value: str) -> None:
    with pytest.raises(InvalidKey):
        checked(ITEMS[name], value)


@pytest.mark.asyncio
async def test_the_view_holds_values_and_markers_and_a_saved_switch_wins(tmp_path: Path) -> None:
    class Both(ScriptedConnection):
        async def execute(self, query: str, params: SqlParams | None = None, /) -> ScriptedRows:
            if "tool_key_settings" in query:
                return ScriptedRows(
                    [("browser_executor", "disabled"), ("github_repository", "owner/saved")]
                )
            return ScriptedRows([("github",)])

    environ = {"AUTOBOTS_BROWSER_EXECUTOR": "enabled", "GITHUB_REPOSITORY": "owner/env"}
    view = await key_sources(Both(), uuid4(), environ)
    assert view["AUTOBOTS_BROWSER_EXECUTOR"] == "disabled"
    assert view["GITHUB_REPOSITORY"] == "owner/saved"
    assert view["GITHUB_TOKEN"] == "<settings>"
    assert view.sources["AUTOBOTS_BROWSER_EXECUTOR"] == "settings"


# PTOL-12: one resolver over every item. Each has a usable fixture value, and an unusable one
# that is still nonblank, so the order and the stop are proved for all five.
USABLE = {
    "tavily": "tvly-fixtureUsable01",
    "jina": "jina_fixtureUsable001",
    "serpapi": "serpapi_fixtureUsable01",
    "github_token": "github_pat_fixtureUse1",
    "github_repository": "owner/fixture",
    "browser_executor": "enabled",
}
UNUSABLE = {
    "tavily": "has a space",
    "jina": "short",
    "serpapi": "has a space",
    "github_token": "has a space",
    "github_repository": "https://evil.example/owner/repo",
    "browser_executor": "on",
}
NAMES = sorted(ITEMS)


def test_every_item_has_a_usable_and_an_unusable_fixture() -> None:
    assert set(USABLE) == set(UNUSABLE) == set(ITEMS)
    for name in NAMES:
        assert ITEMS[name].accepts(USABLE[name])
        assert UNUSABLE[name].strip() and not ITEMS[name].accepts(UNUSABLE[name])


def saved_for(item: Item, value: str) -> tool_keys.Saved:
    """A workspace that saved `value` for `item`: a secret's existence, a value's value."""
    if item.secret:
        return tool_keys.Saved(frozenset({item.name}), {})
    return tool_keys.Saved(frozenset(), {item.name: value})


def unsealing(value: str | None) -> tool_keys.Unseal:
    async def unseal(_: Item) -> str | None:
        return value

    return unseal


async def refusing_to_unseal(item: Item) -> str | None:
    raise ToolKeyUnavailable(item.credential or item.name)


def layered(tmp_path: Path, name: str, process: str, dotenv: str) -> dict[str, str]:
    """The process environment holds `process`, and the lowest `.env` file `dotenv`."""
    variable = ITEMS[name].variable
    return {**config(tmp_path, {".env": f"{variable}={dotenv}"}), variable: process}


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.asyncio
async def test_settings_win_then_the_process_environment_then_env_files(
    tmp_path: Path, name: str
) -> None:
    item = ITEMS[name]
    environ = layered(tmp_path, name, "process-value-1", "dotenv-value-01")
    in_settings = await resolve(
        item, saved_for(item, USABLE[name]), environ, unsealing(USABLE[name])
    )
    assert in_settings == Resolved(SETTINGS, USABLE[name])
    from_process = await resolve(item, NOTHING_SAVED, environ, unsealing(None))
    assert from_process == Resolved(ENVIRONMENT, "process-value-1")
    blank_process = {**environ, item.variable: "   "}
    from_file = await resolve(item, NOTHING_SAVED, blank_process, unsealing(None))
    assert from_file == Resolved(ENVIRONMENT, "dotenv-value-01")
    assert await resolve(item, NOTHING_SAVED, {}, unsealing(None)) == Resolved(None, None)


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.asyncio
async def test_a_nonblank_unusable_process_value_stops_resolution(
    tmp_path: Path, name: str
) -> None:
    """The model-gateway rule: the `.env` file's usable value is never reached."""
    item = ITEMS[name]
    environ = layered(tmp_path, name, UNUSABLE[name], USABLE[name])
    found = await resolve(item, NOTHING_SAVED, environ, unsealing(None))
    assert found == Resolved(ENVIRONMENT, UNUSABLE[name])


@pytest.mark.parametrize("name", [name for name in NAMES if not ITEMS[name].secret])
@pytest.mark.asyncio
async def test_an_attempt_treats_an_unusable_value_as_not_configured(
    tmp_path: Path, name: str
) -> None:
    item = ITEMS[name]
    environ = layered(tmp_path, name, UNUSABLE[name], USABLE[name])
    context = ToolContext(ScriptedConnection(), ToolScope(uuid4(), uuid4(), 1, {}), None)
    resolved = await context.setting(name, environ)
    assert resolved == UNUSABLE[name] and item.usable(resolved) is None


@pytest.mark.parametrize("name", [name for name in NAMES if ITEMS[name].secret])
@pytest.mark.asyncio
async def test_an_attempt_sends_the_unusable_process_key_never_the_env_files(
    tmp_path: Path, name: str
) -> None:
    """A secret goes to the client as it resolved, and its provider refuses it: the `.env` file's
    usable key is never sent in its place."""
    environ = layered(tmp_path, name, UNUSABLE[name], USABLE[name])
    context = ToolContext(ScriptedConnection(), ToolScope(uuid4(), uuid4(), 1, {}), None)
    assert await context.key(name, environ) == UNUSABLE[name]


def test_the_tavily_client_receives_the_process_key_over_the_env_files(tmp_path: Path) -> None:
    environ = layered(tmp_path, "tavily", UNUSABLE["tavily"], USABLE["tavily"])
    assert call(environ) == ([f"Bearer {UNUSABLE['tavily']}"], None)


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.asyncio
async def test_an_unusable_saved_item_never_falls_through_to_the_environment(
    tmp_path: Path, name: str
) -> None:
    """A saved secret that can't be unsealed refuses; a saved value without its form is returned
    as it is, so the environment's usable value is never used (Decisions 0024 and 0025)."""
    item = ITEMS[name]
    environ = layered(tmp_path, name, USABLE[name], USABLE[name])
    saved = saved_for(item, UNUSABLE[name])
    if item.secret:
        with pytest.raises(ToolKeyUnavailable):
            await resolve(item, saved, environ, refusing_to_unseal)
    else:
        found = await resolve(item, saved, environ, unsealing(None))
        assert found == Resolved(SETTINGS, UNUSABLE[name])
        assert item.usable(found.value) is None


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.asyncio
async def test_availability_names_a_source_and_never_unseals_or_reads_a_secret(
    tmp_path: Path, name: str
) -> None:
    item = ITEMS[name]
    environ = layered(tmp_path, name, USABLE[name], USABLE[name])
    saved = await resolve(item, saved_for(item, USABLE[name]), environ)
    assert saved == Resolved(SETTINGS, None if item.secret else USABLE[name])
    environment = await resolve(item, NOTHING_SAVED, environ)
    assert environment == Resolved(ENVIRONMENT, None if item.secret else USABLE[name])


@pytest.mark.asyncio
async def test_the_workspace_view_never_unseals(monkeypatch: pytest.MonkeyPatch) -> None:
    async def forbidden(*_: object) -> str | None:
        raise AssertionError("availability never unseals a secret")

    monkeypatch.setattr(tool_keys, "_saved_secret", forbidden)

    class Everything(ScriptedConnection):
        async def execute(self, query: str, params: SqlParams | None = None, /) -> ScriptedRows:
            if "tool_key_settings" in query:
                return ScriptedRows([("github_repository", "owner/saved")])
            return ScriptedRows([("tavily",), ("jina",), ("serpapi",), ("github",)])

    view = await key_sources(Everything(), uuid4(), {})
    secrets = [item.variable for item in ITEMS.values() if item.secret]
    assert all(view[variable] == "<settings>" for variable in secrets)


@pytest.mark.parametrize("name", [name for name in NAMES if ITEMS[name].secret])
@pytest.mark.asyncio
async def test_a_call_with_an_unsealable_saved_key_is_refused_despite_the_environment(
    monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """Through the tool's context, as an adapter asks: the environment's key is never sent."""
    item = ITEMS[name]

    async def unavailable(*_: object) -> str | None:
        raise ToolKeyUnavailable(item.credential or name)

    monkeypatch.setattr(tool_keys, "_saved_secret", unavailable)

    class SavedKey(ScriptedConnection):
        async def execute(self, query: str, params: SqlParams | None = None, /) -> ScriptedRows:
            if "tool_key_settings" in query:
                return ScriptedRows()
            return ScriptedRows([(item.credential,)])

    context = ToolContext(SavedKey(), ToolScope(uuid4(), uuid4(), 1, {}), "op")
    environ = {item.variable: USABLE[name]}
    with pytest.raises(ToolFailed, match=rf"^{item.credential}_key_unavailable$"):
        await context.key(name, environ)


def test_the_adapters_requirements_name_the_items_variables() -> None:
    """Availability and the call read the same variables (PTOL-12)."""
    assert tavily.TAVILY_KEY.variables == (ITEMS["tavily"].variable,)
    assert jina.JINA_KEY.variables == (ITEMS["jina"].variable,)
    assert github_connector.GITHUB_KEY.variables == (
        ITEMS["github_repository"].variable,
        ITEMS["github_token"].variable,
    )
    assert (
        tavily.TAVILY_KEY.credential,
        jina.JINA_KEY.credential,
        github_connector.GITHUB_KEY.credential,
    ) == ("tavily", "jina", "github")
