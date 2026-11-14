"""A real worker process that kills itself inside its third model call."""
from __future__ import annotations

import asyncio
import os
import signal
import sys
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).parent))
from autobots.application.goal_loop import LoopConfig, run_goal
from autobots.application.worker_leases import claim_next
from goal_loop_script import PLAN, ROUTE, SAVE, Script, calls

URL = sys.argv[1]


def die() -> None:
    os.kill(os.getpid(), signal.SIGKILL)


async def main() -> None:
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        lease = await claim_next(db, worker_id='first-worker', lease_seconds=60)
        assert lease is not None
        model = Script(items=[calls(PLAN), calls(SAVE), die], seen=[], bound=[])
        await run_goal(db, URL, lease, model, LoopConfig(route=ROUTE))


asyncio.run(main())
