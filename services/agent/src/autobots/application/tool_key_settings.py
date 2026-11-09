"""Settings → Tool keys, Decision 0024 K3, K4 and K6 and PRD-Tool-Catalog PK-05.

The owner saves, replaces or removes a workspace's Tavily or Jina key, each with an expected
version. Saving checks the key's shape only and calls no provider (PK-03). The value is sealed with
the master key, like the OpenRouter key. Members read each key's source and version, never a value.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from autobots.application.credentials.precedence import looks_usable
from autobots.application.credentials.store import CredentialMissing, ProviderCredentialStore
from autobots.application.provider_settings import InvalidKey, StaleVersion
from autobots.application.tool_keys import TOOL_KEY_PROVIDERS, key_source, saved_providers


@dataclass(frozen=True)
class ToolKeyState:
    provider: str
    variable: str
    source: str | None
    version: int


class ToolKeySettings:
    """One workspace's tool keys, over one runtime-role connection."""

    def __init__(self, connection: Any, key_file: Path, environ: Mapping[str, str]) -> None:
        self._connection = connection
        self._key_file = key_file
        self._environ = environ

    async def _version(self, workspace_id: UUID, provider: str, lock: bool = False) -> int:
        await self._connection.execute(
            "insert into app_private.tool_key_settings (workspace_id, provider) values (%s, %s) "
            "on conflict (workspace_id, provider) do nothing",
            (workspace_id, provider),
        )
        suffix = " for update" if lock else ""
        cursor = await self._connection.execute(
            "select version from app_private.tool_key_settings "
            f"where workspace_id = %s and provider = %s{suffix}",
            (workspace_id, provider),
        )
        row = await cursor.fetchone()
        return int(row[0])

    async def _advance(self, workspace_id: UUID, provider: str) -> None:
        await self._connection.execute(
            "update app_private.tool_key_settings set version = version + 1 "
            "where workspace_id = %s and provider = %s",
            (workspace_id, provider),
        )

    async def status(self, workspace_id: UUID) -> list[ToolKeyState]:
        saved = await saved_providers(self._connection, workspace_id)
        states = []
        for provider, variable in TOOL_KEY_PROVIDERS.items():
            states.append(
                ToolKeyState(
                    provider=provider,
                    variable=variable,
                    source=key_source(provider, saved, self._environ),
                    version=await self._version(workspace_id, provider),
                )
            )
        return states

    async def save(self, workspace_id: UUID, provider: str, draft: str, expected: int) -> None:
        """A malformed or stale draft leaves the saved key alone. Nothing calls the provider."""
        if not looks_usable(draft):
            raise InvalidKey("that key was not accepted")
        store = ProviderCredentialStore(self._connection, self._key_file, provider)
        async with self._connection.transaction():
            if await self._version(workspace_id, provider, lock=True) != expected:
                raise StaleVersion("the settings changed; reload them")
            await store.save(workspace_id, draft)
            await self._advance(workspace_id, provider)

    async def remove(self, workspace_id: UUID, provider: str, expected: int) -> None:
        """Removes the saved key only, so the environment applies again. `.env` is never edited."""
        async with self._connection.transaction():
            if await self._version(workspace_id, provider, lock=True) != expected:
                raise StaleVersion("the settings changed; reload them")
            cursor = await self._connection.execute(
                "update app_private.provider_credentials set status = 'deleted' "
                "where workspace_id = %s and provider = %s and status = 'active' "
                "returning credential_id",
                (workspace_id, provider),
            )
            if await cursor.fetchone() is None:
                raise CredentialMissing("no key is saved for this provider")
            await self._advance(workspace_id, provider)
