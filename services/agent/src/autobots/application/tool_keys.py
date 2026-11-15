"""Settings → Keys & vars: where each key and value comes from, Decisions 0024 and 0025.

Five items, per workspace: the Tavily key, the Jina key and the GitHub token, which are secrets, and
the GitHub repository and the browsing switch, which aren't. Highest first: the value saved in
Settings, the process environment, then the `.env` files under the configuration root in MP-03's
order. The first non-blank value wins. `resolve` is the one place that order is written (PTOL-12),
and `ITEMS` the one description of each item. A call resolves its item inside the attempt (PK-01),
so a change applies to the next call without a restart. Availability needs only where a secret
comes from, so it never unseals one.
"""

import re
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from autobots.application.credentials.precedence import dotenv_order, looks_usable, parse_dotenv
from autobots.application.credentials.store import (
    CredentialMissing,
    CredentialStorageUnavailable,
    ProviderCredentialStore,
)
from autobots.application.sql import SqlConnection
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
    # Whether a value has this item's form: a secret's shape, a value's own form. A draft without
    # it is refused with `refusal` as it is saved (tool_key_settings.checked).
    accepts: Callable[[str], bool]
    refusal: str

    @property
    def secret(self) -> bool:
        return self.credential is not None

    def usable(self, value: str | None) -> str | None:
        """`value` when it has this item's form, for a value item an attempt reads, such as the
        repository. Resolution has already stopped at it, so one without the form leaves the item
        unconfigured rather than reaching a lower source. A secret is sent as it resolved, and its
        provider judges it."""
        return value if value is not None and self.accepts(value) else None


def _repository(value: str) -> bool:
    return REPOSITORY.fullmatch(value) is not None


def _switch(value: str) -> bool:
    return value in SWITCH_VALUES


ITEMS: dict[str, Item] = {
    item.name: item
    for item in (
        Item("tavily", "TAVILY_API_KEY", "tavily", looks_usable, "that key was not accepted"),
        Item("jina", "JINA_API_KEY", "jina", looks_usable, "that key was not accepted"),
        Item("github_token", "GITHUB_TOKEN", "github", looks_usable, "that key was not accepted"),
        Item(
            "github_repository",
            "GITHUB_REPOSITORY",
            None,
            _repository,
            "that repository is not owner/name",
        ),
        Item(
            "browser_executor",
            "AUTOBOTS_BROWSER_EXECUTOR",
            None,
            _switch,
            "the switch is enabled or disabled",
        ),
    )
}
_BY_CREDENTIAL = {item.credential: item for item in ITEMS.values() if item.credential}


def key_requirement(*names: str, scopes: tuple[str, ...] = ()) -> KeyRequirement:
    """A tool's requirement, named from `ITEMS`, so the catalog's availability and the call read
    the same variables (PTOL-12). Its credential is the secret's among `names`."""
    items = [ITEMS[name] for name in names]
    credential = next(item.credential for item in items if item.credential is not None)
    return KeyRequirement(credential, tuple(item.variable for item in items), scopes)


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


NOTHING_SAVED = Saved(frozenset(), {})


async def saved_items(connection: SqlConnection, workspace_id: UUID) -> Saved:
    cursor = await connection.execute(
        "select provider from app_private.provider_credentials "
        "where workspace_id = %s and provider = any(%s) and status = 'active'",
        (workspace_id, list(_BY_CREDENTIAL)),
    )
    secrets = frozenset(_BY_CREDENTIAL[str(row[0])].name for row in await cursor.fetchall())
    cursor = await connection.execute(
        "select provider, value from app_private.tool_key_settings "
        "where workspace_id = %s and value is not null",
        (workspace_id,),
    )
    values = {str(row[0]): str(row[1]) for row in await cursor.fetchall()}
    return Saved(secrets, values)


@dataclass(frozen=True)
class Resolved:
    """Where an item's value comes from, and the value: a value item's always, a secret's only
    when it was resolved for a call."""

    source: str | None
    value: str | None


# Unseals an item's saved secret for one call: its value, None once it is no longer saved, or
# ToolKeyUnavailable when it can't be read.
Unseal = Callable[[Item], Awaitable[str | None]]


async def resolve(
    item: Item, saved: Saved, environ: Mapping[str, str], unseal: Unseal | None = None
) -> Resolved:
    """Decisions 0024 and 0025, PRD-Tool-Catalog PK-04 and PK-07: Settings, then the process
    environment, then the configuration root's `.env` files in MP-03's order.

    The first non-blank value wins, and resolution stops there even when that value is unusable
    (the model-gateway rule): a saved secret that can't be unsealed raises `ToolKeyUnavailable` and
    never falls through, a secret without its shape is returned for its provider to refuse, and a
    value without its item's form is returned for its caller to treat as not configured.
    A secret removed since `saved` was read is no longer in Settings, so the environment applies.

    Without `unseal`, as availability asks, a secret's value is never read, only its source. With
    it, as one attempt asks, a saved secret is unsealed and an environment one read.
    """
    if item.secret:
        if item.name in saved.secrets:
            if unseal is None:
                return Resolved(SETTINGS, None)
            value = await unseal(item)
            if value is not None:
                return Resolved(SETTINGS, value)
    elif item.name in saved.values:
        return Resolved(SETTINGS, saved.values[item.name])
    value = environment_key(item.variable, environ)
    if value is None:
        return Resolved(None, None)
    return Resolved(ENVIRONMENT, None if item.secret and unseal is None else value)


class KeySources(dict[str, str]):
    """An environment for availability only. A secret's variable holds a marker, never a value, so
    it can't reach an adapter by mistake. A value's variable holds its resolved value, which isn't
    secret. `sources` says where each item comes from."""

    sources: dict[str, str]


async def key_sources(
    connection: SqlConnection, workspace_id: UUID, environ: Mapping[str, str]
) -> KeySources:
    """The workspace's view of every Keys & vars item, in PK-04's order."""
    saved = await saved_items(connection, workspace_id)
    view = KeySources(environ)
    view.sources = {}
    for item in ITEMS.values():
        found = await resolve(item, saved, environ)
        view.pop(item.variable, None)
        if found.source is not None:
            view[item.variable] = f"<{found.source}>" if item.secret else str(found.value)
            view.sources[item.variable] = found.source
    return view


async def _saved_secret(
    connection: SqlConnection, workspace_id: UUID, item: Item, environ: Mapping[str, str]
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


async def attempt_value(
    connection: SqlConnection | None,
    workspace_id: UUID | None,
    item: Item,
    environ: Mapping[str, str],
) -> str | None:
    """One attempt's value of `item` for the run's workspace, by `resolve` (PK-01). A saved secret
    is unsealed for this call only. Without a connection, as offline checks call it, nothing is
    saved and only the environment is read. Raises `ToolKeyUnavailable`, naming no value."""
    if connection is None or workspace_id is None:
        saved = NOTHING_SAVED
    else:
        saved = await saved_items(connection, workspace_id)

    async def unseal(secret: Item) -> str | None:
        # Only a saved secret is unsealed, and nothing is saved without both.
        assert connection is not None and workspace_id is not None
        return await _saved_secret(connection, workspace_id, secret, environ)

    return (await resolve(item, saved, environ, unseal)).value
