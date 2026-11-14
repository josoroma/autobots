"""Completion decided from storage, stale verifiers, and the failure paths review found. JSON cases."""
from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import sys
import time
from typing import Any
from uuid import UUID, uuid4

import psycopg
from autobots.adapters.loop_middleware import ModelRoute
from autobots.adapters.object_storage import SupabaseObjectStore
from autobots.application.artifacts import publish
from autobots.application.goal_loop import (
    LoopConfig,
    _settle_candidate,
    loop_registry,
    process_next,
    run_goal,
)
from autobots.application.model_admission import AdmissionRequest, ModelAdmission
from autobots.application.model_attempts import FailureClass, ProviderFailure
from autobots.application.recovery import classify_interrupted
from autobots.application.run_projection import read_workspace
from autobots.application.run_usage import RootLimits
from autobots.application.runs import IdempotencyConflict, admit_run, apply_command
from autobots.application.tool_gateway import ToolFailed, ToolGateway, ToolScope
from autobots.application.tools import default_registry
from autobots.application.worker_leases import claim_next
from autobots.contracts.plans import InputDocument, RequiredArtifact
from autobots.domain.models import resolve_role_policy
from autobots.domain.runs import Actor, RunCommand
from autobots.operations.logs import JsonFormatter, redact
from goal_loop_script import PLAN, ROUTE, SAVE, Script, calls, say
from langchain_core.messages import AIMessage
from pydantic import SecretStr

URL, BASE = os.environ['AUTOBOTS_DATABASE_URL'], os.environ['AUTOBOTS_STORAGE_BASE']
SERVICE = SecretStr(os.environ['AUTOBOTS_STORAGE_SERVICE'])
WORKSPACE = UUID(sys.argv[1])
TASK = {'id': 'a', 'title': 'Report', 'criteria': ['c1'], 'expected_evidence': 'a file'}
ONE_PLAN = ('propose_plan', {'tasks': [TASK]})
cases = []


def check(name: str, expected: str, observed: object, passed: bool) -> None:
    cases.append({'id': name, 'expected': expected, 'observed': str(observed), 'passed': bool(passed)})


