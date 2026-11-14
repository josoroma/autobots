"""Cancellation, resume and recovery, with a real stopped process for Mac sleep. JSON cases."""
from __future__ import annotations

import asyncio
import json
import os
import signal
import sys
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import psycopg
from autobots.adapters.loop_middleware import ModelRoute
from autobots.application.goal_loop import LoopConfig, process_next, run_goal
from autobots.application.model_admission import ModelAdmission
from autobots.application.recovery import outstanding
from autobots.application.runs import (
    LeaseLost,
    LinkRefused,
    VersionConflict,
    admit_run,
    apply_command,
)
from autobots.application.tool_gateway import ToolDefinition, ToolGateway, ToolRegistry, ToolScope
from autobots.application.worker_leases import claim_next
from autobots.domain.models import resolve_role_policy
from autobots.domain.runs import Actor, CommandRefused, RunCommand
from autobots.domain.tools import OperationClass
from goal_loop_script import DONE_A, PLAN, ROUTE, SAVE, Script, calls, say
from pydantic import BaseModel

URL = os.environ['AUTOBOTS_DATABASE_URL']
WORKSPACE, OTHER, PYTHON = UUID(sys.argv[1]), UUID(sys.argv[2]), sys.argv[3]
HERE = Path(__file__).parent
cases = []
RESUME_ROUTE = LoopConfig(route=ROUTE, sleep=lambda _: asyncio.sleep(0))


def check(name: str, expected: str, observed: object, passed: bool) -> None:
    cases.append({'id': name, 'expected': expected, 'observed': str(observed), 'passed': bool(passed)})


class Nothing(BaseModel):
    note: str = ''


