"""Runs a browser test needs in a state no screen can reach by itself, on a disposable stack. JSON out.

One waits on an approval with a plan and a published artifact. One finished in a workspace with no key.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import psycopg
from autobots.adapters.object_storage import SupabaseObjectStore
from autobots.application.experts import create_expert, create_session
from autobots.application.goal_loop import drive_lease
from autobots.application.run_lifecycle import LoopConfig
from autobots.application.runs import admit_run
from autobots.application.worker_leases import claim_run
from autobots.contracts.experts import ExpertConfig, SessionExpert
from autobots.domain.models import resolve_role_policy
from autobots.domain.tools import LOOP_TOOL_GRANTS, PLAN_TOOLS
from effect_tools import tools
from goal_loop_script import ROUTE, Script, calls, say
from mock_sink import Sink
from pydantic import SecretStr

URL = os.environ['AUTOBOTS_DATABASE_URL']
BASE = os.environ['AUTOBOTS_STORAGE_BASE']
SERVICE = SecretStr(os.environ['AUTOBOTS_STORAGE_SERVICE'])
TASK = {'id': 'report', 'title': 'Write the report', 'criteria': ['c1'], 'expected_evidence': 'the published report'}
PLAN = ('propose_plan', {'tasks': [TASK]})
SAVE = ('save_artifact', {'path': 'outputs/report.md', 'content': '# Report\n\nTotal: 5\n'})
PUBLISH = ('publish_artifact', {'path': 'outputs/report.md', 'version': 1})
DONE = ('complete_task', {'task_id': 'report', 'evidence': [{'kind': 'artifact', 'reference': 'outputs/report.md'}], 'summary': 'Wrote it.'})


async def main() -> None:
    waiting_in, keyless_in = UUID(sys.argv[1]), UUID(sys.argv[2])
    store = SupabaseObjectStore(BASE, SERVICE)
    config = LoopConfig(route=ROUTE, object_store=store, sleep=lambda _: asyncio.sleep(0),
                        tools=tools(Sink(Path(tempfile.mkdtemp()) / 'sink.log')))
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        async def run(workspace: UUID, goal: str, items: list, granted: dict) -> str:
            binding = SimpleNamespace(session_id=None, expert_id=None, version=None, instructions='', tools=granted)
            accepted = await admit_run(db, workspace_id=workspace, actor_id=uuid4(), idempotency_key=str(uuid4()), goal_text=goal,
                                       limit_micro_usd=1_000_000, policy=resolve_role_policy(), binding=binding)
            lease = await claim_run(db, accepted.run_id, worker_id='browser-arrangement')
            await drive_lease(db, URL, lease, lambda: Script(items=items, seen=[], bound=[]), config)
            return str(accepted.run_id)

        waiting = await run(waiting_in, 'A plan, an artifact and a pending approval',
                            [calls(PLAN), calls(SAVE), calls(PUBLISH), calls(('send_blind', {'body': 'a note'})), say('never')],
                            {**LOOP_TOOL_GRANTS, 'send_blind': 1})
        finished = await run(keyless_in, 'An artifact in a workspace with no key',
                             [calls(PLAN), calls(SAVE), calls(PUBLISH), calls(DONE), say('The report is ready.')],
                             {**PLAN_TOOLS, **LOOP_TOOL_GRANTS})
        # A saved binding no write can make now, for the screens that have to say so.
        stale = await create_expert(db, workspace_id=waiting_in, actor_id=uuid4(), idempotency_key=str(uuid4()), name='Saved on DeepSeek',
                                    config=ExpertConfig(tools=['calculate'], role_bindings={'executor': 'openrouter_deepseek_flash', 'coder': 'openrouter_deepseek_flash'}))
        pinned = await create_session(db, workspace_id=waiting_in, actor_id=uuid4(), idempotency_key=str(uuid4()), kind='direct', experts=[SessionExpert(expert_id=stale.id)])
        states = {}
        for name, run_id in (('waiting', waiting), ('finished', finished)):
            states[name] = (await (await db.execute('select status from public.runs where id = %s', (run_id,))).fetchone())[0]
    print(json.dumps({'waiting_run': waiting, 'keyless_run': finished, 'stale_session': str(pinned.id), 'stale_expert': str(stale.id), 'states': states}))


asyncio.run(main())
