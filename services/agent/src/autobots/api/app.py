"""Pure application factory: building the app or its schema opens nothing and needs no key."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Owns process resources once there are any. This scaffold has none."""
    yield


def create_app() -> FastAPI:
    return FastAPI(
        title="Autobots Agent API",
        version="0.0.0",
        lifespan=lifespan,
        openapi_url=None,
        docs_url=None,
        redoc_url=None,
    )
