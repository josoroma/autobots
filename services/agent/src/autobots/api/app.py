"""Pure application factory: building the app or its schema opens nothing and needs no key."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Protocol

from fastapi import FastAPI
from psycopg_pool import AsyncConnectionPool
from starlette.middleware.trustedhost import TrustedHostMiddleware

from autobots.api.errors import register_error_handlers
from autobots.api.routes import router
from autobots.api.security import DenyAllMembership, MembershipStore
from autobots.api.settings import Settings
from autobots.api.settings_routes import router as settings_router


class Pool(Protocol):
    async def open(self) -> None: ...
    async def close(self) -> None: ...


def default_pool(url: str) -> Pool:
    return AsyncConnectionPool(url, open=False, min_size=1, max_size=5)


def create_app(
    settings: Settings | None = None,
    *,
    membership: MembershipStore | None = None,
    pool_factory: Callable[[str], Pool] = default_pool,
) -> FastAPI:
    resolved = Settings() if settings is None else settings

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Owns process resources: created at startup and closed at shutdown, never at import."""
        url = resolved.database_url.get_secret_value()
        pool = pool_factory(url) if url else None
        if pool is not None:
            await pool.open()
        app.state.pool = pool
        try:
            yield
        finally:
            if pool is not None:
                await pool.close()
            app.state.pool = None

    app = FastAPI(
        title="Autobots Agent API",
        version="0.0.0",
        lifespan=lifespan,
        openapi_url=None,
        docs_url=None,
        redoc_url=None,
    )
    app.state.settings = resolved
    app.state.membership = DenyAllMembership() if membership is None else membership
    app.state.pool = None
    app.state.provider_context = None
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(resolved.allowed_hosts))
    register_error_handlers(app)
    app.include_router(router)
    app.include_router(settings_router)
    return app
