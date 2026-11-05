"""Workflows on real services: iteration, joins, approvals, specialists and a killed worker. JSON cases."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import psycopg
from pydantic import SecretStr

sys.path.insert(0, str(Path(__file__).parent))
from goal_loop_script import ROUTE, Script, calls, say  # noqa: E402

from autobots.adapters.object_storage import SupabaseObjectStore  # noqa: E402
from autobots.application.approvals import decide  # noqa: E402
from autobots.application.experts import create_expert  # noqa: E402
from autobots.application.goal_loop import LoopConfig, process_next  # noqa: E402
from autobots.application.runs import apply_command  # noqa: E402
from autobots.application.worker_leases import claim_next  # noqa: E402
from autobots.application.workflows import create_execution, create_workflow, publish_version  # noqa: E402
from autobots.contracts.experts import ExpertConfig  # noqa: E402
from autobots.contracts.plans import InputDocument  # noqa: E402
from autobots.contracts.workflows import WorkflowGraph  # noqa: E402
from autobots.domain.runs import Actor, RunCommand  # noqa: E402

URL, BASE = os.environ['AUTOBOTS_DATABASE_URL'], os.environ['AUTOBOTS_STORAGE_BASE']
SERVICE = SecretStr(os.environ['AUTOBOTS_STORAGE_SERVICE'])
WORKSPACE, PYTHON = UUID(sys.argv[1]), sys.argv[2]
HERE = Path(__file__).parent
ACTOR = uuid4()
cases = []


def check(name: str, expected: str, observed: object, passed: bool) -> None:
    cases.append({'id': name, 'expected': expected, 'observed': str(observed), 'passed': bool(passed)})


def node(name: str, block: str, **config: Any) -> dict[str, Any]:
    return {'id': name, 'block': block, 'version': 1, 'config': config}


def link(source: str, source_port: str, target: str, target_port: str) -> dict[str, str]:
    return {'source': source, 'source_port': source_port, 'target': target, 'target_port': target_port}


LOOP = {
    'nodes': [node('in', 'input', type='list'), node('each', 'foreach', max_items=5), node('up', 'transform', operation='upper'), node('all', 'join'), node('out', 'output')],
    'links': [link('in', 'value', 'each', 'items'), link('each', 'item', 'up', 'value'), link('up', 'value', 'all', 'value'), link('all', 'items', 'out', 'value')],
}
BRANCH = {
    'nodes': [node('in', 'input', type='number'), node('if', 'condition', predicate='greater_than', operand=3), node('big', 'output'), node('small', 'output')],
    'links': [link('in', 'value', 'if', 'value'), link('if', 'true', 'big', 'value'), link('if', 'false', 'small', 'value')],
}
FILES = {
    'nodes': [node('in', 'input', type='string'), node('read', 'read'), node('save', 'artifact', path='outputs/copy.md'), node('out', 'output')],
    'links': [link('in', 'value', 'read', 'path'), link('read', 'content', 'save', 'content'), link('save', 'artifact_id', 'out', 'value')],
}
EFFECT_LOOP = {
    'nodes': [node('in', 'input', type='list'), node('each', 'foreach', max_items=5, item_type='string'), node('save', 'artifact', path='outputs/item.md'), node('all', 'join'), node('out', 'output')],
    'links': [link('in', 'value', 'each', 'items'), link('each', 'item', 'save', 'content'), link('save', 'artifact_id', 'all', 'value'), link('all', 'items', 'out', 'value')],
}
GATED = {
    'nodes': [node('in', 'input', type='string'), node('ok', 'approval'), node('out', 'output')],
    'links': [link('in', 'value', 'ok', 'value'), link('ok', 'value', 'out', 'value')],
}


async def main() -> None:
    store = SupabaseObjectStore(BASE, SERVICE)
    config = LoopConfig(route=ROUTE, object_store=store, sleep=lambda _: asyncio.sleep(0))
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        async def value(sql: str, *values: object) -> Any:
            return (await (await db.execute(sql, values)).fetchone())[0]

        async def start(name: str, graph: dict[str, Any], inputs: dict[str, Any], documents: tuple[InputDocument, ...] = ()) -> Any:
            await db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null where status <> 'done'")
            flow = await create_workflow(db, workspace_id=WORKSPACE, actor_id=ACTOR, idempotency_key=name, name=name)
            await publish_version(db, workspace_id=WORKSPACE, actor_id=ACTOR, workflow_id=flow.id, idempotency_key=f'{name}-p', expected_version=0, graph=WorkflowGraph.model_validate(graph), source='user')
            return await create_execution(db, workspace_id=WORKSPACE, actor_id=ACTOR, workflow_id=flow.id, idempotency_key=f'{name}-e', version=1, inputs=inputs, documents=documents)

        async def advance(model: Any = None) -> Any:
            return await process_next(db, URL, 'worker', lambda: model, config)

        async def statuses(execution: Any) -> dict[str, str]:
            rows = await (await db.execute('select instance_key, status from public.workflow_node_instances where execution_id = %s', (execution.id,))).fetchall()
            return dict(rows)

        async def emitted(execution: Any, key: str, port: str) -> Any:
            row = await (await db.execute('select value from public.workflow_emissions where execution_id = %s and instance_key = %s and port = %s', (execution.id, key, port))).fetchone()
            return row[0] if row else None

        async def run_state(execution: Any) -> str:
            return await value('select status from public.runs where id = %s', execution.run_id)

        # Iteration: distinct instances and emissions, gathered by a join.
        execution = await start('Loop', LOOP, {'in': ['a', 'b', 'c']})
        result = await advance()
        found = await statuses(execution)
        check('each iteration has its own instance', 'up#0, up#1, up#2', sorted(k for k in found if k.startswith('up')), sorted(k for k in found if k.startswith('up')) == ['up#0', 'up#1', 'up#2'])
        check('and its own emission', 'A, B, C', [await emitted(execution, f'up#{i}', 'value') for i in range(3)], [await emitted(execution, f'up#{i}', 'value') for i in range(3)] == ['A', 'B', 'C'])
        check('the join gathers them in order', "['A', 'B', 'C']", await emitted(execution, 'out', 'value'), await emitted(execution, 'out', 'value') == ['A', 'B', 'C'])
        check('and the run succeeds', 'succeeded', (result.outcome, await run_state(execution)), result.outcome == 'succeeded' and await run_state(execution) == 'succeeded')
        check('an execution keeps its bound version and hash', 'version 1', await value('select workflow_version from public.workflow_executions where id = %s', execution.id), await value('select workflow_version from public.workflow_executions where id = %s', execution.id) == 1)

        # Branches: skipped, failed and blocked stay different.
        execution = await start('Branch', BRANCH, {'in': 5})
        await advance()
        found = await statuses(execution)
        check('a branch not taken is skipped', 'big succeeded, small skipped', found, found['big'] == 'succeeded' and found['small'] == 'skipped')
        execution = await start('Too many', LOOP, {'in': ['a'] * 6})
        result = await advance()
        found = await statuses(execution)
        check('a list past the bound fails that node, and blocks what follows', 'each failed, out blocked, run failed', (found.get('each'), found.get('out'), await run_state(execution)), found.get('each') == 'failed' and found.get('out') == 'blocked' and await run_state(execution) == 'failed')
        code = await value("select error_code from public.workflow_node_instances where execution_id = %s and instance_key = 'each'", execution.id)
        check('with a typed reason', 'foreach_over_bound', code, code == 'foreach_over_bound')
        execution = await start('Bad item', LOOP, {'in': ['a', 5]})
        result = await advance()
        found = await statuses(execution)
        check('a failed iteration blocks the join, and the good one stays', 'up#0 ok, up#1 failed, all blocked', found, found['up#0'] == 'succeeded' and found['up#1'] == 'failed' and found['all'] == 'blocked' and await emitted(execution, 'up#0', 'value') == 'A')

        # Reads and artifacts go through the gateway.
        execution = await start('Files', FILES, {'in': 'inputs/doc.md'}, (InputDocument(path='inputs/doc.md', content='the document'),))
        result = await advance()
        artifact = await emitted(execution, 'out', 'value')
        name = await value('select name from public.artifacts where id = %s', artifact)
        check('a read and a published artifact run through the gateway', 'copy.md, succeeded', (name, result.outcome), name == 'copy.md' and result.outcome == 'succeeded')

        # A real worker dies after some iterations have committed.
        execution = await start('Restart', EFFECT_LOOP, {'in': ['one', 'two', 'three']})
        process = await asyncio.create_subprocess_exec(PYTHON, str(HERE / 'workflow_worker.py'), URL, BASE, 'save#1', stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=os.environ)
        _, err = await asyncio.wait_for(process.communicate(), 60)
        check('a worker process is killed after two iterations committed', 'exit -9, 2 committed', (f'exit {process.returncode}: {err.decode()[-200:]}', sorted(k for k in await statuses(execution) if k.startswith('save'))), process.returncode == -9 and sorted(k for k in await statuses(execution) if k.startswith('save')) == ['save#0', 'save#1'])
        before = await (await db.execute('select instance_key, value, created_at from public.workflow_emissions where execution_id = %s order by instance_key, port, sequence', (execution.id,))).fetchall()
        artifacts_before = await value('select count(*) from public.artifacts where run_id = %s', execution.run_id)
        await db.execute("update app_private.run_jobs set lease_expires_at = clock_timestamp() - interval '1 second' where run_id = %s", (execution.run_id,))
        result = await advance()
        after = await (await db.execute('select instance_key, value, created_at from public.workflow_emissions where execution_id = %s order by instance_key, port, sequence', (execution.id,))).fetchall()
        kept = [row for row in before if row in after]
        check('the replacement keeps what was committed, unchanged', 'all earlier emissions identical', (len(before), len(kept)), len(kept) == len(before))
        artifacts = await value('select count(*) from public.artifacts where run_id = %s', execution.run_id)
        check('and repeats no known effect', '2 artifacts before, 3 after', (artifacts_before, artifacts), artifacts_before == 2 and artifacts == 3)
        check('and finishes the rest', 'succeeded, 3 ids', (result.outcome, len(await emitted(execution, 'out', 'value'))), result.outcome == 'succeeded' and len(await emitted(execution, 'out', 'value')) == 3)
        generation = await value('select generation from app_private.run_jobs where run_id = %s', execution.run_id)
        check('under a new generation', '2', generation, generation == 2)

        # A stale worker can't commit an instance.
        execution = await start('Stale', LOOP, {'in': ['a']})
        lease = await claim_next(db, worker_id='stale', lease_seconds=60)
        await db.execute("update app_private.run_jobs set generation = generation + 1 where run_id = %s", (execution.run_id,))
        from autobots.application.workflow_runner import run_workflow  # noqa: PLC0415
        result = await run_workflow(db, URL, lease, None, config)
        rows = await value('select count(*) from public.workflow_node_instances where execution_id = %s', execution.id)
        check('a stale worker commits nothing', 'lost, 0 instances', (result.outcome, rows), result.outcome == 'lost' and rows == 0)

        # An approval step waits with nothing after it, and replays on the decision.
        execution = await start('Gate', GATED, {'in': 'please'})
        result = await advance()
        found = await statuses(execution)
        check('an approval step waits', 'waiting_approval, out not started', (await run_state(execution), found.get('out')), await run_state(execution) == 'waiting_approval' and 'out' not in found)
        approval = await (await db.execute("select id, argument_hash from public.approval_requests where run_id = %s", (execution.run_id,))).fetchone()
        await decide(db, workspace_id=WORKSPACE, actor_id=ACTOR, approval_id=approval[0], idempotency_key='g1', decision='approve', argument_hash=approval[1])
        result = await advance()
        check('approving continues from there', 'please, succeeded', (await emitted(execution, 'out', 'value'), result.outcome), await emitted(execution, 'out', 'value') == 'please' and result.outcome == 'succeeded')
        count = await value('select count(*) from public.approval_requests where run_id = %s', execution.run_id)
        check('with one proposal', '1', count, count == 1)
        execution = await start('Gate refused', GATED, {'in': 'no'})
        await advance()
        approval = await (await db.execute("select id, argument_hash from public.approval_requests where run_id = %s", (execution.run_id,))).fetchone()
        await decide(db, workspace_id=WORKSPACE, actor_id=ACTOR, approval_id=approval[0], idempotency_key='g2', decision='reject', argument_hash=approval[1])
        result = await advance()
        found = await statuses(execution)
        check('a rejection fails the step, and blocks what follows', 'ok failed, out blocked, run failed', (found.get('ok'), found.get('out'), await run_state(execution)), found.get('ok') == 'failed' and found.get('out') == 'blocked' and await run_state(execution) == 'failed')

        # An agent step is a bounded assignment.
        helper = await create_expert(db, workspace_id=WORKSPACE, actor_id=ACTOR, idempotency_key='wf-e', name='Workflow helper', config=ExpertConfig(tools=['calculate']))
        agent_graph = {
            'nodes': [node('in', 'input', type='string'), node('ask', 'agent', expert_id=str(helper.id)), node('out', 'output')],
            'links': [link('in', 'value', 'ask', 'goal'), link('ask', 'result', 'out', 'value')],
        }
        execution = await start('Agent', agent_graph, {'in': 'Work it out'})
        model = Script(items=[say('no plan')], seen=[], bound=[])
        result = await advance(model)
        found = await statuses(execution)
        children = await value('select count(*) from app_private.assignments where parent_run_id = %s', execution.run_id)
        check('an agent step runs one assignment, and its honest failure fails the step', 'ask failed, 1 child, 1 model call', (found.get('ask'), children, len(model.seen)), found.get('ask') == 'failed' and children == 1 and len(model.seen) == 1)

        # A cancel stops between instances.
        execution = await start('Cancelled', LOOP, {'in': ['a', 'b']})
        version = await value('select version from public.runs where id = %s', execution.run_id)
        await apply_command(db, workspace_id=WORKSPACE, run_id=execution.run_id, command=RunCommand.CANCEL, actor=Actor.USER, expected_version=version)
        idle = await advance()
        check('a cancelled execution does not run', 'nothing to do, no instances', (idle, await statuses(execution)), idle is None and await statuses(execution) == {})
    print(json.dumps({'cases': cases}))


try:
    asyncio.run(main())
except Exception:
    print(json.dumps({'cases': cases}))
    raise
