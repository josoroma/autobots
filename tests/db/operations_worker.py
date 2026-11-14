"""The product's `serve` loop driving the real goal loop with a scripted model. No provider is involved."""
from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

from autobots.adapters.loop_middleware import ModelRoute
from autobots.adapters.object_storage import SupabaseObjectStore
from autobots.application.goal_loop import LoopConfig, process_next
from autobots.operations.logs import configure_logging, forbid_remote_tracing, log_event
from autobots.operations.worker import WorkerConfig, install_signal_handlers, serve
from goal_loop_script import DONE_A, ROUTE, SAVE, TASK_A, Script, calls, say
from pydantic import SecretStr

URL = sys.argv[1]
NAME = sys.argv[2]
HOLD = float(sys.argv[3])
DRAIN = float(sys.argv[4])
MARKER = Path(sys.argv[5])
RESUME = sys.argv[6] == 'resume'
PLAN = ('propose_plan', {'tasks': [TASK_A]})
PUBLISH = ('publish_artifact', {'path': 'outputs/a.md', 'version': 1})


def slow() -> Any:
    """Inside a model call: a marker for the parent, then the time a real call could take."""
    MARKER.write_text('in-call')
    time.sleep(HOLD)
    return calls(SAVE)


def script() -> Script:
    if RESUME:
        return Script(items=[calls(SAVE), calls(PUBLISH), calls(DONE_A), say('finished')], seen=[], bound=[])
    return Script(items=[calls(PLAN), slow, calls(PUBLISH), calls(DONE_A), say('finished')], seen=[], bound=[])


async def main() -> None:
    forbid_remote_tracing(os.environ)
    configure_logging()
    # Arranged: a secret-shaped value and a connection string go through the real logger.
    log_event(logging.getLogger('autobots.fixture'), f'connected {URL} with sk-or-v1-planted-log-secret')
    stop = asyncio.Event()
    install_signal_handlers(stop)

    store = SupabaseObjectStore(os.environ['AUTOBOTS_STORAGE_BASE'], SecretStr(os.environ['AUTOBOTS_STORAGE_SERVICE']))
    # This fixture has one route, where the real worker binds each run's own. A saved run keeps its model.
    route = ModelRoute(ROUTE.role, os.environ.get('AUTOBOTS_TEST_ROUTE_PROFILE', ROUTE.profile), ROUTE.wire_id, ROUTE.worst_case_micro_usd)

    async def step(connection: Any) -> bool:
        result = await process_next(connection, URL, NAME, script, LoopConfig(route=route, object_store=store, lease_seconds=8, heartbeat_seconds=2))
        return result is not None

    await serve(WorkerConfig(worker_id=NAME, database_url=URL, claims_inference=True, idle_seconds=0.3, beat_seconds=1, drain_seconds=DRAIN), step, stop)


asyncio.run(main())
