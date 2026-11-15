"""US-15.17: plan task times on the worker's fenced path, and the runs the side panel spec opens.

A run bound to an Expert has three tasks. Its first worker serves the first task, then loses its lease
to a second worker. The stale worker's start and finish are refused, and the current worker's are
stored in database time. Three of its uses are admitted as metered on the real path, and a second run
is cancelled so the panel can show a terminal run. JSON cases, and the values the browser suite needs.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import psycopg
from autobots.adapters import tool_registry
from autobots.adapters.tool_registry import build_registry
from autobots.application.experts import create_expert
from autobots.application.run_projection import read_workspace
from autobots.application.run_usage import RootLimits
from autobots.application.runs import CommandReceipt, admit_run, apply_command
from autobots.application.tool_definitions import ToolRuntime, ToolScope
from autobots.application.tool_gateway import ToolGateway
from autobots.application.tool_uses import admit_metered
from autobots.application.worker_leases import claim_run
from autobots.contracts.experts import ExpertConfig
from autobots.domain.models import resolve_role_policy
from autobots.domain.runs import RunCommand
from autobots.domain.tools import PLAN_TOOLS

URL = os.environ['AUTOBOTS_DATABASE_URL']
WORKSPACE = UUID(sys.argv[1])
GRANTS = {**PLAN_TOOLS, 'calculate': 1, 'save_artifact': 1}
TASKS = [
    {'id': 'gather', 'title': 'Gather the figures', 'depends_on': [], 'criteria': ['c1'], 'tools': ['calculate', 'save_artifact'], 'expected_evidence': 'notes'},
    {'id': 'write', 'title': 'Write the summary', 'depends_on': ['gather'], 'criteria': ['c1'], 'tools': ['save_artifact'], 'expected_evidence': 'a draft'},
    {'id': 'review', 'title': 'Check the totals', 'depends_on': ['write'], 'criteria': ['c1'], 'tools': ['calculate'], 'expected_evidence': 'a sum'},
]
cases: list[dict[str, Any]] = []


def check(name: str, expected: str, observed: object, passed: bool) -> None:
    cases.append({'id': name, 'expected': expected, 'observed': str(observed), 'passed': bool(passed)})


async def main() -> None:
    # Every tool, the planning tools among them, as a pass registers them (adapters/tool_registry.py).
    gateway = ToolGateway(build_registry(ToolRuntime(RootLimits())))
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        async def one(sql: str, *values: object) -> Any:
            return await (await db.execute(sql, values)).fetchone()

        async def times(run: UUID) -> dict[str, tuple[Any, Any]]:
            rows = await (await db.execute('select task_id, started_at, finished_at from app_private.plan_task_times where run_id = %s', (run,))).fetchall()
            return {row[0]: (row[1], row[2]) for row in rows}

        actor = uuid4()
        expert = await create_expert(db, workspace_id=WORKSPACE, actor_id=actor, idempotency_key=str(uuid4()), name='Figures analyst',
                                     config=ExpertConfig(tools=['calculate', 'save_artifact']), catalog=tool_registry.catalog())
        binding = SimpleNamespace(session_id=None, expert_id=expert.id, version=expert.latest_version, instructions='', tools=GRANTS)
        admitted = await admit_run(db, workspace_id=WORKSPACE, actor_id=actor, idempotency_key=str(uuid4()), goal_text='Summarize the quarter figures',
                                   limit_micro_usd=1_000_000, policy=resolve_role_policy(), binding=binding,
                                   acceptance_criteria=('The summary states the quarter total',))
        run = admitted.run_id
        first = await claim_run(db, run, worker_id='task-timing-first', lease_seconds=600)
        assert first is not None
        await db.execute('insert into app_private.plan_versions (run_id, version, tasks) values (%s, 1, %s)', (run, json.dumps(TASKS)))
        stale_scope = ToolScope(WORKSPACE, run, first.generation, GRANTS, ('inputs', 'outputs'))

        before = (await one('select clock_timestamp()'))[0]
        summed = await gateway.execute(db, stale_scope, 'calculate', {'operation': 'sum', 'values': [4, 5]})
        after = (await one('select clock_timestamp()'))[0]
        started = (await times(run)).get('gather', (None, None))[0]
        check('the first use that serves a task starts it, in database time', 'gather started between the database clock before and after',
              (summed.outcome.value, started), summed.outcome.value == 'succeeded' and started is not None and before <= started <= after)

        # The first worker's lease runs out and a second worker claims the run.
        await db.execute('update app_private.run_jobs set lease_expires_at = clock_timestamp() where run_id = %s', (run,))
        second = await claim_run(db, run, worker_id='task-timing-second', lease_seconds=1800)
        assert second is not None and second.generation > first.generation
        scope = ToolScope(WORKSPACE, run, second.generation, GRANTS, ('inputs', 'outputs'))

        saved = await gateway.execute(db, scope, 'save_artifact', {'path': 'outputs/gather.md', 'content': 'Q3: 9'})
        uses_before = (await one('select count(*) from app_private.tool_uses where run_id = %s', run))[0]
        stale_start = await gateway.execute(db, stale_scope, 'save_artifact', {'path': 'outputs/stale.md', 'content': 'late'})
        stale_finish = await gateway.execute(db, stale_scope, 'complete_task', {'task_id': 'gather', 'summary': 'stale',
                                                                              'evidence': [{'kind': 'artifact', 'reference': 'outputs/gather.md'}]})
        recorded = await times(run)
        uses_after = (await one('select count(*) from app_private.tool_uses where run_id = %s', run))[0]
        evidence = (await one('select count(*) from app_private.plan_evidence where run_id = %s', run))[0]
        check("the stale worker's start and finish are refused, and write nothing", 'refused, no use, no finish, no evidence',
              (stale_start.outcome.value, stale_start.code, stale_finish.outcome.value, stale_finish.code, uses_after - uses_before, recorded['gather'][1], evidence),
              stale_start.outcome.value != 'succeeded' and stale_finish.outcome.value != 'succeeded' and uses_after == uses_before
              and recorded['gather'][1] is None and evidence == 0 and set(recorded) == {'gather'})

        before = (await one('select clock_timestamp()'))[0]
        finished = await gateway.execute(db, scope, 'complete_task', {'task_id': 'gather', 'summary': 'Gathered the figures.',
                                                                      'evidence': [{'kind': 'artifact', 'reference': 'outputs/gather.md'}]})
        drafted = await gateway.execute(db, scope, 'save_artifact', {'path': 'outputs/draft.md', 'content': 'Q3 total: 9'})
        after = (await one('select clock_timestamp()'))[0]
        recorded = await times(run)
        gather_start, gather_finish = recorded['gather']
        write_start = recorded.get('write', (None, None))[0]
        check("the current worker's finish and next start are stored in database time", 'gather finished and write started between the clock readings',
              (saved.outcome.value, finished.outcome.value, drafted.outcome.value, gather_finish, write_start),
              saved.outcome.value == finished.outcome.value == drafted.outcome.value == 'succeeded'
              and gather_finish is not None and before <= gather_finish <= after and write_start is not None and before <= write_start <= after
              and gather_start <= gather_finish and 'review' not in recorded)

        repeat = await gateway.execute(db, scope, 'complete_task', {'task_id': 'gather', 'summary': 'Again.',
                                                                    'evidence': [{'kind': 'artifact', 'reference': 'outputs/gather.md'}]})
        check('a repeated finish keeps the first one', str(gather_finish), (repeat.outcome.value, (await times(run))['gather'][1]),
              (await times(run))['gather'][1] == gather_finish)

        # Three uses admitted as metered on the real path, counted for the run's root tree.
        use_ids = [row[0] for row in await (await db.execute('select id from app_private.tool_uses where run_id = %s order by id limit 3', (run,))).fetchall()]
        admitted_metered = [await admit_metered(db, scope, use_id) for use_id in use_ids]
        view = await read_workspace(db, WORKSPACE, run)
        plan = view.plan
        assert plan is not None
        markers = {task.id: task.marker for task in plan.tasks}
        tools = {task.id: task.tools for task in plan.tasks}
        walls = {task.id: task.wall_seconds for task in plan.tasks}
        check('the current task is the earliest open task that has started', 'gather done, write current, review to do',
              (markers, plan.current_task_id), markers == {'gather': 'done', 'write': 'current', 'review': 'to_do'} and plan.current_task_id == 'write')
        check("each task lists the tools its uses served, planning tools excepted, and its wall time", "gather: calculate, save_artifact; write: save_artifact; review: none and no time",
              (tools, walls), tools == {'gather': ['calculate', 'save_artifact'], 'write': ['save_artifact'], 'review': []}
              and walls['gather'] is not None and walls['write'] is not None and walls['review'] is None)
        check('three metered calls are counted for the root tree, of 20', '3 of 20',
              (admitted_metered, view.metered_tool_calls, view.metered_tool_call_limit),
              admitted_metered == [True, True, True] and view.metered_tool_calls == 3 and view.metered_tool_call_limit == 20)
        check('the panel run names its Expert', 'Figures analyst', view.expert.name if view.expert else None,
              view.expert is not None and view.expert.name == 'Figures analyst')

        # A terminal run, cancelled through its canonical transition, for the panel with no controls.
        ended = await admit_run(db, workspace_id=WORKSPACE, actor_id=actor, idempotency_key=str(uuid4()), goal_text='An ended run for the panel',
                                limit_micro_usd=1_000_000, policy=resolve_role_policy())
        cancelled = await apply_command(db, workspace_id=WORKSPACE, run_id=ended.run_id, command=RunCommand.CANCEL,
                                        expected_version=ended.version, receipt=CommandReceipt(actor, str(uuid4())))
        check('the terminal panel run is cancelled', 'cancelled', cancelled.status, cancelled.status == 'cancelled')
    print(json.dumps({'cases': cases, 'browser_env': {
        'AUTOBOTS_TEST_PANEL_RUN': str(run), 'AUTOBOTS_TEST_PANEL_GENERATION': str(second.generation),
        'AUTOBOTS_TEST_PANEL_TERMINAL': str(ended.run_id), 'AUTOBOTS_TEST_PANEL_WORKSPACE': str(WORKSPACE),
        'AUTOBOTS_TEST_PANEL_HELPER': str(Path(__file__).parent / 'task_timing_live.py')}}))


asyncio.run(main())
