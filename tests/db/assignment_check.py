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
from pydantic import SecretStr

sys.path.insert(0, str(Path(__file__).parent))
from goal_loop_script import ROUTE, Script, calls, say  # noqa: E402

from autobots.adapters.object_storage import SupabaseObjectStore  # noqa: E402
from autobots.application.experts import create_expert, create_session, resolve_binding  # noqa: E402
from autobots.application.goal_loop import LoopConfig, process_next  # noqa: E402
from autobots.application.model_admission import ModelAdmission  # noqa: E402
from autobots.application.run_usage import RootLimits  # noqa: E402
from autobots.application.runs import admit_run, apply_command  # noqa: E402
from autobots.contracts.experts import ExpertConfig, SessionExpert  # noqa: E402
from autobots.domain.models import resolve_role_policy  # noqa: E402
from autobots.domain.runs import Actor, RunCommand  # noqa: E402

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
        helper = await expert('Assign Helper', tools=['calculate', 'save_artifact', 'publish_artifact', 'read_run_file'], role_bindings={'executor': 'openrouter_astra'}, instructions='Help.')
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
        check('the child keeps the parent\'s fixed policy, not its Expert\'s binding', 'the same snapshot', child_snapshot == parent_snapshot, child_snapshot == parent_snapshot and child_snapshot['bindings']['executor'] == 'openrouter_deepseek_flash')
        spec = await value('select spec from app_private.goal_specs where run_id = %s', child)
        check('child tools are the intersection with the parent', 'no read_run_file', sorted(spec['allowed_tools']), 'read_run_file' not in spec['allowed_tools'] and 'calculate' in spec['allowed_tools'])
        check('child paths are the parent inputs and its own namespace', "inputs, outputs/child-1", spec['allowed_paths'], spec['allowed_paths'] == ['inputs', 'outputs/child-1'])
        check('the model running the child sees only those tools', 'no read_run_file', model.bound[2] if len(model.bound) > 2 else None, len(model.bound) > 2 and 'read_run_file' not in model.bound[2])

        result, model, run = await go([calls(PARENT_PLAN), calls(assign(limited)), calls(CHILD_PLAN), calls(('read_run_file', {'path': 'inputs/x'})), say('child stops'), say('parent stops')])
        replies = tool_replies(model, 'read_run_file')
        check('a tool the parent lacks is denied to the child, though its Expert has it', 'tool_not_granted', replies[-1]['code'], replies[-1]['code'] == 'tool_not_granted')

        result, model, run = await go([calls(PARENT_PLAN), calls(assign(helper, tools=['read_run_file'])), say('parent stops')])
        reply = tool_replies(model, 'assign_specialist')[-1]
        check('asking for more than the parent holds is refused', 'scope_expansion_denied, no child', (reply['code'], await value('select count(*) from app_private.assignments where parent_run_id = %s', run)), reply['code'] == 'scope_expansion_denied')
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
