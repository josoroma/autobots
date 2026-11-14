"""US-15.21: two runs that start waiting for a person while a browser has the app open.

Each run is admitted, claimed by a worker, and moved by that worker through its canonical transition:
one to waiting_approval and one to waiting_input. Prints their ids.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from uuid import UUID, uuid4

import psycopg
from autobots.application.runs import admit_run, apply_command
from autobots.application.worker_leases import claim_run
from autobots.domain.models import resolve_role_policy
from autobots.domain.runs import Actor, RunCommand


async def main() -> None:
    workspace, label = UUID(sys.argv[1]), sys.argv[2]
    made = {}
    async with await psycopg.AsyncConnection.connect(os.environ['AUTOBOTS_DATABASE_URL'], autocommit=True) as db:
        for command in (RunCommand.REQUEST_APPROVAL, RunCommand.REQUEST_INPUT):
            admitted = await admit_run(db, workspace_id=workspace, actor_id=uuid4(), idempotency_key=str(uuid4()),
                                       goal_text=f'Notify check {label}: {command.value}', limit_micro_usd=1_000_000, policy=resolve_role_policy())
            lease = await claim_run(db, admitted.run_id, worker_id=f'notify-{label}', lease_seconds=120)
            assert lease is not None
            version = (await (await db.execute('select version from public.runs where id = %s', (admitted.run_id,))).fetchone())[0]
            moved = await apply_command(db, workspace_id=workspace, run_id=admitted.run_id, command=command, actor=Actor.WORKER,
                                        expected_version=version, generation=lease.generation, detail='arranged for the notification check')
            made[moved.status] = str(admitted.run_id)
    print(json.dumps(made))


asyncio.run(main())
