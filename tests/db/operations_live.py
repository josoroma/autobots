"""US-15.18: two live worker heartbeats while a browser reads Operations, then stopped again.

`start` writes two fresh heartbeats from workers that can call a model. `stop` marks them stopped, so a
later suite that expects no worker finds none. Nothing else is changed.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

import psycopg

WORKERS = ('arranged-ops-worker-1', 'arranged-ops-worker-2')


async def main() -> None:
    action = sys.argv[1]
    async with await psycopg.AsyncConnection.connect(os.environ['AUTOBOTS_DATABASE_URL'], autocommit=True) as db:
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
