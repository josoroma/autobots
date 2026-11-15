"""The lease keeper, one look at a time, with an arranged `WakeClock` (PRUN-15, US-11.10, SP-012).

A look notices a sleep, beats when a beat is due or the Mac just woke, revives a lease that ran out
during a sleep, and then takes the sleep off the active time, after the beat. The database calls are
replaced, so these cases cover the decisions; tests/db/wake_check.py covers them against a database.
"""

import asyncio
import contextlib
import logging
from dataclasses import dataclass
from unittest.mock import patch
from uuid import uuid4

import pytest

from autobots.application import run_lifecycle
from autobots.application.run_lifecycle import LeaseKeeper, LoopConfig, lease_heartbeat
from autobots.application.runs import LeaseLost
from autobots.application.sql import SqlParams
from autobots.application.worker_leases import Lease, WakeClock
from autobots.domain.models import ModelRoute

LEASE = Lease(uuid4(), uuid4(), 3, "worker", 1, "running")
ROUTE = ModelRoute("executor", "openrouter_terra", "fixture/model", 1000)
SLEEP = 300.0


class Clocks:
    """The wall and monotonic clocks a sleep separates, moved by hand."""

    def __init__(self) -> None:
        self.wall = 1000.0
        self.mono = 500.0

    def clock(self) -> WakeClock:
        return WakeClock(wall=lambda: self.wall, mono=lambda: self.mono)


class Unused:
    """The keeper's connection. Every call the keeper makes through it is replaced."""

    description = None

    async def execute(self, query: str, params: SqlParams | None = None, /) -> "Unused":
        raise AssertionError(query)

    async def fetchone(self) -> tuple[object, ...] | None:
        raise AssertionError("fetchone")

    async def fetchall(self) -> list[tuple[object, ...]]:
        raise AssertionError("fetchall")

    def transaction(self) -> contextlib.nullcontext[None]:
        raise AssertionError("transaction")


@dataclass(frozen=True)
class Look:
    name: str
    calls: tuple[str, ...]
    heartbeat_seconds: float = 20.0
    since_beat: float = 0.0
    # Wall seconds the Mac slept since the last look.
    slept: float = 0.0
    # A sleep an earlier look already saw, still inside the wake window.
    woke_earlier: bool = False
    beat_lost: bool = False
    revive_lost: bool = False
    keeps: bool = True
    since_after: float = 0.0
    events: tuple[str, ...] = ()


LOOKS = (
    Look("a look with no beat due only counts the time", (), since_after=1.0),
    Look("a beat falls due", ("heartbeat",), since_beat=19.0),
    Look("a heartbeat shorter than a look beats every look", ("heartbeat",), heartbeat_seconds=0.5),
    Look("the first look after a reconnect beats", ("heartbeat",), since_beat=20.0),
    Look(
        "a sleep beats at once, and comes off the active time after the beat",
        ("heartbeat", f"discount {SLEEP}"),
        slept=SLEEP,
        events=("worker.woke",),
    ),
    Look(
        "just after a sleep every look beats, and the sleep is discounted once",
        ("heartbeat",),
        woke_earlier=True,
    ),
    Look(
        "a lost lease with no sleep ends the keeper",
        ("heartbeat",),
        since_beat=19.0,
        beat_lost=True,
        keeps=False,
    ),
    Look(
        "a lease that ran out during a sleep is revived, then the sleep is discounted",
        ("heartbeat", "revive", f"discount {SLEEP}"),
        slept=SLEEP,
        beat_lost=True,
        events=("worker.woke", "worker.lease_revived"),
    ),
    Look(
        "a lease someone took during a sleep ends the keeper, with nothing discounted",
        ("heartbeat", "revive"),
        slept=SLEEP,
        beat_lost=True,
        revive_lost=True,
        keeps=False,
        events=("worker.woke",),
    ),
)


@pytest.mark.parametrize("look", LOOKS, ids=[look.name for look in LOOKS])
def test_one_look(look: Look, caplog: pytest.LogCaptureFixture) -> None:
    clocks = Clocks()
    clock = clocks.clock()
    if look.woke_earlier:
        clocks.wall += SLEEP
        clock.check()
    config = LoopConfig(route=ROUTE, heartbeat_seconds=look.heartbeat_seconds, lease_seconds=60)
    keeper = LeaseKeeper("postgresql://unused", LEASE, config, clock)
    keeper.since_beat = look.since_beat
    keeper.failures.count = 2
    # The look's own wait passes on both clocks. A sleep moves only the wall clock.
    clocks.wall += keeper.look_seconds + look.slept
    clocks.mono += keeper.look_seconds
    calls: list[str] = []

    async def beat(_: object, lease: Lease, *, lease_seconds: float) -> None:
        assert (lease, lease_seconds) == (LEASE, 60)
        calls.append("heartbeat")
        if look.beat_lost:
            raise LeaseLost("arranged")

    async def revive(_: object, lease: Lease, *, lease_seconds: float) -> None:
        assert (lease, lease_seconds) == (LEASE, 60)
        calls.append("revive")
        if look.revive_lost:
            raise LeaseLost("arranged")

    async def discount(_: object, lease: Lease, seconds: float) -> None:
        assert lease == LEASE
        calls.append(f"discount {seconds}")

    with (
        caplog.at_level(logging.INFO, logger="autobots.worker"),
        patch.object(run_lifecycle, "heartbeat", beat),
        patch.object(run_lifecycle, "revive_lease", revive),
        patch.object(run_lifecycle, "discount_sleep", discount),
    ):
        keeps = asyncio.run(keeper.look(Unused()))
    events = tuple(record.getMessage() for record in caplog.records)
    assert (keeps, tuple(calls), keeper.since_beat, events) == (
        look.keeps,
        look.calls,
        look.since_after,
        look.events,
    )
    # A look that keeps the lease clears the failure count. One that ends the keeper leaves it.
    assert keeper.failures.count == (0 if look.keeps else 2)
    # A discount is made once, so an ended keeper is the only one still holding a sleep.
    assert keeper.undiscounted == (look.slept if not look.keeps else 0.0)


