"""Real concurrent admission and transitions through the runtime role, printed as JSON cases."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from uuid import UUID, uuid4

import psycopg
from autobots.application.runs import (
    IdempotencyConflict,
    RunNotFound,
    VersionConflict,
    admit_run,
    apply_command,
)
from autobots.domain.models import resolve_role_policy
from autobots.domain.runs import Actor, CommandRefused, RunCommand

URL = os.environ['AUTOBOTS_DATABASE_URL']
WORKSPACE, OTHER = UUID(sys.argv[1]), UUID(sys.argv[2])
ACTOR, OTHER_ACTOR = uuid4(), uuid4()
POLICY = resolve_role_policy()
cases = []


def check(name: str, expected: str, observed: object, passed: bool) -> None:
    cases.append({'id': name, 'expected': expected, 'observed': str(observed), 'passed': bool(passed)})


async def admit(key: str, goal: str = 'write the report', actor: UUID = ACTOR, workspace: UUID = WORKSPACE, limit: int = 1000):  # type: ignore[no-untyped-def]
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as connection:
        return await admit_run(connection, workspace_id=workspace, actor_id=actor, idempotency_key=key, goal_text=goal, limit_micro_usd=limit, policy=POLICY)


async def hold_lease(connection, run_id):  # type: ignore[no-untyped-def]
    """Arranged, with no worker: this file tests the table, and US-4.2's check tests real claims."""
    await connection.execute("update app_private.run_jobs set status = 'claimed', generation = 1, lease_expires_at = now() + interval '1 hour' where run_id = %s", (run_id,))


async def command(connection, run_id, name, version, actor=Actor.USER, **options):  # type: ignore[no-untyped-def]
    if actor is Actor.WORKER:
        await hold_lease(connection, run_id)
        options['generation'] = 1
    return await apply_command(connection, workspace_id=WORKSPACE, run_id=run_id, command=name, actor=actor, expected_version=version, **options)


