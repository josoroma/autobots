"""A pass that keeps raising is bounded, on a real database through the runtime role (Decision 0028 E4,
R-35, PRUN-14, XERR-10, SP-012). JSON cases.

Scope guidance raises an arranged defect inside the pass, under the lease keeper and the fenced
checkpointer, so it leaves `run_goal` the way an unclassified defect does. Each `process_next` claims
the run once, so the job's `attempts` counts claims. The backoff runs on database time: each scenario
observes it, then moves `available_at` back instead of waiting it out (arranged).

Argument: the workspace.
"""
from __future__ import annotations

import os
import sys
from collections.abc import Awaitable, Callable
from unittest.mock import patch
from uuid import UUID, uuid4

from autobots.application import goal_loop
from autobots.application.run_lifecycle import LoopConfig
from autobots.application.run_projection import read_events, read_workspace
from autobots.application.worker_leases import FAILURE_BOUND, RETRY_DELAYS_SECONDS, claim_next
from autobots.domain.runs import RunCommand
from autobots.operations.job_dispatch import process_next
from checklib import QUIESCE, Cases, Db, run_check
from goal_loop_script import ROUTE, Script, say

URL = os.environ['AUTOBOTS_DATABASE_URL']
WORKSPACE = UUID(sys.argv[1])
CONFIG = LoopConfig(route=ROUTE)
# The defect's message is never stored or published; only its module-qualified type is kept, privately.
MESSAGE = 'arranged-defect-message-never-stored'
TYPE = '__main__.ArrangedDefect'
# Every run this check admits, so that none is left for a later check's worker to claim.
CREATED: list[UUID] = []
JOB = ('select j.status, j.attempts, j.failed_attempts, j.last_failure_type, '
       'extract(epoch from j.available_at - clock_timestamp())::float8, r.status '
       'from app_private.run_jobs j join public.runs r on r.id = j.run_id where j.run_id = %s')


class ArrangedDefect(Exception):
    """Raised where no handler in the pass classifies it, as a defect would be."""


async def failing_pass(db: Db, run: UUID, label: str, before: Callable[[], Awaitable[object]] | None = None) -> None:
    """One claim and one pass of `run`, whose scope guidance raises the defect out of process_next.
    `before`, when given, runs inside the pass first, as a person's command arriving then."""

    async def broken(*_: object) -> str:
        if before is not None:
            await before()
        raise ArrangedDefect(MESSAGE)

    await db.quiesce(keep=run)
    with patch.object(goal_loop, 'scope_guidance', broken):
        await db.cases.refused(f'{label}: the pass raises the defect out of process_next', None,
                               process_next(db.connection, URL, 'failing-worker', lambda: Script(items=[], seen=[], bound=[]), CONFIG),
                               ArrangedDefect)


async def due_now(db: Db, run: UUID) -> None:
    """Arranged: the backoff was observed, so it is moved back rather than waited out."""
    await db.connection.execute('update app_private.run_jobs set available_at = clock_timestamp() where run_id = %s', (run,))


