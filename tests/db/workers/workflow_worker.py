"""A real worker process that dies after a chosen workflow instance has committed."""
from __future__ import annotations

import asyncio
import os
import signal
import sys

import psycopg
from autobots.adapters import tool_registry
from autobots.adapters.loop_middleware import ModelRoute
from autobots.adapters.object_storage import SupabaseObjectStore
from autobots.application.run_lifecycle import LoopConfig
from autobots.application.worker_leases import claim_next
from autobots.application.workflow_runner import run_workflow
from autobots.operations.job_dispatch import drive_lease
from pydantic import SecretStr

URL, BASE, DIE_AFTER = sys.argv[1], sys.argv[2], sys.argv[3]
ROUTE = ModelRoute('executor', 'openrouter_terra', 'fixture/model', 1000)


def die_after(step: object) -> None:
    if getattr(step, 'key', '') == DIE_AFTER:
        os.kill(os.getpid(), signal.SIGKILL)


async def main() -> None:
    store = SupabaseObjectStore(BASE, SecretStr(os.environ['AUTOBOTS_STORAGE_SERVICE']))
    config = LoopConfig(route=ROUTE, object_store=store, lease_seconds=60, tool_set=tool_registry.build_registry)
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        lease = await claim_next(db, worker_id='dying', lease_seconds=60)
        assert lease is not None
        await run_workflow(db, URL, lease, None, config, drive=drive_lease, after_commit=die_after)


asyncio.run(main())
