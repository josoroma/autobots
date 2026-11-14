"""A real parent worker that kills itself inside its child's model call."""
from __future__ import annotations

import asyncio
import os
import signal
import sys
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).parent))
from autobots.application.goal_loop import LoopConfig, process_next
from goal_loop_script import ROUTE, Script, calls

URL, EXPERT = sys.argv[1], sys.argv[2]
TASK = {'id': 'p', 'title': 'Delegate', 'criteria': ['c1'], 'expected_evidence': 'a result'}


def die() -> None:
    os.kill(os.getpid(), signal.SIGKILL)


async def main() -> None:
    plan = ('propose_plan', {'tasks': [TASK]})
    assign = ('assign_specialist', {'expert_id': EXPERT, 'goal': 'Do the part'})
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        model = Script(items=[calls(plan), calls(assign), die], seen=[], bound=[])
        await process_next(db, URL, 'first-parent', lambda: model, LoopConfig(route=ROUTE, lease_seconds=60))


asyncio.run(main())
