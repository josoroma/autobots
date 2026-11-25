"""A stealth browse's pace, Decision 0038 Z12: steps apart, and one browse of a site at a time
across the install.

A site is the registrable part of a domain the call names, so `a.example.com` and `b.example.com`
are one. Each site's turn is a Postgres session advisory lock on the attempt's connection, so it is
freed when the browse ends, when its attempt is cancelled, and when a lost worker's connection
closes. Two calls of one attempt share that connection, whose lock would let both in, so a site held
in this process waits too.
"""

import asyncio
import contextlib
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass

from autobots.application.sql import SqlConnection, one

STEP_SECONDS = 2.0
POLL_SECONDS = 1.0
_HELD: set[str] = set()


@dataclass
class Pace:
    """Called before each step, it returns at least `seconds` after it last returned."""

    seconds: float = STEP_SECONDS
    clock: Callable[[], float] = time.monotonic
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep
    last: float | None = None

    async def __call__(self) -> None:
        if self.last is not None:
            wait = self.last + self.seconds - self.clock()
            if wait > 0:
                await self.sleep(wait)
        self.last = self.clock()


def site_of(domain: str) -> str:
    """A domain's registrable part: its last two labels, or three under a two-part country suffix
    such as `co.cr` or `com.mx`. One label too few only makes two sites share a turn."""
    labels = domain.lower().rstrip(".").split(".")
    second = len(labels) > 2 and len(labels[-1]) == 2 and len(labels[-2]) <= 3
    return ".".join(labels[-3:] if second else labels[-2:])


class SiteBusy(Exception):
    """Another stealth browse held a site of this call until its time was up."""


class TurnLost(Exception):
    """The attempt ended while its browse waited for a turn."""


async def _take(connection: SqlConnection, site: str) -> bool:
    if site in _HELD:
        return False
    _HELD.add(site)
    try:
        (taken,) = await one(
            connection,
            "select pg_try_advisory_lock(hashtextextended(%s, 0))",
            (f"browse-site:{site}",),
        )
    except BaseException:
        _HELD.discard(site)
        raise
    if not taken:
        _HELD.discard(site)
    return bool(taken)


async def _free(connection: SqlConnection, site: str) -> None:
    try:
        # A connection that is gone freed it already.
        with contextlib.suppress(Exception):
            await connection.execute(
                "select pg_advisory_unlock(hashtextextended(%s, 0))", (f"browse-site:{site}",)
            )
    finally:
        _HELD.discard(site)


@asynccontextmanager
async def turn(
    connection: SqlConnection,
    domains: Sequence[str],
    seconds: float,
    alive: Callable[[], Awaitable[bool]],
    *,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> AsyncIterator[float]:
    """The turn of every site the domains name, in one order so two calls never wait for each
    other. Yields the seconds it waited. `SiteBusy` once `seconds` are up, `TurnLost` when the
    attempt ends."""
    started = clock()
    held: list[str] = []
    try:
        for site in sorted({site_of(domain) for domain in domains}):
            while not await _take(connection, site):
                if clock() - started >= seconds:
                    raise SiteBusy(site)
                if not await alive():
                    raise TurnLost(site)
                await sleep(POLL_SECONDS)
            held.append(site)
        yield clock() - started
    finally:
        for site in reversed(held):
            await _free(connection, site)
