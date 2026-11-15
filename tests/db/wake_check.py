"""Wake handling against a real database, with an arranged clock, US-11.10.

Only a real sleep proves the fix. This covers what a sleep can't arrange on demand: that fencing still holds, and
that a stall with no clock gap, such as SIGSTOP, gets none of this.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from unittest.mock import patch
from uuid import UUID, uuid4

import psycopg
from autobots.adapters.loop_middleware import ModelRoute
from autobots.application import run_lifecycle
from autobots.application.run_lifecycle import LeaseKeeper, LoopConfig
from autobots.application.run_usage import (
    active_seconds_used,
    begin_segment,
    discount_sleep,
    end_segment,
    ensure_usage,
)
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
        await begin_segment(db, lease)
        await asyncio.sleep(0.2)
        clock = ArrangedClock()
        keeper = asyncio.create_task(LeaseKeeper(URL, lease, CONFIG, clock).run())
        await asyncio.sleep(0.3)
        clock.sleep_for(600)
        await db.execute("update app_private.run_usage set segment_started_at = segment_started_at - interval '600 seconds' where run_id = %s", (run,))
        await expire(db, run)
        await asyncio.sleep(0.6)
        check('after a sleep the keeper revives its expired lease and carries on', 'live, still running', (await live(db, run), keeper.done()), await live(db, run) and not keeper.done())
        used = await active_seconds_used(db, run)
        check('the time asleep comes off the active time', 'under 60 of 600 seconds', round(used, 1), used < 60)
        keeper.cancel()

        # A sleep can drop the keeper's connection, and it comes back and goes on.
        run = await admitted(db)
        lease = await claim_run(db, run, worker_id='waking')
        keeper = asyncio.create_task(LeaseKeeper(URL, lease, CONFIG, ArrangedClock()).run())
        await asyncio.sleep(0.3)
        await db.execute("select pg_terminate_backend(pid) from pg_stat_activity where usename = current_user and pid <> pg_backend_pid()")
        await db.execute("update app_private.run_jobs set lease_expires_at = clock_timestamp() + interval '5 seconds' where run_id = %s", (run,))
        await asyncio.sleep(1.5)
        left = (await (await db.execute('select extract(epoch from lease_expires_at - clock_timestamp()) from app_private.run_jobs where run_id = %s', (run,))).fetchone())[0]
        check('a dropped connection leaves the keeper running, and still beating', 'alive, the lease back near 60 seconds', (keeper.done(), round(float(left))), not keeper.done() and float(left) > 30)
        keeper.cancel()

        # A discount applied while the database's clock lags a wake, as Docker's does by half a minute.
        run = await admitted(db)
        lease = await claim_run(db, run, worker_id='lagging')
        await db.execute('insert into app_private.run_usage (run_id) values (%s) on conflict do nothing', (run,))
        await begin_segment(db, lease)
        await discount_sleep(db, lease, 600)
        ahead = (await (await db.execute('select extract(epoch from segment_started_at - clock_timestamp()) from app_private.run_usage where run_id = %s', (run,))).fetchone())[0]
        check('a discount stands though the clock has not caught up yet', 'the segment starts about 600 seconds ahead', round(float(ahead)), 590 < float(ahead) <= 600)
        used = await active_seconds_used(db, run)
        check('and meanwhile the active time reads zero, not negative', '0', used, used == 0)
        # The clock now jumps by the whole sleep. Moving the segment back is the same thing, as only the difference counts.
        await db.execute("update app_private.run_usage set segment_started_at = segment_started_at - interval '600 seconds' where run_id = %s", (run,))
        used = await active_seconds_used(db, run)
        check("the jump doesn't count the sleep as work", 'under 60 of 600 seconds', round(used, 1), used < 60)

        # With a long beat, only the beat forced after reconnecting can renew the lease in time.
        run = await admitted(db)
        lease = await claim_run(db, run, worker_id='forced')
        keeper = asyncio.create_task(LeaseKeeper(URL, lease, LoopConfig(route=ROUTE, heartbeat_seconds=3, lease_seconds=60), ArrangedClock()).run())
        await asyncio.sleep(0.3)
        await db.execute("select pg_terminate_backend(pid) from pg_stat_activity where usename = current_user and pid <> pg_backend_pid()")
        await db.execute("update app_private.run_jobs set lease_expires_at = clock_timestamp() + interval '20 seconds' where run_id = %s", (run,))
        await asyncio.sleep(5.5)
        left = (await (await db.execute('select extract(epoch from lease_expires_at - clock_timestamp()) from app_private.run_jobs where run_id = %s', (run,))).fetchone())[0]
        check('the first look after reconnecting beats, without waiting for the next beat', 'near 60 seconds by 5.8s, before the next regular beat at about 7s', round(float(left)), float(left) > 40 and not keeper.done())
        keeper.cancel()

        # Any other failure reconnects too, and the keeper goes on.
        run = await admitted(db)
        lease = await claim_run(db, run, worker_id='unusual')
        real, raised = run_lifecycle.heartbeat, []

        async def raises_once(*args: object, **options: object) -> object:
            if not raised:
                raised.append(True)
                raise RuntimeError('arranged')
            return await real(*args, **options)

        with patch.object(run_lifecycle, 'heartbeat', raises_once):
            keeper = asyncio.create_task(LeaseKeeper(URL, lease, CONFIG, ArrangedClock()).run())
            await asyncio.sleep(0.4)
            await db.execute("update app_private.run_jobs set lease_expires_at = clock_timestamp() + interval '5 seconds' where run_id = %s", (run,))
            await asyncio.sleep(1.5)
            left = (await (await db.execute('select extract(epoch from lease_expires_at - clock_timestamp()) from app_private.run_jobs where run_id = %s', (run,))).fetchone())[0]
            check('an unexpected error leaves the keeper running, and still beating', 'alive, the lease back near 60 seconds', (keeper.done(), round(float(left))), raised and not keeper.done() and float(left) > 40)
            keeper.cancel()

        # A worker that lost the run can't move the new owner's clock.
        run = await admitted(db)
        lost = await claim_run(db, run, worker_id='lost')
        await expire(db, run)
        owner = await claim_run(db, run, worker_id='new')
        await begin_segment(db, owner)
        before = await active_seconds_used(db, run)
        await discount_sleep(db, lost, 500)
        after = await active_seconds_used(db, run)
        check('a lost worker can\'t discount the new owner\'s time', 'unchanged', (round(before, 1), round(after, 1)), after >= before)

        # PRUN-20: nor restart or end the new owner's segment, though the lost worker's own pass still ends.
        run = await admitted(db)
        lost = await claim_run(db, run, worker_id='lost-segment')
        await ensure_usage(db, run)
        await begin_segment(db, lost)
        await expire(db, run)
        owner = await claim_run(db, run, worker_id='new-segment')
        await begin_segment(db, owner)
        segment = 'select segment_started_at, active_seconds from app_private.run_usage where run_id = %s'
        started = await (await db.execute(segment, (run,))).fetchone()
        await begin_segment(db, lost)
        await end_segment(db, lost)
        kept = await (await db.execute(segment, (run,))).fetchone()
        check("a lost worker can't restart or end the new owner's segment", 'the same open segment, nothing counted',
              (kept[0] == started[0], float(kept[1])), kept[0] is not None and kept[0] == started[0] and float(kept[1]) == 0)
        await asyncio.sleep(0.2)
        await end_segment(db, owner)
        closed = await (await db.execute(segment, (run,))).fetchone()
        check('the owner ends its own segment and its time counts', 'closed, over 0.1 seconds counted',
              (closed[0], round(float(closed[1]), 2)), closed[0] is None and float(closed[1]) > 0.1)

        # No gap between the clocks, as with SIGSTOP or a hung process: nothing changes.
        run = await admitted(db)
        lease = await claim_run(db, run, worker_id='stalled')
        keeper = asyncio.create_task(LeaseKeeper(URL, lease, CONFIG, ArrangedClock()).run())
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
