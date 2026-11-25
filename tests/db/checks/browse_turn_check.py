"""US-20.3 and Decision 0038 Z12 on a real database: one stealth browse of a site at a time across the install. JSON cases.

Each connection stands in for a worker's attempt. No browser or model is involved: what a browse does in its turn is a
wait the check controls.
"""
from __future__ import annotations

import asyncio
import os
import time

import psycopg
from autobots.application.browse_turns import SiteBusy, TurnLost, turn
from checklib import Cases, run_check, run_scenarios

URL = os.environ['AUTOBOTS_DATABASE_URL']


async def connect() -> psycopg.AsyncConnection[tuple[object, ...]]:
    return await psycopg.AsyncConnection.connect(URL, autocommit=True)


async def alive() -> bool:
    return True


async def try_turn(domains: list[str], seconds: float, hold: float = 0.0) -> tuple[str, float]:
    """One attempt's browse on its own connection: how its turn ended, and how long it waited."""
    began = time.monotonic()
    async with await connect() as db:
        try:
            async with turn(db, domains, seconds, alive):
                waited = time.monotonic() - began
                await asyncio.sleep(hold)
                return 'ran', waited
        except (SiteBusy, TurnLost) as ended:
            return type(ended).__name__, time.monotonic() - began


async def waits_or_gives_up(cases: Cases) -> None:
    first = asyncio.create_task(try_turn(['www.example.com'], 30, hold=4))
    await asyncio.sleep(0.5)
    outlasts, short, other = await asyncio.gather(try_turn(['example.com'], 30), try_turn(['blog.example.com'], 1),
                                                  try_turn(['example.org'], 1))
    ran = await first
    cases.check('a second browse of a site waits and runs after the first, and one whose time is up never runs',
                'the first at once, the second 3 to 8 seconds later, the third SiteBusy, another site at once',
                (ran, outlasts, short, other),
                ran[0] == 'ran' and ran[1] < 1 and outlasts[0] == 'ran' and 3 <= outlasts[1] < 8 and short[0] == 'SiteBusy'
                and other[0] == 'ran' and other[1] < 1)


async def freed_however_it_ends(cases: Cases) -> None:
    lost = await connect()
    held = turn(lost, ['lost.test'], 5, alive)
    await held.__aenter__()
    busy = await try_turn(['lost.test'], 1)
    # A worker that dies takes its connection with it. This process held the site's own note of it too.
    await lost.close()
    await held.__aexit__(None, None, None)
    after_loss = await try_turn(['lost.test'], 5)

    cancelled = asyncio.create_task(try_turn(['cancel.test'], 5, hold=60))
    await asyncio.sleep(0.5)
    cancelled.cancel()
    await asyncio.gather(cancelled, return_exceptions=True)
    after_cancel = await try_turn(['cancel.test'], 5)

    async with await connect() as db:
        rows = await (await db.execute("select count(*) from pg_locks where locktype = 'advisory' and granted")).fetchone()
    cases.check('a site is free again when its browse is cancelled or its worker is lost, and no turn is left held',
                'SiteBusy while held, then free twice, and no advisory lock left', (busy[0], after_loss[0], after_cancel[0], rows),
                busy[0] == 'SiteBusy' and after_loss[0] == 'ran' and after_cancel[0] == 'ran' and rows is not None and rows[0] == 0)


async def overlapping_sites(cases: Cases) -> None:
    results = await asyncio.wait_for(asyncio.gather(*(try_turn(domains, 30, hold=0.5) for domains in (
        ['a.test', 'b.test'], ['b.test', 'a.test'], ['b.test', 'c.test'], ['c.test', 'a.test']))), 60)
    cases.check('calls that name several sites never wait for each other', 'all four run, one after another', results,
                all(result[0] == 'ran' for result in results))


SCENARIOS = (waits_or_gives_up, freed_however_it_ends, overlapping_sites)


async def main(cases: Cases) -> None:
    await run_scenarios(cases, SCENARIOS, cases)


if __name__ == '__main__':
    run_check(main, parent_timeout=180)
