"""The native process entry: `uvicorn --factory autobots.api.main:create_configured_app`."""

import os
from pathlib import Path

from fastapi import FastAPI

from autobots.adapters.models.openrouter_metadata import catalog_fetcher, key_validator
from autobots.api.app import create_app
from autobots.api.membership import PostgresMembership
from autobots.api.settings import load_settings
from autobots.application.provider_settings import ProviderContext

DEFAULT_KEY_FILE = "Library/Application Support/Autobots/secrets/provider-master.key"


def create_configured_app() -> FastAPI:
    app = create_app(load_settings())
    app.state.membership = PostgresMembership(app.state)
    config_root = os.environ.get("AUTOBOTS_CONFIG_ROOT", "")
    if config_root:
        key_file = os.environ.get("AUTOBOTS_PROVIDER_MASTER_KEY_FILE") or str(
            Path.home() / DEFAULT_KEY_FILE
        )
        app.state.provider_context = ProviderContext(
            config_root=config_root,
            mode=os.environ.get("NODE_ENV", "development"),
            master_key_file=Path(key_file),
            process_environment=dict(os.environ),
            validate_key=key_validator(),
            fetch_catalog=catalog_fetcher(),
        )
    return app
