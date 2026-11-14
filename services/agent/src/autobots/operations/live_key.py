"""The real OpenRouter key's three uses in a paid entry point, each in a process of its own, so
the script that runs it never holds the key (refactor plan R-23, TDBC-11).

`python -m autobots.operations.live_key usage <key file>` prints the key's whole spend as
OpenRouter reports it, in US dollars. `save <key file> <workspace>` saves it into the workspace
through the product's own path, OpenRouter's key check included. `leaks <key file> <logs>` prints
how many durable rows and how many log files hold it. Only OPENROUTER_API_KEY is read from the
file, and only numbers or counts are printed. The key check and the usage read are OpenRouter's
free metadata calls, not inference. scripts/paid_run.py runs it for persistent_install.py,
live_goal.py and qualify_release.py.
"""

import argparse
import asyncio
import os
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Protocol
from uuid import UUID

import httpx
import psycopg
from pydantic import SecretStr

from autobots.adapters.models.openrouter_metadata import catalog_fetcher, key_validator
from autobots.application.provider_settings import ProviderContext, ProviderSettings
from autobots.operations.route_qualification import read_key

USAGE_URL = "https://openrouter.ai/api/v1/key"
USAGE_SECONDS = 30.0
CONFIG_ROOT = "AUTOBOTS_CONFIG_ROOT"
MASTER_KEY_FILE = "AUTOBOTS_PROVIDER_MASTER_KEY_FILE"
DATABASE_URL = "AUTOBOTS_DATABASE_URL"
# Every durable text a run writes that could carry the key back out.
DURABLE_TEXT = (
    "select blob from agent_runtime.checkpoint_blobs",
    "select blob from agent_runtime.checkpoint_writes",
    "select payload::text from public.run_events",
    "select result::text from app_private.tool_receipts",
    "select content from app_private.run_files",
    "select accumulated_output from app_private.model_invocations",
)


class ProviderContextIncomplete(Exception):
    """The environment doesn't say where this install keeps provider keys, so nothing is saved."""


class Rows(Protocol):
    async def fetchall(self) -> list[tuple[Any, ...]]: ...


class Database(Protocol):
    """The part of a runtime-role connection the leak count reads through."""

    async def execute(self, query: str) -> Rows: ...


class SettingsVersion(Protocol):
    @property
    def settings_version(self) -> int: ...


class KeySaver(Protocol):
    """The part of ProviderSettings that saves a credential."""

    async def status(self, workspace_id: UUID) -> SettingsVersion: ...

    async def save_credential(self, workspace_id: UUID, draft: str, expected: int) -> None: ...


def provider_context(environ: Mapping[str, str]) -> ProviderContext:
    """The context the API builds (api.main.provider_context_from_environment), with no default
    master key file: every paid entry point names both, and operations doesn't import api
    (tests/test_layers.py)."""
    missing = [name for name in (CONFIG_ROOT, MASTER_KEY_FILE) if not environ.get(name)]
    if missing:
        raise ProviderContextIncomplete(
            f"{' and '.join(missing)} must be set, so the key is saved where this install keeps it"
        )
    return ProviderContext(
        config_root=environ[CONFIG_ROOT],
        mode=environ.get("NODE_ENV", "development"),
        master_key_file=Path(environ[MASTER_KEY_FILE]),
        process_environment=dict(environ),
        validate_key=key_validator(),
        fetch_catalog=catalog_fetcher(),
    )


async def key_usage(key: SecretStr, client: httpx.AsyncClient) -> float:
    """The key's whole spend as OpenRouter reports it, in US dollars."""
    reply = await client.get(
        USAGE_URL, headers={"Authorization": f"Bearer {key.get_secret_value()}"}
    )
    reply.raise_for_status()
    return float(reply.json()["data"]["usage"])


async def save_key(key: SecretStr, workspace: UUID, settings: KeySaver) -> None:
    """At the workspace's current settings version, as the settings page saves it."""
    status = await settings.status(workspace)
    await settings.save_credential(workspace, key.get_secret_value(), status.settings_version)


def holds(secret: str, value: object) -> bool:
    if isinstance(value, bytes | memoryview):
        return secret in bytes(value).decode(errors="replace")
    return value is not None and secret in str(value)


async def durable_rows_holding(secret: str, database: Database) -> int:
    """How many durable rows hold the key. A count only, so the key can't reach a report."""
    found = 0
    for query in DURABLE_TEXT:
        cursor = await database.execute(query)
        found += sum(holds(secret, value) for (value,) in await cursor.fetchall())
    return found


def log_files_holding(secret: str, logs: Path) -> int:
    """How many of the run's log files hold the key, each counted once."""
    return sum(secret in path.read_text(errors="replace") for path in logs.glob("*.log"))


def http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=USAGE_SECONDS)


@asynccontextmanager
async def runtime_connection(url: str) -> AsyncIterator[Database]:
    async with await psycopg.AsyncConnection.connect(url, autocommit=True) as connection:
        yield connection


async def _usage(key: SecretStr) -> float:
    async with http_client() as client:
        return await key_usage(key, client)


async def _save(key: SecretStr, workspace: UUID, environ: Mapping[str, str]) -> None:
    context = provider_context(environ)
    async with runtime_connection(environ[DATABASE_URL]) as connection:
        await save_key(key, workspace, ProviderSettings(connection, context))


async def _durable(secret: str, url: str) -> int:
    async with runtime_connection(url) as connection:
        return await durable_rows_holding(secret, connection)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("usage").add_argument("key_file", type=Path)
    save = commands.add_parser("save")
    save.add_argument("key_file", type=Path)
    save.add_argument("workspace", type=UUID)
    leaks = commands.add_parser("leaks")
    leaks.add_argument("key_file", type=Path)
    leaks.add_argument("logs", type=Path)
    arguments = parser.parse_args(argv)
    key = read_key(arguments.key_file)
    if arguments.command == "usage":
        print(asyncio.run(_usage(key)))
    elif arguments.command == "save":
        asyncio.run(_save(key, arguments.workspace, os.environ))
    else:
        secret = key.get_secret_value()
        durable = asyncio.run(_durable(secret, os.environ[DATABASE_URL]))
        print(f"{durable} {log_files_holding(secret, arguments.logs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