async def main() -> None:
    results = await asyncio.gather(*(admit('key-1') for _ in range(12)), return_exceptions=True)
    good = [r for r in results if not isinstance(r, Exception)]
    ids = {r.run_id for r in good}
    check('twelve concurrent matching admissions give one run', '1 run, 11 replays', f'{len(ids)} runs, {sum(r.replayed for r in good)} replays, {len(good)} results',
          len(ids) == 1 and len(good) == 12 and sum(r.replayed for r in good) == 11)
    run_id = next(iter(ids))
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as connection:
        async def count(sql: str, *values: object) -> int:
            return (await (await connection.execute(sql, values)).fetchone())[0]
        counts = (await count('select count(*) from public.runs where id = %s', run_id),
                  await count('select count(*) from app_private.run_jobs where run_id = %s', run_id),
                  await count('select count(*) from public.run_events where run_id = %s', run_id))
        check('one run, one job and one event are committed', '(1, 1, 1)', counts, counts == (1, 1, 1))
        snapshot = (await (await connection.execute('select policy_snapshot from public.runs where id = %s', (run_id,))).fetchone())[0]
        check('the role policy is frozen at admission', '14 bindings', len(snapshot['bindings']), len(snapshot['bindings']) == 14)

        try:
            await admit('key-1', goal='something else')
            check('the same key with different content is refused', 'conflict', 'admitted', False)
        except IdempotencyConflict as error:
            check('the same key with different content is refused', 'conflict', error.code, True)
        same = await admit('key-1', goal='  write the report  ')
        check('normalized content matches', 'replayed', same.replayed, same.replayed and same.run_id == run_id)
        different_actor = await admit('key-1', actor=OTHER_ACTOR)
        check('a key is scoped by actor', 'a new run', different_actor.replayed, not different_actor.replayed and different_actor.run_id != run_id)
        different_workspace = await admit('key-1', workspace=OTHER)
        check('a key is scoped by workspace', 'a new run', different_workspace.replayed, not different_workspace.replayed and different_workspace.run_id != run_id)

        racing = await asyncio.gather(*(admit(f'race-{i}') for i in range(5)))
        check('different keys admit separately', '5 runs', len({r.run_id for r in racing}), len({r.run_id for r in racing}) == 5)

        async def in_status(status: str, version: int = 1) -> UUID:
            new = (await admit(f'status-{uuid4()}')).run_id
            await connection.execute('update public.runs set status = %s, version = %s where id = %s', (status, version, new))
            return new

        for status, name, actor, wanted in (
                ('queued', RunCommand.CLAIM, Actor.WORKER, 'running'), ('running', RunCommand.VERIFY, Actor.WORKER, 'verifying'),
                ('verifying', RunCommand.COMPLETE, Actor.WORKER, 'succeeded'), ('running', RunCommand.FAIL, Actor.WORKER, 'failed'),
                ('running', RunCommand.REQUEST_INPUT, Actor.WORKER, 'waiting_input'), ('running', RunCommand.REQUEST_APPROVAL, Actor.WORKER, 'waiting_approval'),
                ('waiting_input', RunCommand.SUBMIT_INPUT, Actor.USER, 'queued'), ('waiting_approval', RunCommand.DECIDE_APPROVAL, Actor.USER, 'queued'),
                ('running', RunCommand.PAUSE, Actor.USER, 'paused'), ('paused', RunCommand.RESUME, Actor.USER, 'queued')):
            target = await in_status(status)
            result = await command(connection, target, name, 1, actor)
            events = await count('select count(*) from public.run_events where run_id = %s and sequence = 2', target)
            check(f'{status} --{name.value}--> {wanted}', f'{wanted}, version 2, an event', (result.status, result.version, events),
                  result.status == wanted and result.version == 2 and events == 1)

        for status, name, actor in (('queued', RunCommand.COMPLETE, Actor.WORKER), ('running', RunCommand.COMPLETE, Actor.WORKER),
                                    ('paused', RunCommand.CLAIM, Actor.WORKER), ('running', RunCommand.RESUME, Actor.USER),
                                    ('queued', RunCommand.SUBMIT_INPUT, Actor.USER), ('verifying', RunCommand.COMPLETE, Actor.USER),
                                    ('queued', RunCommand.CLAIM, Actor.USER), ('running', RunCommand.FAIL, Actor.USER)):
            target = await in_status(status)
            try:
                await command(connection, target, name, 1, actor)
                check(f'{actor.value} {name.value} from {status} is refused', 'refused', 'applied', False)
            except CommandRefused:
                unchanged = await count("select version from public.runs where id = %s", target)
                check(f'{actor.value} {name.value} from {status} is refused', 'refused, version unchanged', unchanged, unchanged == 1)

        for terminal in ('succeeded', 'failed', 'cancelled'):
            for name, actor in ((RunCommand.RESUME, Actor.USER), (RunCommand.CLAIM, Actor.WORKER), (RunCommand.PAUSE, Actor.USER)):
                target = await in_status(terminal)
                try:
                    await command(connection, target, name, 1, actor)
                    check(f'{terminal} cannot {name.value}', 'refused', 'reopened', False)
                except CommandRefused:
                    check(f'{terminal} cannot {name.value}', 'refused', 'refused', True)

        target = await in_status('queued')
        result = await command(connection, target, RunCommand.CANCEL, 1)
        check('cancel with no active work goes straight to cancelled', 'cancelled', result.status, result.status == 'cancelled')
        job = (await (await connection.execute('select status from app_private.run_jobs where run_id = %s', (target,))).fetchone())[0]
        check('a cancelled run has no claimable job', 'done', job, job == 'done')
        target = await in_status('running')
        await hold_lease(connection, target)
        result = await command(connection, target, RunCommand.CANCEL, 1)
        check('cancel with active work enters cancelling', 'cancelling', result.status, result.status == 'cancelling')
        repeat = await command(connection, target, RunCommand.CANCEL, 2)
        check('repeating cancel changes nothing', 'unchanged', repeat.changed, not repeat.changed and repeat.status == 'cancelling')
        done = await command(connection, target, RunCommand.FINISH_CANCEL, 2, Actor.WORKER)
        check('settling finishes the cancellation', 'cancelled', done.status, done.status == 'cancelled')

        target = await in_status('running')
        try:
            await command(connection, target, RunCommand.PAUSE, 99)
            check('a stale expected version is refused', 'conflict', 'applied', False)
        except VersionConflict as error:
            check('a stale expected version is refused', 'conflict', error.code, True)

        target = await in_status('running')
        async def race(index: int) -> object:
            async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as other:
                try:
                    return await command(other, target, RunCommand.PAUSE, 1)
                except Exception as error:  # noqa: BLE001
                    return error
        raced = await asyncio.gather(*(race(i) for i in range(6)))
        wins = [r for r in raced if not isinstance(r, Exception)]
        version = await count('select version from public.runs where id = %s', target)
        check('concurrent commands on one version apply once', '1 applied, version 2', f'{len(wins)}, {version}', len(wins) == 1 and version == 2)

        target = await in_status('running')
        first = await command(connection, target, RunCommand.PAUSE, 1, actor_id=ACTOR, idempotency_key='pause-1')
        again = await command(connection, target, RunCommand.PAUSE, 1, actor_id=ACTOR, idempotency_key='pause-1')
        check('a repeated command key returns the original result', 'same version, unchanged', (again.version, again.changed), again.version == first.version and not again.changed)

        foreign = (await admit('foreign', workspace=OTHER)).run_id
        try:
            await command(connection, foreign, RunCommand.PAUSE, 1)
            check('a run in another workspace is not found', 'not found', 'applied', False)
        except RunNotFound as error:
            check('a run in another workspace is not found', 'not found', error.code, True)
    print(json.dumps({'cases': cases}))


asyncio.run(main())
