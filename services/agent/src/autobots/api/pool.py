"""The connection pool the lifespan in app.py opens and closes, typed as the routes use it."""

from contextlib import AbstractAsyncContextManager
from typing import Protocol

from psycopg_pool import AsyncConnectionPool

from autobots.application.sql import CommittingConnection

# How long a request waits for a pooled connection. psycopg_pool's default is 30 s, the same as the
# BFF's own abort in apps/web/lib/bff.ts, so the BFF's timer could fire first and a stopped
# database would read as its timeout. Shorter, so it reaches the person as this service's
# retryable 503 (XERR-06).
POOL_WAIT_SECONDS = 10.0


class Pool(Protocol):
    """psycopg_pool's `AsyncConnectionPool`, or a test's fake. Its connections aren't autocommit,
    so retention commits between its steps (application/retention.py)."""

    async def open(self) -> None: ...

    async def close(self) -> None: ...

    def connection(self) -> AbstractAsyncContextManager[CommittingConnection]: ...


def default_pool(url: str) -> Pool:
    return AsyncConnectionPool(
        url,
        open=False,
        min_size=1,
        max_size=5,
        check=AsyncConnectionPool.check_connection,
        timeout=POOL_WAIT_SECONDS,
    )
