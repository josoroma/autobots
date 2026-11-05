"""The native process entry: `uvicorn --factory autobots.api.main:create_configured_app`."""

from fastapi import FastAPI

from autobots.api.app import create_app
from autobots.api.settings import load_settings


def create_configured_app() -> FastAPI:
    return create_app(load_settings())
