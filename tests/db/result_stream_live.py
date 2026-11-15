"""US-15.24: a run that writes its result slowly while a browser watches it.

Prints the run's ID at once, waits for the page to connect, then drives the run with a streaming
scripted model whose pieces are spaced out, and prints the outcome when the result is stored.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from types import SimpleNamespace
from uuid import UUID, uuid4

import psycopg
from autobots.adapters.object_storage import SupabaseObjectStore
from autobots.application.goal_loop import drive_lease
from autobots.application.run_lifecycle import LoopConfig
from autobots.application.runs import admit_run
from autobots.application.worker_leases import claim_run
from autobots.domain.models import resolve_role_policy
from autobots.domain.tools import LOOP_TOOL_GRANTS
from goal_loop_script import ROUTE, calls, say
from pydantic import SecretStr
from stream_script import StreamScript

CONTENT = '# Live report\n\n' + ''.join(f'Paragraph {n}: the running total is {n * 11}, written as it goes.\n' for n in range(1, 41))
TASK = {'id': 'report', 'title': 'Write the report', 'criteria': ['c1'], 'expected_evidence': 'the published report'}


async def main() -> None:
    workspace, delay, wait = UUID(sys.argv[1]), float(sys.argv[2]), float(sys.argv[3])
    url = os.environ['AUTOBOTS_DATABASE_URL']
    store = SupabaseObjectStore(os.environ['AUTOBOTS_STORAGE_BASE'], SecretStr(os.environ['AUTOBOTS_STORAGE_SERVICE']))
    config = LoopConfig(route=ROUTE, object_store=store, sleep=lambda _: asyncio.sleep(0))
    steps = [calls(('propose_plan', {'tasks': [TASK]})),
             calls(('save_artifact', {'path': 'outputs/report.md', 'content': CONTENT})),
             calls(('publish_artifact', {'path': 'outputs/report.md', 'version': 1})),
             calls(('complete_task', {'task_id': 'report', 'evidence': [{'kind': 'artifact', 'reference': 'outputs/report.md'}], 'summary': 'Wrote it.'})),
             say('The report is ready.')]
    async with await psycopg.AsyncConnection.connect(url, autocommit=True) as db:
        binding = SimpleNamespace(session_id=None, expert_id=None, version=None, instructions='', tools=dict(LOOP_TOOL_GRANTS))
        admitted = await admit_run(db, workspace_id=workspace, actor_id=uuid4(), idempotency_key=str(uuid4()), goal_text='Write the live report',
                                   limit_micro_usd=1_000_000, policy=resolve_role_policy(), binding=binding)
        lease = await claim_run(db, admitted.run_id, worker_id='result-stream-live')
        assert lease is not None
        print(json.dumps({'run_id': str(admitted.run_id), 'content_length': len(CONTENT)}), flush=True)
        await asyncio.sleep(wait)
        model = StreamScript(items=steps, seen=[], bound=[], delay=delay, chunked=[])
        await drive_lease(db, url, lease, lambda: model, config)
        status = (await (await db.execute('select status from public.runs where id = %s', (admitted.run_id,))).fetchone())[0]
        durable = (await (await db.execute("select count(*) from public.run_events where run_id = %s and payload ->> 'type' = 'result.text.delta'",
                                           (admitted.run_id,))).fetchone())[0]
    print(json.dumps({'run_id': str(admitted.run_id), 'status': status, 'durable_deltas': durable, 'content': CONTENT}), flush=True)


asyncio.run(main())
