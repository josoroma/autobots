"""The live key helper's commands on a fake OpenRouter, a fake database and a fake settings
store. No network and no database (refactor plan R-23, TDBC-11). The save itself, OpenRouter's
key check included, is ProviderSettings.save_credential, which these tests don't repeat.
"""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from pydantic import SecretStr

from autobots.application.readiness import MalformedSetting
from autobots.operations import live_key

KEY = "sk-or-arranged-not-a-real-key"


def key_file(tmp_path: Path) -> Path:
    path = tmp_path / "keys.env"
    path.write_text(f"OTHER=keep-out\nOPENROUTER_API_KEY={KEY}\n")
    return path


def openrouter(seen: list[httpx.Request], status: int = 200) -> httpx.AsyncClient:
    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(status, json={"data": {"usage": 1.25, "label": "kept out"}})

    return httpx.AsyncClient(transport=httpx.MockTransport(handle))


class Cursor:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self.rows = rows

    async def fetchall(self) -> list[tuple[Any, ...]]:
        return self.rows


class Database:
    """Answers each query with the rows of the first fragment it contains, and no rows otherwise."""

    def __init__(self, rows: dict[str, list[tuple[Any, ...]]]) -> None:
        self.rows = rows
        self.queries: list[str] = []

    async def execute(self, query: str) -> Cursor:
        self.queries.append(query)
        return Cursor(next((rows for fragment, rows in self.rows.items() if fragment in query), []))


class Status:
    settings_version = 7


class Settings:
    def __init__(self) -> None:
        self.saved: list[tuple[UUID, str, int]] = []

    async def status(self, workspace_id: UUID) -> Status:
        return Status()

    async def save_credential(self, workspace_id: UUID, draft: str, expected: int) -> None:
        self.saved.append((workspace_id, draft, expected))


@pytest.mark.asyncio
async def test_usage_sends_the_key_only_as_a_bearer_and_returns_the_dollar_figure() -> None:
    seen: list[httpx.Request] = []
    async with openrouter(seen) as client:
        assert await live_key.key_usage(SecretStr(KEY), client) == 1.25
    [request] = seen
    assert str(request.url) == live_key.USAGE_URL
    assert request.method == "GET"
    assert request.headers["Authorization"] == f"Bearer {KEY}"
    assert request.content == b""


@pytest.mark.asyncio
async def test_usage_refuses_an_error_reply() -> None:
    async with openrouter([], status=401) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await live_key.key_usage(SecretStr(KEY), client)


@pytest.mark.asyncio
async def test_rows_holding_the_key_are_counted_in_every_durable_text() -> None:
    database = Database(
        {
            "checkpoint_blobs": [(f"x{KEY}x".encode(),), (b"clean",)],
            "run_events": [(json.dumps({"text": KEY}),), (None,)],
            "model_invocations": [(memoryview(KEY.encode()),)],
        }
    )
    assert await live_key.durable_rows_holding(KEY, database) == 3
    assert database.queries == list(live_key.DURABLE_TEXT)


def test_log_files_are_counted_once_each_and_only_logs(tmp_path: Path) -> None:
    (tmp_path / "worker.log").write_text(f"{KEY} and again {KEY}\n")
    (tmp_path / "api.log").write_text("clean\n")
    (tmp_path / "notes.txt").write_text(KEY)
    assert live_key.log_files_holding(KEY, tmp_path) == 1


def test_the_context_needs_where_the_install_keeps_its_keys() -> None:
    """Both are settings to set, so the key is saved where this install keeps it (exit 2)."""
    with pytest.raises(MalformedSetting) as refused:
        live_key.provider_context({"NODE_ENV": "production"})
    assert str(refused.value) == "set AUTOBOTS_CONFIG_ROOT, AUTOBOTS_PROVIDER_MASTER_KEY_FILE"
    environ = {
        "AUTOBOTS_CONFIG_ROOT": "/install/config",
        "AUTOBOTS_PROVIDER_MASTER_KEY_FILE": "/install/config/secrets/master.key",
        "NODE_ENV": "production",
    }
    context = live_key.provider_context(environ)
    assert (context.config_root, context.mode) == ("/install/config", "production")
    assert context.master_key_file == Path("/install/config/secrets/master.key")
    assert context.process_environment is environ


@pytest.mark.asyncio
async def test_the_key_is_saved_at_the_current_settings_version() -> None:
    settings, workspace = Settings(), uuid4()
    await live_key.save_key(SecretStr(KEY), workspace, settings)
    assert settings.saved == [(workspace, KEY, 7)]


def test_usage_prints_one_number_and_never_the_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(live_key, "http_client", lambda: openrouter([]))
    assert live_key.main(["usage", str(key_file(tmp_path))]) == 0
    printed = capsys.readouterr()
    assert (printed.out, printed.err) == ("1.25\n", "")


def test_leaks_prints_two_counts_and_never_the_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "worker.log").write_text(KEY)
    database = Database({"tool_receipts": [(KEY,)]})
    urls: list[str] = []

    @asynccontextmanager
    async def connection(url: str) -> AsyncIterator[Database]:
        urls.append(url)
        yield database

    monkeypatch.setattr(live_key, "runtime_connection", connection)
    monkeypatch.setenv("AUTOBOTS_DATABASE_URL", "postgresql://runtime@127.0.0.1/postgres")
    assert live_key.main(["leaks", str(key_file(tmp_path)), str(logs)]) == 0
    printed = capsys.readouterr()
    assert (printed.out, printed.err) == ("1 1\n", "")
    assert urls == ["postgresql://runtime@127.0.0.1/postgres"]


def test_a_key_file_without_the_key_refuses_before_any_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    empty = tmp_path / "empty.env"
    empty.write_text("OTHER=keep-out\n")
    monkeypatch.setattr(live_key, "http_client", lambda: pytest.fail("no request"))
    assert live_key.main(["usage", str(empty)]) == 1
    printed = capsys.readouterr()
    assert printed.out == ""
    assert printed.err == "REFUSED: OPENROUTER_API_KEY isn't set in that file\n"


def test_counting_leaks_without_a_database_is_a_setting_to_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("AUTOBOTS_DATABASE_URL", raising=False)
    assert live_key.main(["leaks", str(key_file(tmp_path)), str(tmp_path)]) == 2
    printed = capsys.readouterr()
    assert (printed.out, printed.err) == ("", "ERROR: set AUTOBOTS_DATABASE_URL\n")
    assert KEY not in printed.err
