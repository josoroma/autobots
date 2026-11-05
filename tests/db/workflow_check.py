"""Immutable versions and exact bindings on a real database. JSON cases."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any
from uuid import UUID, uuid4

import psycopg

from autobots.application.workflows import WorkflowRefused, create_execution, create_workflow, publish_version
from autobots.contracts.workflows import WorkflowGraph

URL = os.environ['AUTOBOTS_DATABASE_URL']
WORKSPACE, OTHER = UUID(sys.argv[1]), UUID(sys.argv[2])
ACTOR = uuid4()
cases = []


def check(name: str, expected: str, observed: object, passed: bool) -> None:
    cases.append({'id': name, 'expected': expected, 'observed': str(observed), 'passed': bool(passed)})


def graph(operation: str = 'upper') -> WorkflowGraph:
    return WorkflowGraph.model_validate({
        'nodes': [{'id': 'in', 'block': 'input', 'version': 1, 'config': {'type': 'string'}},
                  {'id': 'up', 'block': 'transform', 'version': 1, 'config': {'operation': operation}},
                  {'id': 'out', 'block': 'output', 'version': 1}],
        'links': [{'source': 'in', 'source_port': 'value', 'target': 'up', 'target_port': 'value'},
                  {'source': 'up', 'source_port': 'value', 'target': 'out', 'target_port': 'value'}]})


async def main() -> None:
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        async def value(sql: str, *values: object) -> Any:
            return (await (await db.execute(sql, values)).fetchone())[0]

        flow = await create_workflow(db, workspace_id=WORKSPACE, actor_id=ACTOR, idempotency_key='w1', name='Totals')
        check('a new workflow has no version', '0', flow.latest_version, flow.latest_version == 0)
        again = await create_workflow(db, workspace_id=WORKSPACE, actor_id=ACTOR, idempotency_key='w1', name='Totals')
        check('creating it again with its key returns it', 'the same id', again.id == flow.id, again.id == flow.id)
        published = await publish_version(db, workspace_id=WORKSPACE, actor_id=ACTOR, workflow_id=flow.id, idempotency_key='p1', expected_version=0, graph=graph(), source='user')
        check('a valid graph publishes as version 1', 'version 1, block versions recorded', published.versions[0].block_versions, published.latest_version == 1 and published.versions[0].block_versions['up'] == 'transform@1')
        invalid = graph('eval')
        count = await value('select count(*) from public.workflow_versions where workflow_id = %s', flow.id)
        try:
            await publish_version(db, workspace_id=WORKSPACE, actor_id=ACTOR, workflow_id=flow.id, idempotency_key='p2', expected_version=1, graph=invalid, source='model_proposal')
            check('a model\'s invalid proposal is refused like any other', 'workflow_invalid', 'published', False)
        except WorkflowRefused as error:
            after = await value('select count(*) from public.workflow_versions where workflow_id = %s', flow.id)
            check('a model\'s invalid proposal is refused like any other', 'typed errors, nothing published', ([item.code for item in error.errors], after - count), error.code == 'workflow_invalid' and after == count)
        proposed = await publish_version(db, workspace_id=WORKSPACE, actor_id=ACTOR, workflow_id=flow.id, idempotency_key='p3', expected_version=1, graph=graph('lower'), source='model_proposal')
        check('a valid proposal publishes, marked as a proposal', 'model_proposal, version 2', proposed.versions[1].source, proposed.versions[1].source == 'model_proposal' and proposed.latest_version == 2)
        for label, attempt, code in (
                ('a stale version', lambda: publish_version(db, workspace_id=WORKSPACE, actor_id=ACTOR, workflow_id=flow.id, idempotency_key='p4', expected_version=1, graph=graph(), source='user'), 'workflow_version_conflict'),
                ('another workspace publishing', lambda: publish_version(db, workspace_id=OTHER, actor_id=ACTOR, workflow_id=flow.id, idempotency_key='p5', expected_version=2, graph=graph(), source='user'), 'workflow_not_found'),
                ('a version that doesn\'t exist', lambda: create_execution(db, workspace_id=WORKSPACE, actor_id=ACTOR, workflow_id=flow.id, idempotency_key='e0', version=9, inputs={}), 'workflow_version_not_found'),
                ('another workspace executing', lambda: create_execution(db, workspace_id=OTHER, actor_id=ACTOR, workflow_id=flow.id, idempotency_key='e1', version=1, inputs={'in': 'x'}), 'workflow_version_not_found'),
                ('inputs of the wrong type', lambda: create_execution(db, workspace_id=WORKSPACE, actor_id=ACTOR, workflow_id=flow.id, idempotency_key='e2', version=1, inputs={'in': 5}), 'workflow_inputs_invalid')):
            try:
                await attempt()
                check(f'{label} is refused', code, 'allowed', False)
            except WorkflowRefused as error:
                check(f'{label} is refused', code, error.code, error.code == code)

        first = published.versions[0]
        binding = await create_execution(db, workspace_id=WORKSPACE, actor_id=ACTOR, workflow_id=flow.id, idempotency_key='e3', version=1, inputs={'in': 'x'})
        check('an execution binds the exact version and hash', 'version 1, the same hash', binding.graph_hash == first.graph_hash, binding.workflow_version == 1 and binding.graph_hash == first.graph_hash and binding.block_versions == first.block_versions)
        repeat = await create_execution(db, workspace_id=WORKSPACE, actor_id=ACTOR, workflow_id=flow.id, idempotency_key='e3', version=1, inputs={'in': 'x'})
        check('repeating it with its key returns the same execution', 'the same id', repeat.id == binding.id, repeat.id == binding.id)
        latest = await create_execution(db, workspace_id=WORKSPACE, actor_id=ACTOR, workflow_id=flow.id, idempotency_key='e4', version=2, inputs={'in': 'x'})
        check('a later version is a different binding', 'different hash', latest.graph_hash != binding.graph_hash, latest.graph_hash != binding.graph_hash)
        try:
            await db.execute("update public.workflow_versions set graph = '{}' where workflow_id = %s", (flow.id,))
            check('a published version can\'t be rewritten', 'permission denied', 'updated', False)
        except psycopg.errors.InsufficientPrivilege:
            check('a published version can\'t be rewritten', 'permission denied', 'permission denied', True)
    print(json.dumps({'cases': cases}))


try:
    asyncio.run(main())
except Exception:
    print(json.dumps({'cases': cases}))
    raise
