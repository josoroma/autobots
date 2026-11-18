"""Cancellation, resume and recovery, with a real stopped process for Mac sleep. JSON cases through checklib, one
scenario at a time (refactor plan R-66, TDBC-06)."""
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
from autobots.adapters import tool_registry
from autobots.adapters.loop_middleware import ModelRoute
from autobots.application.goal_loop import run_goal
from autobots.application.model_admission import AdmissionRequest, ModelAdmission
from autobots.application.recovery import outstanding
from autobots.application.run_lifecycle import LoopConfig
from autobots.application.runs import (
    LeaseLost,
    LinkRefused,
    VersionConflict,
    admit_run,
    apply_command,
    apply_worker_command,
)
from autobots.application.tool_definitions import ToolDefinition, ToolRegistry, ToolScope
from autobots.application.tool_gateway import ToolGateway
from autobots.application.worker_leases import claim_next
from autobots.domain.models import resolve_role_policy
from autobots.domain.runs import CommandRefused, RunCommand
from autobots.domain.tools import OperationClass
from autobots.operations.job_dispatch import drive_lease, process_next
from checklib import Cases, run_check, run_scenarios, started_worker
from goal_loop_script import DONE_A, PLAN, ROUTE, SAVE, Script, calls, say
from pydantic import BaseModel

URL = os.environ['AUTOBOTS_DATABASE_URL']
WORKSPACE, OTHER, PYTHON = UUID(sys.argv[1]), UUID(sys.argv[2]), sys.argv[3]
# The workers these scenarios start and kill (tests/db/README.md).
WORKERS = Path(__file__).resolve().parents[1] / 'workers'
RESUME_ROUTE = LoopConfig(route=ROUTE, sleep=lambda _: asyncio.sleep(0), tool_set=tool_registry.build_registry)


class Nothing(BaseModel):
    note: str = ''


class Recovering:
    """One connection, and the commands and arrangements each scenario repeats."""

    def __init__(self, db: Any, cases: Cases) -> None:
        self.db, self.cases = db, cases
        self.admission = ModelAdmission(db)

    async def value(self, sql: str, *values: object) -> Any:
        return (await (await self.db.execute(sql, values)).fetchone())[0]

    async def clear(self) -> None:
        await self.db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null where status <> 'done'")

    async def admit(self, workspace: UUID = WORKSPACE) -> UUID:
        await self.clear()
        return (await admit_run(self.db, workspace_id=workspace, actor_id=uuid4(), idempotency_key=str(uuid4()), goal_text='Write the report', limit_micro_usd=1_000_000, policy=resolve_role_policy(), acceptance_criteria=('Has a summary', 'Has figures'))).run_id

    async def state_of(self, run: UUID) -> str:
        return await self.value('select status from public.runs where id = %s', run)

    async def version_of(self, run: UUID) -> int:
        return await self.value('select version from public.runs where id = %s', run)

    async def user(self, run: UUID, command: RunCommand, **options: Any) -> Any:
        return await apply_command(self.db, workspace_id=WORKSPACE, run_id=run, command=command, expected_version=await self.version_of(run), **options)

    async def worker(self, run: UUID, lease: Any, command: RunCommand, **options: Any) -> Any:
        return await apply_worker_command(self.db, lease, command, **options)

    async def expire(self, run: UUID) -> None:
        await self.db.execute("update app_private.run_jobs set lease_expires_at = clock_timestamp() - interval '1 second' where run_id = %s", (run,))


async def cancel_from_every_nonterminal_state(ctx: Recovering) -> None:
    """Cancel from every nonterminal state."""
    admit, check, db, expire, state_of, user, worker = ctx.admit, ctx.cases.check, ctx.db, ctx.expire, ctx.state_of, ctx.user, ctx.worker
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


async def unsettled_work_keeps_cancel_honest(ctx: Recovering) -> None:
    """Unsettled work keeps it honest, even with no live owner."""
    admission, admit, check, db, expire, state_of, user, value = ctx.admission, ctx.admit, ctx.cases.check, ctx.db, ctx.expire, ctx.state_of, ctx.user, ctx.value
    run = await admit()
    await claim_next(db, worker_id='dead')
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