async def main() -> None:
    store = SupabaseObjectStore(BASE, SERVICE)
    config = LoopConfig(route=ROUTE, object_store=store, sleep=lambda _: asyncio.sleep(0))
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        async def value(sql: str, *values: object) -> Any:
            return (await (await db.execute(sql, values)).fetchone())[0]

        async def admit(limit: int = 1_000_000, required: tuple[RequiredArtifact, ...] = (), documents: tuple[InputDocument, ...] = ()) -> UUID:
            await db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null where status <> 'done'")
            return (await admit_run(db, workspace_id=WORKSPACE, actor_id=uuid4(), idempotency_key=str(uuid4()), goal_text='Report it', limit_micro_usd=limit, policy=resolve_role_policy(), required_artifacts=required, input_documents=documents)).run_id

        async def candidate(run: UUID, content: str | None = 'Total: 9') -> Any:
            """A real pass through the loop that leaves the run verifying, with its plan complete."""
            lease = await claim_next(db, worker_id='candidate', lease_seconds=120)
            evidence = {'task_id': 'a', 'evidence': [{'kind': 'artifact', 'reference': 'outputs/report.md'}], 'summary': 'done'}
            save = ('save_artifact', {'path': 'outputs/report.md', 'content': content or 'x'})
            result = await run_goal(db, URL, lease, Script(items=[calls(ONE_PLAN), calls(save), calls(('complete_task', evidence)), say('Finished.')], seen=[], bound=[]), config)
            assert result.outcome == 'candidate', result
            return lease

        def scope_of(lease: Any) -> ToolScope:
            return ToolScope(lease.workspace_id, lease.run_id, lease.generation, {}, ('outputs',))

        async def state(run: UUID) -> str:
            return await value('select status from public.runs where id = %s', run)

        required = (RequiredArtifact(name='report.md', must_contain=['Total: 9']),)

        # What a run must deliver.
        run = await admit()
        lease = await candidate(run)
        result = await _settle_candidate(db, URL, lease, config)
        check('a finished plan citing a saved file is not success with nothing published', 'failed, no_published_artifact', (result.run_status, await value('select unmet from app_private.run_verifications where run_id = %s', run)), result.run_status == 'failed' and await value('select unmet from app_private.run_verifications where run_id = %s', run) == ['no_published_artifact'])

        run = await admit()
        lease = await candidate(run)
        await publish(db, store, scope_of(lease), operation_id=uuid4().hex, name='anything.md', media_type='text/plain', content=b'bytes')
        result = await _settle_candidate(db, URL, lease, config)
        checks = await value('select checks from app_private.run_verifications where run_id = %s', run)
        check('with no requirement, a published artifact passes, and says nothing was judged', 'succeeded, 0 checks', (result.run_status, checks), result.run_status == 'succeeded' and checks == 0)

        run = await admit(required=required)
        lease = await candidate(run)
        await publish(db, store, scope_of(lease), operation_id=uuid4().hex, name='report.md', media_type='text/plain', content=b'Total: 9')
        result = await _settle_candidate(db, URL, lease, config)
        judged = await value('select checks from app_private.run_verifications where run_id = %s', run)
        check('the right bytes pass', 'succeeded, 1 check', (result.run_status, judged), result.run_status == 'succeeded' and judged == 1)

        run = await admit(required=required)
        lease = await candidate(run)
        await publish(db, store, scope_of(lease), operation_id=uuid4().hex, name='report.md', media_type='text/plain', content=b'Total: 8')
        result = await _settle_candidate(db, URL, lease, config)
        check('the wrong bytes fail', 'failed', result.run_status, result.run_status == 'failed')

        # A superseded copy can't stand in, and a lost object fails even with a good record.
        run = await admit(required=required)
        lease = await candidate(run)
        first = uuid4().hex
        await publish(db, store, scope_of(lease), operation_id=first, name='report.md', media_type='text/plain', content=b'Total: 9')
        second = uuid4().hex
        await publish(db, store, scope_of(lease), operation_id=second, name='report.md', media_type='text/plain', content=b'Total: 9 and more')
        await store.remove(f'{WORKSPACE}/{run}/{second}-report.md')
        result = await _settle_candidate(db, URL, lease, config)
        unmet = await value('select unmet from app_private.run_verifications where run_id = %s', run)
        check('a lost newest copy fails, though an older good one exists', 'failed, artifact_missing', (result.run_status, unmet), result.run_status == 'failed' and 'artifact_missing:report.md' in unmet)

        # Unknowns block success.
        run = await admit(required=required)
        lease = await candidate(run)
        await publish(db, store, scope_of(lease), operation_id=uuid4().hex, name='report.md', media_type='text/plain', content=b'Total: 9')
        await db.execute("insert into app_private.tool_receipts (operation_id, run_id, workspace_id, tool_id, tool_version, argument_hash, status, generation) values (%s, %s, %s, 'x', 1, 'h', 'unknown', 1)", (uuid4().hex, run, WORKSPACE))
        result = await _settle_candidate(db, URL, lease, config)
        unmet = await value('select unmet from app_private.run_verifications where run_id = %s', run)
        check('an unknown effect blocks success', 'failed, unknown_effect', (result.run_status, unmet), result.run_status == 'failed' and unmet == ['unknown_effect'])
        view = await read_workspace(db, WORKSPACE, run)
        check('and stays visible on the finished run', '1 unknown effect', view.outstanding, view.outstanding.unknown_effects == 1)

        # A stale verifier records nothing.
        run = await admit(required=required)
        stale = await candidate(run)
        await publish(db, store, scope_of(stale), operation_id=uuid4().hex, name='report.md', media_type='text/plain', content=b'Total: 8')
        await db.execute("update app_private.run_jobs set lease_expires_at = clock_timestamp() - interval '1 second' where run_id = %s", (run,))
        current = await claim_next(db, worker_id='current', lease_seconds=120)
        good = await _settle_candidate(db, URL, current, config)
        check('a dead verifier\'s job is claimed and settled by a replacement', 'failed for the wrong bytes', (current.run_status, good.run_status), current.run_status == 'verifying' and good.run_status == 'failed')
        before = await value('select count(*) from app_private.run_verifications where run_id = %s', run)
        reason = await value('select stop_reason from app_private.run_usage where run_id = %s', run)
        events = await value('select count(*) from public.run_events where run_id = %s', run)
        await store.put(f'{WORKSPACE}/{run}/not-known.md', b'x', 'text/plain')
        late = await _settle_candidate(db, URL, stale, config)
        after = await value('select count(*) from app_private.run_verifications where run_id = %s', run)
        check('a stale verifier\'s recovery writes nothing to a finished run', 'no new event, the object stays', (await value('select count(*) from public.run_events where run_id = %s', run) - events, await store.get(f'{WORKSPACE}/{run}/not-known.md') is not None), await value('select count(*) from public.run_events where run_id = %s', run) == events and await store.get(f'{WORKSPACE}/{run}/not-known.md') is not None)
        check('a stale verifier writes no verdict and no reason', 'lost, 1 row, reason unchanged', (late.outcome, after, await value('select stop_reason from app_private.run_usage where run_id = %s', run)), late.outcome == 'lost' and before == after == 1 and await value('select stop_reason from app_private.run_usage where run_id = %s', run) == reason)

        # A retry after backoff is fenced like the first attempt.
        run = await admit()
        lease = await claim_next(db, worker_id='retry', lease_seconds=120)

        async def cancel_during_backoff(_: float) -> None:
            await apply_command(db, workspace_id=WORKSPACE, run_id=run, command=RunCommand.CANCEL, actor=Actor.USER, expected_version=await value('select version from public.runs where id = %s', run))

        model = Script(items=[ProviderFailure(FailureClass.PROVIDER_ERROR), calls(PLAN)], seen=[], bound=[])
        result = await run_goal(db, URL, lease, model, LoopConfig(route=ROUTE, sleep=cancel_during_backoff))
        check('a cancel during backoff stops the retry', '1 call, cancelled', (len(model.seen), result.run_status), len(model.seen) == 1 and result.run_status == 'cancelled')
        released = await value("select count(*) from app_private.model_invocations where run_id = %s and status in ('reserved', 'dispatched')", run)
        check('and the retry\'s reservation is released', '0 open', released, released == 0)

        run = await admit()
        ticket = await ModelAdmission(db).admit(AdmissionRequest(WORKSPACE, run, run, 'executor', 'openrouter_deepseek_flash', 'fixture/model', 1, 1000))
        await classify_interrupted(db, run, 2)
        try:
            await ModelAdmission(db).mark_dispatched(ticket.invocation_id)
            check('a reservation recovery closed can\'t be sent', 'refused', 'sent', False)
        except ValueError:
            check('a reservation recovery closed can\'t be sent', 'refused', 'refused', True)

        # A pause during a dispatched call, then a cancel, doesn't strand the run.
        run = await admit()
        lease = await claim_next(db, worker_id='stranded', lease_seconds=120)
        ticket = await ModelAdmission(db).admit(AdmissionRequest(WORKSPACE, run, run, 'executor', 'openrouter_deepseek_flash', 'fixture/model', 1, 1000))
        await ModelAdmission(db).mark_dispatched(ticket.invocation_id)
        await db.execute("update app_private.run_jobs set lease_expires_at = clock_timestamp() - interval '1 second' where run_id = %s", (run,))
        await apply_command(db, workspace_id=WORKSPACE, run_id=run, command=RunCommand.PAUSE, actor=Actor.USER, expected_version=2)
        cancelling = await apply_command(db, workspace_id=WORKSPACE, run_id=run, command=RunCommand.CANCEL, actor=Actor.USER, expected_version=3)
        job = await value('select status from app_private.run_jobs where run_id = %s', run)
        check('a cancel with open work and no owner queues it for recovery', 'cancelling, queued', (cancelling.status, job), cancelling.status == 'cancelling' and job == 'queued')
        settled = await process_next(db, URL, 'recovery', lambda: Script(items=[], seen=[], bound=[]), config)
        check('and recovery finishes it truthfully', 'cancelled_with_unknown_outcomes', (settled.run_status, settled.code), settled.run_status == 'cancelled' and settled.code == 'cancelled_with_unknown_outcomes')

        # The run's own limit, and honest public figures.
        run = await admit(limit=500)
        lease = await claim_next(db, worker_id='cap', lease_seconds=120)
        model = Script(items=[calls(PLAN)], seen=[], bound=[])
        result = await run_goal(db, URL, lease, model, LoopConfig(route=ROUTE))
        check('a run\'s own lower limit is enforced', 'budget_exceeded, no call', (result.code, len(model.seen)), result.code == 'budget_exceeded' and not model.seen)
        run = await admit()
        lease = await candidate(run)
        view = await read_workspace(db, WORKSPACE, run)
        check('the public budget comes from the ledger', '400 spent, 0 reserved', view.run.budget, view.run.budget.spent_micro_usd == 400 and view.run.budget.reserved_micro_usd == 0)

        # A pause lets a call in flight finish, and its reply is charged normally.
        def slow() -> AIMessage:
            time.sleep(1.5)
            return calls(ONE_PLAN)

        run = await admit()
        lease = await claim_next(db, worker_id='pause-live', lease_seconds=120)

        async def pause_soon() -> None:
            await asyncio.sleep(0.3)
            async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as other:
                await apply_command(other, workspace_id=WORKSPACE, run_id=run, command=RunCommand.PAUSE, actor=Actor.USER, expected_version=2)

        pausing = asyncio.create_task(pause_soon())
        model = Script(items=[slow, say('never')], seen=[], bound=[])
        result = await run_goal(db, URL, lease, model, LoopConfig(route=ROUTE))
        await pausing
        row = await (await db.execute('select status, charged_micro_usd from app_private.model_invocations where run_id = %s', (run,))).fetchone()
        job = await value('select status from app_private.run_jobs where run_id = %s', run)
        plans = await value('select count(*) from app_private.plan_versions where run_id = %s', run)
        check('a pause lets the call finish, with its charge', 'succeeded, 100', row, row == ('succeeded', 100))
        check('and stops at the next boundary, letting go of the job', 'paused, no more calls, job done', (result.run_status, await state(run), len(model.seen), job, plans), await state(run) == 'paused' and len(model.seen) == 1 and job == 'done')
        unsettled = await read_workspace(db, WORKSPACE, run)
        check('so nothing is left to reconcile, and any member can resume', '0 uncertain', unsettled.outstanding, unsettled.outstanding.uncertain_calls == 0)

        # Internal writes interrupted before their receipt finish on replay, so they stay resolvable.
        run = await admit()
        lease = await claim_next(db, worker_id='internal', lease_seconds=120)
        gateway_full = ToolGateway(loop_registry(RootLimits()))
        scope = ToolScope(WORKSPACE, run, lease.generation, {'propose_plan': 1, 'save_artifact': 1, 'complete_task': 1}, ('outputs',))
        proposal = {'tasks': [TASK]}
        first = await gateway_full.execute(db, scope, 'propose_plan', proposal)
        await db.execute("update app_private.tool_receipts set status = 'unknown', result = null where operation_id = %s", (first.operation_id,))
        again = await gateway_full.execute(db, scope, 'propose_plan', proposal)
        versions = await value('select count(*) from app_private.plan_versions where run_id = %s', run)
        check('an interrupted plan that committed is recognized', 'succeeded, 1 version', (again.outcome.value, versions), again.outcome.value == 'succeeded' and versions == 1)
        save = {'path': 'outputs/x.md', 'content': 'x'}
        first = await gateway_full.execute(db, scope, 'save_artifact', save)
        await db.execute("update app_private.tool_receipts set status = 'unknown', result = null where operation_id = %s", (first.operation_id,))
        again = await gateway_full.execute(db, scope, 'save_artifact', save)
        left = await read_workspace(db, WORKSPACE, run)
        check('a save with no receipt is resolved by readback', 'succeeded, nothing unknown', (again.outcome.value, left.outstanding.unknown_effects), again.outcome.value == 'succeeded' and left.outstanding.unknown_effects == 0)
        await db.execute("update app_private.run_jobs set generation = generation + 1 where run_id = %s", (run,))
        lost = await gateway_full.execute(db, scope, 'save_artifact', {'path': 'outputs/y.md', 'content': 'y'})
        check('a stale write is refused before it starts', 'lease_lost', lost.code, lost.code == 'lease_lost')

        # A key covers its input value.
        run = await admit()
        lease = await claim_next(db, worker_id='input', lease_seconds=120)
        await apply_command(db, workspace_id=WORKSPACE, run_id=run, command=RunCommand.REQUEST_INPUT, actor=Actor.WORKER, expected_version=2, generation=lease.generation, detail='Which?')
        actor = uuid4()
        await apply_command(db, workspace_id=WORKSPACE, run_id=run, command=RunCommand.SUBMIT_INPUT, actor=Actor.USER, expected_version=3, actor_id=actor, idempotency_key='same', response='first')
        try:
            await apply_command(db, workspace_id=WORKSPACE, run_id=run, command=RunCommand.SUBMIT_INPUT, actor=Actor.USER, expected_version=3, actor_id=actor, idempotency_key='same', response='second')
            check('the same key with a different input is refused', 'conflict', 'accepted', False)
        except IdempotencyConflict:
            check('the same key with a different input is refused', 'conflict', 'conflict', True)

        # A hung call is bounded, and a cancel doesn't wait for it. Each says why in the worker's log.
        written = io.StringIO()
        capture = logging.StreamHandler(written)
        capture.setFormatter(JsonFormatter())
        logging.getLogger('autobots.worker').addHandler(capture)

        def uncertain_events() -> list[dict]:
            return [line for line in map(json.loads, written.getvalue().splitlines()) if line['event'] == 'worker.call_uncertain']

        def one_new(seen: int, run_id: UUID) -> dict | None:
            new = uncertain_events()[seen:]
            short = str(run_id)[:8]
            return new[0] if len(new) == 1 and new[0]['run'].startswith(short) and new[0].get('invocation') else None

        seen = len(uncertain_events())
        def hang() -> AIMessage:
            time.sleep(4)
            return calls(SAVE)

        run = await admit()
        lease = await claim_next(db, worker_id='hung', lease_seconds=120)
        started = time.monotonic()
        result = await run_goal(db, URL, lease, Script(items=[hang], seen=[], bound=[]), LoopConfig(route=ROUTE, model_call_seconds=0.5))
        elapsed = time.monotonic() - started
        check('a hung model call is bounded and its outcome stays uncertain', 'uncertain_acceptance, paused, under 4s', (result.code, result.run_status, round(elapsed, 1)), result.code == 'uncertain_acceptance' and result.run_status == 'paused' and elapsed < 3.9)

        event = one_new(seen, run)
        check('and the log says it hit the call time limit', 'one event, reason call_time_limit', event, event is not None and event.get('reason') == 'call_time_limit' and 'error_type' in event)
        seen = len(uncertain_events())

        run = await admit()
        lease = await claim_next(db, worker_id='hung-cancel', lease_seconds=120)

        async def cancel_soon() -> None:
            await asyncio.sleep(0.5)
            async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as other:
                await apply_command(other, workspace_id=WORKSPACE, run_id=run, command=RunCommand.CANCEL, actor=Actor.USER, expected_version=2)

        started = time.monotonic()
        canceller = asyncio.create_task(cancel_soon())
        result = await run_goal(db, URL, lease, Script(items=[hang], seen=[], bound=[]), LoopConfig(route=ROUTE))
        await canceller
        elapsed = time.monotonic() - started
        check('a cancel interrupts a hung call', 'cancelled, unknown outcome, under 4s', (result.run_status, result.code, round(elapsed, 1)), result.run_status == 'cancelled' and result.code == 'cancelled_with_unknown_outcomes' and elapsed < 3.9)

        event = one_new(seen, run)
        check('and the log says the run was interrupted', 'one event, reason run_interrupted', event, event is not None and event.get('reason') == 'run_interrupted')

        # What was raised is named by type. A sentinel in a shape redaction doesn't know stays out.
        sentinel = 'arranged-sentinel-91c2'

        class Gateway(Exception):
            status_code = 504

        def with_cause() -> AIMessage:
            try:
                raise ValueError(sentinel)
            except ValueError as cause:
                raise RuntimeError(sentinel) from cause

        def with_status() -> AIMessage:
            raise Gateway(sentinel)

        def partial() -> AIMessage:
            raise ProviderFailure(FailureClass.PARTIAL_STREAM, accumulated_output=sentinel)

        class OddStatus(Exception):
            status_code = '504'

        def odd_status() -> AIMessage:
            raise OddStatus(sentinel)

        def known() -> AIMessage:
            raise ProviderFailure(FailureClass.INVALID_CREDENTIAL)

        for name, item, wanted in (('no status, with a cause', with_cause, {'error_type': 'builtins.RuntimeError', 'cause_type': 'builtins.ValueError', 'failure': 'uncertain_acceptance'}),
                                   ('a status', with_status, {'status': 504, 'failure': 'uncertain_acceptance'}),
                                   ('a partial stream, arranged, as nothing raises one today', partial, {'error_type': 'autobots.application.model_attempts.ProviderFailure', 'failure': 'partial_stream'}),
                                   ('a status that is no number, so none is reported', odd_status, {'status': None, 'failure': 'uncertain_acceptance'})):
            seen = len(uncertain_events())
            run = await admit()
            lease = await claim_next(db, worker_id='named', lease_seconds=120)
            result = await run_goal(db, URL, lease, Script(items=[item], seen=[], bound=[]), LoopConfig(route=ROUTE))
            event = one_new(seen, run)
            row = await (await db.execute("select id::text from app_private.model_invocations where run_id = %s and status = 'uncertain'", (run,))).fetchone()
            check(f'the log names the exception: {name}', str(wanted), (result.code, event),
                  event is not None and all(event.get(key) == value for key, value in wanted.items()) and result.run_status == 'paused'
                  and row is not None and event['invocation'].startswith(row[0][:8]))

        # A failure that is known, from inside the handler: it was never sent, so nothing is uncertain.
        seen = len(uncertain_events())
        run = await admit()
        lease = await claim_next(db, worker_id='known', lease_seconds=120)
        result = await run_goal(db, URL, lease, Script(items=[known], seen=[], bound=[]), LoopConfig(route=ROUTE))
        check('a known failure from inside the call logs no uncertain event', 'invalid_credential, paused, no new event', (result.code, result.run_status, len(uncertain_events()) - seen),
              result.code == 'invalid_credential' and result.run_status == 'paused' and len(uncertain_events()) == seen)
        logging.getLogger('autobots.worker').removeHandler(capture)
        check('no exception message, cause or partial output reached the log', 'absent, with 6 events read, and redaction leaves the sentinel alone', (len(uncertain_events()), sentinel in written.getvalue()),
              len(uncertain_events()) == 6 and sentinel not in written.getvalue() and redact(sentinel) == sentinel)

        # Documents given at admission are read-only.
        document = InputDocument(path='inputs/data.md', content='apples: 4')
        run = await admit(documents=(document,))
        lease = await claim_next(db, worker_id='docs', lease_seconds=120)
        scope = ToolScope(WORKSPACE, run, lease.generation, {'read_run_file': 1, 'save_artifact': 1}, ('inputs', 'outputs'))
        gateway = ToolGateway(default_registry())
        read = await gateway.execute(db, scope, 'read_run_file', {'path': 'inputs/data.md'})
        check('a tool reads a document given at admission', 'its content', read.output['content'], read.output['content'] == 'apples: 4')
        write = await gateway.execute(db, scope, 'save_artifact', {'path': 'inputs/data.md', 'content': 'pears: 100'})
        check('and can\'t change it', 'inputs_read_only', write.code, write.code == 'inputs_read_only')
        again = await gateway.execute(db, scope, 'read_run_file', {'path': 'inputs/data.md'})
        check('so it still holds the original', 'apples: 4', again.output['content'], again.output['content'] == 'apples: 4')
        from autobots.application.artifacts import publish_tool
        registry = default_registry()
        registry.register(publish_tool(store))
        publishing = await ToolGateway(registry).execute(db, ToolScope(WORKSPACE, run, lease.generation, {'publish_artifact': 1}, ('inputs', 'outputs')), 'publish_artifact', {'path': 'inputs/data.md', 'version': 1})
        check('and an input can\'t be published as a result', 'artifact_source_not_output', publishing.code, publishing.code == 'artifact_source_not_output')
        assert ToolFailed and ModelRoute
    print(json.dumps({'cases': cases}))


try:
    asyncio.run(main())
except Exception:
    print(json.dumps({'cases': cases}))
    raise
