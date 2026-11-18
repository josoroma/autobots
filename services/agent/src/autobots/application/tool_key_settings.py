"""Settings → Keys & vars, Decisions 0024 (K3, K4, K6) and 0025 (V1 to V4), PRD-Tool-Catalog PK-07.

The owner saves, replaces or removes each of a workspace's six items with an expected version.
- Secrets (the Tavily, Jina and SerpApi keys and the GitHub token) get a shape check only, and are
  sealed with the master key, like the OpenRouter key.
- Values (the GitHub repository and the browsing switch) are checked against their form, and kept
  as they are, since they aren't secret.
Nothing here calls a provider (PK-03). Members read each item's source and version, and a value's
current value, never a secret.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from autobots.application.credentials.store import CredentialMissing, ProviderCredentialStore
from autobots.application.provider_settings import InvalidKey, StaleVersion
from autobots.application.sql import SqlConnection, one
from autobots.application.tool_keys import ITEMS, Item, resolve, saved_items


@dataclass(frozen=True)
class ItemState:
    name: str
    variable: str
    kind: str
    source: str | None
    # A value's resolved value. Always None for a secret.
    value: str | None
    version: int


def checked(item: Item, value: str) -> str:
    """The value to save, or `InvalidKey` with the item's own refusal. A secret's shape, as it was
    given; a value's form, once its surrounding space is gone (tool_keys.ITEMS)."""
    if not item.secret:
        value = value.strip()
    if not item.accepts(value):
        raise InvalidKey(item.refusal)
    return value


class ToolKeySettings:
    """One workspace's keys and values, over one runtime-role connection."""

    def __init__(
        self, connection: SqlConnection, key_file: Path, environ: Mapping[str, str]
    ) -> None:
        self._connection = connection
        self._key_file = key_file
        self._environ = environ

    async def _version(self, workspace_id: UUID, name: str, lock: bool = False) -> int:
        await self._connection.execute(
            "insert into app_private.tool_key_settings (workspace_id, provider) values (%s, %s) "
            "on conflict (workspace_id, provider) do nothing",
            (workspace_id, name),
        )
        suffix = " for update" if lock else ""
        (version,) = await one(
            self._connection,
            "select version from app_private.tool_key_settings "
            f"where workspace_id = %s and provider = %s{suffix}",
            (workspace_id, name),
        )
        return int(version)

    async def _advance(self, workspace_id: UUID, name: str, value: str | None = None) -> None:
        await self._connection.execute(
            "update app_private.tool_key_settings set version = version + 1, value = %s "
            "where workspace_id = %s and provider = %s",
            (value, workspace_id, name),
        )

    async def status(self, workspace_id: UUID) -> list[ItemState]:
        saved = await saved_items(self._connection, workspace_id)
        states = []
        for item in ITEMS.values():
            found = await resolve(item, saved, self._environ)
            states.append(
                ItemState(
                    name=item.name,
                    variable=item.variable,
                    kind="secret" if item.secret else "value",
                    source=found.source,
                    value=None if item.secret else found.value,
                    version=await self._version(workspace_id, item.name),
                )
            )
        return states

    async def save(self, workspace_id: UUID, name: str, draft: str, expected: int) -> None:
        """A malformed or stale draft leaves the saved item alone. Nothing calls a provider."""
        item = ITEMS[name]
        value = checked(item, draft)
        async with self._connection.transaction():
            if await self._version(workspace_id, name, lock=True) != expected:
                raise StaleVersion("the settings changed; reload them")
            if item.credential is not None:
                store = ProviderCredentialStore(self._connection, self._key_file, item.credential)
                await store.save(workspace_id, value)
                await self._advance(workspace_id, name)
            else:
                await self._advance(workspace_id, name, value)

    async def remove(self, workspace_id: UUID, name: str, expected: int) -> None:
        """Removes the saved item only, so the environment applies again. `.env` is never edited."""
        item = ITEMS[name]
        async with self._connection.transaction():
            if await self._version(workspace_id, name, lock=True) != expected:
                raise StaleVersion("the settings changed; reload them")
            if item.credential is not None:
                cursor = await self._connection.execute(
                    "update app_private.provider_credentials set status = 'deleted' "
                    "where workspace_id = %s and provider = %s and status = 'active' "
                    "returning credential_id",
                    (workspace_id, item.credential),
                )
            else:
                cursor = await self._connection.execute(
                    "select 1 from app_private.tool_key_settings "
                    "where workspace_id = %s and provider = %s and value is not null",
                    (workspace_id, name),
                )
            if await cursor.fetchone() is None:
                raise CredentialMissing("nothing is saved for this item")
            await self._advance(workspace_id, name)
