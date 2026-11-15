"""A real worker process that kills itself inside its third model call."""
from __future__ import annotations

import asyncio
import os
import signal
import sys

import psycopg
from autobots.adapters import tool_registry
from autobots.application.goal_loop import run_goal
from autobots.application.run_lifecycle import LoopConfig
from autobots.application.worker_leases import claim_next
from autobots.operations.job_dispatch import drive_lease
from goal_loop_script import PLAN, ROUTE, SAVE, Script, calls

URL = sys.argv[1]


def die() -> None:
    os.kill(os.getpid(), signal.SIGKILL)


async def main() -> None:
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        lease = await claim_next(db, worker_id='first-worker', lease_seconds=60)
        assert lease is not None
        model = Script(items=[calls(PLAN), calls(SAVE), die], seen=[], bound=[])
        await run_goal(db, URL, lease, model, LoopConfig(route=ROUTE, tool_set=tool_registry.build_registry), drive=drive_lease)


asyncio.run(main())
