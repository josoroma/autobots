"""The native process entry: `uvicorn --factory autobots.api.main:create_configured_app`.

What it builds from the environment comes from `operations/composition.py`, which the worker shares,
so both read a key, the object store and a refusal the same way (POPS-03, XMOD-08).
"""

import os

from fastapi import FastAPI

from autobots.api.app import create_app
from autobots.api.membership import PostgresMembership
from autobots.api.resources import DEFAULT_STREAM_SECONDS, AppResources
from autobots.api.settings import load_settings
from autobots.application.readiness import MalformedSetting
from autobots.logs import configure_logging, forbid_remote_tracing
from autobots.operations.composition import (
    object_store,
    provider_context,
    seconds,
    stop_unconfigured,
)

STREAM_SECONDS = "AUTOBOTS_STREAM_SECONDS"


def create_configured_app() -> FastAPI:
    """A setting it can't start with stops it here, exit 2 with the variable named, rather than
    refusing every admission. A missing database isn't one: Local Operations answers without it."""
    # First, so nothing built below can see an inherited tracing setting.
    forbid_remote_tracing(os.environ)
    configure_logging()
    try:
        settings = load_settings(os.environ)
        stream_seconds = seconds(os.environ, STREAM_SECONDS)
    except MalformedSetting as error:
        stop_unconfigured(error)
    resources = AppResources(
        settings,
        stream_seconds=DEFAULT_STREAM_SECONDS if stream_seconds is None else stream_seconds,
        object_store=object_store(os.environ),
        # The live mapping, so a key is resolved again for each attempt (model-gateway rule).
        provider_context=provider_context(os.environ),
    )
    # Membership reads the pool the lifespan sets on these same resources.
    resources.membership = PostgresMembership(resources)
    return create_app(resources)
