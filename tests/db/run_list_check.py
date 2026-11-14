"""US-15.4 on a real database: the run list's facts, status groups, filters and keyset paging. JSON cases.

It arranges its own two workspaces, so earlier checks' runs don't change its counts.
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import psycopg
from autobots.application.experts import create_expert, create_session
from autobots.application.run_projection import InvalidCursor, read_run_list
from autobots.contracts.experts import ExpertConfig, SessionExpert
from psycopg.types.json import Jsonb

URL = os.environ['AUTOBOTS_DATABASE_URL']
cases: list[dict[str, Any]] = []
BASE = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)


def check(name: str, expected: str, observed: object, passed: bool) -> None:
    cases.append({'id': name, 'expected': expected, 'observed': str(observed)[:700], 'passed': bool(passed)})


async def main() -> None:
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        workspace, other = uuid4(), uuid4()
        for identifier, name in ((workspace, 'Run list'), (other, 'Run list other')):
            await db.execute('insert into public.workspaces (id, name) values (%s, %s)', (identifier, name))
        tag = uuid4().hex[:6]
        expert = await create_expert(db, workspace_id=workspace, actor_id=uuid4(), idempotency_key=str(uuid4()),
                                     name=f'Writer {tag}', config=ExpertConfig(tools=['calculate']))
        try:
            session = await create_session(db, workspace_id=workspace, actor_id=uuid4(), idempotency_key=str(uuid4()),
                                           kind='coordinator', experts=[SessionExpert(expert_id=expert.id)])
        except Exception:  # noqa: BLE001 - a coordinator may need more Experts; a second one is added then.
            second = await create_expert(db, workspace_id=workspace, actor_id=uuid4(), idempotency_key=str(uuid4()),
                                         name=f'Reader {tag}', config=ExpertConfig(tools=['calculate']))
            session = await create_session(db, workspace_id=workspace, actor_id=uuid4(), idempotency_key=str(uuid4()),
                                           kind='coordinator', experts=[SessionExpert(expert_id=expert.id),
                                                                        SessionExpert(expert_id=second.id)])
        bindings = {'executor': 'openrouter_terra', 'researcher': 'openrouter_sol'}
        made: dict[str, UUID] = {}

        async def run(key: str, status: str, minutes: int, *, goal: str, expert_id: UUID | None = None,
                      session_id: UUID | None = None, owner: UUID | None = None, terra_only: bool = False) -> UUID:
            identifier = uuid4()
            policy = {'bindings': {'executor': 'openrouter_terra'} if terra_only else bindings}
            await db.execute(
                'insert into public.runs (id, workspace_id, status, goal_summary, limit_micro_usd, policy_snapshot, '
                'expert_id, session_id, created_at, updated_at) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)',
                (identifier, owner or workspace, status, goal, 1_000_000, Jsonb(policy), expert_id, session_id,
                 BASE + timedelta(minutes=minutes), BASE + timedelta(minutes=minutes, seconds=30)))
            made[key] = identifier
            return identifier

        async def invocation(run_id: UUID, *, status: str, reserved: int, charged: int | None,
                             failure: str | None = None) -> None:
            await db.execute(
                'insert into app_private.model_invocations (id, workspace_id, root_run_id, run_id, role, profile, wire_id, '
                'attempt, spend_day, reserved_micro_usd, charged_micro_usd, status, failure_class) '
                "values (%s, %s, %s, %s, 'executor', 'openrouter_terra', 'openai/gpt-6.1-terra', 1, current_date, "
                '%s, %s, %s, %s)',
                (uuid4(), workspace, run_id, run_id, reserved, charged, status, failure))

        goal = await run('goal', 'running', 10, goal=f'Compare rates {tag}')
        tasks = [{'id': f't{index}', 'title': f'Task {index}', 'criteria': []} for index in range(1, 6)]
        await db.execute('insert into app_private.plan_versions (run_id, version, tasks) values (%s, 1, %s)', (goal, Jsonb(tasks)))
        for task in ('t1', 't2'):
            await db.execute("insert into app_private.plan_evidence (run_id, task_id, evidence, summary) values (%s, %s, '[]', 'done')",
                             (goal, task))
        await invocation(goal, status='reserved', reserved=50_000, charged=None)
        reported = await run('expert', 'succeeded', 9, goal='Write the notes', expert_id=expert.id, terra_only=True)
        await invocation(reported, status='succeeded', reserved=0, charged=70_000)
        await run('session', 'waiting_input', 8, goal='Ask the team', expert_id=expert.id, session_id=session.id)
        flow = uuid4()
        await db.execute('insert into public.workflows (id, workspace_id, name, latest_version) values (%s, %s, %s, 1)',
                         (flow, workspace, f'Weekly {tag}'))
        await db.execute("insert into public.workflow_versions (workflow_id, version, graph, graph_hash, block_versions, source, "
                         "created_by) values (%s, 1, '{}', 'hash', '{}', 'user', %s)", (flow, uuid4()))
        flow_run = await run('workflow', 'queued', 7, goal='Weekly brief')
        await db.execute("insert into public.workflow_executions (id, workspace_id, workflow_id, workflow_version, graph_hash, "
                         "block_versions, inputs, created_by, run_id) values (%s, %s, %s, 1, 'hash', '{}', '{}', %s, %s)",
                         (uuid4(), workspace, flow, uuid4(), flow_run))
        failed = await run('failed', 'failed', 6, goal='Map the docs')
        await db.execute("insert into app_private.run_usage (run_id, stop_reason) values (%s, 'tool_budget_exceeded')", (failed,))
        await invocation(failed, status='uncertain', reserved=30_000, charged=None, failure='charge_not_reported')
        for index, status in enumerate(('paused', 'waiting_approval', 'verifying', 'cancelling', 'cancelled'), start=1):
            await run(status, status, 5 - index, goal=f'State {status}')
        await run('outside', 'running', 11, goal=f'Compare rates {tag}', owner=other)

        everything = await read_run_list(db, workspace)
        rows = {row.id: row for row in everything.runs}
        check("only this workspace's runs are listed", '10 rows, none from the other workspace',
              (len(rows), made['outside'] in rows), len(rows) == 10 and made['outside'] not in rows)
        counts = everything.counts
        check('each status group is counted on the server', 'all 10, active 5, needs you 2, finished 3',
              counts, (counts.all, counts.active, counts.needs_you, counts.finished) == (10, 5, 2, 3))
        active = await read_run_list(db, workspace, group='active')
        check('Active holds queued, running, verifying, paused and cancelling', 'those five states',
              sorted(row.status for row in active.runs),
              sorted(row.status for row in active.runs) == ['cancelling', 'paused', 'queued', 'running', 'verifying'])
        needs = await read_run_list(db, workspace, group='needs_you')
        check('Needs you holds waiting_approval and waiting_input', 'those two states',
              sorted(row.status for row in needs.runs), sorted(row.status for row in needs.runs) == ['waiting_approval', 'waiting_input'])
        finished = await read_run_list(db, workspace, group='finished')
        check('Finished holds succeeded, failed and cancelled', 'those three, with total 3',
              (sorted(row.status for row in finished.runs), finished.total),
              sorted(row.status for row in finished.runs) == ['cancelled', 'failed', 'succeeded'] and finished.total == 3)

        g = rows[goal]
        check('a goal run carries progress, frozen profiles and an estimate', 'goal, 2 of 5, Sol and Terra, 50000 reserved',
              (g.label_kind, g.label, g.tasks_complete, g.tasks_total, g.profiles, g.charged_micro_usd, g.reserved_micro_usd, g.unreported),
              (g.label_kind, g.label, g.tasks_complete, g.tasks_total) == ('goal', None, 2, 5)
              and g.profiles == ['openrouter_sol', 'openrouter_terra'] and g.reserved_micro_usd == 50_000 and not g.unreported)
        e = rows[reported]
        check('an Expert run is labelled and fully reported', f'expert, Writer {tag}, 70000 charged, nothing held',
              (e.label_kind, e.label, e.charged_micro_usd, e.reserved_micro_usd, e.unreported, e.profiles),
              (e.label_kind, e.label) == ('expert', f'Writer {tag}') and e.charged_micro_usd == 70_000
              and e.reserved_micro_usd == 0 and not e.unreported and e.profiles == ['openrouter_terra'])
        s = rows[made['session']]
        check('a coordinator session run is labelled', 'session, Coordinator session', (s.label_kind, s.label),
              (s.label_kind, s.label) == ('session', 'Coordinator session'))
        w = rows[flow_run]
        check('a workflow run is labelled with its version', f'workflow, Weekly {tag}, version 1', (w.label_kind, w.label),
              (w.label_kind, w.label) == ('workflow', f'Weekly {tag}, version 1'))
        f = rows[failed]
        check('a failed run carries its stop reason and an unreported charge', 'tool_budget_exceeded, unreported',
              (f.stop_reason, f.unreported, f.reserved_micro_usd), f.stop_reason == 'tool_budget_exceeded' and f.unreported)
        check('created and updated times are returned', 'updated after created', (g.created_at, g.updated_at),
              g.updated_at > g.created_at)

        by_goal = await read_run_list(db, workspace, query=f'compare rates {tag}')
        check('text matches a goal, case-insensitively, in this workspace only', 'the goal run only',
              [row.id == goal for row in by_goal.runs], [row.id for row in by_goal.runs] == [goal] and by_goal.total == 1)
        by_expert = await read_run_list(db, workspace, query=f'writer {tag}')
        check('text matches an Expert name', 'the Expert and session runs',
              len(by_expert.runs), {row.id for row in by_expert.runs} == {reported, made['session']})
        by_profile = await read_run_list(db, workspace, profile='openrouter_sol')
        check('a profile filter keeps runs that froze it', 'every run except the Terra-only one',
              len(by_profile.runs), reported not in {row.id for row in by_profile.runs} and by_profile.total == 9)
        literal = await read_run_list(db, workspace, query='%')
        check('a % in the text is a literal, not a wildcard', 'no rows', len(literal.runs), literal.runs == [])

        seen: list[UUID] = []
        page = await read_run_list(db, workspace, 3)
        first_page = True
        while True:
            seen.extend(row.id for row in page.runs)
            if first_page:
                # A run admitted while paging is newer than every cursor, so it never shifts a later page.
                await run('late', 'queued', 30, goal='Admitted while paging')
                first_page = False
            if page.next_cursor is None:
                break
            page = await read_run_list(db, workspace, 3, cursor=page.next_cursor)
        expected = [row.id for row in everything.runs]
        check('keyset pages repeat and skip nothing while a run is admitted', '10 rows in order, once each',
              (len(seen), len(set(seen))), seen == expected)
        filtered_pages = await read_run_list(db, workspace, 2, group='active')
        check('a filtered page reports its group total', 'total 5 for Active plus the admitted run',
              (filtered_pages.total, filtered_pages.has_more), filtered_pages.total == 6 and filtered_pages.has_more)
        try:
            await read_run_list(db, workspace, cursor='not-a-cursor')
            refused = 'accepted'
        except InvalidCursor:
            refused = 'invalid_cursor'
        check('a cursor the API did not issue is refused', 'invalid_cursor', refused, refused == 'invalid_cursor')
    print(json.dumps({'cases': cases}))


asyncio.run(main())
