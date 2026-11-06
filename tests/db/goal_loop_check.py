"""The loop on a real database and a real Deep Agents graph, with a scripted model. JSON cases."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import psycopg
from langchain_core.outputs import ChatResult

sys.path.insert(0, str(Path(__file__).parent))
from goal_loop_script import DONE_A, PLAN, ROUTE, SAVE, TASK_A, TASK_B, Script, calls, say  # noqa: E402

from autobots.adapters.loop_middleware import AdmittedModel, ModelRoute, UnadmittedModelCall
from autobots.application.goal_loop import LoopConfig, run_goal
from autobots.application.model_admission import ModelAdmission
from autobots.application.model_attempts import FailureClass, ProviderFailure
from autobots.application.plans import _evidence_exists, latest_plan, load_goal
from autobots.application.run_usage import RootLimits, consume, LimitReached, ensure_usage
from autobots.application.runs import admit_run, apply_command
from autobots.application.worker_leases import claim_next
from autobots.domain.models import resolve_role_policy
from autobots.domain.runs import Actor, RunCommand

URL = os.environ['AUTOBOTS_DATABASE_URL']
WORKSPACE, OTHER, PYTHON = UUID(sys.argv[1]), UUID(sys.argv[2]), sys.argv[3]
cases = []


def check(name: str, expected: str, observed: object, passed: bool) -> None:
    cases.append({'id': name, 'expected': expected, 'observed': str(observed), 'passed': bool(passed)})


async def main() -> None:
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        async def value(sql: str, *values: object) -> Any:
            return (await (await db.execute(sql, values)).fetchone())[0]

        async def start(workspace: UUID = WORKSPACE) -> Any:
            await db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null where status <> 'done'")
            await admit_run(db, workspace_id=workspace, actor_id=uuid4(), idempotency_key=str(uuid4()), goal_text='Write the report', limit_micro_usd=1_000_000, policy=resolve_role_policy(), acceptance_criteria=('Has a summary', 'Has figures'))
            return await claim_next(db, worker_id='loop', lease_seconds=300)

        async def go(lease: Any, items: list[Any], limits: RootLimits | None = None, route: ModelRoute = ROUTE) -> tuple[Any, Script]:
            model = Script(items=items, seen=[], bound=[])
            config = LoopConfig(route=route, limits=limits or RootLimits(), sleep=lambda _: asyncio.sleep(0), slot_wait_seconds=2)
            return await run_goal(db, URL, lease, model, config), model

        # The goal is kept, and the plan is versioned through a real loop.
        lease = await start()
        revised = {'tasks': [TASK_A, {**TASK_B, 'title': 'Figures and table'}, {'id': 'c', 'title': 'Check', 'criteria': ['c2'], 'expected_evidence': 'a file'}], 'revision_reason': 'the figures need a table'}
        result, model = await go(lease, [
            calls(PLAN), calls(SAVE), calls(DONE_A),
            calls(('propose_plan', revised)),
            calls(('save_artifact', {'path': 'outputs/b.md', 'content': 'figures'})),
            calls(('complete_task', {'task_id': 'b', 'evidence': [{'kind': 'artifact', 'reference': 'outputs/b.md'}], 'summary': 'figures'})),
            calls(('complete_task', {'task_id': 'c', 'evidence': [{'kind': 'artifact', 'reference': 'outputs/b.md'}], 'summary': 'checked'})),
            say('all done')])
        check('a finished plan becomes a candidate, and the run moves to verifying', 'candidate, verifying', (result.outcome, result.run_status), result.outcome == 'candidate' and result.run_status == 'verifying')
        check('the model is shown only its grants', 'seven tools', sorted(model.bound[0]), sorted(model.bound[0]) == ['calculate', 'complete_task', 'propose_plan', 'read_offload', 'read_run_file', 'save_artifact', 'search_memory'])
        goal = await load_goal(db, lease.run_id)
        check('the original request and criteria are kept', 'request and two criteria', (goal.original_request, goal.criteria), goal.original_request == 'Write the report' and list(goal.criteria.values()) == ['Has a summary', 'Has figures'])
        rows = await (await db.execute('select version, revision_reason, jsonb_array_length(tasks) from app_private.plan_versions where run_id = %s order by version', (lease.run_id,))).fetchall()
        check('plans are versioned with revision reasons', 'v1 no reason, v2 with reason', rows, rows == [(1, None, 2), (2, 'the figures need a table', 3)])
        first = await value("select tasks -> 1 ->> 'title' from app_private.plan_versions where run_id = %s and version = 1", lease.run_id)
        check('the earlier version is still there', 'Figures', first, first == 'Figures')
        kept = await value("select evidence -> 0 ->> 'reference' from app_private.plan_evidence where run_id = %s and task_id = 'a'", lease.run_id)
        check('completed evidence survives the revision', 'outputs/a.md', kept, kept == 'outputs/a.md')
        shown = [reply.get('operation_id') for reply in (json.loads(m.content) for m in model.seen[-1] if m.type == 'tool') if reply['outcome'] == 'succeeded']
        check('a reply shows an operation_id that receipt evidence accepts', 'accepted', shown[:1], bool(shown[0]) and await _evidence_exists(db, lease.run_id, 'receipt', shown[0]))
        check('and receipt evidence refuses anything else', 'refused', 'not-an-operation', not await _evidence_exists(db, lease.run_id, 'receipt', 'not-an-operation'))
        check('usage is counted', '8 calls, 7 tools, 1 revision', result.usage, result.usage['model_calls'] == 8 and result.usage['tool_dispatches'] == 7 and result.usage['plan_revisions'] == 1)
        settled = await value("select count(*) from app_private.model_invocations where run_id = %s and status = 'succeeded'", lease.run_id)
        check('every model call went through admission and settled', '8', settled, settled == 8)
        prompt = str(model.seen[0][-1].content)
        check('the model is given the goal and criteria', 'present', 'c2: Has figures' in prompt, 'c2: Has figures' in prompt and 'Write the report' in prompt)
        state_text = await value("""select (select coalesce(string_agg(encode(blob, 'escape'), ''), '') from agent_runtime.checkpoint_blobs where thread_id = %s)
                                 || (select coalesce(string_agg(checkpoint::text || metadata::text, ''), '') from agent_runtime.checkpoints where thread_id = %s)
                                 || (select coalesce(string_agg(encode(blob, 'escape'), ''), '') from agent_runtime.checkpoint_writes where thread_id = %s)""", str(lease.run_id), str(lease.run_id), str(lease.run_id))
        check('checkpoints were really read', 'non-empty', len(state_text) > 100, len(state_text) > 100)
        check('a key held by the model client reaches no checkpoint table', 'absent', 'sk-or-planted' in state_text, 'sk-or-planted' not in state_text)

        # A model saying it is done does not make it so.
        lease = await start()
        result, _ = await go(lease, [calls(PLAN), say('finished, trust me')])
        check('a claim of completion with open tasks is not success', 'stopped, plan_incomplete, failed', (result.outcome, result.code, result.run_status), result.code == 'plan_incomplete' and result.run_status == 'failed')
        check('it reports what remains', "('a', 'b')", result.remaining, result.remaining == ('a', 'b') and result.uncovered_criteria == ('c1', 'c2'))
        lease = await start()
        result, _ = await go(lease, [say('no plan needed')])
        check('no plan at all is not success', 'plan_missing, failed', (result.code, result.run_status), result.code == 'plan_missing' and result.run_status == 'failed')

        # Scope can't grow through a plan, and evidence can't be invented.
        lease = await start()
        wide = {'tasks': [{'id': 'x', 'title': 'x', 'criteria': ['c1', 'c2', 'c9'], 'expected_evidence': 'x'}]}
        result, model = await go(lease, [calls(('propose_plan', wide)), calls(('propose_plan', wide)), say('unused')])
        check('a plan widening scope is refused, and repeating it spends the one repair', 'repair_limit, failed', (result.code, result.run_status), result.code == 'repair_limit:plan_out_of_scope' and result.run_status == 'failed')
        check('no plan was committed', 'None', result.plan_version, result.plan_version is None)
        check('nothing past the limit was called', '2 calls', len(model.seen), len(model.seen) == 2)
        why = await value("select failure_code || '/' || failure_detail from app_private.tool_receipts where run_id = %s and tool_id = 'propose_plan'", lease.run_id)
        check('the receipt records why the plan was refused', 'plan_out_of_scope/criterion', why, why == 'plan_out_of_scope/criterion')
        lease = await start()
        fake = ('complete_task', {'task_id': 'a', 'evidence': [{'kind': 'artifact', 'reference': 'outputs/never.md'}], 'summary': 'done'})
        result, model = await go(lease, [calls(PLAN), calls(fake), say('stop')])
        replies = [m for m in model.seen[-1] if m.type == 'tool']
        check('invented evidence is refused', 'evidence_invalid', json.loads(replies[-1].content)['code'], json.loads(replies[-1].content)['code'] == 'evidence_invalid')
        check('and the task stays open', "('a', 'b')", result.remaining, result.remaining == ('a', 'b'))
        why = await value("select failure_code || '/' || failure_detail from app_private.tool_receipts where run_id = %s and tool_id = 'complete_task'", lease.run_id)
        check('the receipt records the form of what was cited, not its text', 'evidence_invalid/artifact:run_path', why, why == 'evidence_invalid/artifact:run_path')
        lease = await start()
        out_of_order = ('complete_task', {'task_id': 'b', 'evidence': [{'kind': 'artifact', 'reference': 'outputs/a.md'}], 'summary': 'done'})
        result, model = await go(lease, [calls(PLAN), calls(SAVE), calls(out_of_order), say('stop')])
        replies = [m for m in model.seen[-1] if m.type == 'tool']
        check('a task with open dependencies cannot complete', 'task_dependencies_open', json.loads(replies[-1].content)['code'], json.loads(replies[-1].content)['code'] == 'task_dependencies_open')

        # Root limits stop new work.
        lease = await start()
        result, model = await go(lease, [calls(PLAN), calls(SAVE), calls(DONE_A), say('x')], RootLimits(model_calls=2))
        check('the model call limit stops new work', 'model_calls_limit, 2 calls, failed', (result.code, len(model.seen), result.run_status), result.code == 'model_calls_limit' and len(model.seen) == 2 and result.run_status == 'failed')
        check('that refused attempt was never dispatched', 'released, not charged', await value("select count(*) from app_private.model_invocations where run_id = %s and status = 'dispatched'", lease.run_id), await value("select count(*) from app_private.model_invocations where run_id = %s and status = 'dispatched'", lease.run_id) == 0)
        lease = await start()
        result, _ = await go(lease, [calls(PLAN), calls(SAVE), calls(DONE_A), say('x')], RootLimits(tool_dispatches=2))
        files = await value('select count(*) from app_private.run_files where run_id = %s', lease.run_id)
        check('the tool limit stops new work, and reports partial progress honestly', 'tool_dispatches_limit, plan v1, a file', (result.code, result.plan_version, files), result.code == 'tool_dispatches_limit' and result.plan_version == 1 and files == 1 and result.run_status == 'failed')
        lease = await start()
        result, _ = await go(lease, [calls(PLAN), say('x')], RootLimits(active_seconds=0.0))
        check('the active time limit stops new work', 'active_time_limit, no calls', (result.code, result.usage['model_calls']), result.code == 'active_time_limit' and result.usage['model_calls'] == 0)
        lease = await start()
        rev = lambda n: ('propose_plan', {'tasks': [TASK_A, {**TASK_B, 'title': f'v{n}'}], 'revision_reason': f'r{n}'})  # noqa: E731
        result, _ = await go(lease, [calls(PLAN), calls(rev(1)), calls(rev(2)), calls(rev(3)), say('x')])
        check('a third revision is past the two allowed', 'plan_revisions_limit, v3', (result.code, result.plan_version), result.code == 'plan_revisions_limit' and result.plan_version == 3)

        # Invalid structured output gets only the allowed repair.
        lease = await start()
        bad = ('save_artifact', {'path': 'outputs/a.md'})
        result, model = await go(lease, [calls(bad), calls(bad), calls(PLAN), say('x')])
        check('invalid arguments twice stops after one repair', 'repair_limit, 2 calls', (result.code, len(model.seen)), result.code == 'repair_limit:invalid_arguments' and len(model.seen) == 2)
        lease = await start()
        result, model = await go(lease, [calls(bad), calls(PLAN), calls(SAVE), calls(DONE_A), calls(('complete_task', {'task_id': 'b', 'evidence': [{'kind': 'artifact', 'reference': 'outputs/a.md'}], 'summary': 's'})), say('done')])
        check('one invalid call can be repaired, and the work finishes', 'candidate, 1 repair', (result.outcome, result.usage['repairs']), result.outcome == 'candidate' and result.usage['repairs'] == 1)
        lease = await start()
        cut = calls(SAVE, finish='length')
        result, model = await go(lease, [cut, cut, say('x')])
        files = await value('select count(*) from app_private.run_files where run_id = %s', lease.run_id)
        check('truncated output never runs its tool calls', 'no file, 1 repair, then stopped', (files, result.usage['repairs'], result.code), files == 0 and result.usage['repairs'] == 1 and result.code == 'incomplete_output')
        check('the repair told the model its reply was cut off', 'a note', 'cut off' in str(model.seen[1][-1].content), 'cut off' in str(model.seen[1][-1].content))
        lease = await start()
        result, _ = await go(lease, [calls(('execute', {'command': 'id'}), ('task', {'description': 'x', 'subagent_type': 'general-purpose'})), say('x')])
        check('shell and child requests get no capability, and stop honestly', 'plan_missing, failed', (result.code, result.run_status), result.code == 'plan_missing' and result.run_status == 'failed')

        # Retries use the same budget.
        lease = await start()
        failing = ProviderFailure(FailureClass.PROVIDER_ERROR)
        result, model = await go(lease, [failing, failing, failing, calls(PLAN)])
        check('retries are bounded, and each one counts', '3 attempts, provider_error, failed', (len(model.seen), result.usage['model_calls'], result.code), len(model.seen) == 3 and result.usage['model_calls'] == 3 and result.code == 'provider_error' and result.run_status == 'failed')
        lease = await start()
        result, model = await go(lease, [ProviderFailure(FailureClass.INVALID_CREDENTIAL)])
        check('a rejected credential pauses, with one attempt', 'invalid_credential, paused, 1', (result.code, result.run_status, len(model.seen)), result.code == 'invalid_credential' and result.run_status == 'paused' and len(model.seen) == 1)
        lease = await start()
        result, model = await go(lease, [calls(PLAN)], route=ModelRoute('executor', 'openrouter_deepseek_flash', 'fixture/model', 2_000_000))
        check('a call past the budget pauses without dispatching', 'budget_exceeded, paused, 0', (result.code, result.run_status, len(model.seen)), result.code == 'budget_exceeded' and result.run_status == 'paused' and len(model.seen) == 0)

        # A generic counter refuses past its limit, ready for the delegation stories.
        lease = await start()
        await ensure_usage(db, lease.run_id)
        for _ in range(4):
            await consume(db, lease.run_id, 'children', RootLimits().children)
        try:
            await consume(db, lease.run_id, 'children', RootLimits().children)
            check('the child limit refuses a fifth', 'children_limit', 'allowed', False)
        except LimitReached as reached:
            check('the child limit refuses a fifth', 'children_limit', reached.code, reached.code == 'children_limit')

        # An SDK path calling the model on its own gets nothing.
        guarded = AdmittedModel(delegate=Script(items=[say('leak')], seen=[], bound=[]))
        try:
            await guarded.ainvoke('summarize this')
            check('a model call outside admission is refused', 'refused', 'answered', False)
        except UnadmittedModelCall:
            check('a model call outside admission is refused', 'refused, delegate not called', len(guarded.delegate.seen), len(guarded.delegate.seen) == 0)

        # An uncertain call stays reserved and isn't sent again. These use the other workspace.
        lease = await start(OTHER)
        result, model = await go(lease, [ProviderFailure(FailureClass.PARTIAL_STREAM, accumulated_output='par'), calls(PLAN)])
        status = await value('select status from app_private.model_invocations where run_id = %s', lease.run_id)
        check('an uncertain call pauses and is not redispatched', 'partial_stream, paused, 1, uncertain', (result.code, result.run_status, len(model.seen), status), result.code == 'partial_stream' and result.run_status == 'paused' and len(model.seen) == 1 and status == 'uncertain')

        # A real worker process is killed inside a model call, and a new generation inherits everything.
        await db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null where status <> 'done'")
        admitted = await admit_run(db, workspace_id=OTHER, actor_id=uuid4(), idempotency_key=str(uuid4()), goal_text='Write the report', limit_micro_usd=1_000_000, policy=resolve_role_policy(), acceptance_criteria=('Has a summary', 'Has figures'))
        process = await asyncio.create_subprocess_exec(PYTHON, str(Path(__file__).parent / 'goal_loop_worker.py'), URL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        _, err = await asyncio.wait_for(process.communicate(), 60)
        check('the worker process was killed mid-loop', 'exit -9', f'exit {process.returncode}: {err.decode()[-300:]}', process.returncode == -9)
        job = await (await db.execute('select status, generation from app_private.run_jobs where run_id = %s', (admitted.run_id,))).fetchone()
        check('its job is still claimed by a dead owner', 'claimed', job, job[0] == 'claimed')
        leftover = await value("select count(*) from app_private.model_invocations where run_id = %s and status = 'dispatched'", admitted.run_id)
        check('its call stays open, since nobody knows how it ended', '1 dispatched', leftover, leftover == 1)
        # Arranged: the lease is expired rather than waited for.
        await db.execute("update app_private.run_jobs set lease_expires_at = clock_timestamp() - interval '1 second' where run_id = %s", (admitted.run_id,))
        replacement = await claim_next(db, worker_id='replacement', lease_seconds=300)
        usage_before = await value('select model_calls from app_private.run_usage where run_id = %s', admitted.run_id)
        blocked, untouched = await go(replacement, [calls(PLAN)])
        check('the open call is classified uncertain, and blocks another paid call', 'paused, no call', (blocked.code, blocked.run_status, len(untouched.seen)), blocked.code == 'uncertain_model_call' and blocked.run_status == 'paused' and len(untouched.seen) == 0)
        invocation = await value("select id from app_private.model_invocations where run_id = %s and status = 'uncertain'", admitted.run_id)
        await ModelAdmission(db).reconcile(invocation, 90)
        await apply_command(db, workspace_id=OTHER, run_id=admitted.run_id, command=RunCommand.RESUME, actor=Actor.USER, expected_version=await value('select version from public.runs where id = %s', admitted.run_id))
        replacement = await claim_next(db, worker_id='after-reconcile', lease_seconds=300)
        lease = replacement
        result, model = await go(replacement, [calls(DONE_A), calls(('complete_task', {'task_id': 'b', 'evidence': [{'kind': 'artifact', 'reference': 'outputs/a.md'}], 'summary': 's'})), say('done')])
        check('a replacement continues from the checkpoint after reconciliation', 'candidate, a new generation', (result.outcome, replacement.generation), result.outcome == 'candidate' and replacement.generation == 3)
        check('it does not start over', 'the prompt holds earlier tool results', sum(m.type == 'tool' for m in model.seen[0]), sum(m.type == 'tool' for m in model.seen[0]) == 2)
        check('usage carries across the restart', '3 before, 6 after', (usage_before, result.usage['model_calls']), usage_before == 3 and result.usage['model_calls'] == 6)
        files = await value('select count(*) from app_private.run_files where run_id = %s', lease.run_id)
        check('the saved file was not written again', '1', files, files == 1)

        # Ownership lost during the loop: new work stops, and no status is written.
        lease = await start()

        class Reassigned(Script):
            def _generate(self, messages: Any, stop: Any = None, run_manager: Any = None, **options: Any) -> ChatResult:
                with psycopg.connect(URL, autocommit=True) as other:
                    other.execute('update app_private.run_jobs set generation = generation + 1 where run_id = %s', (lease.run_id,))
                return super()._generate(messages, stop, run_manager, **options)

        model = Reassigned(items=[calls(PLAN), say('x')], seen=[], bound=[])
        result = await run_goal(db, URL, lease, model, LoopConfig(route=ROUTE))
        status = await value('select status from public.runs where id = %s', lease.run_id)
        check('a worker that lost the lease stops and writes no status', 'lost, running', (result.outcome, result.code, status), result.outcome == 'lost' and result.code == 'lease_lost' and status == 'running')
        await latest_plan(db, lease.run_id)
    print(json.dumps({'cases': cases}))


try:
    asyncio.run(main())
except Exception:
    print(json.dumps({'cases': cases}))
    raise