def test_a_look_waits_a_second_or_one_heartbeat_if_that_is_shorter() -> None:
    def interval(heartbeat_seconds: float) -> float:
        config = LoopConfig(route=ROUTE, heartbeat_seconds=heartbeat_seconds)
        return LeaseKeeper("postgresql://unused", LEASE, config, Clocks().clock()).look_seconds

    assert (interval(20.0), interval(1.0), interval(0.1)) == (1.0, 1.0, 0.1)


def test_a_revived_lease_and_a_sleep_are_logged_with_their_fields(
    caplog: pytest.LogCaptureFixture,
) -> None:
    clocks = Clocks()
    keeper = LeaseKeeper("postgresql://unused", LEASE, LoopConfig(route=ROUTE), clocks.clock())
    clocks.wall += keeper.look_seconds + SLEEP
    clocks.mono += keeper.look_seconds

    async def lost(*_: object, **__: object) -> None:
        raise LeaseLost("arranged")

    async def nothing(*_: object, **__: object) -> None:
        return None

    with (
        caplog.at_level(logging.INFO, logger="autobots.worker"),
        patch.object(run_lifecycle, "heartbeat", lost),
        patch.object(run_lifecycle, "revive_lease", nothing),
        patch.object(run_lifecycle, "discount_sleep", nothing),
    ):
        asyncio.run(keeper.look(Unused()))
    fields = [getattr(record, "fields", None) for record in caplog.records]
    assert fields == [{"seconds": SLEEP}, {"generation": LEASE.generation}]


class Keeper:
    """Stands in for `LeaseKeeper`, which the context builds by calling it: runs until cancelled,
    then cleans up with an await of its own."""

    def __init__(self) -> None:
        self.seen: list[str] = []
        self.started = asyncio.Event()

    def __call__(self, *_: object) -> "Keeper":
        return self

    async def run(self) -> None:
        self.seen.append("started")
        self.started.set()
        try:
            await asyncio.Event().wait()
        finally:
            await asyncio.sleep(0)
            self.seen.append("closed")


def test_the_keeper_ends_before_the_block_returns() -> None:
    keeper = Keeper()

    async def block() -> None:
        async with lease_heartbeat("postgresql://unused", LEASE, LoopConfig(route=ROUTE)):
            await keeper.started.wait()
            keeper.seen.append("worked")
        keeper.seen.append("after")

    with patch.object(run_lifecycle, "LeaseKeeper", keeper):
        asyncio.run(block())
    assert keeper.seen == ["started", "worked", "closed", "after"]


def test_a_failing_block_still_ends_the_keeper_and_raises() -> None:
    keeper = Keeper()

    async def block() -> None:
        async with lease_heartbeat("postgresql://unused", LEASE, LoopConfig(route=ROUTE)):
            await keeper.started.wait()
            raise RuntimeError("the pass failed")

    with patch.object(run_lifecycle, "LeaseKeeper", keeper), pytest.raises(RuntimeError):
        asyncio.run(block())
    assert keeper.seen == ["started", "closed"]


def test_a_cancelled_caller_ends_the_keeper_and_stays_cancelled() -> None:
    """DH-06: cleanup finishes, and the cancellation that bounds the caller still propagates."""
    keeper = Keeper()

    async def cancel_a_pass() -> tuple[bool, list[str]]:
        async def held() -> None:
            async with lease_heartbeat("postgresql://unused", LEASE, LoopConfig(route=ROUTE)):
                await asyncio.Event().wait()

        task = asyncio.create_task(held())
        await keeper.started.wait()
        task.cancel()
        await asyncio.wait({task})
        return task.cancelled(), list(keeper.seen)

    with patch.object(run_lifecycle, "LeaseKeeper", keeper):
        cancelled, seen = asyncio.run(cancel_a_pass())
    assert (cancelled, seen) == (True, ["started", "closed"])
