"""A real worker process that dies right after its effect reached the destination."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).parent))
from autobots.application.goal_loop import LoopConfig, process_next
from effect_tools import tools
from goal_loop_script import ROUTE, Script
from mock_sink import Sink

URL, SINK, BODY = sys.argv[1], sys.argv[2], sys.argv[3]


async def main() -> None:
    config = LoopConfig(route=ROUTE, tools=tools(Sink(SINK), behavior={BODY: 'die_after'}), lease_seconds=60)
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        await process_next(db, URL, 'dying', lambda: Script(items=[], seen=[], bound=[]), config)


asyncio.run(main())