async def bounded(db: Db, cases: Cases) -> UUID:
    """Three consecutive failures: requeued after 30 s, then 60 s, then the run is paused."""
    run = await db.admit('Write the report', acceptance_criteria=('Has a summary',))
    CREATED.append(run)
    for attempt in range(1, FAILURE_BOUND):
        await failing_pass(db, run, f'failure {attempt}')
        delay = RETRY_DELAYS_SECONDS[attempt - 1]
        cases.check(f'failure {attempt} is recorded privately and requeued after {delay:.0f} s',
                    f'queued, claim {attempt}, {attempt} failed, {TYPE}, due in about {delay:.0f} s, run running',
                    await db.row(JOB, run),
                    lambda row, attempt=attempt, delay=delay: row[:4] == ('queued', attempt, attempt, TYPE)
                    and delay - 5 <= row[4] <= delay + 0.5 and row[5] == 'running')
        await db.quiesce(keep=run)
        early = await claim_next(db.connection, worker_id='too-early')
        cases.check(f'nothing claims it during the {delay:.0f} s backoff', 'no claim', early, early is None)
        await due_now(db, run)
    await failing_pass(db, run, f'failure {FAILURE_BOUND}')
    status, claims, failed, kind, _, run_status = await db.row(JOB, run)
    cases.check(f'failure {FAILURE_BOUND} suspends the run, and its job is done', f'paused, job done, {FAILURE_BOUND} claims, {FAILURE_BOUND} failed, {TYPE}',
                (run_status, status, claims, failed, kind),
                (run_status, status, claims, failed, kind) == ('paused', 'done', FAILURE_BOUND, FAILURE_BOUND, TYPE))
    await db.quiesce(keep=run)
    after = await process_next(db.connection, URL, 'later-worker', lambda: Script(items=[], seen=[], bound=[]), CONFIG)
    claims = await db.value('select attempts from app_private.run_jobs where run_id = %s', run)
    cases.check('no worker claims the paused run again', f'no claim, still {FAILURE_BOUND} claims', (after, claims),
                after is None and claims == FAILURE_BOUND)
    view = await read_workspace(db.connection, WORKSPACE, run)
    shown = view.model_dump_json()
    cases.check('a person sees it paused with worker_failed, and neither the type nor the message',
                'paused, worker_failed, no type, no message', (view.run.status, view.stop_reason),
                view.run.status == 'paused' and view.stop_reason == 'worker_failed' and 'ArrangedDefect' not in shown and MESSAGE not in shown)
    page = await read_events(db.connection, WORKSPACE, run, after=0)
    last = page.events[-1].payload.model_dump(mode='json') if page.events else None
    published = page.model_dump_json()
    cases.check('its events publish only the status change, with no type or message',
                "last: running to paused; no type, no message", last,
                last == {'type': 'run.status_changed', 'previous': 'running', 'current': 'paused'}
                and 'ArrangedDefect' not in published and MESSAGE not in published)
    stored = await db.leaked([MESSAGE])
    holding = await db.leaked([TYPE])
    cases.check('the message is stored nowhere, and the type only in the private job row', 'message nowhere; type in app_private.run_jobs',
                (stored, holding), stored == [] and holding == ['app_private.run_jobs'])
    return run


async def resets(db: Db, cases: Cases, run: UUID) -> None:
    """A person's resume starts the count again, and so does a pass that completes."""
    await db.command(run, RunCommand.RESUME)
    status, _, failed, _, _, run_status = await db.row(JOB, run)
    cases.check("a person's resume queues the job with the count reset", 'queued, 0 failed, run queued',
                (status, failed, run_status), (status, failed, run_status) == ('queued', 0, 'queued'))
    await failing_pass(db, run, 'after the resume')
    cases.check('a failure after the resume starts the bound again', 'queued, 1 failed, due in about 30 s, run running',
                await db.row(JOB, run),
                lambda row: row[0] == 'queued' and row[2] == 1 and 25 <= row[4] <= 30.5 and row[5] == 'running')
    await due_now(db, run)
    await db.quiesce(keep=run)
    result = await process_next(db.connection, URL, 'working-worker', lambda: Script(items=[say('Nothing to plan.')], seen=[], bound=[]), CONFIG)
    failed = await db.value('select failed_attempts from app_private.run_jobs where run_id = %s', run)
    cases.check('a pass that completes resets the count', 'plan_missing, 0 failed',
                (result.code if result else None, failed), result is not None and result.code == 'plan_missing' and failed == 0)


async def paused_meanwhile(db: Db, cases: Cases) -> None:
    """A person pauses the run while the failing pass holds it: their pause stands, and the job is let go."""
    run = await db.admit('Write the report', acceptance_criteria=('Has a summary',))
    CREATED.append(run)
    await failing_pass(db, run, 'paused during the pass', before=lambda: db.command(run, RunCommand.PAUSE))
    status, claims, failed, kind, _, run_status = await db.row(JOB, run)
    cases.check("a person's pause during a failing pass stands, and the job is let go", f'paused, job done, 1 claim, 1 failed, {TYPE}',
                (run_status, status, claims, failed, kind), (run_status, status, claims, failed, kind) == ('paused', 'done', 1, 1, TYPE))
    # Nothing waits on it after this check.
    await db.command(run, RunCommand.CANCEL)


async def main(cases: Cases) -> None:
    async with Db.connect(URL, cases, WORKSPACE, uuid4()) as db:
        try:
            run = None
            with cases.scenario('a pass that keeps raising is bounded'):
                run = await bounded(db, cases)
            if run is not None:
                with cases.scenario('the count resets'):
                    await resets(db, cases, run)
            with cases.scenario('a pause during a failing pass'):
                await paused_meanwhile(db, cases)
        finally:
            await db.connection.execute(f'{QUIESCE} and run_id = any(%s)', (CREATED,))


run_check(main)