async def cancel_stops_new_dispatch(ctx: Recovering) -> None:
    """A cancel reaching a live loop stops new dispatch."""
    admit, check, db, value = ctx.admit, ctx.cases.check, ctx.db, ctx.value
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
    result = await run_goal(db, URL, lease, model, RESUME_ROUTE, drive=drive_lease)
    files = await value('select count(*) from app_private.run_files where run_id = %s', run)
    check('a cancel during a model call stops the next dispatch', 'cancelled, 2 calls, no file', (result.run_status, len(model.seen), files), result.run_status == 'cancelled' and len(model.seen) == 2 and files == 0)


async def late_tool_result_is_refused(ctx: Recovering) -> None:
    """A late tool result is recorded, and can't reopen anything."""
    admit, check, db, value, version_of = ctx.admit, ctx.cases.check, ctx.db, ctx.value, ctx.version_of
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


async def completion_and_cancellation_race(ctx: Recovering) -> None:
    """Competing completion and cancellation: one order wins, consistently."""
    admit, check, db, state_of, version_of, worker = ctx.admit, ctx.cases.check, ctx.db, ctx.state_of, ctx.version_of, ctx.worker
    outcomes = {'succeeded': 0, 'cancelling': 0}
    for _ in range(20):
        run = await admit()
        lease = await claim_next(db, worker_id='race')
        await worker(run, lease, RunCommand.VERIFY)
        version = await version_of(run)

        async def complete() -> str:
            async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as other:
                try:
                    return (await apply_worker_command(other, lease, RunCommand.COMPLETE)).status  # noqa: B023 - called within this iteration, so it reads this iteration's values
                except (VersionConflict, CommandRefused, LeaseLost) as error:
                    # TDBC-07: the loser is refused. Any other failure propagates and fails the check.
                    return type(error).__name__

        async def cancel() -> str:
            async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as other:
                try:
                    return (await apply_command(other, workspace_id=WORKSPACE, run_id=run, command=RunCommand.CANCEL, expected_version=version)).status  # noqa: B023 - called within this iteration, so it reads this iteration's values
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


async def resume_keeps_obligations_and_bindings(ctx: Recovering) -> None:
    """Resume keeps obligations and bindings."""
    admit, check, db, user, value, worker = ctx.admit, ctx.cases.check, ctx.db, ctx.user, ctx.value, ctx.worker
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
    processed = await process_next(db, URL, 'after-input', lambda: Script(items=[calls(PLAN), say('stop')], seen=[], bound=[]), LoopConfig(route=ROUTE, tool_set=tool_registry.build_registry))
    check('and the run continues', 'stopped at plan_incomplete after a real pass', (processed.code, processed.usage['model_calls']), processed.code == 'plan_incomplete' and processed.usage['model_calls'] == 2)
    await db.execute("update app_private.model_policies set default_profile = 'openrouter_terra' where workspace_id = %s", (WORKSPACE,))

    run = await admit()
    lease = await claim_next(db, worker_id='bound')
    other_route = LoopConfig(route=ModelRoute('executor', 'openrouter_deepseek_flash', 'fixture/other', 1000), tool_set=tool_registry.build_registry)
    model = Script(items=[calls(PLAN)], seen=[], bound=[])
    result = await run_goal(db, URL, lease, model, other_route, drive=drive_lease)
    check('a route that differs from the frozen policy is refused', 'route_not_bound, no call', (result.code, len(model.seen)), result.code == 'route_not_bound' and len(model.seen) == 0)


async def terminal_runs_take_a_linked_new_run(ctx: Recovering) -> None:
    """Terminal states take a linked new run."""
    admit, check, db, state_of, user, value = ctx.admit, ctx.cases.check, ctx.db, ctx.state_of, ctx.user, ctx.value
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
    await apply_command(db, workspace_id=OTHER, run_id=foreign, command=RunCommand.CANCEL, expected_version=1)
    try:
        await admit_run(db, workspace_id=WORKSPACE, actor_id=uuid4(), idempotency_key=str(uuid4()), goal_text='x', limit_micro_usd=1_000_000, policy=resolve_role_policy(), continues_run_id=foreign)
        check('a run in another workspace cannot be continued', 'refused', 'admitted', False)
    except LinkRefused:
        check('a run in another workspace cannot be continued', 'refused', 'refused', True)


