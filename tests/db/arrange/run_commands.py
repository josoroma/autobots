"""The run commands the operations, backup and upgrade qualifiers arrange through the product's own code
and the runtime role: `admit <workspace>` queues one fixture job and prints its run, and `cancel` and
`resume <workspace> <run>` apply a person's command at the run's current version. Split from
tests/db/checks/operations_check.py, which keeps the retention check (TDBC-09)."""
from __future__ import annotations

import asyncio
import os
import sys
from uuid import UUID, uuid4

import psycopg
from autobots.application.runs import admit_run, apply_command
from autobots.domain.models import resolve_role_policy
from autobots.domain.runs import RunCommand

URL = os.environ['AUTOBOTS_DATABASE_URL']


async def admit(workspace: str) -> None:
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        accepted = await admit_run(db, workspace_id=UUID(workspace), actor_id=uuid4(), idempotency_key=str(uuid4()),
                                   goal_text='Write the report', limit_micro_usd=1_000_000, policy=resolve_role_policy())
        print(accepted.run_id)


async def resume(workspace: str, run: str) -> None:
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        version = (await (await db.execute("select version from public.runs where id = %s", (run,))).fetchone())[0]
        await apply_command(db, workspace_id=UUID(workspace), run_id=UUID(run), command=RunCommand.RESUME, expected_version=version)


async def cancel(workspace: str, run: str) -> None:
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        version = (await (await db.execute("select version from public.runs where id = %s", (run,))).fetchone())[0]
        await apply_command(db, workspace_id=UUID(workspace), run_id=UUID(run), command=RunCommand.CANCEL, expected_version=version)


COMMANDS = {'admit': admit, 'cancel': cancel, 'resume': resume}

if __name__ == '__main__':
    asyncio.run(COMMANDS[sys.argv[1]](*sys.argv[2:]))
