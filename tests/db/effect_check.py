"""Lost responses and duplicate delivery against a controlled sink. JSON cases."""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import psycopg
from autobots.application.approvals import decide
from autobots.application.reconciliation import (
    ReconciliationRefused,
    has_unresolvable_effect,
    record_evidence,
    unknown_operations,
)
from autobots.application.run_lifecycle import LoopConfig
from autobots.application.run_projection import read_workspace
from autobots.application.runs import admit_run, apply_command
from autobots.domain.models import resolve_role_policy
from autobots.domain.runs import RunCommand
from autobots.domain.tools import PLAN_TOOLS
from autobots.operations.job_dispatch import process_next
from effect_tools import tools
from goal_loop_script import ROUTE, Script, calls, say
from mock_sink import Sink

URL = os.environ['AUTOBOTS_DATABASE_URL']
WORKSPACE, OTHER, PYTHON = UUID(sys.argv[1]), UUID(sys.argv[2]), sys.argv[3]
HERE = Path(__file__).parent
ACTOR = uuid4()
cases = []


def check(name: str, expected: str, observed: object, passed: bool) -> None:
    cases.append({'id': name, 'expected': expected, 'observed': str(observed), 'passed': bool(passed)})


async def main() -> dict[str, str]:
    directory = tempfile.mkdtemp()
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        async def value(sql: str, *values: object) -> Any:
            return (await (await db.execute(sql, values)).fetchone())[0]

        async def admit() -> UUID:
            await db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null where status <> 'done'")
            binding = SimpleNamespace(session_id=None, expert_id=None, version=None, instructions='', tools={**PLAN_TOOLS, 'send_readable': 1, 'send_blind': 1})
            return (await admit_run(db, workspace_id=WORKSPACE, actor_id=ACTOR, idempotency_key=str(uuid4()), goal_text='Send it', limit_micro_usd=1_000_000, policy=resolve_role_policy(), binding=binding)).run_id

        async def state(run: UUID) -> str:
            return await value('select status from public.runs where id = %s', run)

        async def advance(sink: Sink, items: list[Any], behavior: dict[str, str] | None = None) -> tuple[Any, Script]:
            model = Script(items=items, seen=[], bound=[])
            config = LoopConfig(route=ROUTE, tools=tools(sink, behavior=behavior), sleep=lambda _: asyncio.sleep(0))
            return await process_next(db, URL, 'worker', lambda: model, config), model

        async def approve(run: UUID) -> None:
            row = await (await db.execute("select id, argument_hash from public.approval_requests where run_id = %s and status = 'pending' order by created_at desc limit 1", (run,))).fetchone()
            await decide(db, workspace_id=WORKSPACE, actor_id=ACTOR, approval_id=row[0], idempotency_key=str(uuid4()), decision='approve', argument_hash=row[1])

        async def resume(run: UUID) -> None:
            version = await value('select version from public.runs where id = %s', run)
            await apply_command(db, workspace_id=WORKSPACE, run_id=run, command=RunCommand.RESUME, expected_version=version)

        def send(tool: str, body: str) -> tuple[str, dict[str, str]]:
            return (tool, {'body': body})

        def sink_for(name: str, **options: Any) -> Sink:
            return Sink(Path(directory) / f'{name}.log', **options)

        # A lost acknowledgment, with a destination that can answer.
        sink = sink_for('readable')
        run = await admit()
        await advance(sink, [calls(send('send_readable', 'a')), say('never')])
        await approve(run)
        result, _ = await advance(sink, [say('never')], {'a': 'lose_ack'})
        status = await value("select status from app_private.tool_receipts where run_id = %s", run)
        check('a lost acknowledgment records an unknown outcome and pauses', 'paused, unknown, delivered once', (result.run_status, result.code, status, sink.attempts()), result.run_status == 'paused' and result.code == 'outcome_unknown' and status == 'unknown' and sink.attempts() == 1)
        check('a tool with a readback isn\'t blocked, since replay resolves it', 'not blocked', await has_unresolvable_effect(db, run), not await has_unresolvable_effect(db, run))
        view = await read_workspace(db, WORKSPACE, run)
        check('it shows on the run', '1 unknown effect, listed', view.outstanding, view.outstanding.unknown_effects == 1 and len(view.unknown_operations) == 1)
        await resume(run)
        result, model = await advance(sink, [say('stop')])
        status = await value("select status from app_private.tool_receipts where run_id = %s", run)
        check('recovery reads back from the destination instead of resending', 'succeeded, still 1 delivery', (status, sink.attempts()), status == 'succeeded' and sink.attempts() == 1)
        reply = [json.loads(item.content) for item in model.seen[0] if item.type == 'tool'][-1]
        check('and the model is told it happened', 'succeeded', reply['outcome'], reply['outcome'] == 'succeeded')

        # The destination says it never arrived, so a retry is safe.
        sink = sink_for('retry')
        run = await admit()
        await advance(sink, [calls(send('send_readable', 'b')), say('never')])
        await approve(run)
        await db.execute("update app_private.run_jobs set status = 'queued' where run_id = %s", (run,))
        operation = await value('select operation_id from public.approval_requests where run_id = %s', run)
        await db.execute("insert into app_private.tool_receipts (operation_id, run_id, workspace_id, tool_id, tool_version, argument_hash, status, generation) values (%s, %s, %s, 'send_readable', 1, 'h', 'unknown', 1)", (operation, run, WORKSPACE))
        result, _ = await advance(sink, [say('stop')])
        check('a readback showing no delivery allows one real attempt', '1 delivery', sink.attempts(), sink.attempts() == 1)

        # A real worker dies right after the effect reached the destination.
        sink = sink_for('killed')
        run = await admit()
        await advance(sink, [calls(send('send_readable', 'c')), say('never')])
        await approve(run)
        process = await asyncio.create_subprocess_exec(PYTHON, str(HERE / 'effect_worker.py'), URL, str(sink.path), 'c', stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        _, err = await asyncio.wait_for(process.communicate(), 60)
        check('the worker process was killed after the effect, before its receipt', 'exit -9, 1 delivery, started', (f'exit {process.returncode}: {err.decode()[-200:]}', sink.attempts(), await value('select status from app_private.tool_receipts where run_id = %s', run)), process.returncode == -9 and sink.attempts() == 1 and await value('select status from app_private.tool_receipts where run_id = %s', run) == 'started')
        await db.execute("update app_private.run_jobs set lease_expires_at = clock_timestamp() - interval '1 second' where run_id = %s", (run,))
        result, _ = await advance(sink, [say('stop')])
        status = await value('select status from app_private.tool_receipts where run_id = %s', run)
        check('the replacement reads back, and doesn\'t send again', 'succeeded, still 1', (status, sink.attempts()), status == 'succeeded' and sink.attempts() == 1)

        # A destination that can't say.
        sink = sink_for('blind')
        run = await admit()
        await advance(sink, [calls(send('send_blind', 'd')), say('never')])
        await approve(run)
        result, _ = await advance(sink, [say('never')], {'d': 'lose_ack'})
        check('with no readback, the outcome stays unknown', 'paused, outcome_unknown', (result.run_status, result.code), result.run_status == 'paused' and result.code == 'outcome_unknown')
        await resume(run)
        result, model = await advance(sink, [say('never')])
        check('a replay doesn\'t resend it and stays paused', 'still 1 delivery, paused', (sink.attempts(), result.run_status, len(model.seen)), sink.attempts() == 1 and result.run_status == 'paused' and not model.seen)
        operation = (await unknown_operations(db, run))[0].operation_id
        check('resume is blocked with no way to resolve it alone', 'blocked', await has_unresolvable_effect(db, run), await has_unresolvable_effect(db, run))
        view = await read_workspace(db, WORKSPACE, run)
        check('the uncertainty stays visible', 'send_blind listed', view.unknown_operations[0].tool_id, view.unknown_operations[0].tool_id == 'send_blind')
        try:
            await record_evidence(db, operation_id=operation, actor_id=ACTOR, idempotency_key=str(uuid4()), outcome='not_delivered', evidence='x', workspace_id=WORKSPACE, run_id=run, generation=view.unknown_operations[0].generation + 1)
            check('a ruling on an attempt that has since changed is refused', 'operation_attempt_changed', 'recorded', False)
        except ReconciliationRefused as error:
            check('a ruling on an attempt that has since changed is refused', 'operation_attempt_changed', error.code, error.code == 'operation_attempt_changed')
        for label, options, code in (('another workspace', {'workspace_id': OTHER, 'run_id': run}, 'operation_not_found'), ('another run', {'workspace_id': WORKSPACE, 'run_id': uuid4()}, 'operation_not_found')):
            try:
                await record_evidence(db, operation_id=operation, actor_id=ACTOR, idempotency_key=str(uuid4()), outcome='delivered', evidence='x', **options)
                check(f'{label} can\'t reconcile it', code, 'recorded', False)
            except ReconciliationRefused as error:
                check(f'{label} can\'t reconcile it', code, error.code, error.code == code)
        await record_evidence(db, workspace_id=WORKSPACE, run_id=run, operation_id=operation, actor_id=ACTOR, idempotency_key='o1', outcome='delivered', evidence='Seen in the destination log, entry 12.')
        kept = await value('select evidence from app_private.tool_receipts where operation_id = %s', operation)
        check('operator evidence is kept with the receipt', 'the note', kept, 'entry 12' in kept)
        try:
            await record_evidence(db, workspace_id=WORKSPACE, run_id=run, operation_id=operation, actor_id=ACTOR, idempotency_key='o2', outcome='not_delivered', evidence='changed my mind')
            check('a resolved outcome can\'t be changed', 'operation_not_unknown', 'recorded', False)
        except ReconciliationRefused as error:
            check('a resolved outcome can\'t be changed', 'operation_not_unknown', error.code, error.code == 'operation_not_unknown')
        await resume(run)
        result, model = await advance(sink, [say('stop')])
        check('after evidence of delivery, the replay doesn\'t resend', 'still 1', sink.attempts(), sink.attempts() == 1)

        # Operator evidence of no delivery allows a retry, and an idempotent destination absorbs a wrong call.
        sink = sink_for('deduped', idempotent=True)
        run = await admit()
        await advance(sink, [calls(send('send_blind', 'e')), say('never')])
        await approve(run)
        await advance(sink, [say('never')], {'e': 'lose_ack'})
        operation = (await unknown_operations(db, run))[0].operation_id
        await record_evidence(db, workspace_id=WORKSPACE, run_id=run, operation_id=operation, actor_id=ACTOR, idempotency_key='o3', outcome='not_delivered', evidence='Nothing in the log.')
        await resume(run)
        await advance(sink, [say('stop')])
        check('a mistaken report of no delivery causes a second attempt, and the key prevents a second effect', '2 attempts, 1 effect', (sink.attempts(), sink.effects()), sink.attempts() == 2 and sink.effects() == 1)
        keys = {line['key'] for line in sink._lines()}
        check('both attempts carry the same operation identity', 'one key', len(keys), len(keys) == 1)

        # A destination with no idempotency keys shows why a retry needs that evidence to be right.
        sink = sink_for('duplicate')
        run = await admit()
        await advance(sink, [calls(send('send_blind', 'f')), say('never')])
        await approve(run)
        await advance(sink, [say('never')], {'f': 'lose_ack'})
        operation = (await unknown_operations(db, run))[0].operation_id
        await record_evidence(db, workspace_id=WORKSPACE, run_id=run, operation_id=operation, actor_id=ACTOR, idempotency_key='o4', outcome='not_delivered', evidence='Mistaken report.')
        await resume(run)
        await advance(sink, [say('stop')])
        check('with no destination key, a mistaken report really duplicates: nothing claims exactly once', '2 effects', sink.effects(), sink.effects() == 2)

        # A confirmed refusal isn't unknown.
        sink = sink_for('refused')
        run = await admit()
        await advance(sink, [calls(send('send_readable', 'g')), say('never')])
        await approve(run)
        result, model = await advance(sink, [say('stop')], {'g': 'refuse'})
        status = await value('select status from app_private.tool_receipts where run_id = %s', run)
        check('a refusal from the destination is a known failure', 'failed, no delivery', (status, sink.attempts()), status == 'failed' and sink.attempts() == 0)

        # Left unknown for the browser.
        sink = sink_for('browser')
        run = await admit()
        await advance(sink, [calls(send('send_blind', 'h')), say('never')])
        await approve(run)
        await advance(sink, [say('never')], {'h': 'lose_ack'})
        operation = (await unknown_operations(db, run))[0].operation_id
    return {'AUTOBOTS_TEST_UNKNOWN_RUN': str(run), 'AUTOBOTS_TEST_UNKNOWN_OPERATION': operation}


try:
    browser_env = asyncio.run(main())
    print(json.dumps({'cases': cases, 'browser_env': browser_env}))
except Exception:
    print(json.dumps({'cases': cases}))
    raise
