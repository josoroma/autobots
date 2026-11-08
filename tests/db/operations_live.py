"""US-15.18 and US-15.19: what a browser needs while it reads Operations.

`start` writes two fresh heartbeats from workers that can call a model, and `stop` marks them stopped,
so a later suite that expects no worker finds none. `jobs` gives the operations workspace runs whose
status changes fall at fixed offsets from the database's clock, for the jobs chart: in the hours 1, 2, 3
and 5 before the current one, and one 30 hours ago that the chart must leave out. It writes each once.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

import psycopg

WORKERS = ('arranged-ops-worker-1', 'arranged-ops-worker-2')
# Run, its status now, and its status changes as (hours ago, status), oldest first.
JOBS = (
    ('99999999-9999-4999-8999-0000000000c1', 'succeeded', ((2, 'succeeded'),)),
    ('99999999-9999-4999-8999-0000000000c2', 'waiting_approval', ((2, 'waiting_approval'),)),
    ('99999999-9999-4999-8999-0000000000c3', 'waiting_input', ((5, 'waiting_input'),)),
    ('99999999-9999-4999-8999-0000000000c4', 'failed', ((1, 'failed'),)),
    ('99999999-9999-4999-8999-0000000000c5', 'cancelled', ((1, 'cancelled'),)),
    ('99999999-9999-4999-8999-0000000000c6', 'paused', ((4, 'running'), (3, 'paused'))),
    ('99999999-9999-4999-8999-0000000000c7', 'running', ((3, 'running'),)),
    ('99999999-9999-4999-8999-0000000000c8', 'succeeded', ((30, 'succeeded'),)),
)


async def jobs(db: psycopg.AsyncConnection, workspace: str) -> None:
    for run, status, changes in JOBS:
        created = await db.execute("insert into public.runs (id, workspace_id, status, goal_summary, limit_micro_usd, policy_snapshot, event_sequence) "
                                   "values (%s, %s, %s, 'Arranged chart job', 1000000, '{}', %s) on conflict (id) do nothing", (run, workspace, status, len(changes)))
        if created.rowcount == 0:
            continue
        previous = 'queued'
        for sequence, (hours, current) in enumerate(changes, start=1):
            # Exactly that many hours before now, so it falls that many hours before the current one.
            await db.execute("insert into public.run_events (run_id, sequence, schema_version, payload, occurred_at) "
                             "values (%s, %s, 1, %s, now() - make_interval(hours => %s))",
                             (run, sequence, json.dumps({'type': 'run.status_changed', 'previous': previous, 'current': current}), hours))
            previous = current


async def main() -> None:
    action = sys.argv[1]
    async with await psycopg.AsyncConnection.connect(os.environ['AUTOBOTS_DATABASE_URL'], autocommit=True) as db:
        if action == 'jobs':
            await jobs(db, os.environ['AUTOBOTS_TEST_OPS_WORKSPACE'])
            now = await (await db.execute('select now()')).fetchone()
            print(json.dumps({'action': action, 'now': now[0].isoformat()}))
            return
        for worker in WORKERS:
            if action == 'start':
                await db.execute("insert into app_private.worker_heartbeats (worker_id, state, claims_inference) values (%s, 'running', true) "
                                 "on conflict (worker_id) do update set state = 'running', claims_inference = true, beat_at = now()", (worker,))
            else:
                await db.execute("update app_private.worker_heartbeats set state = 'stopped', beat_at = now() where worker_id = %s", (worker,))
        live = await (await db.execute("select count(*) from app_private.worker_heartbeats where state <> 'stopped' "
                                       "and beat_at >= clock_timestamp() - interval '60 seconds'")).fetchone()
    print(json.dumps({'action': action, 'live': live[0]}))


asyncio.run(main())
