"""The native process entry: `uvicorn --factory autobots.api.main:create_configured_app`."""

import os
from pathlib import Path

from fastapi import FastAPI
from pydantic import SecretStr

from autobots.adapters.models.openrouter_metadata import catalog_fetcher, key_validator
from autobots.adapters.object_storage import SupabaseObjectStore
from autobots.api.app import create_app
from autobots.api.membership import PostgresMembership
from autobots.api.settings import load_settings
from autobots.application.provider_settings import ProviderContext
from autobots.operations.logs import configure_logging, forbid_remote_tracing

DEFAULT_KEY_FILE = "Library/Application Support/Autobots/secrets/provider-master.key"


def provider_context_from_environment() -> ProviderContext | None:
    config_root = os.environ.get("AUTOBOTS_CONFIG_ROOT", "")
    if not config_root:
        return None
    key_file = os.environ.get("AUTOBOTS_PROVIDER_MASTER_KEY_FILE") or str(
        Path.home() / DEFAULT_KEY_FILE
    )
    return ProviderContext(
        config_root=config_root,
        mode=os.environ.get("NODE_ENV", "development"),
        master_key_file=Path(key_file),
        process_environment=dict(os.environ),
        validate_key=key_validator(),
        fetch_catalog=catalog_fetcher(),
    )


def create_configured_app() -> FastAPI:
    # First, so nothing built below can see an inherited tracing setting.
    forbid_remote_tracing(os.environ)
    configure_logging()
    app = create_app(load_settings())
    app.state.membership = PostgresMembership(app.state)
    stream_seconds = os.environ.get("AUTOBOTS_STREAM_SECONDS", "")
    if stream_seconds:
        app.state.stream_seconds = float(stream_seconds)
    storage_url = os.environ.get("AUTOBOTS_SUPABASE_URL", "")
    storage_key = os.environ.get("AUTOBOTS_SERVICE_ROLE_KEY", "")
    if storage_url and storage_key:
        app.state.object_store = SupabaseObjectStore(storage_url, SecretStr(storage_key))
    app.state.provider_context = provider_context_from_environment()
    return app
