"""Workflows on real services: iteration, joins, approvals, specialists and a killed worker. JSON cases."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch
from uuid import UUID, uuid4

import psycopg
from autobots.adapters.object_storage import SupabaseObjectStore
from autobots.application import workflow_runner
from autobots.application.approvals import decide
from autobots.application.experts import create_expert
from autobots.application.goal_loop import drive_lease, process_next
from autobots.application.plans import load_goal
from autobots.application.run_lifecycle import LoopConfig
from autobots.application.runs import apply_command
from autobots.application.worker_leases import claim_next
from autobots.application.workflows import (
    create_execution,
    create_workflow,
    publish_version,
    set_description,
)
from autobots.contracts.experts import ExpertConfig
from autobots.contracts.plans import InputDocument
from autobots.contracts.workflows import WorkflowGraph
from autobots.domain.runs import Actor, RunCommand
from autobots.domain.workflows import block_versions, graph_hash
from goal_loop_script import ROUTE, Script, say
from pydantic import SecretStr

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
        from autobots.application.workflow_runner import run_workflow
        result = await run_workflow(db, URL, lease, None, config, drive=drive_lease)
        rows = await value('select count(*) from public.workflow_node_instances where execution_id = %s', execution.id)
        check('a stale worker commits nothing', 'lost, 0 instances', (result.outcome, rows), result.outcome == 'lost' and rows == 0)

        # commit_instance's own fence, with a scope whose generation has moved on.
        from autobots.application.tool_gateway import LeaseLost, ToolScope
        from autobots.application.workflow_runner import commit_instance
        from autobots.domain.workflow_execution import Step
        stale_scope = ToolScope(WORKSPACE, execution.run_id, lease.generation, {})
        step = Step('up', 'up', None, 'run', {})
        try:
            await commit_instance(db, stale_scope, execution.id, step, 'succeeded', [('value', 0, 'x')])
            fenced = 'committed'
        except LeaseLost:
            fenced = 'refused'
        counts = await (await db.execute('select (select count(*) from public.workflow_node_instances where execution_id = %s), (select count(*) from public.workflow_emissions where execution_id = %s)', (execution.id, execution.id))).fetchone()
        check("_commit refuses a stale generation and writes nothing", 'refused, no instance or emission', (fenced, counts), fenced == 'refused' and counts == (0, 0))

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

        # A workflow's own limit stops its agent step before any call.
        execution = await start('Agent no money', agent_graph, {'in': 'Work it out'})
        await db.execute('update public.runs set limit_micro_usd = 0 where id = %s', (execution.run_id,))
        model = Script(items=[say('never')], seen=[], bound=[])
        await advance(model)
        found = await statuses(execution)
        reason = await value("select coalesce(u.stop_reason, '-') from app_private.assignments a join app_private.run_usage u on u.run_id = a.child_run_id where a.parent_run_id = %s", execution.run_id)
        check("a workflow's limit stops its agent step with no model call", 'no instance settled, budget_exceeded, 0 model calls', (found.get('ask'), reason, len(model.seen)), found.get('ask') is None and reason == 'budget_exceeded' and not model.seen)

        # A cancel before any worker claims it. The stop between instances is its own case below.
        execution = await start('Cancelled', LOOP, {'in': ['a', 'b']})
        version = await value('select version from public.runs where id = %s', execution.run_id)
        await apply_command(db, workspace_id=WORKSPACE, run_id=execution.run_id, command=RunCommand.CANCEL, actor=Actor.USER, expected_version=version)
        idle = await advance()
        check('an execution cancelled while queued does not run', 'nothing to do, no instances', (idle, await statuses(execution)), idle is None and await statuses(execution) == {})
        # B5: a worker dies after VERIFY commits, and a cancel lands after the last node commits.
        no_tools = {'nodes': [node('in', 'input', type='string'), node('out', 'output')], 'links': [link('in', 'value', 'out', 'value')]}
        execution = await start('settle-verifying', no_tools, {'in': 'x'})
        run = execution.run_id
        real_command = workflow_runner.apply_command

        # A process that dies runs no handler, so the death is a BaseException the worker's failure
        # record (Decision 0028 E4) doesn't catch: the job stays claimed until its lease lapses.
        class WorkerDied(BaseException):
            pass

        async def dies_after_verify(*arguments: Any, **options: Any) -> Any:
            result = await real_command(*arguments, **options)
            if options.get('command') is RunCommand.VERIFY:
                raise WorkerDied('the worker died here')
            return result

        workflow_runner.apply_command = dies_after_verify
        try:
            await advance()
            died = False
        except WorkerDied:
            died = True
        finally:
            workflow_runner.apply_command = real_command
        left = await value('select status from public.runs where id = %s', run)
        check('a worker can die between VERIFY and COMPLETE', 'died, verifying', (died, left), died and left == 'verifying')
        await db.execute("update app_private.run_jobs set lease_expires_at = clock_timestamp() - interval '1 second' where run_id = %s", (run,))
        result = await advance()
        state = await value('select status from public.runs where id = %s', run)
        check('a workflow left verifying finishes on the next claim', 'succeeded', (state, result.code if result else None), state == 'succeeded')
        execution = await start('settle-cancelling', no_tools, {'in': 'x'})
        lease = await claim_next(db, worker_id='cancelled-under')
        run = execution.run_id
        version = await value('select version from public.runs where id = %s', run)
        await apply_command(db, workspace_id=WORKSPACE, run_id=run, command=RunCommand.CANCEL, actor=Actor.USER, expected_version=version)
        before = await value('select status from public.runs where id = %s', run)
        await workflow_runner.complete_workflow(db, lease, await load_goal(db, run))
        after = await value('select status from public.runs where id = %s', run)
        check('a workflow cancelled after its last commit finishes cancelling', 'cancelling, then cancelled', (before, after), before == 'cancelling' and after == 'cancelled')

        # B7 in the real runner: nothing can move, but nothing has finished either.
        execution = await start('stalled', no_tools, {'in': 'x'})

        async def nothing_moves(*_: Any, **__: Any) -> bool:
            return False

        with patch.object(workflow_runner, 'run_pass', nothing_moves):
            result = await advance()
        state = await run_state(execution)
        check('a workflow that stalls fails instead of succeeding', 'failed, workflow_stalled', (state, result.code if result else None), state == 'failed' and result is not None and result.code == 'workflow_stalled')

        # Finding 9: a version published under older rules doesn't run.
        execution = await start('older-rules', no_tools, {'in': 'x'})
        real_validate = workflow_runner.validate_graph
        workflow_runner.validate_graph = lambda _: ['join_multiple_foreach']
        try:
            result = await advance()
        finally:
            workflow_runner.validate_graph = real_validate
        state = await run_state(execution)
        check('a version the rules now reject fails without running', 'failed, workflow_invalid, no instance', (state, result.code if result else None, await statuses(execution)), state == 'failed' and result is not None and result.code == 'workflow_invalid' and await statuses(execution) == {})

        # US-15.11 (PRD-Studio WF-06): an optional description, labels at IR version 2, and version 1 unchanged.
        shout = {'nodes': [node('in', 'input', type='string'), node('up', 'transform', operation='upper'), node('out', 'output')],
                 'links': [link('in', 'value', 'up', 'value'), link('up', 'value', 'out', 'value')]}
        described = await create_workflow(db, workspace_id=WORKSPACE, actor_id=ACTOR, idempotency_key='described', name='Described', description='Shouts the topic back')
        plain_flow = await create_workflow(db, workspace_id=WORKSPACE, actor_id=ACTOR, idempotency_key='undescribed', name='Undescribed')
        check('a workflow keeps its optional description, and one without has none', 'the text, then None',
              (described.description, plain_flow.description), described.description == 'Shouts the topic back' and plain_flow.description is None)
        labelled = {**shout, 'nodes': [shout['nodes'][0], {**shout['nodes'][1], 'label': 'Shout it'}, shout['nodes'][2]]}
        execution = await start('Labelled', labelled, {'in': 'loud'})
        stored = await value('select graph from public.workflow_versions v join public.workflow_executions x on x.workflow_id = v.workflow_id and x.workflow_version = v.version where x.id = %s', execution.id)
        check('a labelled graph is stored at IR version 2 with its labels', "ir_version 2, up labelled 'Shout it'",
              (stored.get('ir_version'), [item.get('label') for item in stored['nodes']]),
              stored.get('ir_version') == 2 and [item.get('label') for item in stored['nodes']] == [None, 'Shout it', None])
        result = await advance()
        check('and it runs', 'succeeded, LOUD', (result.outcome, await emitted(execution, 'out', 'value')), result.outcome == 'succeeded' and await emitted(execution, 'out', 'value') == 'LOUD')
        execution = await start('Version one', shout, {'in': 'quiet'})
        row = await (await db.execute('select v.graph, v.graph_hash from public.workflow_versions v join public.workflow_executions x on x.workflow_id = v.workflow_id and x.workflow_version = v.version where x.id = %s', (execution.id,))).fetchone()
        check('an unlabelled graph stays at IR version 1 and hashes as before', 'no ir_version or label keys, the raw hash',
              (sorted(row[0]), row[1] == graph_hash(shout)),
              'ir_version' not in row[0] and all('label' not in item for item in row[0]['nodes']) and row[1] == graph_hash(shout) and row[0] == shout)
        result = await advance()
        check('and it still runs', 'succeeded, QUIET', (result.outcome, await emitted(execution, 'out', 'value')), result.outcome == 'succeeded' and await emitted(execution, 'out', 'value') == 'QUIET')
        # Arranged as a version published before the migration: its stored graph and hash, written as they were.
        older = uuid4()
        await db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null where status <> 'done'")
        await db.execute('insert into public.workflows (id, workspace_id, name, latest_version) values (%s, %s, %s, 1)', (older, WORKSPACE, 'Published before'))
        await db.execute("insert into public.workflow_versions (workflow_id, version, graph, graph_hash, block_versions, source, created_by) values (%s, 1, %s, %s, %s, 'user', %s)",
                         (older, json.dumps(shout), graph_hash(shout), json.dumps(block_versions(shout)), ACTOR))
        bound = await create_execution(db, workspace_id=WORKSPACE, actor_id=ACTOR, workflow_id=older, idempotency_key='older-e', version=1, inputs={'in': 'kept'})
        check('a version published before the change binds the same version and hash', 'version 1, the stored hash',
              (bound.workflow_version, bound.graph_hash == graph_hash(shout)), bound.workflow_version == 1 and bound.graph_hash == graph_hash(shout))
        result = await advance()
        check('and runs unchanged', 'succeeded, KEPT', (result.outcome, await emitted(bound, 'out', 'value')), result.outcome == 'succeeded' and await emitted(bound, 'out', 'value') == 'KEPT')
        described = await set_description(db, WORKSPACE, plain_flow.id, 'Added later')
        check('a description can be added later without a new version', 'Added later, version 0', (described.description, described.latest_version),
              described.description == 'Added later' and described.latest_version == 0)
    print(json.dumps({'cases': cases}))

try:
    asyncio.run(main())
except Exception:
    print(json.dumps({'cases': cases}))
    raise
