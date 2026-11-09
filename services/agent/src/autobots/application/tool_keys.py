"""Where the Tavily and Jina keys come from, Decision 0024 and PRD-Tool-Catalog PK-04 to PK-06.

Highest first: the workspace's key saved in Settings, the process environment, then the `.env`
files under the configuration root in MP-03's order. The first non-blank value wins. A call resolves
its key inside the attempt (PK-01), so a change applies to the next call without a restart.
Availability needs only where a key comes from, so it never unseals one.
"""

from collections.abc import Mapping
from pathlib import Path
from typing import Any
from uuid import UUID

from autobots.application.credentials.crypto import CredentialDecryptionError
from autobots.application.credentials.precedence import dotenv_order, parse_dotenv
from autobots.application.credentials.store import (
    CredentialMissing,
    CredentialStorageUnavailable,
    ProviderCredentialStore,
)
from autobots.domain.tool_catalog import KeyRequirement

# The providers a workspace may save a key for, and the variable each is read from otherwise.
TOOL_KEY_PROVIDERS: dict[str, str] = {"tavily": "TAVILY_API_KEY", "jina": "JINA_API_KEY"}
SETTINGS = "settings"
ENVIRONMENT = "environment"
DEFAULT_KEY_FILE = "Library/Application Support/Autobots/secrets/provider-master.key"


class ToolKeyMissing(Exception):
    """No source has a non-blank value. `code` names the credential, never a value."""

    def __init__(self, provider: str) -> None:
        super().__init__(f"{provider}_key_missing")
        self.code = f"{provider}_key_missing"


class ToolKeyUnavailable(Exception):
    """A saved key exists and can't be unsealed. It never falls through to the environment."""

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


async def saved_providers(connection: Any, workspace_id: UUID) -> set[str]:
    cursor = await connection.execute(
        "select provider from app_private.provider_credentials "
        "where workspace_id = %s and provider = any(%s) and status = 'active'",
        (workspace_id, list(TOOL_KEY_PROVIDERS)),
    )
    return {str(row[0]) for row in await cursor.fetchall()}


def key_source(provider: str, saved: set[str], environ: Mapping[str, str]) -> str | None:
    if provider in saved:
        return SETTINGS
    if environment_key(TOOL_KEY_PROVIDERS[provider], environ) is not None:
        return ENVIRONMENT
    return None


class KeySources(dict[str, str]):
    """An environment for availability only. Each tool-key variable holds a marker, never a value,
    so it can't be handed to an adapter by mistake, and `sources` says where the key comes from."""

    sources: dict[str, str]


async def key_sources(
    connection: Any, workspace_id: UUID, environ: Mapping[str, str]
) -> KeySources:
    """The workspace's view of the variables key requirements name, in PK-04's order."""
    saved = await saved_providers(connection, workspace_id)
    view = KeySources(environ)
    view.sources = {}
    for provider, variable in TOOL_KEY_PROVIDERS.items():
        source = key_source(provider, saved, environ)
        view.pop(variable, None)
        if source is not None:
            view[variable] = f"<{source}>"
            view.sources[variable] = source
    return view


async def resolve_tool_key(
    connection: Any, workspace_id: UUID, requirement: KeyRequirement, environ: Mapping[str, str]
) -> str:
    """One attempt's key. Raises `ToolKeyMissing` or `ToolKeyUnavailable`, naming no value."""
    provider = requirement.credential
    variable = requirement.variables[0]
    if provider in TOOL_KEY_PROVIDERS and connection is not None:
        store = ProviderCredentialStore(connection, master_key_file(environ), provider)
        try:
            resolved = await store.load_active(workspace_id)
        except CredentialMissing:
            pass
        except (CredentialStorageUnavailable, CredentialDecryptionError):
            raise ToolKeyUnavailable(provider) from None
        else:
            return resolved.client_secret().get_secret_value()
    value = environment_key(variable, environ)
    if value is None:
        raise ToolKeyMissing(provider)
    return value