async def stopped_worker_is_recovered_and_fenced(ctx: Recovering) -> None:
    """Mac sleep: a real process is stopped past its lease, a replacement recovers, and it wakes."""
    admit, check, db, state_of, user, value = ctx.admit, ctx.cases.check, ctx.db, ctx.state_of, ctx.user, ctx.value
    run = await admit()
    # A worker left stopped by a failure here is killed on the way out (started_worker).
    async with started_worker(PYTHON, str(WORKERS / 'sleeping_worker.py'), URL) as process:
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
    await user(run, RunCommand.RESUME)
    processed = await process_next(db, URL, 'after-sleep', lambda: Script(items=[calls(('complete_task', {'task_id': 'a', 'evidence': [{'kind': 'artifact', 'reference': 'outputs/a.md'}], 'summary': 's'})), say('stop')], seen=[], bound=[]), RESUME_ROUTE)
    calls_used = processed.usage['model_calls']
    check('after reconciliation a paid dispatch is allowed again', 'more calls', calls_used, calls_used > calls_at_stop)


async def late_response_is_evidence(ctx: Recovering) -> None:
    """A response that arrives after recovery classified the call is late evidence."""
    admit, check, db = ctx.admit, ctx.cases.check, ctx.db
    run = await admit()
    lease = await claim_next(db, worker_id='late', lease_seconds=120)

    def classified_while_out() -> Any:
        with psycopg.connect(URL, autocommit=True) as other:
            other.execute("update app_private.model_invocations set status = 'uncertain', failure_class = 'worker_lost' where run_id = %s and status = 'dispatched'", (run,))
        return say('late')

    result = await run_goal(db, URL, lease, Script(items=[classified_while_out], seen=[], bound=[]), RESUME_ROUTE, drive=drive_lease)
    row = await (await db.execute('select status, charged_micro_usd from app_private.model_invocations where run_id = %s', (run,))).fetchone()
    check('a late response settles the charge as evidence', 'succeeded, 100', row, row == ('succeeded', 100) and result.outcome == 'lost')


async def uncertain_call_blocks_next_pass(ctx: Recovering) -> None:
    """An uncertain call blocks the next pass until it is reconciled."""
    admission, admit, check, db = ctx.admission, ctx.admit, ctx.cases.check, ctx.db
    await db.execute("update app_private.model_spend_limits set slots = 2 where workspace_id = %s", (WORKSPACE,))
    run = await admit()
    lease = await claim_next(db, worker_id='w')
    ticket = await admission.admit(AdmissionRequest(WORKSPACE, run, run, 'executor', 'openrouter_terra', 'fixture/model', 1, 1000))
    await admission.mark_dispatched(ticket.invocation_id)
    await admission.mark_uncertain(ticket.invocation_id, 'partial_stream', 'par')
    model = Script(items=[calls(PLAN)], seen=[], bound=[])
    result = await run_goal(db, URL, lease, model, RESUME_ROUTE, drive=drive_lease)
    check('an unreconciled call blocks another paid dispatch', 'paused, 0 model calls', (result.run_status, len(model.seen)), result.run_status == 'paused' and len(model.seen) == 0)


SCENARIOS = (
    cancel_from_every_nonterminal_state,
    unsettled_work_keeps_cancel_honest,
    cancel_stops_new_dispatch,
    late_tool_result_is_refused,
    completion_and_cancellation_race,
    resume_keeps_obligations_and_bindings,
    terminal_runs_take_a_linked_new_run,
    stopped_worker_is_recovered_and_fenced,
    late_response_is_evidence,
    uncertain_call_blocks_next_pass,
)


async def _cancel(run: UUID, version: int) -> None:
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as other:
        await apply_command(other, workspace_id=WORKSPACE, run_id=run, command=RunCommand.CANCEL, expected_version=version)


async def main(cases: Cases) -> None:
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        context = Recovering(db, cases)
        await run_scenarios(cases, SCENARIOS, context)


if __name__ == '__main__':
    # Its parent's Child entry in scripts/app_db.py gives it 240 seconds.
    run_check(main, parent_timeout=240)
