"""Settings → Keys & vars: where each key and value comes from, Decisions 0024 and 0025.

Five items, per workspace: the Tavily key, the Jina key and the GitHub token, which are secrets, and
the GitHub repository and the browsing switch, which aren't. Highest first: the value saved in
Settings, the process environment, then the `.env` files under the configuration root in MP-03's
order. The first non-blank value wins. A call resolves its item inside the attempt (PK-01), so a
change applies to the next call without a restart. Availability needs only where a secret comes
from, so it never unseals one.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from autobots.application.credentials.precedence import dotenv_order, parse_dotenv
from autobots.application.credentials.store import (
    CredentialMissing,
    CredentialStorageUnavailable,
    ProviderCredentialStore,
)
from autobots.domain.tool_catalog import KeyRequirement

SETTINGS = "settings"
ENVIRONMENT = "environment"
DEFAULT_KEY_FILE = "Library/Application Support/Autobots/secrets/provider-master.key"
REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
SWITCH_VALUES = ("enabled", "disabled")


@dataclass(frozen=True)
class Item:
    name: str
    variable: str
    # The sealed credential's provider for a secret, and None for a value that isn't secret.
    credential: str | None

    @property
    def secret(self) -> bool:
        return self.credential is not None


ITEMS: dict[str, Item] = {
    item.name: item
    for item in (
        Item("tavily", "TAVILY_API_KEY", "tavily"),
        Item("jina", "JINA_API_KEY", "jina"),
        Item("github_token", "GITHUB_TOKEN", "github"),
        Item("github_repository", "GITHUB_REPOSITORY", None),
        Item("browser_executor", "AUTOBOTS_BROWSER_EXECUTOR", None),
    )
}
BY_CREDENTIAL = {item.credential: item for item in ITEMS.values() if item.credential}
# Kept for the Tavily and Jina adapters, whose requirement names the credential.
TOOL_KEY_PROVIDERS: dict[str, str] = {"tavily": "TAVILY_API_KEY", "jina": "JINA_API_KEY"}


class ToolKeyMissing(Exception):
    """No source has a non-blank value. `code` names the credential, never a value."""

    def __init__(self, provider: str) -> None:
        super().__init__(f"{provider}_key_missing")
        self.code = f"{provider}_key_missing"


class ToolKeyUnavailable(Exception):
    """A saved secret exists and can't be unsealed. It never falls through to the environment."""

    def __init__(self, provider: str) -> None:
        super().__init__(f"{provider}_key_unavailable")
        self.code = f"{provider}_key_unavailable"


def master_key_file(environ: Mapping[str, str]) -> Path:
    return Path(environ.get("AUTOBOTS_PROVIDER_MASTER_KEY_FILE") or Path.home() / DEFAULT_KEY_FILE)


def environment_key(variable: str, environ: Mapping[str, str]) -> str | None:
    """The process environment, then the configuration root's `.env` files, as MP-03 orders them."""
    value = environ.get(variable, "").strip()
    if value:
        return value
    root = environ.get("AUTOBOTS_CONFIG_ROOT", "")
    if not root or not Path(root).is_absolute():
        return None
    for name in dotenv_order(environ.get("NODE_ENV", "development")):
        path = Path(root) / name
        if path.is_file():
            value = parse_dotenv(path.read_text()).get(variable, "").strip()
            if value:
                return value
    return None


@dataclass(frozen=True)
class Saved:
    """What a workspace saved: which secrets exist, and each value's setting."""

    secrets: frozenset[str]
    values: Mapping[str, str]


async def saved_items(connection: Any, workspace_id: UUID) -> Saved:
    cursor = await connection.execute(
        "select provider from app_private.provider_credentials "
        "where workspace_id = %s and provider = any(%s) and status = 'active'",
        (workspace_id, list(BY_CREDENTIAL)),
    )
    secrets = frozenset(BY_CREDENTIAL[str(row[0])].name for row in await cursor.fetchall())
    cursor = await connection.execute(
        "select provider, value from app_private.tool_key_settings "
        "where workspace_id = %s and value is not null",
        (workspace_id,),
    )
    values = {str(row[0]): str(row[1]) for row in await cursor.fetchall()}
    return Saved(secrets, values)


