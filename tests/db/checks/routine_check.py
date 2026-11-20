"""Duplicate, missed and overlapping occurrences, and what a saved key does not do. JSON cases."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import psycopg
from autobots.adapters import tool_registry
from autobots.application.experts import create_expert
from autobots.application.routines import (
    RoutineRefused,
    add_routine_version,
    create_routine,
    evaluate_routines,
    set_enabled,
)
from autobots.application.runs import apply_command
from autobots.application.workflows import create_workflow, publish_version, rename_workflow
from autobots.contracts.experts import ExpertConfig
from autobots.contracts.routines import RoutineConfig, RoutineTarget
from autobots.contracts.workflows import WorkflowGraph
from autobots.domain.runs import RunCommand

URL = os.environ['AUTOBOTS_DATABASE_URL']
WORKSPACE, OTHER = UUID(sys.argv[1]), UUID(sys.argv[2])
ACTOR = uuid4()
START = datetime(2026, 11, 5, 12, 0, tzinfo=UTC)
cases = []
asked: list[UUID] = []


def check(name: str, expected: str, observed: object, passed: bool) -> None:
    cases.append({'id': name, 'expected': expected, 'observed': str(observed), 'passed': bool(passed)})


async def ready(workspace: UUID) -> str:
    asked.append(workspace)
    return 'ready'


async def no_key(_: UUID) -> str:
    return 'credentials_required'


async def main() -> None:
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        async def value(sql: str, *values: object) -> Any:
            return (await (await db.execute(sql, values)).fetchone())[0]

        async def history(routine: UUID) -> list[str]:
            rows = await (await db.execute('select status from public.routine_occurrences where routine_id = %s order by occurrence_time', (routine,))).fetchall()
            return [row[0] for row in rows]

        async def clear_active() -> None:
            await db.execute("update public.routines set enabled = false where enabled")

        # A saved key alone starts nothing.
        await clear_active()
        started = await evaluate_routines(db, ready, START, catalog=tool_registry.catalog())
        check('with no enabled routine, nothing starts and no key is even looked at', '0, not asked', (started, asked), started == 0 and asked == [])

        expert = await create_expert(db, workspace_id=WORKSPACE, actor_id=ACTOR, idempotency_key='r-e', name='Routine worker', config=ExpertConfig(tools=['calculate', 'save_artifact'], instructions='Be brief.'), catalog=tool_registry.catalog())

        def config(goal: str = 'Summarize the day', **options: Any) -> RoutineConfig:
            return RoutineConfig(target=RoutineTarget(kind='expert', id=expert.id, version=1), trigger={'kind': 'interval', 'minutes': 60}, goal=goal, **options)

        async def routine(name: str, **options: Any) -> Any:
            await clear_active()
            return await create_routine(db, workspace_id=WORKSPACE, actor_id=ACTOR, idempotency_key=f'r-{name}', name=name, config=config(**options), budget_cap=None, now=START)

        # One due occurrence, from concurrent workers.
        made = await routine('Hourly')

        async def worker() -> int:
            async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as other:
                return await evaluate_routines(other, ready, START + timedelta(hours=1), catalog=tool_registry.catalog())

        results = await asyncio.gather(*(worker() for _ in range(6)))
        rows = await history(made.id)
        check('six concurrent evaluations admit one occurrence', '1 admitted', (sum(results), rows), sum(results) == 1 and rows == ['admitted'])
        again = await evaluate_routines(db, ready, START + timedelta(hours=1), catalog=tool_registry.catalog())
        check('evaluating the same time again adds nothing', '0, 1 row', (again, await history(made.id)), again == 0 and await history(made.id) == ['admitted'])
        run = await value('select run_id from public.routine_occurrences where routine_id = %s', made.id)
        spec = await value('select spec from app_private.goal_specs where run_id = %s', run)
        check('the run takes the routine\'s goal and its Expert\'s frozen scope', 'calculate and save only', sorted(spec['allowed_tools']), spec['objective'] == 'Summarize the day' and 'read_run_file' not in spec['allowed_tools'] and 'save_artifact' in spec['allowed_tools'])

        # Overlap: the first run is still active.
        due = await evaluate_routines(db, ready, START + timedelta(hours=2), catalog=tool_registry.catalog())
        check('with a run still active, the next occurrence is skipped, and says so', '0 admitted, skipped_overlap', (due, await history(made.id)), due == 0 and await history(made.id) == ['admitted', 'skipped_overlap'])
        version = await value('select version from public.runs where id = %s', run)
        await apply_command(db, workspace_id=WORKSPACE, run_id=run, command=RunCommand.CANCEL, expected_version=version)
        due = await evaluate_routines(db, ready, START + timedelta(hours=3), catalog=tool_registry.catalog())
        check('once it finishes, the next one runs', '1 admitted', (due, (await history(made.id))[-1]), due == 1 and (await history(made.id))[-1] == 'admitted')

        # Missed work: only the latest catches up, and the rest are visible.
        await db.execute("update public.runs r set status = 'cancelled' from public.routine_occurrences o where o.run_id = r.id and o.routine_id = %s", (made.id,))
        due = await evaluate_routines(db, ready, START + timedelta(hours=8), catalog=tool_registry.catalog())
        rows = await history(made.id)
        check('after the Mac wakes, one catch-up runs and the rest show as missed', '4 missed, then 1 admitted', rows[-5:], due == 1 and rows[-5:] == ['missed', 'missed', 'missed', 'missed', 'admitted'])
        reason = await value("select reason from public.routine_occurrences where routine_id = %s and status = 'missed' limit 1", made.id)
        check('with a reason', 'host_away', reason, reason == 'host_away')

        # An edit reaches only future occurrences.
        await db.execute("update public.runs r set status = 'cancelled' from public.routine_occurrences o where o.run_id = r.id and o.routine_id = %s", (made.id,))
        latest_run = await value("select run_id from public.routine_occurrences where routine_id = %s and status = 'admitted' order by occurrence_time desc limit 1", made.id)
        await add_routine_version(db, workspace_id=WORKSPACE, actor_id=ACTOR, routine_id=made.id, idempotency_key='v2', expected_version=1, config=config('A different goal', tools=['calculate'], limit_micro_usd=500), budget_cap=None)
        unchanged = await value('select spec from app_private.goal_specs where run_id = %s', latest_run)
        check('an edit does not change a run already admitted', 'the old goal and tools', unchanged['objective'], unchanged['objective'] == 'Summarize the day' and 'save_artifact' in unchanged['allowed_tools'])
        await evaluate_routines(db, ready, START + timedelta(hours=9), catalog=tool_registry.catalog())
        newest = await (await db.execute("select routine_version, run_id from public.routine_occurrences where routine_id = %s order by occurrence_time desc limit 1", (made.id,))).fetchone()
        spec = await value('select spec from app_private.goal_specs where run_id = %s', newest[1])
        limit = await value('select limit_micro_usd from public.runs where id = %s', newest[1])
        check('the next occurrence uses the new version, with its narrower scope and budget', 'version 2, no save, 500', (newest[0], 'save_artifact' in spec['allowed_tools'], limit), newest[0] == 2 and 'save_artifact' not in spec['allowed_tools'] and limit == 500)

        # An edit can't widen what its target has.
        for label, change, code in (
                ('a tool the Expert lacks', lambda: config(tools=['read_run_file']), 'routine_scope_widened'),
                ('a shell', lambda: config(tools=['execute']), 'routine_scope_widened'),
                ('a timezone that doesn\'t exist', lambda: config(timezone='Mars/Olympus'), 'timezone_unknown'),
                ('no goal', lambda: config(goal='  '), 'routine_goal_required')):
            try:
                await create_routine(db, workspace_id=WORKSPACE, actor_id=ACTOR, idempotency_key=str(uuid4()), name=f'Bad {code}', config=change(), budget_cap=None, now=START)
                check(f'{label} is refused', code, 'created', False)
            except RoutineRefused as error:
                check(f'{label} is refused', code, error.code, error.code == code)
        try:
            await create_routine(db, workspace_id=OTHER, actor_id=ACTOR, idempotency_key=str(uuid4()), name='Foreign', config=config(), budget_cap=None, now=START)
            check('another workspace\'s Expert is refused', 'routine_target_not_found', 'created', False)
        except RoutineRefused as error:
            check('another workspace\'s Expert is refused', 'routine_target_not_found', error.code, error.code == 'routine_target_not_found')
        try:
            await add_routine_version(db, workspace_id=WORKSPACE, actor_id=ACTOR, routine_id=made.id, idempotency_key='stale', expected_version=1, config=config(), budget_cap=None)
            check('a stale edit conflicts', 'routine_version_conflict', 'saved', False)
        except RoutineRefused as error:
            check('a stale edit conflicts', 'routine_version_conflict', error.code, error.code == 'routine_version_conflict')

        # With no usable key, nothing is admitted, and that shows.
        blocked = await routine('No key')
        due = await evaluate_routines(db, no_key, START + timedelta(hours=1), catalog=tool_registry.catalog())
        reason = await value('select reason from public.routine_occurrences where routine_id = %s', blocked.id)
        check('with no usable key, an occurrence is blocked rather than started', '0, credentials_required', (due, await history(blocked.id), reason), due == 0 and await history(blocked.id) == ['blocked'] and reason == 'credentials_required')

        # A disabled routine stays quiet, and doesn't catch up when turned back on.
        quiet = await routine('Quiet')
        await set_enabled(db, WORKSPACE, quiet.id, enabled=False)
        due = await evaluate_routines(db, ready, START + timedelta(hours=5), catalog=tool_registry.catalog())
        check('a disabled routine admits nothing', '0, no rows', (due, await history(quiet.id)), due == 0 and await history(quiet.id) == [])
        await set_enabled(db, WORKSPACE, quiet.id, enabled=True)
        moved = await value('select evaluated_until from public.routines where id = %s', quiet.id)
        check('turning it on starts counting from then', 'later than its start', moved > START, moved > START)

        # A workflow target, which needs no key when it has no agent step.
        flow = await create_workflow(db, workspace_id=WORKSPACE, actor_id=ACTOR, idempotency_key='r-w', name='Routine flow')
        graph = WorkflowGraph.model_validate({
            'nodes': [{'id': 'in', 'block': 'input', 'version': 1, 'config': {'type': 'string'}}, {'id': 'out', 'block': 'output', 'version': 1}],
            'links': [{'source': 'in', 'source_port': 'value', 'target': 'out', 'target_port': 'value'}]})
        await publish_version(db, workspace_id=WORKSPACE, actor_id=ACTOR, workflow_id=flow.id, idempotency_key='r-wp', expected_version=0, graph=graph, source='user')
        await clear_active()
        scheduled = await create_routine(db, workspace_id=WORKSPACE, actor_id=ACTOR, idempotency_key='r-flow', name='Flow routine', config=RoutineConfig(target=RoutineTarget(kind='workflow', id=flow.id, version=1), trigger={'kind': 'interval', 'minutes': 30}, inputs={'in': 'hello'}), budget_cap=None, now=START)
        due = await evaluate_routines(db, no_key, START + timedelta(minutes=30), catalog=tool_registry.catalog())
        bound = await value('select workflow_version from public.workflow_executions e join public.routine_occurrences o on o.run_id = e.run_id where o.routine_id = %s', scheduled.id)
        check('a workflow routine binds its exact version, and needs no key without an agent step', '1, version 1', (due, bound), due == 1 and bound == 1)

        # US-19.1 (Decision 0037 N3): a routine binds its workflow by id and version, so a rename leaves what it binds alone.
        routine_before = await value('select jsonb_build_object(\'latest\', r.latest_version, \'config\', v.config) from public.routines r '
                                     'join public.routine_versions v on v.routine_id = r.id and v.version = r.latest_version where r.id = %s', scheduled.id)
        first_hash = await value('select e.graph_hash from public.workflow_executions e join public.routine_occurrences o on o.run_id = e.run_id '
                                 'where o.routine_id = %s', scheduled.id)
        first_run = await value('select run_id from public.routine_occurrences where routine_id = %s', scheduled.id)
        await apply_command(db, workspace_id=WORKSPACE, run_id=first_run, command=RunCommand.CANCEL,
                            expected_version=await value('select version from public.runs where id = %s', first_run))
        await rename_workflow(db, WORKSPACE, flow.id, 'Routine flow, retitled')
        due = await evaluate_routines(db, no_key, START + timedelta(minutes=60), catalog=tool_registry.catalog())
        bound = await value('select jsonb_build_object(\'version\', e.workflow_version, \'hash\', e.graph_hash, \'workflow\', e.workflow_id) '
                            'from public.workflow_executions e join public.routine_occurrences o on o.run_id = e.run_id '
                            'where o.routine_id = %s and o.run_id <> %s', scheduled.id, first_run)
        routine_after = await value('select jsonb_build_object(\'latest\', r.latest_version, \'config\', v.config) from public.routines r '
                                    'join public.routine_versions v on v.routine_id = r.id and v.version = r.latest_version where r.id = %s', scheduled.id)
        check("after the workflow is renamed, the routine's next occurrence binds the same version and hash, and the routine is unchanged",
              '1 admitted, version 1, the same hash and workflow, the same routine version and configuration', (due, bound, routine_after == routine_before),
              due == 1 and bound == {'version': 1, 'hash': first_hash, 'workflow': str(flow.id)} and routine_after == routine_before)

        # A daily routine in its own timezone.
        await clear_active()
        daily = await create_routine(db, workspace_id=WORKSPACE, actor_id=ACTOR, idempotency_key='r-day', name='Daily', config=RoutineConfig(target=RoutineTarget(kind='expert', id=expert.id, version=1), trigger={'kind': 'daily', 'time': '09:00'}, timezone='America/Costa_Rica', goal='Morning'), budget_cap=None, now=datetime(2026, 11, 5, 14, 0, tzinfo=UTC))
        await evaluate_routines(db, ready, datetime(2026, 11, 5, 15, 30, tzinfo=UTC), catalog=tool_registry.catalog())
        when = await value('select occurrence_time from public.routine_occurrences where routine_id = %s', daily.id)
        check('a daily occurrence is stored as a UTC instant for its local time', '15:00 UTC for 09:00 in Costa Rica', when.astimezone(UTC).isoformat(), when.astimezone(UTC) == datetime(2026, 11, 5, 15, 0, tzinfo=UTC))
        try:
            await db.execute("update public.routine_versions set config = '{}' where routine_id = %s", (made.id,))
            check('a saved version can\'t be rewritten', 'permission denied', 'updated', False)
        except psycopg.errors.InsufficientPrivilege:
            check('a saved version can\'t be rewritten', 'permission denied', 'permission denied', True)
    print(json.dumps({'cases': cases}))


try:
    asyncio.run(main())
except Exception:
    print(json.dumps({'cases': cases}))
    raise
