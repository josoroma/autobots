"""What each process entry builds from its environment: the API's `api/main.py` and the worker.

Every function takes the live environment mapping, `os.environ` itself, and never copies it, so a
key the process or an `.env` file supplies is resolved again for each attempt (model-gateway rule).

A setting a process can't start with raises `MalformedSetting`, whose message names the variable and
never its value. The entry point stops with `stop_unconfigured`: `ERROR: <message>` on stderr and
exit 2, a prerequisite that isn't there (AGENTS.md Commands, POPS-14).
"""

import math
import sys
from collections.abc import Mapping
from typing import NoReturn
from uuid import UUID

from pydantic import SecretStr

from autobots.adapters.models.openrouter_metadata import catalog_fetcher, key_validator
from autobots.adapters.object_storage import SupabaseObjectStore
from autobots.application.provider_settings import (
    ConnectionReadiness,
    ProviderContext,
    ProviderSettings,
)
from autobots.application.readiness import MalformedSetting
from autobots.application.tool_keys import master_key_file

EXIT_UNCONFIGURED = 2
DATABASE_URL = "AUTOBOTS_DATABASE_URL"
CONFIG_ROOT = "AUTOBOTS_CONFIG_ROOT"
STORAGE_URL = "AUTOBOTS_SUPABASE_URL"
SERVICE_KEY = "AUTOBOTS_SERVICE_ROLE_KEY"


def require(environ: Mapping[str, str], *names: str) -> tuple[str, ...]:
    """Each named value, in order. The unset or blank ones are named together, never a value."""
    missing = [name for name in names if not environ.get(name, "").strip()]
    if missing:
        raise MalformedSetting(f"set {', '.join(missing)}")
    return tuple(environ[name] for name in names)


def seconds(environ: Mapping[str, str], name: str) -> float | None:
    """A duration in seconds, 0 or more. None when unset or blank, for the caller's default."""
    raw = environ.get(name, "").strip()
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError:
        value = math.nan
    if not math.isfinite(value) or value < 0:
        raise MalformedSetting(f"{name} must be a number of seconds, 0 or more")
    return value


def unconfigured(error: MalformedSetting) -> int:
    """Says what to set or fix, and gives the exit code for it."""
    print(f"ERROR: {error}", file=sys.stderr)
    return EXIT_UNCONFIGURED


def stop_unconfigured(error: MalformedSetting) -> NoReturn:
    """For a process entry: it stops at start rather than refusing every request or pass."""
    raise SystemExit(unconfigured(error))


def provider_context(environ: Mapping[str, str]) -> ProviderContext | None:
    """None without a configuration root, so settings report unavailable and nothing unattended
    starts. The master key file defaults as the tool keys' does (`tool_keys.master_key_file`)."""
    config_root = environ.get(CONFIG_ROOT, "")
    if not config_root:
        return None
    return ProviderContext(
        config_root=config_root,
        mode=environ.get("NODE_ENV", "development"),
        master_key_file=master_key_file(environ),
        process_environment=environ,
        validate_key=key_validator(),
        fetch_catalog=catalog_fetcher(),
    )


def object_store(environ: Mapping[str, str]) -> SupabaseObjectStore | None:
    """Storage through its service role, when both its address and key are set."""
    url, key = environ.get(STORAGE_URL, ""), environ.get(SERVICE_KEY, "")
    return SupabaseObjectStore(url, SecretStr(key)) if url and key else None


async def no_credential(_connection: object, _workspace_id: UUID) -> str:
    """With no provider context, nothing unattended starts. The code matches a missing key."""
    return "credentials_required"


def credential_check(environ: Mapping[str, str]) -> ConnectionReadiness:
    """The API's own answer about a key, so a routine and a person see the same one."""
    context = provider_context(environ)
    if context is None:
        return no_credential

    async def check(connection: object, workspace_id: UUID) -> str:
        return await ProviderSettings(connection, context).run_intent(workspace_id)

    return check