async def saved_providers(connection: Any, workspace_id: UUID) -> set[str]:
    """The Tavily and Jina providers this workspace saved a key for (US-14.17)."""
    saved = await saved_items(connection, workspace_id)
    return {name for name in saved.secrets if name in TOOL_KEY_PROVIDERS}


def resolve_item(
    item: Item, saved: Saved, environ: Mapping[str, str]
) -> tuple[str | None, str | None]:
    """(source, value). A secret's value is never returned: it is unsealed only for a call."""
    if item.secret:
        if item.name in saved.secrets:
            return SETTINGS, None
        return (ENVIRONMENT, None) if environment_key(item.variable, environ) else (None, None)
    if item.name in saved.values:
        return SETTINGS, saved.values[item.name]
    value = environment_key(item.variable, environ)
    return (ENVIRONMENT, value) if value is not None else (None, None)


def key_source(provider: str, saved: set[str], environ: Mapping[str, str]) -> str | None:
    return resolve_item(ITEMS[provider], Saved(frozenset(saved), {}), environ)[0]


class KeySources(dict[str, str]):
    """An environment for availability only. A secret's variable holds a marker, never a value, so
    it can't reach an adapter by mistake. A value's variable holds its resolved value, which isn't
    secret. `sources` says where each item comes from."""

    sources: dict[str, str]


async def key_sources(
    connection: Any, workspace_id: UUID, environ: Mapping[str, str]
) -> KeySources:
    """The workspace's view of every Keys & vars item, in PK-04's order."""
    saved = await saved_items(connection, workspace_id)
    view = KeySources(environ)
    view.sources = {}
    for item in ITEMS.values():
        source, value = resolve_item(item, saved, environ)
        view.pop(item.variable, None)
        if source is not None:
            view[item.variable] = f"<{source}>" if item.secret else str(value)
            view.sources[item.variable] = source
    return view


async def _saved_secret(
    connection: Any, workspace_id: UUID, item: Item, environ: Mapping[str, str]
) -> str | None:
    assert item.credential is not None
    store = ProviderCredentialStore(connection, master_key_file(environ), item.credential)
    try:
        resolved = await store.load_active(workspace_id)
    except CredentialMissing:
        return None
    except CredentialStorageUnavailable:
        raise ToolKeyUnavailable(item.credential) from None
    return resolved.client_secret().get_secret_value()


async def resolve_tool_key(
    connection: Any, workspace_id: UUID, requirement: KeyRequirement, environ: Mapping[str, str]
) -> str:
    """One attempt's key. Raises `ToolKeyMissing` or `ToolKeyUnavailable`, naming no value."""
    provider = requirement.credential
    variable = requirement.variables[0]
    if provider in TOOL_KEY_PROVIDERS and connection is not None:
        saved = await _saved_secret(connection, workspace_id, ITEMS[provider], environ)
        if saved is not None:
            return saved
    value = environment_key(variable, environ)
    if value is None:
        raise ToolKeyMissing(provider)
    return value


async def resolve_value(
    connection: Any, workspace_id: UUID | None, name: str, environ: Mapping[str, str]
) -> str | None:
    """One attempt's value for an item that isn't secret, by PK-07's order."""
    item = ITEMS[name]
    if connection is not None and workspace_id is not None:
        cursor = await connection.execute(
            "select value from app_private.tool_key_settings "
            "where workspace_id = %s and provider = %s and value is not null",
            (workspace_id, item.name),
        )
        row = await cursor.fetchone()
        if row is not None:
            return str(row[0])
    return environment_key(item.variable, environ)


async def github_repository(
    connection: Any, workspace_id: UUID | None, environ: Mapping[str, str]
) -> str | None:
    """The workspace's repository, or None when it isn't a valid `owner/name`."""
    repository = await resolve_value(connection, workspace_id, "github_repository", environ)
    return repository if repository and REPOSITORY.fullmatch(repository) else None


async def github_target(
    connection: Any, workspace_id: UUID | None, environ: Mapping[str, str]
) -> tuple[str | None, str | None]:
    """(repository, token) for one attempt, by PK-07's order. Either is None when not configured."""
    repository = await github_repository(connection, workspace_id, environ)
    token = None
    if connection is not None and workspace_id is not None:
        token = await _saved_secret(connection, workspace_id, ITEMS["github_token"], environ)
    if token is None:
        token = environment_key("GITHUB_TOKEN", environ)
    return repository, token