async def main() -> None:
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        async def value(sql: str, *values: object) -> Any:
            return (await (await db.execute(sql, values)).fetchone())[0]

        async def clear() -> None:
            await db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null where status <> 'done'")

        async def admit(workspace: UUID = WORKSPACE) -> UUID:
            await clear()
            return (await admit_run(db, workspace_id=workspace, actor_id=uuid4(), idempotency_key=str(uuid4()), goal_text='Write the report', limit_micro_usd=1_000_000, policy=resolve_role_policy(), acceptance_criteria=('Has a summary', 'Has figures'))).run_id

        async def state_of(run: UUID) -> str:
            return await value('select status from public.runs where id = %s', run)

        async def version_of(run: UUID) -> int:
            return await value('select version from public.runs where id = %s', run)

        async def user(run: UUID, command: RunCommand, **options: Any) -> Any:
            return await apply_command(db, workspace_id=WORKSPACE, run_id=run, command=command, actor=Actor.USER, expected_version=await version_of(run), **options)

        async def worker(run: UUID, lease: Any, command: RunCommand, **options: Any) -> Any:
            return await apply_command(db, workspace_id=WORKSPACE, run_id=run, command=command, actor=Actor.WORKER, expected_version=await version_of(run), generation=lease.generation, **options)

        async def expire(run: UUID) -> None:
            await db.execute("update app_private.run_jobs set lease_expires_at = clock_timestamp() - interval '1 second' where run_id = %s", (run,))

        async def finish(lease: Any, items: list[Any]) -> Any:
            return await run_goal(db, URL, lease, Script(items=items, seen=[], bound=[]), RESUME_ROUTE)

        # Cancel from every nonterminal state.
        run = await admit()
        result = await user(run, RunCommand.CANCEL)
        check('queued cancels directly', 'cancelled', result.status, result.status == 'cancelled')
        run = await admit()
        lease = await claim_next(db, worker_id='w')
        result = await user(run, RunCommand.CANCEL)
        check('running, with a live owner, enters cancelling', 'cancelling', result.status, result.status == 'cancelling')
        repeat = await user(run, RunCommand.CANCEL)
        check('cancelling again changes nothing', 'unchanged', repeat.changed, not repeat.changed and repeat.status == 'cancelling')
        for command in (RunCommand.COMPLETE, RunCommand.VERIFY, RunCommand.REQUEST_INPUT):
            try:
                await worker(run, lease, command)
                check(f'{command.value} after a cancel is refused', 'refused', 'applied', False)
            except CommandRefused:
                check(f'{command.value} after a cancel is refused', 'refused', await state_of(run), await state_of(run) == 'cancelling')
        done = await worker(run, lease, RunCommand.FINISH_CANCEL)
        check('the owner finishes it', 'cancelled', done.status, done.status == 'cancelled')
        for setup, label in ((RunCommand.REQUEST_INPUT, 'waiting_input'), (RunCommand.REQUEST_APPROVAL, 'waiting_approval')):
            run = await admit()
            lease = await claim_next(db, worker_id='w')
            await worker(run, lease, setup, detail='Which file?')
            result = await user(run, RunCommand.CANCEL)
            check(f'{label} cancels directly, since no worker holds it', 'cancelled', result.status, result.status == 'cancelled')
        run = await admit()
        lease = await claim_next(db, worker_id='w')
        await user(run, RunCommand.PAUSE)
        result = await user(run, RunCommand.CANCEL)
        check('paused with its owner still stopping enters cancelling', 'cancelling', result.status, result.status == 'cancelling')
        run = await admit()
        lease = await claim_next(db, worker_id='w')
        await expire(run)
        await user(run, RunCommand.PAUSE)
        result = await user(run, RunCommand.CANCEL)
        check('paused with no owner and no open work cancels directly', 'cancelled', result.status, result.status == 'cancelled')
        run = await admit()
        lease = await claim_next(db, worker_id='w')
        await worker(run, lease, RunCommand.VERIFY)
        result = await user(run, RunCommand.CANCEL)
        check('verifying, with a live owner, enters cancelling', 'cancelling', result.status, result.status == 'cancelling')

        # Unsettled work keeps it honest, even with no live owner.
        run = await admit()
        lease = await claim_next(db, worker_id='dead')
        admission = ModelAdmission(db)
        from autobots.application.model_admission import AdmissionRequest
        ticket = await admission.admit(AdmissionRequest(WORKSPACE, run, run, 'executor', 'openrouter_terra', 'fixture/model', 1, 1000))
        await admission.mark_dispatched(ticket.invocation_id)
        await expire(run)
        result = await user(run, RunCommand.CANCEL)
        check('a dead owner with a dispatched call enters cancelling, not cancelled', 'cancelling', result.status, result.status == 'cancelling')
        processed = await process_next(db, URL, 'recovery', lambda: Script(items=[], seen=[], bound=[]), RESUME_ROUTE)
        status = await value('select status from app_private.model_invocations where id = %s', ticket.invocation_id)
        check('recovery classifies the call as uncertain and finishes the cancel', 'cancelled, uncertain, a reason', (processed.run_status, status, processed.code), processed.run_status == 'cancelled' and status == 'uncertain' and processed.code == 'cancelled_with_unknown_outcomes')
        reserved = await value('select reserved_micro_usd from app_private.model_invocations where id = %s', ticket.invocation_id)
        check('its reservation is kept until reconciled', '1000', reserved, reserved == 1000)
        late = await outstanding(db, run)
        check('the unknown outcome stays visible after the run is terminal', '1 uncertain', late, late.uncertain_calls == 1)
        await admission.reconcile(ticket.invocation_id, 700)
        status = await state_of(run)
        charged = await value('select charged_micro_usd from app_private.model_invocations where id = %s', ticket.invocation_id)
        check('a late charge updates the evidence and does not reopen the run', 'cancelled, 700', (status, charged), status == 'cancelled' and charged == 700)

        # A cancel reaching a live loop stops new dispatch.
        run = await admit()
        lease = await claim_next(db, worker_id='loop')

        class Cancels(Script):
            def _generate(self, messages: Any, stop: Any = None, run_manager: Any = None, **options: Any) -> Any:
                if len(self.seen) == 1:
                    with psycopg.connect(URL, autocommit=True) as other:
                        version = other.execute('select version from public.runs where id = %s', (run,)).fetchone()[0]
                        other.execute('select 1')
                    asyncio.run(_cancel(run, version))
                return super()._generate(messages, stop, run_manager, **options)

        model = Cancels(items=[calls(PLAN), calls(SAVE), calls(DONE_A), say('x')], seen=[], bound=[])
        result = await run_goal(db, URL, lease, model, RESUME_ROUTE)
        files = await value('select count(*) from app_private.run_files where run_id = %s', run)
        check('a cancel during a model call stops the next dispatch', 'cancelled, 2 calls, no file', (result.run_status, len(model.seen), files), result.run_status == 'cancelled' and len(model.seen) == 2 and files == 0)

        # A late tool result is recorded, and can't reopen anything.
        run = await admit()
        lease = await claim_next(db, worker_id='tool')
        version = await version_of(run)

        async def late_handler(_: Any, __: Any) -> Nothing:
            await _cancel(run, version)
            return Nothing()

        registry = ToolRegistry()
        registry.register(ToolDefinition(tool_id='late', version=1, description='fixture', input_model=Nothing, output_model=Nothing, operation_class=OperationClass.REVERSIBLE_INTERNAL_WRITE, handler=late_handler))
        scope = ToolScope(WORKSPACE, run, lease.generation, {'late': 1})
        result = await ToolGateway(registry).execute(db, scope, 'late', {})
        receipt = await value('select status from app_private.tool_receipts where operation_id = %s', result.operation_id)
        check('a tool result arriving after a cancel is recorded and refused', 'run_not_running, receipt succeeded', (result.code, receipt), result.code == 'run_not_running' and receipt == 'succeeded')

        # Competing completion and cancellation: one order wins, consistently.
        outcomes = {'succeeded': 0, 'cancelling': 0}
        for _ in range(20):
            run = await admit()
            lease = await claim_next(db, worker_id='race')
            await worker(run, lease, RunCommand.VERIFY)
            version = await version_of(run)

            async def complete() -> str:
                async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as other:
                    try:
                        return (await apply_command(other, workspace_id=WORKSPACE, run_id=run, command=RunCommand.COMPLETE, actor=Actor.WORKER, expected_version=version, generation=lease.generation)).status  # noqa: B023 - called within this iteration, so it reads this iteration's values
                    except (VersionConflict, CommandRefused, LeaseLost) as error:
                        # TDBC-07: the loser is refused. Any other failure propagates and fails the check.
                        return type(error).__name__

            async def cancel() -> str:
                async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as other:
                    try:
                        return (await apply_command(other, workspace_id=WORKSPACE, run_id=run, command=RunCommand.CANCEL, actor=Actor.USER, expected_version=version)).status  # noqa: B023 - called within this iteration, so it reads this iteration's values
                    except (VersionConflict, CommandRefused, LeaseLost) as error:
                        return type(error).__name__

            first, second = await asyncio.gather(complete(), cancel())
            final = await state_of(run)
            won = {first, second} & {'succeeded', 'cancelling'}
            if len(won) != 1 or final not in won:
                check('competing completion and cancellation never both apply', 'one winner', (first, second, final), False)
                break
            outcomes[final] += 1
        else:
            check('competing completion and cancellation never both apply', '20 rounds, one winner each', outcomes, sum(outcomes.values()) == 20)

        # Resume keeps obligations and bindings.
        run = await admit()
        lease = await claim_next(db, worker_id='w')
        await worker(run, lease, RunCommand.REQUEST_INPUT, detail='Which file?')
        await user(run, RunCommand.PAUSE)
        snapshot = await value('select policy_snapshot from public.runs where id = %s', run)
        await db.execute("insert into app_private.model_policies (workspace_id, version, default_profile, role_overrides) values (%s, 99, 'openrouter_deepseek_flash', '{}') on conflict (workspace_id) do update set default_profile = 'openrouter_deepseek_flash'", (WORKSPACE,))
        resumed = await user(run, RunCommand.RESUME)
        check('resume re-enters the queue', 'queued', resumed.status, resumed.status == 'queued')
        processed = await process_next(db, URL, 'after-resume', lambda: Script(items=[calls(PLAN)], seen=[], bound=[]), RESUME_ROUTE)
        check('an outstanding input can\'t be skipped by resuming', 'waiting_input, no model call', (processed.run_status, processed.usage['model_calls']), processed.run_status == 'waiting_input' and processed.usage['model_calls'] == 0)
        obligations = await value("select count(*) from app_private.run_obligations where run_id = %s and status = 'open'", run)
        check('there is still one open obligation', '1', obligations, obligations == 1)
        unchanged = await value('select policy_snapshot from public.runs where id = %s', run)
        check('a changed workspace policy leaves the run bound to its own', 'same snapshot', unchanged == snapshot, unchanged == snapshot)
        await user(run, RunCommand.SUBMIT_INPUT, response='report.md')
        response = await value("select response from app_private.run_obligations where run_id = %s", run)
        check('answering meets the obligation', 'report.md', response, response == 'report.md')
        processed = await process_next(db, URL, 'after-input', lambda: Script(items=[calls(PLAN), say('stop')], seen=[], bound=[]), LoopConfig(route=ROUTE))
        check('and the run continues', 'stopped at plan_incomplete after a real pass', (processed.code, processed.usage['model_calls']), processed.code == 'plan_incomplete' and processed.usage['model_calls'] == 2)
        await db.execute("update app_private.model_policies set default_profile = 'openrouter_terra' where workspace_id = %s", (WORKSPACE,))

        run = await admit()
        lease = await claim_next(db, worker_id='bound')
        other_route = LoopConfig(route=ModelRoute('executor', 'openrouter_deepseek_flash', 'fixture/other', 1000))
        model = Script(items=[calls(PLAN)], seen=[], bound=[])
        result = await run_goal(db, URL, lease, model, other_route)
        check('a route that differs from the frozen policy is refused', 'route_not_bound, no call', (result.code, len(model.seen)), result.code == 'route_not_bound' and len(model.seen) == 0)

        # Terminal states take a linked new run.
        run = await admit()
        await user(run, RunCommand.CANCEL)
        for command in (RunCommand.RESUME, RunCommand.SUBMIT_INPUT, RunCommand.PAUSE):
            try:
                await user(run, command)
                check(f'{command.value} cannot reopen a terminal run', 'refused', 'applied', False)
            except CommandRefused:
                check(f'{command.value} cannot reopen a terminal run', 'refused', await state_of(run), await state_of(run) == 'cancelled')
        linked = await admit_run(db, workspace_id=WORKSPACE, actor_id=uuid4(), idempotency_key=str(uuid4()), goal_text='Continue it', limit_micro_usd=1_000_000, policy=resolve_role_policy(), continues_run_id=run)
        link = await value('select continues_run_id from public.runs where id = %s', linked.run_id)
        check('continuing takes a new run linked to the old one', 'linked, and the old one stays cancelled', (link == run, await state_of(run)), link == run and await state_of(run) == 'cancelled')
        active = await admit()
        try:
            await admit_run(db, workspace_id=WORKSPACE, actor_id=uuid4(), idempotency_key=str(uuid4()), goal_text='x', limit_micro_usd=1_000_000, policy=resolve_role_policy(), continues_run_id=active)
            check('only a terminal run can be continued', 'refused', 'admitted', False)
        except LinkRefused:
            check('only a terminal run can be continued', 'refused', 'refused', True)
        foreign = await admit(OTHER)
        await apply_command(db, workspace_id=OTHER, run_id=foreign, command=RunCommand.CANCEL, actor=Actor.USER, expected_version=1)
        try:
            await admit_run(db, workspace_id=WORKSPACE, actor_id=uuid4(), idempotency_key=str(uuid4()), goal_text='x', limit_micro_usd=1_000_000, policy=resolve_role_policy(), continues_run_id=foreign)
            check('a run in another workspace cannot be continued', 'refused', 'admitted', False)
        except LinkRefused:
            check('a run in another workspace cannot be continued', 'refused', 'refused', True)

        # Mac sleep: a real process is stopped past its lease, a replacement recovers, and it wakes.
        run = await admit()
        process = await asyncio.create_subprocess_exec(PYTHON, str(HERE / 'sleeping_worker.py'), URL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        for _ in range(200):
            if await value("select count(*) from app_private.model_invocations where run_id = %s and status = 'dispatched'", run):
                break
            await asyncio.sleep(0.1)
        process.send_signal(signal.SIGSTOP)
        # Stopped at whichever call it had reached, so what follows compares against that.
        calls_at_stop = await value('select model_calls from app_private.run_usage where run_id = %s', run)
        waited = 0
        while await value('select lease_expires_at > clock_timestamp() from app_private.run_jobs where run_id = %s', run) and waited < 100:
            await asyncio.sleep(0.1)
            waited += 1
        check('a stopped worker stops renewing, so its lease runs out', 'expired', waited < 100, waited < 100)
        dispatched = await process_next(db, URL, 'replacement', lambda: Script(items=[calls(PLAN)], seen=[], bound=[]), RESUME_ROUTE)
        status = await value("select status from app_private.model_invocations where run_id = %s order by created_at desc limit 1", run)
        check('recovery classifies the interrupted call before any new dispatch', 'paused, uncertain_model_call, uncertain, no new call', (dispatched.run_status, dispatched.code, status, dispatched.usage['model_calls']), dispatched.run_status == 'paused' and dispatched.code == 'uncertain_model_call' and status == 'uncertain' and dispatched.usage['model_calls'] == calls_at_stop)
        process.send_signal(signal.SIGCONT)
        out, err = await asyncio.wait_for(process.communicate(), 60)
        woke = json.loads(out.decode().strip().splitlines()[-1]) if out.strip() else {'error': err.decode()[-300:]}
        check('when it wakes, the old worker is fenced and writes no status', 'lost', woke, woke.get('outcome') == 'lost')
        check('the replacement\'s decision stands', 'paused', await state_of(run), await state_of(run) == 'paused')
        late = await value("select charged_micro_usd from app_private.model_invocations where run_id = %s order by created_at desc limit 1", run)
        check('its late response settles the charge as evidence', 'a charge recorded', late, late == 100)
        left = await outstanding(db, run)
        check('nothing is left unknown', '0 uncertain', left, left.uncertain_calls == 0)
        resumed = await user(run, RunCommand.RESUME)
        processed = await process_next(db, URL, 'after-sleep', lambda: Script(items=[calls(('complete_task', {'task_id': 'a', 'evidence': [{'kind': 'artifact', 'reference': 'outputs/a.md'}], 'summary': 's'})), say('stop')], seen=[], bound=[]), RESUME_ROUTE)
        calls_used = processed.usage['model_calls']
        check('after reconciliation a paid dispatch is allowed again', 'more calls', calls_used, calls_used > calls_at_stop)

        # A response that arrives after recovery classified the call is late evidence.
        run = await admit()
        lease = await claim_next(db, worker_id='late', lease_seconds=120)

        def classified_while_out() -> Any:
            with psycopg.connect(URL, autocommit=True) as other:
                other.execute("update app_private.model_invocations set status = 'uncertain', failure_class = 'worker_lost' where run_id = %s and status = 'dispatched'", (run,))
            return say('late')

        result = await run_goal(db, URL, lease, Script(items=[classified_while_out], seen=[], bound=[]), RESUME_ROUTE)
        row = await (await db.execute('select status, charged_micro_usd from app_private.model_invocations where run_id = %s', (run,))).fetchone()
        check('a late response settles the charge as evidence', 'succeeded, 100', row, row == ('succeeded', 100) and result.outcome == 'lost')

        # An uncertain call blocks the next pass until it is reconciled.
        await db.execute("update app_private.model_spend_limits set slots = 2 where workspace_id = %s", (WORKSPACE,))
        run = await admit()
        lease = await claim_next(db, worker_id='w')
        ticket = await admission.admit(AdmissionRequest(WORKSPACE, run, run, 'executor', 'openrouter_terra', 'fixture/model', 1, 1000))
        await admission.mark_dispatched(ticket.invocation_id)
        await admission.mark_uncertain(ticket.invocation_id, 'partial_stream', 'par')
        model = Script(items=[calls(PLAN)], seen=[], bound=[])
        result = await run_goal(db, URL, lease, model, RESUME_ROUTE)
        check('an unreconciled call blocks another paid dispatch', 'paused, 0 model calls', (result.run_status, len(model.seen)), result.run_status == 'paused' and len(model.seen) == 0)
    print(json.dumps({'cases': cases}))


async def _cancel(run: UUID, version: int) -> None:
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as other:
        await apply_command(other, workspace_id=WORKSPACE, run_id=run, command=RunCommand.CANCEL, actor=Actor.USER, expected_version=version)


try:
    asyncio.run(main())
except Exception:
    print(json.dumps({'cases': cases}))
    raise
