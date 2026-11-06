"""Wake handling against a real database, with an arranged clock, US-11.10.

Only a real sleep proves the fix. This covers what a sleep can't arrange on demand: that fencing still holds, and
that a stall with no clock gap, such as SIGSTOP, gets none of this.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from uuid import UUID, uuid4

import psycopg

from autobots.application.goal_loop import LoopConfig, _keep_lease  # noqa: PLC2701
from autobots.adapters.loop_middleware import ModelRoute
from autobots.application.run_usage import active_seconds_used, begin_segment
from autobots.application.runs import LeaseLost, admit_run
from autobots.application.worker_leases import WakeClock, claim_run, heartbeat, revive_lease
from autobots.domain.models import resolve_role_policy

URL = os.environ['AUTOBOTS_DATABASE_URL']
WORKSPACE = UUID(sys.argv[1])
ROUTE = ModelRoute('executor', 'openrouter_terra', 'fixture/model', 1000)
CONFIG = LoopConfig(route=ROUTE, heartbeat_seconds=0.1, lease_seconds=60)
cases: list[dict] = []


def check(name: str, expected: str, observed: object, passed: bool) -> None:
    cases.append({'id': name, 'expected': expected, 'observed': str(observed)[:300], 'passed': bool(passed)})


class ArrangedClock(WakeClock):
    """The two clocks a sleep separates, moved by hand."""

    def __init__(self) -> None:
        self.wall_now, self.mono_now = 1000.0, 500.0
        super().__init__(wall=lambda: self.wall_now, mono=lambda: self.mono_now)

    def tick(self) -> None:
        self.wall_now += 0.05
        self.mono_now += 0.05

    def sleep_for(self, seconds: float) -> None:
        self.wall_now += seconds


async def admitted(db: psycopg.AsyncConnection) -> UUID:
    accepted = await admit_run(db, workspace_id=WORKSPACE, actor_id=uuid4(), idempotency_key=str(uuid4()), goal_text='Sleep through this',
                               limit_micro_usd=1000, policy=resolve_role_policy())
    return accepted.run_id


async def expire(db: psycopg.AsyncConnection, run: UUID) -> None:
    await db.execute("update app_private.run_jobs set lease_expires_at = clock_timestamp() - interval '1 second' where run_id = %s", (run,))


async def live(db: psycopg.AsyncConnection, run: UUID) -> bool:
    return (await (await db.execute('select lease_expires_at > clock_timestamp() from app_private.run_jobs where run_id = %s', (run,))).fetchone())[0]


async def main() -> None:
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        # The clock itself, with both directions of a stall.
        clock = ArrangedClock()
        clock.tick()
        check('steady clocks report no sleep', '0 seconds, not woken', (clock.check(), clock.just_woke()), clock.check() == 0 and not clock.just_woke())
        clock.sleep_for(300)
        slept = clock.check()
        check('a wall clock ahead of the monotonic one is a sleep', '300 seconds, woken', (slept, clock.just_woke()), slept == 300 and clock.just_woke())
        clock.mono_now += 1000
        clock.wall_now += 1000
        check('the wake window closes', 'not woken', clock.just_woke(), not clock.just_woke())

        # Reviving is for the same generation only.
        run = await admitted(db)
        lease = await claim_run(db, run, worker_id='waking')
        await expire(db, run)
        try:
            await heartbeat(db, lease)
            check('an ordinary heartbeat still refuses an expired lease', 'LeaseLost', 'extended', False)
        except LeaseLost:
            check('an ordinary heartbeat still refuses an expired lease', 'LeaseLost', 'LeaseLost', True)
        await revive_lease(db, lease)
        check('nobody took it, so its own worker revives it', 'live, same generation', await live(db, run), await live(db, run))
        await expire(db, run)
        taker = await claim_run(db, run, worker_id='other')
        check('another worker can still take an expired lease', 'a higher generation', taker.generation if taker else None, taker is not None and taker.generation > lease.generation)
        try:
            await revive_lease(db, lease)
            check('a lease someone took is never revived', 'LeaseLost', 'revived', False)
        except LeaseLost:
            check('a lease someone took is never revived', 'LeaseLost', 'LeaseLost', True)

        # The whole keeper: a sleep revives the lease and takes itself off the active time.
        run = await admitted(db)
        lease = await claim_run(db, run, worker_id='waking')
        await begin_segment(db, run)
        await asyncio.sleep(0.2)
        clock = ArrangedClock()
        keeper = asyncio.create_task(_keep_lease(URL, lease, CONFIG, clock))
        await asyncio.sleep(0.3)
        clock.sleep_for(600)
        await db.execute("update app_private.run_usage set segment_started_at = segment_started_at - interval '600 seconds' where run_id = %s", (run,))
        await expire(db, run)
        await asyncio.sleep(0.6)
        check('after a sleep the keeper revives its expired lease and carries on', 'live, still running', (await live(db, run), keeper.done()), await live(db, run) and not keeper.done())
        used = await active_seconds_used(db, run)
        check('the time asleep comes off the active time', 'under 60 of 600 seconds', round(used, 1), used < 60)
        keeper.cancel()

        # No gap between the clocks, as with SIGSTOP or a hung process: nothing changes.
        run = await admitted(db)
        lease = await claim_run(db, run, worker_id='stalled')
        keeper = asyncio.create_task(_keep_lease(URL, lease, CONFIG, ArrangedClock()))
        await asyncio.sleep(0.2)
        await expire(db, run)
        await asyncio.sleep(0.4)
        check('with no sleep an expired lease stays lost', 'expired, keeper ended', (await live(db, run), keeper.done()), not await live(db, run) and keeper.done())
        keeper.cancel()
    print(json.dumps({'cases': cases}))


try:
    asyncio.run(main())
except Exception:
    print(json.dumps({'cases': cases}))
    raise
