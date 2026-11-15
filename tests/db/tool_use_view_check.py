"""US-14.4's arranged runs: a claimed run with tool uses that a browser test extends live, and a
workflow execution whose nodes used tools. JSON cases, and the values the browser suite needs."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import psycopg
from autobots.adapters import tool_registry
from autobots.adapters.object_storage import SupabaseObjectStore
from autobots.adapters.tool_registry import build_registry
from autobots.application.run_lifecycle import LoopConfig
from autobots.application.runs import admit_run
from autobots.application.tool_definitions import ToolScope
from autobots.application.tool_gateway import ToolGateway
from autobots.application.tool_uses import list_tool_uses
from autobots.application.worker_leases import claim_next
from autobots.application.workflows import create_execution, create_workflow, publish_version
from autobots.contracts.plans import InputDocument
from autobots.contracts.workflows import WorkflowGraph
from autobots.domain.models import resolve_role_policy
from autobots.operations.job_dispatch import process_next
from goal_loop_script import ROUTE
from pydantic import SecretStr

URL, BASE = os.environ['AUTOBOTS_DATABASE_URL'], os.environ['AUTOBOTS_STORAGE_BASE']
SERVICE = SecretStr(os.environ['AUTOBOTS_STORAGE_SERVICE'])
WORKSPACE = UUID(sys.argv[1])
ACTOR = uuid4()
GRANTS = {'calculate': 1, 'save_artifact': 1}
TASKS = [{'id': 't1', 'title': 'Add the totals', 'depends_on': [], 'criteria': [], 'tools': ['calculate'], 'expected_evidence': 'a sum'},
         {'id': 't2', 'title': 'Save the note', 'depends_on': [], 'criteria': [], 'tools': ['save_artifact'], 'expected_evidence': 'a file'}]
cases: list[dict[str, Any]] = []


def check(name: str, expected: str, observed: object, passed: bool) -> None:
    cases.append({'id': name, 'expected': expected, 'observed': str(observed), 'passed': bool(passed)})


def node(name: str, block: str, **config: Any) -> dict[str, Any]:
    return {'id': name, 'block': block, 'version': 1, 'config': config}


def link(source: str, source_port: str, target: str, target_port: str) -> dict[str, str]:
    return {'source': source, 'source_port': source_port, 'target': target, 'target_port': target_port}


FILES = {
    'nodes': [node('in', 'input', type='string'), node('read', 'read'), node('save', 'artifact', path='outputs/copy.md'), node('out', 'output')],
    'links': [link('in', 'value', 'read', 'path'), link('read', 'content', 'save', 'content'), link('save', 'artifact_id', 'out', 'value')],
}


async def main() -> None:
    store = SupabaseObjectStore(BASE, SERVICE)
    config = LoopConfig(route=ROUTE, object_store=store, sleep=lambda _: asyncio.sleep(0), tool_set=tool_registry.build_registry)
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        await db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null where status <> 'done'")
        flow = await create_workflow(db, workspace_id=WORKSPACE, actor_id=ACTOR, idempotency_key='tool-view', name='Tool uses by node')
        await publish_version(db, workspace_id=WORKSPACE, actor_id=ACTOR, workflow_id=flow.id, idempotency_key='tool-view-p', expected_version=0,
                              graph=WorkflowGraph.model_validate(FILES), source='user')
        execution = await create_execution(db, workspace_id=WORKSPACE, actor_id=ACTOR, workflow_id=flow.id, idempotency_key='tool-view-e', version=1,
                                           inputs={'in': 'inputs/doc.md'}, documents=(InputDocument(path='inputs/doc.md', content='the document'),))
        await process_next(db, URL, 'tool-view', lambda: None, config)
        listed = await list_tool_uses(db, WORKSPACE, execution.run_id)
        by_node = sorted({(use.instance_key, use.tool_id) for use in (listed.uses if listed else [])}, key=str)
        check("a workflow's tool uses record the node instance that made them", "read: read_run_file, save: save_artifact",
              by_node, ('read', 'read_run_file') in by_node and ('save', 'save_artifact') in by_node)

        # A claimed run, held long enough for the browser suite, with two uses before it opens.
        admitted = await admit_run(db, workspace_id=WORKSPACE, actor_id=uuid4(), idempotency_key=str(uuid4()), goal_text='Watch tools live',
                                   limit_micro_usd=1000, policy=resolve_role_policy())
        lease = await claim_next(db, worker_id='tool-view-live', lease_seconds=1800)
        assert lease is not None and lease.run_id == admitted.run_id
        await db.execute("insert into app_private.plan_versions (run_id, version, tasks) values (%s, 1, %s)", (admitted.run_id, json.dumps(TASKS)))
        scope = ToolScope(WORKSPACE, admitted.run_id, lease.generation, GRANTS, ('inputs', 'outputs'))
        gateway = ToolGateway(build_registry(None))
        added = await gateway.execute(db, scope, 'calculate', {'operation': 'sum', 'values': [1, 2]})
        refused = await gateway.execute(db, scope, 'publish_artifact', {'path': 'outputs/x.md', 'version': 1})
        check('the live run has two uses before the page opens', 'succeeded, tool_not_granted', (added.outcome.value, refused.code),
              added.outcome.value == 'succeeded' and refused.code == 'tool_not_granted')
    print(json.dumps({'cases': cases, 'browser_env': {
        'AUTOBOTS_TEST_TOOL_RUN': str(admitted.run_id), 'AUTOBOTS_TEST_TOOL_GENERATION': str(lease.generation),
        'AUTOBOTS_TEST_TOOL_WORKSPACE': str(WORKSPACE), 'AUTOBOTS_TEST_TOOL_EXECUTION': str(execution.id),
        'AUTOBOTS_TEST_RUNTIME_URL': URL, 'AUTOBOTS_TEST_PYTHON': sys.executable,
        'AUTOBOTS_TEST_PYTHONPATH': os.environ.get('PYTHONPATH', ''),
        'AUTOBOTS_TEST_TOOL_HELPER': str(Path(__file__).parent / 'tool_use_live.py')}}))


asyncio.run(main())
