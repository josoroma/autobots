"""A real worker process: it claims, runs a real graph, and can kill itself at a chosen node."""
from __future__ import annotations

import asyncio
import os
import signal
import sys
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).parent))
from autobots.adapters.checkpoints import DURABILITY, fenced_checkpointer, graph_config
from autobots.application.worker_leases import claim_next
from worker_graph import build

URL, LOG, DIE_AT, LEASE_SECONDS = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4])


def die(node: str) -> None:
    if node == DIE_AT:
        os.kill(os.getpid(), signal.SIGKILL)


async def main() -> None:
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as connection:
        lease = await claim_next(connection, worker_id='first-worker', lease_seconds=LEASE_SECONDS)
    assert lease is not None
    print(lease.run_id, flush=True)
    async with fenced_checkpointer(URL, lease) as saver:
        await build(saver, LOG, die).ainvoke({'seen': []}, graph_config(lease), durability=DURABILITY)


asyncio.run(main())
