"""Competing workers, stale owners and a real killed process, printed as JSON cases."""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
from langgraph.checkpoint.postgres import PostgresSaver

sys.path.insert(0, str(Path(__file__).parent))
from worker_graph import build  # noqa: E402

from autobots.adapters.checkpoints import DURABILITY, fenced_checkpointer, graph_config, is_stale_owner  # noqa: E402
from autobots.application.runs import LeaseLost, admit_run, apply_command  # noqa: E402
from autobots.application.tool_gateway import ToolScope, ownership_refusal  # noqa: E402
from autobots.application.worker_leases import claim_next, heartbeat  # noqa: E402
from autobots.domain.models import resolve_role_policy  # noqa: E402
from autobots.domain.runs import Actor, RunCommand  # noqa: E402

URL = os.environ['AUTOBOTS_DATABASE_URL']
WORKSPACE = UUID(sys.argv[1])
PYTHON = sys.argv[2]
HERE = Path(__file__).parent
ACTOR = uuid4()
POLICY = resolve_role_policy()
cases = []


def check(name: str, expected: str, observed: object, passed: bool) -> None:
    cases.append({'id': name, 'expected': expected, 'observed': str(observed), 'passed': bool(passed)})


async def main() -> None:
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        async def value(sql: str, *values: object) -> object:
            return (await (await db.execute(sql, values)).fetchone())[0]

        async def admit() -> UUID:
            """Only this run's job is eligible, so each case observes one job."""
            await db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null where status <> 'done'")
            return (await admit_run(db, workspace_id=WORKSPACE, actor_id=ACTOR, idempotency_key=str(uuid4()), goal_text='work', limit_micro_usd=1000, policy=POLICY)).run_id

        async def expire(run_id: UUID) -> None:
            await db.execute("update app_private.run_jobs set lease_expires_at = clock_timestamp() - interval '1 second' where run_id = %s", (run_id,))

        async def rejected(attempt) -> str:  # type: ignore[no-untyped-def]
            try:
                await attempt()
            except Exception as error:  # noqa: BLE001
                return 'stale owner' if is_stale_owner(error) else type(error).__name__
            return 'accepted'

        versions = await value('select max(v) from agent_runtime.checkpoint_migrations')
        check('the migration matches the pinned adapter', f'version {len(PostgresSaver.MIGRATIONS) - 1}', versions, versions == len(PostgresSaver.MIGRATIONS) - 1)

        run = await admit()

        async def compete():  # type: ignore[no-untyped-def]
            async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as other:
                return await claim_next(other, worker_id=str(uuid4()), lease_seconds=30)
        claims = [c for c in await asyncio.gather(*(compete() for _ in range(8))) if c is not None]
        check('eight competing workers get one claim', '1', len(claims), len(claims) == 1)
        lease = claims[0]
        check('the claim starts generation 1 and moves the run', 'generation 1, running', (lease.generation, lease.run_status), lease.generation == 1 and lease.run_status == 'running')
        status, version = (await (await db.execute('select status, version from public.runs where id = %s', (run,))).fetchone())
        events = await value('select count(*) from public.run_events where run_id = %s and sequence = 2', run)
        check('the claim is a recorded transition', 'running, version 2, an event', (status, version, events), status == 'running' and version == 2 and events == 1)
        check('a duplicate delivery of a held job gets nothing', 'no claim', await claim_next(db, worker_id='dup'), await claim_next(db, worker_id='dup') is None)
        before = await value('select lease_expires_at from app_private.run_jobs where run_id = %s', run)
        await heartbeat(db, lease, lease_seconds=60)
        after = await value('select lease_expires_at from app_private.run_jobs where run_id = %s', run)
        check('a heartbeat extends a live lease by database time', 'later', after > before, after > before)

        # A stale owner resumes after reassignment, and tries both kinds of write.
        with tempfile.TemporaryDirectory() as directory:
            log = str(Path(directory) / 'effects.log')
            async with fenced_checkpointer(URL, lease) as stale_saver:
                stale = build(stale_saver, log)
                await stale.ainvoke({'seen': []}, graph_config(lease), durability=DURABILITY)
                saved = await value('select count(*) from agent_runtime.checkpoints where thread_id = %s', str(run))
                check('the current owner can checkpoint', 'rows', saved, saved > 0)

                await expire(run)
                refused = await rejected(lambda: stale.ainvoke({'seen': []}, graph_config(lease), durability=DURABILITY))
                check('an expired lease cannot checkpoint, even before anyone reclaims it', 'stale owner', refused, refused == 'stale owner')
                try:
                    await heartbeat(db, lease)
                    check('an expired lease cannot be renewed', 'lease lost', 'renewed', False)
                except LeaseLost:
                    check('an expired lease cannot be renewed', 'lease lost', 'lease lost', True)

                replacement = await claim_next(db, worker_id='second-worker', lease_seconds=60)
                check('a replacement claims after expiry with a higher generation', 'generation 2, attempt 2', (replacement.generation, replacement.attempts), replacement.generation == 2 and replacement.attempts == 2)
                count = await value('select count(*) from agent_runtime.checkpoints where thread_id = %s', str(run))
                refused = await rejected(lambda: stale.ainvoke({'seen': []}, graph_config(lease), durability=DURABILITY))
                unchanged = await value('select count(*) from agent_runtime.checkpoints where thread_id = %s', str(run))
                check('the stale worker cannot checkpoint after reassignment', 'stale owner, no new rows', (refused, unchanged - count), refused == 'stale owner' and unchanged == count)
                version = await value('select version from public.runs where id = %s', run)
                try:
                    await apply_command(db, workspace_id=WORKSPACE, run_id=run, command=RunCommand.VERIFY, actor=Actor.WORKER, expected_version=version, generation=lease.generation)
                    check('the stale worker cannot change the run', 'lease lost', 'applied', False)
                except LeaseLost:
                    unchanged = await value('select version from public.runs where id = %s', run)
                    check('the stale worker cannot change the run', 'lease lost, version unchanged', unchanged, unchanged == version)

                async with fenced_checkpointer(URL, replacement) as saver:
                    await saver.aget_tuple(graph_config(replacement))
                    count = await value('select count(*) from agent_runtime.checkpoints where thread_id = %s', str(run))
                    await build(saver, log).ainvoke({'seen': []}, graph_config(replacement), durability=DURABILITY)
                    grew = await value('select count(*) from agent_runtime.checkpoints where thread_id = %s', str(run))
                    check('the replacement can checkpoint', 'more rows', grew - count, grew > count)
                result = await apply_command(db, workspace_id=WORKSPACE, run_id=run, command=RunCommand.VERIFY, actor=Actor.WORKER, expected_version=version, generation=replacement.generation)
                check('the replacement can change the run', 'verifying', result.status, result.status == 'verifying')

        # A write and a claim race on the job row: the write waits for the claim, and then fails.
        run = await admit()
        lease = await claim_next(db, worker_id='racer', lease_seconds=60)
        async with fenced_checkpointer(URL, lease) as saver:
            async with await psycopg.AsyncConnection.connect(URL) as claimer:
                await claimer.execute('update app_private.run_jobs set generation = generation + 1 where run_id = %s', (run,))
                write = asyncio.create_task(rejected(lambda: build(saver, os.devnull).ainvoke({'seen': []}, graph_config(lease), durability=DURABILITY)))
                await asyncio.sleep(0.5)
                check('a write racing an uncommitted claim waits', 'pending', 'pending' if not write.done() else 'finished', not write.done())
                await claimer.commit()
                outcome = await asyncio.wait_for(write, 20)
                check('and then fails against the new generation', 'stale owner', outcome, outcome == 'stale owner')

        # A pause reaches a live owner at its next check, and it saves its step and lets go.
        run = await admit()
        lease = await claim_next(db, worker_id='paused', lease_seconds=60)
        await apply_command(db, workspace_id=WORKSPACE, run_id=run, command=RunCommand.PAUSE, actor=Actor.USER, expected_version=2)
        scope = ToolScope(WORKSPACE, run, lease.generation, {})
        refusal = await ownership_refusal(db, scope)
        check('a paused run stops its owner dispatching', 'run_not_running', refusal, refusal == 'run_not_running')
        async with fenced_checkpointer(URL, lease) as saver:
            saved = await rejected(lambda: build(saver, os.devnull).ainvoke({'seen': []}, graph_config(lease), durability=DURABILITY))
            check('the owner can still save its step at that boundary', 'accepted', saved, saved == 'accepted')
            check('a paused run is not claimable', 'no claim', await claim_next(db, worker_id='x') is None, await claim_next(db, worker_id='x') is None)
            await expire(run)
            check('even once its owner dies', 'no claim', await claim_next(db, worker_id='x') is None, await claim_next(db, worker_id='x') is None)
            await apply_command(db, workspace_id=WORKSPACE, run_id=run, command=RunCommand.RESUME, actor=Actor.USER, expected_version=3)
            refused = await rejected(lambda: build(saver, os.devnull).ainvoke({'seen': []}, graph_config(lease), durability=DURABILITY))
            check('a resume ends the old owner', 'stale owner', refused, refused == 'stale owner')
        resumed = await claim_next(db, worker_id='after-resume', lease_seconds=60)
        check('a resumed run is claimed by a new generation', 'generation 2', resumed.generation, resumed.generation == 2)
        cancelling = await apply_command(db, workspace_id=WORKSPACE, run_id=run, command=RunCommand.CANCEL, actor=Actor.USER, expected_version=5)
        check('cancelling a run with a live owner waits for it', 'cancelling', cancelling.status, cancelling.status == 'cancelling')
        finished = await apply_command(db, workspace_id=WORKSPACE, run_id=run, command=RunCommand.FINISH_CANCEL, actor=Actor.WORKER, expected_version=6, generation=resumed.generation)
        check('the owner finishes the cancellation', 'cancelled', finished.status, finished.status == 'cancelled')
        run = await admit()
        await claim_next(db, worker_id='crashed', lease_seconds=60)
        await expire(run)
        direct = await apply_command(db, workspace_id=WORKSPACE, run_id=run, command=RunCommand.CANCEL, actor=Actor.USER, expected_version=2)
        check('cancelling after the owner died needs no worker', 'cancelled', direct.status, direct.status == 'cancelled')

        run = await admit()
        await db.execute("update app_private.run_jobs set available_at = clock_timestamp() + interval '1 hour' where run_id = %s", (run,))
        check('a job not yet available is not claimed', 'no claim', await claim_next(db, worker_id='x') is None, await claim_next(db, worker_id='x') is None)

        # Bypassing the application: no generation at all, or a thread with no job.
        run = await admit()
        await claim_next(db, worker_id='owner', lease_seconds=60)
        direct = "insert into agent_runtime.checkpoints (thread_id, checkpoint_id, checkpoint) values (%s, 'x', '{}')"
        try:
            await db.execute(direct, (str(run),))
            check('a write with no generation is refused by the database', 'refused', 'accepted', False)
        except psycopg.Error as error:
            check('a write with no generation is refused by the database', 'AB001', error.sqlstate, error.sqlstate == 'AB001')
        try:
            await db.execute(direct, (str(uuid4()),))
            check('a thread with no job is refused', 'refused', 'accepted', False)
        except psycopg.Error as error:
            check('a thread with no job is refused', 'AB001', error.sqlstate, error.sqlstate == 'AB001')
        try:
            await db.execute('alter table agent_runtime.checkpoints disable trigger all')
            check('the runtime role cannot disable the guard', 'refused', 'disabled', False)
        except psycopg.Error as error:
            check('the runtime role cannot disable the guard', 'must be owner', str(error)[:60], 'must be owner' in str(error))

        # A real process dies after a persisted boundary. The replacement uses the saved checkpoint.
        run = await admit()
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / 'effects.log'
            process = await asyncio.create_subprocess_exec(
                PYTHON, str(HERE / 'worker_process.py'), URL, str(log), 'second', '2',
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            out, err = await asyncio.wait_for(process.communicate(), 60)
            check('the first worker was killed mid-step', 'exit -9', f'exit {process.returncode}: {err.decode()[-200:]}', process.returncode == -9 and out.decode().strip() == str(run))
            lines = log.read_text().split()
            check('it did the first step and started the second', 'first, second', lines, lines == ['first', 'second'])
            live = await claim_next(db, worker_id='too-early')
            check('its lease still holds by database time', 'no claim yet', live is None, live is None)
            deadline = time.monotonic() + 10
            replacement = None
            while replacement is None and time.monotonic() < deadline:
                await asyncio.sleep(0.2)
                replacement = await claim_next(db, worker_id='replacement', lease_seconds=60)
            check('the replacement claims when the lease runs out', 'generation 2, attempt 2', (replacement.generation, replacement.attempts) if replacement else None, replacement is not None and replacement.generation == 2 and replacement.attempts == 2)
            async with fenced_checkpointer(URL, replacement) as saver:
                graph = build(saver, str(log))
                saved = await graph.aget_state(graph_config(replacement))
                check('the saved checkpoint has the completed step', "['first'], next second", (saved.values.get('seen'), saved.next), saved.values.get('seen') == ['first'] and saved.next == ('second',))
                final = await graph.ainvoke(None, graph_config(replacement), durability=DURABILITY)
            lines = log.read_text().split()
            check('the completed step is not redone', 'first once', lines.count('first'), lines.count('first') == 1)
            check('the unfinished step runs again, so remote work is not exactly once', 'second twice', lines.count('second'), lines.count('second') == 2)
            check('the run finishes from the checkpoint', "['first', 'second', 'third']", final['seen'], final['seen'] == ['first', 'second', 'third'])

        # SP-012 asks to measure the cost of synchronous durability.
        run = await admit()
        lease = await claim_next(db, worker_id='timing', lease_seconds=60)
        async with fenced_checkpointer(URL, lease) as saver:
            graph = build(saver, os.devnull)
            timings = {}
            for mode in ('sync', 'exit'):
                started = time.perf_counter()
                for index in range(10):
                    await graph.ainvoke({'seen': []}, {'configurable': {'thread_id': lease.thread_id, 'checkpoint_ns': ''}}, durability=mode)
                timings[mode] = round((time.perf_counter() - started) * 100, 1)
        check('sync durability overhead was measured', 'ms per three-step run', timings, all(t > 0 for t in timings.values()))
    print(json.dumps({'cases': cases}))


asyncio.run(main())
