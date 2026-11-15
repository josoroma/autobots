"""US-15.17: moves an arranged running run's version while a browser holds its panel open.

The current worker verifies and then repairs, two canonical transitions that leave it running.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from uuid import UUID

import psycopg
from autobots.application.runs import apply_worker_command
from autobots.application.worker_leases import Lease
from autobots.domain.runs import RunCommand


async def main() -> None:
    run_id, generation, workspace = UUID(sys.argv[1]), int(sys.argv[2]), UUID(sys.argv[3])
    async with await psycopg.AsyncConnection.connect(os.environ['AUTOBOTS_DATABASE_URL'], autocommit=True) as db:
        version = (await (await db.execute('select version from public.runs where id = %s', (run_id,))).fetchone())[0]
        holder = Lease(run_id, workspace, generation, 'arranged', 1, 'running')
        await apply_worker_command(db, holder, RunCommand.VERIFY)
        repaired = await apply_worker_command(db, holder, RunCommand.REPAIR)
    print(json.dumps({'from': version, 'to': repaired.version, 'status': repaired.status}))


asyncio.run(main())
