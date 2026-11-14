"""A real worker with a short lease and a model call that takes a while. Its parent stops it with SIGSTOP."""
from __future__ import annotations

import asyncio
import json
import sys
import time

import psycopg
from autobots.application.goal_loop import LoopConfig, run_goal
from autobots.application.worker_leases import claim_next
from goal_loop_script import PLAN, ROUTE, SAVE, Script, calls, say
from langchain_core.messages import AIMessage

URL = sys.argv[1]


def wait() -> AIMessage:
    time.sleep(3)
    return calls(SAVE)


async def main() -> None:
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        lease = await claim_next(db, worker_id='sleeper', lease_seconds=2)
        assert lease is not None
        model = Script(items=[calls(PLAN), wait, say('x')], seen=[], bound=[])
        config = LoopConfig(route=ROUTE, heartbeat_seconds=0.5, lease_seconds=2)
        result = await run_goal(db, URL, lease, model, config)
    print(json.dumps({'outcome': result.outcome, 'code': result.code}))


asyncio.run(main())
