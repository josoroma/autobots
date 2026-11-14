"""Narrowed scope, shared budgets, reattachment and cancellation, with real Storage. JSON cases."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import psycopg
from autobots.adapters.loop_middleware import ModelRoute
from autobots.adapters.object_storage import SupabaseObjectStore
from autobots.application.experts import create_expert, create_session, resolve_binding
from autobots.application.goal_loop import LoopConfig, _finish, process_next
from autobots.application.model_admission import ModelAdmission
from autobots.application.plans import load_goal
from autobots.application.run_projection import read_workspace
from autobots.application.run_usage import RootLimits
from autobots.application.runs import Inheritance, admit_run, apply_command
from autobots.application.worker_leases import claim_run
from autobots.contracts.experts import ExpertConfig, SessionExpert
from autobots.domain.models import resolve_role_policy
from autobots.domain.runs import Actor, RunCommand
from autobots.domain.tools import DELEGATION_TOOL
from goal_loop_script import ROUTE, Script, calls, say
from pydantic import SecretStr

URL, BASE = os.environ['AUTOBOTS_DATABASE_URL'], os.environ['AUTOBOTS_STORAGE_BASE']
SERVICE = SecretStr(os.environ['AUTOBOTS_STORAGE_SERVICE'])
WORKSPACE, PYTHON = UUID(sys.argv[1]), sys.argv[2]
HERE = Path(__file__).parent
ACTOR = uuid4()
PARENT_TASK = {'id': 'p', 'title': 'Delegate', 'criteria': ['c1'], 'expected_evidence': 'a result'}
CHILD_TASK = {'id': 'k', 'title': 'Part', 'criteria': ['c1'], 'expected_evidence': 'a file'}
PARENT_PLAN = ('propose_plan', {'tasks': [PARENT_TASK]})
CHILD_PLAN = ('propose_plan', {'tasks': [CHILD_TASK]})
cases = []


def check(name: str, expected: str, observed: object, passed: bool) -> None:
    cases.append({'id': name, 'expected': expected, 'observed': str(observed), 'passed': bool(passed)})


async def main() -> None:
    store = SupabaseObjectStore(BASE, SERVICE)
    config = LoopConfig(route=ROUTE, object_store=store, sleep=lambda _: asyncio.sleep(0))
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        async def value(sql: str, *values: object) -> Any:
            return (await (await db.execute(sql, values)).fetchone())[0]

        async def expert(name: str, **config_values: Any) -> Any:
            return await create_expert(db, workspace_id=WORKSPACE, actor_id=ACTOR, idempotency_key=f'expert-{name}', name=name, config=ExpertConfig(**config_values))

        lead = await expert('Assign Lead', tools=['calculate', 'save_artifact', 'publish_artifact'])
        helper = await expert('Assign Helper', tools=['calculate', 'save_artifact', 'publish_artifact', 'read_run_file'], role_bindings={'executor': 'openrouter_deepseek_flash'}, instructions='Help.')
        limited = await expert('Assign Limited', tools=['read_run_file'])
        outside = await expert('Assign Outside', tools=['calculate'])
        session = await create_session(db, workspace_id=WORKSPACE, actor_id=ACTOR, idempotency_key='sess', kind='coordinator', experts=[SessionExpert(expert_id=e.id) for e in (lead, helper, limited)])

        async def admit() -> UUID:
            await db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null where status <> 'done'")
            binding = await resolve_binding(db, WORKSPACE, session.id, expert_id=lead.id)
            return (await admit_run(db, workspace_id=WORKSPACE, actor_id=ACTOR, idempotency_key=str(uuid4()), goal_text='Lead the work', limit_micro_usd=1_000_000, policy=resolve_role_policy(), binding=binding)).run_id

        def assign(expert_view: Any, **options: Any) -> tuple[str, dict[str, Any]]:
            return ('assign_specialist', {'expert_id': str(expert_view.id), 'goal': 'Do the part', **options})

        async def go(items: list[Any], cfg: LoopConfig = config) -> tuple[Any, Script, UUID]:
            run = await admit()
            model = Script(items=items, seen=[], bound=[])
            result = await process_next(db, URL, 'parent', lambda: model, cfg)
            return result, model, run

        def tool_replies(model: Script, name: str) -> list[dict[str, Any]]:
            return [json.loads(item.content) for messages in model.seen for item in messages if item.type == 'tool' and item.name == name]

        CHILD_SAVE = ('save_artifact', {'path': 'outputs/child-1/part.md', 'content': 'part'})
        CHILD_PUBLISH = ('publish_artifact', {'path': 'outputs/child-1/part.md', 'version': 1})
        CHILD_DONE = ('complete_task', {'task_id': 'k', 'evidence': [{'kind': 'artifact', 'reference': 'outputs/child-1/part.md'}], 'summary': 'done part'})

        # A child completes, and only references come back.
        result, model, run = await go([calls(PARENT_PLAN), calls(assign(helper, criteria=['Finish the part'])), calls(CHILD_PLAN), calls(CHILD_SAVE), calls(CHILD_PUBLISH), calls(CHILD_DONE), say('child finished'), say('parent stops')])
        row = await (await db.execute('select child_run_id, depth, status, outcome from app_private.assignments where parent_run_id = %s', (run,))).fetchone()
        child = row[0]
        check('an assignment runs a real child to a verified result', 'depth 1, finished, succeeded', row[1:], row[1:] == (1, 'finished', 'succeeded'))
        parent_row = await (await db.execute('select parent_run_id, root_run_id, status from public.runs where id = %s', (child,))).fetchone()
        check('the child records its parent and root', 'linked, succeeded', parent_row[2], parent_row[0] == run and parent_row[1] == run and parent_row[2] == 'succeeded')
        reply = tool_replies(model, 'assign_specialist')[-1]['output']
        check('the parent gets a concise result with artifact references', 'references only', sorted(reply), reply['outcome'] == 'succeeded' and len(reply['artifact_ids']) == 1 and 'content' not in reply)
        parent_files = await value('select count(*) from app_private.run_files where run_id = %s', run)
        check('the child\'s intermediate files stay in its own run', '0 on the parent', parent_files, parent_files == 0)

        # Roles are inherited, and scope only narrows.
        parent_snapshot = await value('select policy_snapshot from public.runs where id = %s', run)
        child_snapshot = await value('select policy_snapshot from public.runs where id = %s', child)
        check('the child keeps the parent\'s fixed policy, not its Expert\'s binding', 'the same snapshot', child_snapshot == parent_snapshot, child_snapshot == parent_snapshot and child_snapshot['bindings']['executor'] == 'openrouter_terra')
        spec = await value('select spec from app_private.goal_specs where run_id = %s', child)
        check('child tools are the intersection with the parent', 'no read_run_file', sorted(spec['allowed_tools']), 'read_run_file' not in spec['allowed_tools'] and 'calculate' in spec['allowed_tools'])
        check('child paths are the parent inputs and its own namespace', "inputs, outputs/child-1", spec['allowed_paths'], spec['allowed_paths'] == ['inputs', 'outputs/child-1'])
        check('the model running the child sees only those tools', 'no read_run_file', model.bound[2] if len(model.bound) > 2 else None, len(model.bound) > 2 and 'read_run_file' not in model.bound[2])

        result, model, run = await go([calls(PARENT_PLAN), calls(assign(limited)), calls(CHILD_PLAN), calls(('read_run_file', {'path': 'inputs/x'})), say('child stops'), say('parent stops')])
        replies = tool_replies(model, 'read_run_file')
        check('a tool the parent lacks is denied to the child, though its Expert has it', 'tool_not_granted', replies[-1]['code'], replies[-1]['code'] == 'tool_not_granted')

        result, model, run = await go([calls(PARENT_PLAN), calls(assign(helper, tools=['read_run_file'])), say('parent stops')])
        reply = tool_replies(model, 'assign_specialist')[-1]
        check('asking for more than the parent holds is refused', 'scope_expansion_denied, no child', (reply['code'], await value('select count(*) from app_private.assignments where parent_run_id = %s', run)), reply['code'] == 'scope_expansion_denied' and await value('select count(*) from app_private.assignments where parent_run_id = %s', run) == 0)
        result, model, run = await go([calls(PARENT_PLAN), calls(assign(outside)), say('parent stops')])
        reply = tool_replies(model, 'assign_specialist')[-1]
        check('an Expert outside the session is refused', 'route_not_granted', reply['code'], reply['code'] == 'route_not_granted')

        # Depth, headcount, outstanding and spend.
        result, model, run = await go([calls(PARENT_PLAN), calls(assign(helper)), calls(CHILD_PLAN), calls(assign(helper)), say('child stops'), say('parent stops')], LoopConfig(route=ROUTE, object_store=store, limits=RootLimits(child_levels=1)))
        reply = tool_replies(model, 'assign_specialist')[0]
        check('a child at the depth limit can\'t delegate further', 'tool_not_granted', reply['code'], reply['code'] == 'tool_not_granted')
        result, model, run = await go([calls(PARENT_PLAN), calls(assign(helper, goal='First')), calls(CHILD_PLAN), say('child stops'), calls(assign(helper, goal='Second')), say('parent stops')], LoopConfig(route=ROUTE, object_store=store, limits=RootLimits(children=1)))
        reply = tool_replies(model, 'assign_specialist')[-1]
        count = await value('select count(*) from app_private.assignments where root_run_id = %s', run)
        check('the headcount limit refuses another child', 'children_limit, 1 child', (reply['code'], count), reply['code'] == 'children_limit' and count == 1)
        result, model, run = await go([calls(PARENT_PLAN), calls(assign(helper)), say('parent stops')], LoopConfig(route=ROUTE, object_store=store, limits=RootLimits(outstanding_assignments=0)))
        reply = tool_replies(model, 'assign_specialist')[-1]
        check('the outstanding limit refuses a child', 'outstanding_assignments_limit', reply['code'], reply['code'] == 'outstanding_assignments_limit')
        result, model, run = await go([calls(PARENT_PLAN), calls(assign(helper)), calls(CHILD_PLAN), say('never'), say('never')], LoopConfig(route=ROUTE, object_store=store, limits=RootLimits(model_calls=3)))
        calls_on_root = await value('select model_calls from app_private.run_usage where run_id = %s', run)
        check('calls by the child count against the root', '3 calls, then stopped', (len(model.seen), calls_on_root), len(model.seen) == 3 and calls_on_root == 3)
        roots = await value('select count(distinct root_run_id) from app_private.model_invocations where root_run_id = %s', run)
        children = await (await db.execute('select count(*) from app_private.model_invocations i join public.runs r on r.id = i.run_id where i.root_run_id = %s and r.parent_run_id = %s', (run, run))).fetchone()
        check('the child\'s calls are reserved on the root', 'on the root ledger', (roots, children[0]), roots == 1 and children[0] >= 1)

        # A child stops on the root's money and time, through the same refusals as the root.
        def on_root(sql: str) -> Any:
            def apply() -> Any:
                with psycopg.connect(URL, autocommit=True) as sync:
                    root = sync.execute("select id from public.runs where parent_run_id is null order by created_at desc limit 1").fetchone()[0]
                    sync.execute(sql, (root,))
                return calls(CHILD_PLAN)
            return apply

        result, model, run = await go([calls(PARENT_PLAN), calls(assign(helper)), on_root('update public.runs set limit_micro_usd = 0 where id = %s'), say('never'), say('never')])
        row = await (await db.execute('select r.status, a.outcome from app_private.assignments a join public.runs r on r.id = a.child_run_id where a.parent_run_id = %s', (run,))).fetchone()
        stopped = await value('select u.stop_reason from app_private.run_usage u join public.runs r on r.id = u.run_id where r.parent_run_id = %s', run)
        check('a child past the money stops, and no further call goes out', 'budget_exceeded, paused for more budget, 3 calls', (stopped, row, len(model.seen)), stopped == 'budget_exceeded' and row[0] == 'paused' and len(model.seen) == 3)
        reserved = await value("select count(*) from app_private.model_invocations where root_run_id = %s", run)
        check('nothing was reserved for the refused call', '3 on the ledger', reserved, reserved == 3)
        result, model, run = await go([calls(PARENT_PLAN), calls(assign(helper)), on_root('update app_private.run_usage set active_seconds = 1000 where run_id = %s'), say('never'), say('never')], LoopConfig(route=ROUTE, object_store=store, limits=RootLimits(active_seconds=100)))
        row = await (await db.execute('select r.status, a.outcome from app_private.assignments a join public.runs r on r.id = a.child_run_id where a.parent_run_id = %s', (run,))).fetchone()
        stopped = await value('select u.stop_reason from app_private.run_usage u join public.runs r on r.id = u.run_id where r.parent_run_id = %s', run)
        check("a child past the root's active time stops", 'active_time_limit, failed, 3 calls', (stopped, row, len(model.seen)), stopped == 'active_time_limit' and row[0] == 'failed' and len(model.seen) == 3)

        # LC-04: a limit across the tree stops new work, and what a finished child made stays readable.
        result, model, run = await go([calls(PARENT_PLAN), calls(assign(helper, goal='First')), calls(CHILD_PLAN), calls(CHILD_SAVE), calls(CHILD_PUBLISH), calls(CHILD_DONE), say('child finished'), calls(assign(helper, goal='Second')), calls(CHILD_PLAN), say('never'), say('never')],
                                      LoopConfig(route=ROUTE, object_store=store, sleep=lambda _: asyncio.sleep(0), limits=RootLimits(model_calls=8)))
        first = await (await db.execute("select child_run_id, outcome from app_private.assignments where parent_run_id = %s order by created_at limit 1", (run,))).fetchone()
        readable = await read_workspace(db, WORKSPACE, first[0])
        parent_view = await read_workspace(db, WORKSPACE, run)
        stop = await value('select stop_reason from app_private.run_usage where run_id = %s', run)
        later = await (await db.execute("select count(*), coalesce(sum((select count(*) from app_private.tool_receipts t where t.run_id = a.child_run_id)), 0) from app_private.assignments a where a.parent_run_id = %s and a.child_run_id <> %s", (run, first[0]))).fetchone()
        check('a limit across the tree stops new calls at the limit', '8 calls, stopped by the limit', (len(model.seen), stop), len(model.seen) == 8 and stop == 'model_calls_limit')
        check('and no later child made a tool call', 'a later child exists, with no receipts', later, later[0] >= 1 and later[1] == 0)
        check("a finished child's result and artifact stay readable from the run", 'the card reads succeeded, and the child shows 1 published artifact', ([item.outcome for item in parent_view.assignments], [item.status for item in readable.artifacts]), parent_view.assignments[0].outcome == 'succeeded' and [item.status for item in readable.artifacts] == ['published'])

        # US-12.1: a run admitted on DeepSeek before it stopped being offered keeps its route, and so do its children.
        frozen = await admit_run(db, workspace_id=WORKSPACE, actor_id=ACTOR, idempotency_key=str(uuid4()), goal_text='Lead on a frozen route', limit_micro_usd=1_000_000, policy=resolve_role_policy(run_profile='openrouter_deepseek_flash'), binding=await resolve_binding(db, WORKSPACE, session.id, expert_id=lead.id))
        held = await (await db.execute("update app_private.run_jobs set available_at = clock_timestamp() + interval '1 hour' where status = 'queued' and run_id <> %s returning run_id", (frozen.run_id,))).fetchall()
        model = Script(items=[calls(PARENT_PLAN), calls(assign(helper)), calls(CHILD_PLAN), say('child stops'), say('parent stops')], seen=[], bound=[])
        await process_next(db, URL, 'parent', lambda: model, LoopConfig(route=ModelRoute('executor', 'openrouter_deepseek_flash', 'fixture/model', 1000), object_store=store, sleep=lambda _: asyncio.sleep(0)))
        await db.execute('update app_private.run_jobs set available_at = clock_timestamp() where run_id = any(%s)', ([row[0] for row in held],))
        inherited = await value("select r.policy_snapshot -> 'bindings' ->> 'executor' from app_private.assignments a join public.runs r on r.id = a.child_run_id where a.parent_run_id = %s", frozen.run_id)
        check('a child under a frozen DeepSeek policy is admitted on that route', 'openrouter_deepseek_flash', inherited, inherited == 'openrouter_deepseek_flash')

        # No slot is held while waiting on a child.
        seen_active: list[int] = []

        class Watching(Script):
            def _generate(self, messages: Any, stop: Any = None, run_manager: Any = None, **options: Any) -> Any:
                if len(self.seen) == 2:
                    with psycopg.connect(URL, autocommit=True) as other:
                        parent = other.execute("select id from public.runs where workspace_id = %s and parent_run_id is null order by created_at desc limit 1", (WORKSPACE,)).fetchone()[0]
                        seen_active.append(other.execute("select count(*) from app_private.model_invocations where run_id = %s and status in ('reserved', 'dispatched')", (parent,)).fetchone()[0])
                return super()._generate(messages, stop, run_manager, **options)

        run = await admit()
        model = Watching(items=[calls(PARENT_PLAN), calls(assign(helper)), say('child stops'), say('parent stops')], seen=[], bound=[])
        await process_next(db, URL, 'parent', lambda: model, config)
        check('the parent holds no model slot while its child runs', '0 active on the parent', seen_active, seen_active == [0])

        # A repeated request, and a replay that finds the finished result.
        items = [calls(PARENT_PLAN), calls(assign(helper)), calls(CHILD_PLAN), say('child stops'), calls(assign(helper)), say('parent stops')]
        result, model, run = await go(items)
        count = await value('select count(*) from app_private.assignments where parent_run_id = %s', run)
        replies = tool_replies(model, 'assign_specialist')
        check('the model repeating a request gets the same child', '1 child, same id', (count, replies[0]['output']['child_run_id'] == replies[-1]['output']['child_run_id']), count == 1 and replies[0]['output']['child_run_id'] == replies[-1]['output']['child_run_id'])

        # Parent cancellation reaches the child.
        run = await admit()

        class Cancels(Script):
            def _generate(self, messages: Any, stop: Any = None, run_manager: Any = None, **options: Any) -> Any:
                if len(self.seen) == 2:
                    asyncio.run(_cancel(run))
                return super()._generate(messages, stop, run_manager, **options)

        model = Cancels(items=[calls(PARENT_PLAN), calls(assign(helper)), calls(CHILD_PLAN), calls(CHILD_SAVE), say('never')], seen=[], bound=[])
        result = await process_next(db, URL, 'parent', lambda: model, config)
        child = await value('select child_run_id from app_private.assignments where parent_run_id = %s', run)
        statuses = (await value('select status from public.runs where id = %s', run), await value('select status from public.runs where id = %s', child))
        check('cancelling a parent cancels its child, and no new call starts', 'both cancelled, 3 calls', (statuses, len(model.seen)), statuses == ('cancelled', 'cancelled') and len(model.seen) == 3)
        files = await value('select count(*) from app_private.run_files where run_id = %s', child)
        check('and the child\'s next effect never happens', '0 files', files, files == 0)

        # B3: the parent's lease expires first, then a cancel. The child must not be stranded.
        run = await admit()
        process = await asyncio.create_subprocess_exec(PYTHON, str(HERE / 'assignment_worker.py'), URL, str(helper.id), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await asyncio.wait_for(process.communicate(), 60)
        child = await value('select child_run_id from app_private.assignments where parent_run_id = %s', run)
        await db.execute("update app_private.run_jobs set lease_expires_at = clock_timestamp() - interval '1 second' where run_id = %s", (run,))
        await db.execute("update app_private.run_jobs set lease_expires_at = clock_timestamp() + interval '1 hour' where run_id = %s", (child,))
        version = await value('select version from public.runs where id = %s', run)
        await apply_command(db, workspace_id=WORKSPACE, run_id=run, command=RunCommand.CANCEL, actor=Actor.USER, expected_version=version)
        result = await process_next(db, URL, 'first-settler', lambda: Script(items=[], seen=[], bound=[]), config)
        parent_state = await value('select status from public.runs where id = %s', run)
        child_state = await value('select status from public.runs where id = %s', child)
        job = await (await db.execute('select status, available_at > clock_timestamp() from app_private.run_jobs where run_id = %s', (run,))).fetchone()
        check('a cancelled parent waits for a child that still has a live owner', 'cancelling, children_settling, job queued for later', (parent_state, result.code if result else None, child_state, job), parent_state == 'cancelling' and result is not None and result.code == 'children_settling' and child_state == 'cancelling' and job[0] == 'queued' and job[1])
        await db.execute("update app_private.run_jobs set lease_expires_at = clock_timestamp() - interval '1 second' where run_id = %s", (child,))
        await db.execute("update app_private.run_jobs set available_at = clock_timestamp() where run_id = %s", (run,))
        result = await process_next(db, URL, 'second-settler', lambda: Script(items=[], seen=[], bound=[]), config)
        parent_state = await value('select status from public.runs where id = %s', run)
        child_state = await value('select status from public.runs where id = %s', child)
        closed = await value('select status from app_private.assignments where parent_run_id = %s', run)
        holding = await value("select count(*) from app_private.model_invocations where run_id = %s and status = 'dispatched'", child)
        uncertain = await value("select count(*) from app_private.model_invocations where run_id = %s and status = 'uncertain'", child)
        check('then both settle, the assignment closes and no slot stays held', 'cancelled, cancelled, finished, 0 dispatched, 1 uncertain', (parent_state, child_state, closed, holding, uncertain), parent_state == 'cancelled' and child_state == 'cancelled' and closed == 'finished' and holding == 0 and uncertain == 1)
        invocation = await value("select id from app_private.model_invocations where run_id = %s and status = 'uncertain'", child)
        await ModelAdmission(db).reconcile(invocation, 80)

        # B3 at depth 2: a child that's waiting on its own child must not be recorded as finished.
        run = await admit()
        process = await asyncio.create_subprocess_exec(PYTHON, str(HERE / 'assignment_worker.py'), URL, str(helper.id), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await asyncio.wait_for(process.communicate(), 60)
        child = await value('select child_run_id from app_private.assignments where parent_run_id = %s', run)
        snapshot = await value('select policy_snapshot from public.runs where id = %s', child)
        binding = await resolve_binding(db, WORKSPACE, session.id, expert_id=helper.id)
        grandchild = (await admit_run(db, workspace_id=WORKSPACE, actor_id=ACTOR, idempotency_key=str(uuid4()), goal_text='Do the small part', limit_micro_usd=1_000_000, inherit=Inheritance(parent_run_id=child, root_run_id=run, snapshot=snapshot, tools={'calculate': 1}, paths=('outputs/grand',), instructions='', session_id=session.id, expert_id=binding.expert_id, version=binding.version))).run_id
        await db.execute('insert into app_private.assignments (id, workspace_id, parent_run_id, child_run_id, root_run_id, operation_id, depth, expert_id, expert_version) values (%s, %s, %s, %s, %s, %s, 2, %s, %s)', (uuid4(), WORKSPACE, child, grandchild, run, str(uuid4()), binding.expert_id, binding.version))
        grand_lease = await claim_run(db, grandchild, worker_id='grandchild-owner', lease_seconds=3600)
        await db.execute("update app_private.run_jobs set lease_expires_at = clock_timestamp() - interval '1 second' where run_id in (%s, %s)", (run, child))
        version = await value('select version from public.runs where id = %s', run)
        await apply_command(db, workspace_id=WORKSPACE, run_id=run, command=RunCommand.CANCEL, actor=Actor.USER, expected_version=version)
        states = [await value('select status from public.runs where id = %s', item) for item in (run, child, grandchild)]
        check('a cancel reaches every level', 'all cancelling', states, states == ['cancelling'] * 3)
        result = await process_next(db, URL, 'depth-settler', lambda: Script(items=[], seen=[], bound=[]), config)
        states = [await value('select status from public.runs where id = %s', item) for item in (run, child, grandchild)]
        opened = await value("select count(*) from app_private.assignments where root_run_id = %s and status = 'open'", run)
        check('with a live grandchild, nothing is recorded as finished', 'all cancelling, both assignments open', (states, opened, result.code if result else None), states == ['cancelling'] * 3 and opened == 2 and result is not None and result.code == 'children_settling')
        await db.execute("update app_private.run_jobs set lease_expires_at = clock_timestamp() - interval '1 second', available_at = clock_timestamp() where run_id = %s", (grandchild,))
        await db.execute("update app_private.run_jobs set available_at = clock_timestamp() where run_id in (%s, %s)", (run, child))
        result = await process_next(db, URL, 'depth-settler-2', lambda: Script(items=[], seen=[], bound=[]), config)
        states = [await value('select status from public.runs where id = %s', item) for item in (run, child, grandchild)]
        opened = await value("select count(*) from app_private.assignments where root_run_id = %s and status = 'open'", run)
        check('then every level settles', 'all cancelled, none open', (states, opened), states == ['cancelled'] * 3 and opened == 0)
        check('a grandchild owner that lost the run no longer holds it', 'its lease is gone', grand_lease.generation < await value('select generation from app_private.run_jobs where run_id = %s', grandchild), grand_lease.generation < await value('select generation from app_private.run_jobs where run_id = %s', grandchild))
        invocation = await value("select id from app_private.model_invocations where run_id = %s and status = 'uncertain'", child)
        await ModelAdmission(db).reconcile(invocation, 80)

        # A child admitted as the cancel landed, so the cascade missed it. Queued, and paused.
        run = await admit()
        await claim_run(db, run, worker_id='live-owner', lease_seconds=30)
        snapshot = await value('select policy_snapshot from public.runs where id = %s', run)
        binding = await resolve_binding(db, WORKSPACE, session.id, expert_id=helper.id)
        version = await value('select version from public.runs where id = %s', run)
        await apply_command(db, workspace_id=WORKSPACE, run_id=run, command=RunCommand.CANCEL, actor=Actor.USER, expected_version=version)
        strays = []
        for name in ('queued stray', 'paused stray'):
            stray = (await admit_run(db, workspace_id=WORKSPACE, actor_id=ACTOR, idempotency_key=str(uuid4()), goal_text=name, limit_micro_usd=1_000_000, inherit=Inheritance(parent_run_id=run, root_run_id=run, snapshot=snapshot, tools={'calculate': 1}, paths=('outputs/stray',), instructions='', session_id=session.id, expert_id=binding.expert_id, version=binding.version))).run_id
            await db.execute('insert into app_private.assignments (id, workspace_id, parent_run_id, child_run_id, root_run_id, operation_id, depth, expert_id, expert_version) values (%s, %s, %s, %s, %s, %s, 1, %s, %s)', (uuid4(), WORKSPACE, run, stray, run, str(uuid4()), binding.expert_id, binding.version))
            strays.append(stray)
        stray_version = await value('select version from public.runs where id = %s', strays[1])
        await apply_command(db, workspace_id=WORKSPACE, run_id=strays[1], command=RunCommand.PAUSE, actor=Actor.USER, expected_version=stray_version)
        before = await value('select status from public.runs where id = %s', run)
        check('with a live owner the parent is cancelling', 'cancelling', before, before == 'cancelling')
        await db.execute("update app_private.run_jobs set lease_expires_at = clock_timestamp() - interval '1 second' where run_id = %s", (run,))
        result = await process_next(db, URL, 'stray-settler', lambda: Script(items=[], seen=[], bound=[]), config)
        states = [await value('select status from public.runs where id = %s', item) for item in (run, *strays)]
        opened = await value("select count(*) from app_private.assignments where root_run_id = %s and status = 'open'", run)
        check('children the cascade missed are still cancelled', 'all cancelled, none open', (states, opened, result.code if result else None), states == ['cancelled'] * 3 and opened == 0)

        # B4: the child reached a terminal state, and the parent died before writing that down.
        run = await admit()
        process = await asyncio.create_subprocess_exec(PYTHON, str(HERE / 'assignment_worker.py'), URL, str(helper.id), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await asyncio.wait_for(process.communicate(), 60)
        child = await value('select child_run_id from app_private.assignments where parent_run_id = %s', run)
        await db.execute("update app_private.run_jobs set lease_expires_at = clock_timestamp() - interval '1 second' where run_id in (%s, %s)", (run, child))
        version = await value('select version from public.runs where id = %s', child)
        await apply_command(db, workspace_id=WORKSPACE, run_id=child, command=RunCommand.CANCEL, actor=Actor.USER, expected_version=version)
        settled = await claim_run(db, child, worker_id='settle-child', lease_seconds=30)
        await _finish(db, settled, await load_goal(db, child), 'run_not_running')
        child_state = await value('select status from public.runs where id = %s', child)
        invocation = await value("select id from app_private.model_invocations where run_id = %s and status = 'uncertain'", child)
        await ModelAdmission(db).reconcile(invocation, 80)
        check('a child can be finished while its assignment is still open', 'cancelled, open', (child_state, await value('select status from app_private.assignments where parent_run_id = %s', run)), child_state == 'cancelled' and await value('select status from app_private.assignments where parent_run_id = %s', run) == 'open')
        model = Script(items=[say('parent stops')], seen=[], bound=[])
        result = await process_next(db, URL, 'replay-parent', lambda: model, config)
        rows = await (await db.execute('select status, result from app_private.assignments where parent_run_id = %s', (run,))).fetchall()
        reply = [json.loads(item.content) for messages in model.seen for item in messages if item.type == 'tool' and item.name == DELEGATION_TOOL]
        check('a replay reads the finished child instead of spinning', 'one assignment, finished, the child\'s own status', (len(rows), rows[0][0], rows[0][1].get('run_status') if rows[0][1] else None, reply[-1].get('outcome') if reply else None), len(rows) == 1 and rows[0][0] == 'finished' and rows[0][1].get('run_status') == 'cancelled' and bool(reply) and reply[-1].get('outcome') == 'succeeded')
        await db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null where run_id = %s", (run,))

        # A real parent dies in its child's model call, and the replacement reattaches.
        run = await admit()
        process = await asyncio.create_subprocess_exec(PYTHON, str(HERE / 'assignment_worker.py'), URL, str(helper.id), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        _, err = await asyncio.wait_for(process.communicate(), 60)
        check('the parent process was killed in its child\'s model call', 'exit -9', f'exit {process.returncode}: {err.decode()[-300:]}', process.returncode == -9)
        child = await value('select child_run_id from app_private.assignments where parent_run_id = %s', run)
        await db.execute("update app_private.run_jobs set lease_expires_at = clock_timestamp() - interval '1 second' where run_id in (%s, %s)", (run, child))
        model = Script(items=[calls(PARENT_PLAN)], seen=[], bound=[])
        result = await process_next(db, URL, 'replacement', lambda: model, config)
        check('the replacement finds the child\'s uncertain call and pauses', 'paused, assignment_paused, no new call', (result.run_status, result.code, len(model.seen)), result.run_status == 'paused' and result.code == 'assignment_paused' and not model.seen)
        count = await value('select count(*) from app_private.assignments where parent_run_id = %s', run)
        check('with no second child', '1 assignment', count, count == 1)
        invocation = await value("select id from app_private.model_invocations where run_id = %s and status = 'uncertain'", child)
        await ModelAdmission(db).reconcile(invocation, 80)
        version = await value('select version from public.runs where id = %s', run)
        await apply_command(db, workspace_id=WORKSPACE, run_id=run, command=RunCommand.RESUME, actor=Actor.USER, expected_version=version)
        model = Script(items=[say('child stops now'), say('parent stops')], seen=[], bound=[])
        result = await process_next(db, URL, 'after-reconcile', lambda: model, config)
        count = await value('select count(*) from app_private.assignments where parent_run_id = %s', run)
        finished = await value('select status from app_private.assignments where parent_run_id = %s', run)
        check('after reconciling, resuming the parent finishes the same child', '1 assignment, finished', (count, finished), count == 1 and finished == 'finished')
        generation = await value('select generation from app_private.run_jobs where run_id = %s', child)
        check('under a new generation of its own', 'more than 1', generation, generation > 1)
    print(json.dumps({'cases': cases}))


async def _cancel(run: UUID) -> None:
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as other:
        version = (await (await other.execute('select version from public.runs where id = %s', (run,))).fetchone())[0]
        await apply_command(other, workspace_id=WORKSPACE, run_id=run, command=RunCommand.CANCEL, actor=Actor.USER, expected_version=version)


try:
    asyncio.run(main())
except Exception:
    print(json.dumps({'cases': cases}))
    raise
