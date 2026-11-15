"""Pure application factory: building the app or its schema opens nothing and needs no key."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Protocol

from fastapi import FastAPI
from psycopg_pool import AsyncConnectionPool
from starlette.middleware.trustedhost import TrustedHostMiddleware

from autobots.adapters.tool_registry import catalog
from autobots.api.approval_routes import router as approval_router
from autobots.api.artifact_routes import router as artifact_router
from autobots.api.errors import ERROR_RESPONSES, register_error_handlers
from autobots.api.event_routes import router as event_router
from autobots.api.expert_routes import router as expert_router
from autobots.api.improvement_routes import router as improvement_router
from autobots.api.keys_and_vars_routes import router as keys_and_vars_router
from autobots.api.memory_routes import router as memory_router
from autobots.api.model_policy_routes import router as model_policy_router
from autobots.api.operation_routes import router as operation_router
from autobots.api.pool import POOL_WAIT_SECONDS
from autobots.api.provider_routes import router as provider_router
from autobots.api.routes import router
from autobots.api.routine_routes import router as routine_router
from autobots.api.run_command_routes import router as run_command_router
from autobots.api.run_reconcile_routes import router as run_reconcile_router
from autobots.api.run_routes import router as run_router
from autobots.api.search_routes import router as search_router
from autobots.api.security import DenyAllMembership, MembershipStore
from autobots.api.settings import Settings
from autobots.api.tool_routes import router as tool_router
from autobots.api.workflow_routes import router as workflow_router
from autobots.application.tool_catalog import Catalog


class Pool(Protocol):
    async def open(self) -> None: ...
    async def close(self) -> None: ...


def default_pool(url: str) -> Pool:
    return AsyncConnectionPool(
        url,
        open=False,
        min_size=1,
        max_size=5,
        check=AsyncConnectionPool.check_connection,
        timeout=POOL_WAIT_SECONDS,
    )


def create_app(
    settings: Settings | None = None,
    *,
    membership: MembershipStore | None = None,
    pool_factory: Callable[[str], Pool] = default_pool,
    tools: Catalog | None = None,
) -> FastAPI:
    """`tools` is the tool catalog the routes read and admit through. By default it is the one
    over the registry the worker builds (adapters/tool_registry.py, XMOD-01); a test passes its
    own. Building it opens nothing."""
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
    app.state.tools = catalog() if tools is None else tools
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(resolved.allowed_hosts))
    register_error_handlers(app)
    app.include_router(router, responses=ERROR_RESPONSES)
    app.include_router(provider_router, responses=ERROR_RESPONSES)
    app.include_router(keys_and_vars_router, responses=ERROR_RESPONSES)
    app.include_router(model_policy_router, responses=ERROR_RESPONSES)
    app.include_router(run_router, responses=ERROR_RESPONSES)
    app.include_router(run_command_router, responses=ERROR_RESPONSES)
    app.include_router(run_reconcile_router, responses=ERROR_RESPONSES)
    app.include_router(artifact_router, responses=ERROR_RESPONSES)
    app.include_router(approval_router, responses=ERROR_RESPONSES)
    app.include_router(event_router, responses=ERROR_RESPONSES)
    app.include_router(expert_router, responses=ERROR_RESPONSES)
    app.include_router(workflow_router, responses=ERROR_RESPONSES)
    app.include_router(routine_router, responses=ERROR_RESPONSES)
    app.include_router(memory_router, responses=ERROR_RESPONSES)
    app.include_router(improvement_router, responses=ERROR_RESPONSES)
    app.include_router(operation_router, responses=ERROR_RESPONSES)
    app.include_router(tool_router, responses=ERROR_RESPONSES)
    app.include_router(search_router, responses=ERROR_RESPONSES)
    return app
