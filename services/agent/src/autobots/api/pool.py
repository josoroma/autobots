"""The connection pool the routes read from app state, once the lifespan in app.py opens it."""

from typing import Any

from fastapi import Request
from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

from autobots.api.errors import ApiError

# Rows stay untyped until the SQL boundary is typed (R-54).
ConnectionPool = AsyncConnectionPool[AsyncConnection[Any]]
# How long a request waits for a pooled connection. psycopg_pool's default is 30 s, the same as the
# BFF's own abort in apps/web/lib/bff.ts, so the BFF's timer could fire first and a stopped
# database would read as its timeout. Shorter, so it reaches the person as this service's
# retryable 503 (XERR-06).
POOL_WAIT_SECONDS = 10.0


def request_pool(request: Request) -> ConnectionPool:
    """The open pool, or 503 when the service has no database."""
    pool: ConnectionPool | None = request.app.state.pool
    if pool is None:
        raise ApiError(503, "service_unavailable", "The database is unavailable.")
    return pool
