"""The connection pool the routes read from app state, once the lifespan in app.py opens it."""

from typing import Any

from fastapi import Request
from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

from autobots.api.errors import ApiError

# Rows stay untyped until the SQL boundary is typed (R-54).
ConnectionPool = AsyncConnectionPool[AsyncConnection[Any]]


def request_pool(request: Request) -> ConnectionPool:
    """The open pool, or 503 when the service has no database."""
    pool: ConnectionPool | None = request.app.state.pool
    if pool is None:
        raise ApiError(503, "service_unavailable", "The database is unavailable.")
    return pool
