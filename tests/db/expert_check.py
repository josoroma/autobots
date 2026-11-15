"""Frozen revisions and bounded routing, with a real Deep Agents graph and a scripted model."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any
from uuid import UUID, uuid4

import psycopg
from autobots.adapters.loop_middleware import ModelRoute
from autobots.application.experts import (
    ExpertRefused,
    add_version,
    create_expert,
    create_session,
    resolve_binding,
)
from autobots.application.goal_loop import run_goal
from autobots.application.run_lifecycle import LoopConfig
from autobots.application.runs import admit_run
from autobots.application.worker_leases import claim_next
from autobots.contracts.experts import ExpertConfig, SessionExpert
from autobots.domain.models import ModelRole, resolve_role_policy
from autobots.operations.job_dispatch import drive_lease
from goal_loop_script import ROUTE, Script, calls, say

URL = os.environ['AUTOBOTS_DATABASE_URL']
WORKSPACE, OTHER = UUID(sys.argv[1]), UUID(sys.argv[2])
ACTOR = uuid4()
cases = []


def check(name: str, expected: str, observed: object, passed: bool) -> None:
    cases.append({'id': name, 'expected': expected, 'observed': str(observed), 'passed': bool(passed)})


async def main() -> None:
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        async def value(sql: str, *values: object) -> Any:
            return (await (await db.execute(sql, values)).fetchone())[0]

        async def admit(binding: Any = None, policy: Any = None) -> UUID:
            await db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null where status <> 'done'")
            return (await admit_run(db, workspace_id=WORKSPACE, actor_id=ACTOR, idempotency_key=str(uuid4()), goal_text='Use the tools', limit_micro_usd=1_000_000, policy=policy or resolve_role_policy(), binding=binding)).run_id

        expert = await create_expert(db, workspace_id=WORKSPACE, actor_id=ACTOR, idempotency_key='x1', name='Frozen', config=ExpertConfig(instructions='Always answer in rhyme.', tools=['calculate', 'save_artifact'], skills=['style-guide']))
        session = await create_session(db, workspace_id=WORKSPACE, actor_id=ACTOR, idempotency_key='s1', kind='direct', experts=[SessionExpert(expert_id=expert.id)])
        binding = await resolve_binding(db, WORKSPACE, session.id)
        check('a session pins the revision it started with', 'version 1', binding.version, binding.version == 1)
        running = await admit(binding)
        lease = await claim_next(db, worker_id='frozen', lease_seconds=120)

        await add_version(db, workspace_id=WORKSPACE, actor_id=ACTOR, expert_id=expert.id, idempotency_key='x2', expected_version=1, config=ExpertConfig(instructions='Plain prose only.', tools=['calculate']))
        stored = await value('select spec from app_private.goal_specs where run_id = %s', running)
        check('work in flight keeps its frozen tools and instructions', 'save_artifact kept, rhyme', (sorted(stored['allowed_tools']), stored['instructions']), 'save_artifact' in stored['allowed_tools'] and stored['instructions'] == 'Always answer in rhyme.')
        model = Script(items=[calls(('save_artifact', {'path': 'outputs/a.md', 'content': 'kept'})), say('stop')], seen=[], bound=[])
        await run_goal(db, URL, lease, model, LoopConfig(route=ROUTE), drive=drive_lease)
        files = await value('select count(*) from app_private.run_files where run_id = %s', running)
        check('so it can still use the tool the new revision removed', '1 file', files, files == 1)
        system = ' '.join(str(item.content) for item in model.seen[0] if item.type == 'system')
        check('and it follows the instructions it was frozen with', 'rhyme', 'rhyme' in system, 'Always answer in rhyme.' in system and 'Plain prose' not in system)

        again = await resolve_binding(db, WORKSPACE, session.id)
        check('an existing session keeps its pinned revision by default', 'version 1', again.version, again.version == 1)
        chosen = await resolve_binding(db, WORKSPACE, session.id, version=2)
        check('and new work can choose a later one', 'version 2, no save_artifact', (chosen.version, sorted(chosen.tools)), chosen.version == 2 and 'save_artifact' not in chosen.tools)
        new_run = await admit(chosen)
        lease = await claim_next(db, worker_id='new', lease_seconds=120)
        model = Script(items=[calls(('save_artifact', {'path': 'outputs/a.md', 'content': 'no'})), say('stop')], seen=[], bound=[])
        await run_goal(db, URL, lease, model, LoopConfig(route=ROUTE), drive=drive_lease)
        files = await value('select count(*) from app_private.run_files where run_id = %s', new_run)
        reply = json.loads([m for m in model.seen[-1] if m.type == 'tool'][-1].content)
        check('new work on the later revision loses the tool, at the gateway', 'tool_not_granted, no file', (reply['code'], files), reply['code'] == 'tool_not_granted' and files == 0)
        check('and the model is shown only its granted tools', 'calculate and the plan tools', sorted(model.bound[0]), sorted(model.bound[0]) == ['calculate', 'complete_task', 'propose_plan', 'read_offload'])
        recorded = await (await db.execute('select session_id, expert_id, expert_version from public.runs where id = %s', (new_run,))).fetchone()
        check('the run records its Expert and revision', 'version 2', recorded[2], recorded == (session.id, expert.id, 2))

        # Expert model bindings are frozen into the run's own policy.
        terra = await create_expert(db, workspace_id=WORKSPACE, actor_id=ACTOR, idempotency_key='x3', name='Bound', config=ExpertConfig(role_bindings={'executor': 'openrouter_deepseek_flash'}))
        direct = await create_session(db, workspace_id=WORKSPACE, actor_id=ACTOR, idempotency_key='s2', kind='direct', experts=[SessionExpert(expert_id=terra.id)])
        bound = await resolve_binding(db, WORKSPACE, direct.id)
        run = await admit(bound, resolve_role_policy(run_role_overrides=bound.role_bindings))
        snapshot = await value('select policy_snapshot from public.runs where id = %s', run)
        check('an Expert binding reaches the run policy', 'executor deepseek, others default', (snapshot['bindings']['executor'], snapshot['bindings']['planner']), snapshot['bindings']['executor'] == 'openrouter_deepseek_flash' and snapshot['bindings']['planner'] == 'openrouter_terra')
        lease = await claim_next(db, worker_id='route', lease_seconds=120)
        model = Script(items=[say('x')], seen=[], bound=[])
        result = await run_goal(db, URL, lease, model, LoopConfig(route=ROUTE), drive=drive_lease)
        check('a worker route that differs from the Expert binding is refused', 'route_not_bound, no call', (result.code, len(model.seen)), result.code == 'route_not_bound' and not model.seen)
        run = await admit(bound, resolve_role_policy(run_role_overrides=bound.role_bindings))
        lease = await claim_next(db, worker_id='route', lease_seconds=120)
        model = Script(items=[say('x')], seen=[], bound=[])
        result = await run_goal(db, URL, lease, model, LoopConfig(route=ModelRoute('executor', 'openrouter_deepseek_flash', 'fixture/terra', 1000)), drive=drive_lease)
        check('the bound route runs', 'a model call', len(model.seen), len(model.seen) == 1)
        wire = await value('select wire_id from app_private.model_invocations where run_id = %s', run)
        check('and admission records that route, with nothing substituted', 'fixture/terra', wire, wire == 'fixture/terra')
        check('nothing implicit was added by routing', 'no model role but its own', ModelRole.EXECUTOR.value in bound.role_bindings and len(bound.role_bindings), len(bound.role_bindings) == 1)

        # Refusals.
        for label, attempt, code in (
                ('a session on another workspace', lambda: resolve_binding(db, OTHER, session.id), 'session_not_found'),
                ('a version that does not exist', lambda: resolve_binding(db, WORKSPACE, session.id, version=99), 'expert_version_not_found'),
                ('an unlisted Expert', lambda: resolve_binding(db, WORKSPACE, session.id, expert_id=terra.id), 'route_not_granted'),
                ('a stale revision', lambda: add_version(db, workspace_id=WORKSPACE, actor_id=ACTOR, expert_id=expert.id, idempotency_key='x4', expected_version=1, config=ExpertConfig()), 'expert_version_conflict'),
                ('another workspace saving a revision', lambda: add_version(db, workspace_id=OTHER, actor_id=ACTOR, expert_id=expert.id, idempotency_key='x5', expected_version=2, config=ExpertConfig()), 'expert_not_found'),
                ('a shell tool', lambda: create_expert(db, workspace_id=WORKSPACE, actor_id=ACTOR, idempotency_key='x6', name='Shell', config=ExpertConfig(tools=['execute'])), 'expert_tool_not_available'),
                ('another workspace\'s Expert in a session', lambda: create_session(db, workspace_id=OTHER, actor_id=ACTOR, idempotency_key='s3', kind='direct', experts=[SessionExpert(expert_id=expert.id)]), 'expert_not_found'),
                ('a direct session with two Experts', lambda: create_session(db, workspace_id=WORKSPACE, actor_id=ACTOR, idempotency_key='s4', kind='direct', experts=[SessionExpert(expert_id=expert.id), SessionExpert(expert_id=terra.id)]), 'session_needs_one_expert')):
            try:
                await attempt()
                check(f'{label} is refused', code, 'allowed', False)
            except ExpertRefused as error:
                check(f'{label} is refused', code, error.code, error.code == code)
        try:
            await db.execute("update public.expert_versions set config = '{}' where expert_id = %s", (expert.id,))
            check('a saved revision cannot be rewritten', 'permission denied', 'updated', False)
        except psycopg.errors.InsufficientPrivilege:
            check('a saved revision cannot be rewritten', 'permission denied', 'permission denied', True)
    print(json.dumps({'cases': cases}))


try:
    asyncio.run(main())
except Exception:
    print(json.dumps({'cases': cases}))
    raise
