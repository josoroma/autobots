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
from autobots.application.runs import apply_command
from autobots.domain.runs import Actor, RunCommand


async def main() -> None:
    run_id, generation, workspace = UUID(sys.argv[1]), int(sys.argv[2]), UUID(sys.argv[3])
    async with await psycopg.AsyncConnection.connect(os.environ['AUTOBOTS_DATABASE_URL'], autocommit=True) as db:
        version = (await (await db.execute('select version from public.runs where id = %s', (run_id,))).fetchone())[0]
        verified = await apply_command(db, workspace_id=workspace, run_id=run_id, command=RunCommand.VERIFY, actor=Actor.WORKER,
                                       expected_version=version, generation=generation)
        repaired = await apply_command(db, workspace_id=workspace, run_id=run_id, command=RunCommand.REPAIR, actor=Actor.WORKER,
                                       expected_version=verified.version, generation=generation)
    print(json.dumps({'from': version, 'to': repaired.version, 'status': repaired.status}))


asyncio.run(main())
