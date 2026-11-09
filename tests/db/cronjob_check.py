"""US-14.19 and Decision 0026: the `cronjob` tool through the real gateway, approvals and routine
service, on a disposable database with no model. JSON cases."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import psycopg

from autobots.application.approvals import decide
from autobots.application.cronjob_tool import cronjob_tool
from autobots.application.experts import create_expert
from autobots.application.routines import create_routine, evaluate_routines, list_routines
from autobots.application.runs import admit_run
from autobots.application.tool_catalog import tool_catalog
from autobots.application.tool_gateway import ToolGateway, ToolRegistry, ToolScope
from autobots.application.tool_uses import list_tool_uses
from autobots.application.worker_leases import claim_next
from autobots.contracts.experts import ExpertConfig
from autobots.contracts.routines import RoutineConfig, RoutineTarget
from autobots.domain.models import resolve_role_policy
from autobots.domain.tools import PLAN_TOOLS

URL = os.environ['AUTOBOTS_DATABASE_URL']
WORKSPACE = UUID(sys.argv[1])
ACTOR = uuid4()
GOAL_MARK = 'FAKEGOALTEXT-7c41'
INPUT_MARK = 'FAKEINPUT-93ad'
cases: list[dict[str, Any]] = []
ready = {'code': 'ready'}


def check(name: str, expected: str, observed: object, passed: bool) -> None:
    cases.append({'id': name, 'expected': expected, 'observed': str(observed)[:700], 'passed': bool(passed)})


async def credential_check(_: Any, __: UUID) -> str:
    return ready['code']


def task(expert: UUID, minutes: int = 60, **extra: Any) -> dict[str, Any]:
    return {'target_kind': 'expert', 'target_id': str(expert), 'target_version': 1,
            'schedule': {'kind': 'interval', 'minutes': minutes}, 'goal': 'Summarize the week', **extra}


async def main() -> None:
    registry = ToolRegistry()
    registry.register(cronjob_tool(credential_check))
    gateway = ToolGateway(registry)
    tag = uuid4().hex[:6]
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        other = uuid4()
        await db.execute("insert into public.workspaces (id, name) values (%s, 'Cronjob other')", (other,))
        await db.execute("insert into public.workspace_members (workspace_id, user_id, role) values (%s, %s, 'owner') "
                         "on conflict do nothing", (WORKSPACE, ACTOR))
        target = (await create_expert(db, workspace_id=WORKSPACE, actor_id=ACTOR, idempotency_key=str(uuid4()),
                                      name=f'Weekly {tag}', config=ExpertConfig(tools=['calculate']))).id
        foreign = (await create_expert(db, workspace_id=other, actor_id=ACTOR, idempotency_key=str(uuid4()),
                                       name=f'Foreign {tag}', config=ExpertConfig(tools=['calculate']))).id
        manager = await create_expert(db, workspace_id=WORKSPACE, actor_id=ACTOR, idempotency_key=str(uuid4()),
                                      name=f'Scheduler {tag}', config=ExpertConfig(tools=['cronjob']))
        config = RoutineConfig(target=RoutineTarget(kind='expert', id=target, version=1),
                               trigger={'kind': 'interval', 'minutes': 60}, goal='Existing')
        mine = [await create_routine(db, workspace_id=WORKSPACE, actor_id=ACTOR, idempotency_key=str(uuid4()),
                                     name=f'Mine {tag} {n}', config=config) for n in (1, 2)]
        theirs_config = RoutineConfig(target=RoutineTarget(kind='expert', id=foreign, version=1),
                                      trigger={'kind': 'interval', 'minutes': 60}, goal='Theirs')
        await create_routine(db, workspace_id=other, actor_id=ACTOR, idempotency_key=str(uuid4()),
                             name=f'Theirs {tag}', config=theirs_config)

        async def start(expert: UUID | None = manager.id) -> ToolScope:
            await db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null "
                             "where status <> 'done'")
            binding = SimpleNamespace(session_id=None, expert_id=expert, version=1 if expert else None, instructions='',
                                      tools={**PLAN_TOOLS, 'cronjob': 1})
            run = (await admit_run(db, workspace_id=WORKSPACE, actor_id=ACTOR, started_by=ACTOR, idempotency_key=str(uuid4()),
                                   goal_text='Manage schedules', limit_micro_usd=1_000_000, policy=resolve_role_policy(),
                                   binding=binding)).run_id
            lease = await claim_next(db, worker_id='cronjob', lease_seconds=120)
            assert lease is not None and lease.run_id == run, lease
            return ToolScope(WORKSPACE, run, lease.generation, {'cronjob': 1})

        async def decision(scope: ToolScope, choice: str) -> ToolScope:
            row = await (await db.execute("select id, argument_hash from public.approval_requests where run_id = %s and status = 'pending' "
                                          "order by created_at desc limit 1", (scope.run_id,))).fetchone()
            await decide(db, workspace_id=WORKSPACE, actor_id=ACTOR, approval_id=row[0], idempotency_key=str(uuid4()),
                         decision=choice, argument_hash=row[1])
            await db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null "
                             "where run_id <> %s and status <> 'done'", (scope.run_id,))
            lease = await claim_next(db, worker_id='cronjob', lease_seconds=120)
            assert lease is not None and lease.run_id == scope.run_id, lease
            return ToolScope(WORKSPACE, scope.run_id, lease.generation, scope.tools)

        async def approved(scope: ToolScope, arguments: dict[str, Any]) -> tuple[ToolScope, Any]:
            first = await gateway.execute(db, scope, 'cronjob', arguments)
            assert first.code == 'approval_pending', first
            scope = await decision(scope, 'approve')
            return scope, await gateway.execute(db, scope, 'cronjob', arguments)

        async def routines() -> dict[str, tuple[bool, int]]:
            return {item.name: (item.enabled, item.latest_version) for item in await list_routines(db, WORKSPACE)}

        # The catalog lists cronjob under Automation.
        automation = tool_catalog({}, group='automation').tools
        shape = [(t.tool_id, t.version, t.provider, t.operation_class, t.cost_class, t.network, t.approval, t.grantable_to) for t in automation]
        check('the catalog lists cronjob once under Automation, Expert-only, approval by_action', 'cronjob 1 autobots reversible_internal_write free_local no network by_action [expert]',
              shape, shape == [('cronjob', 1, 'autobots', 'reversible_internal_write', 'free_local', False, 'by_action', ['expert'])])

        # list runs without approval and stays in the run's workspace.
        scope = await start()
        listed = await gateway.execute(db, scope, 'cronjob', {'action': 'list'})
        names = sorted(item['name'] for item in (listed.output or {}).get('routines', []))
        approvals = (await (await db.execute('select count(*) from public.approval_requests where run_id = %s', (scope.run_id,))).fetchone())[0]
        check("list returns only this workspace's routines, with no approval", "this workspace's two, 0 approvals", (names, approvals),
              listed.outcome.value == 'succeeded' and names == sorted(item.name for item in mine) and approvals == 0)

        # Every other action waits for a person's approval, bound to its arguments.
        before = await routines()
        waiting = {}
        for arguments in ({'action': 'create', 'name': f'New {tag}', 'task': task(target)},
                          {'action': 'update', 'routine_id': str(mine[0].id), 'expected_version': 1, 'task': task(target, 30)},
                          {'action': 'pause', 'routine_id': str(mine[0].id)}, {'action': 'resume', 'routine_id': str(mine[0].id)},
                          {'action': 'run', 'routine_id': str(mine[0].id)}, {'action': 'remove', 'routine_id': str(mine[0].id)}):
            scope = await start()
            waiting[arguments['action']] = (await gateway.execute(db, scope, 'cronjob', arguments)).code
            row = await (await db.execute('select resource_target, arguments, policy_rule from public.approval_requests where run_id = %s',
                                          (scope.run_id,))).fetchone()
            waiting[arguments['action'] + ' shown'] = (row[0], 'schedule' in json.dumps(row[1]) or arguments['action'] not in ('create', 'update'), row[2])
        occurrences = (await (await db.execute('select count(*) from public.routine_occurrences where routine_id = %s', (mine[0].id,))).fetchone())[0]
        codes = {k: v for k, v in waiting.items() if not k.endswith('shown')}
        shown = {k: v for k, v in waiting.items() if k.endswith('shown')}
        check('each action but list waits for approval, naming the action and routine, with nothing changed yet',
              'approval_pending x6, target names action, schedule in arguments, action_marked; routines unchanged, 0 occurrences',
              (codes, shown, occurrences), set(codes.values()) == {'approval_pending'} and len(codes) == 6
              and all(target_ and target_.startswith('Routine ') and has_schedule and rule == 'action_marked' for target_, has_schedule, rule in shown.values())
              and await routines() == before and occurrences == 0)
        scope = await start()
        pause = {'action': 'pause', 'routine_id': str(mine[1].id)}
        await gateway.execute(db, scope, 'cronjob', pause)
        scope = await decision(scope, 'reject')
        rejected = (await gateway.execute(db, scope, 'cronjob', pause)).code
        scope2 = await start()
        await gateway.execute(db, scope2, 'cronjob', {'action': 'pause', 'routine_id': str(mine[1].id)})
        scope2 = await decision(scope2, 'approve')
        different = (await gateway.execute(db, scope2, 'cronjob', {'action': 'remove', 'routine_id': str(mine[1].id)})).code
        check('a rejected call changes nothing, and an approval never covers different arguments',
              'approval_rejected, unchanged; a different call waits again', (rejected, different, (await routines())[mine[1].name]),
              rejected == 'approval_rejected' and different == 'approval_pending' and (await routines())[mine[1].name] == (True, 1))

        # create and update follow the routine service's validation.
        refused = {}
        for label, arguments in (('foreign target', {'action': 'create', 'name': f'Bad1 {tag}', 'task': task(foreign)}),
                                 ('wider tools', {'action': 'create', 'name': f'Bad2 {tag}', 'task': task(target, tools=['tavily_search'])}),
                                 ('timezone', {'action': 'create', 'name': f'Bad3 {tag}', 'task': task(target, timezone='Mars/Olympus')}),
                                 ('stale', {'action': 'update', 'routine_id': str(mine[1].id), 'expected_version': 9, 'task': task(target)})):
            _, result = await approved(await start(), arguments)
            refused[label] = result.code
        _, created = await approved(await start(), {'action': 'create', 'name': f'Saved {tag}', 'task': task(target, goal=GOAL_MARK,
                                                                                                     inputs={'note': INPUT_MARK})})
        new_id = (created.output or {}).get('routine_id')
        creator = (await (await db.execute('select created_by from public.routine_versions where routine_id = %s', (new_id,))).fetchone())[0] if new_id else None
        _, updated = await approved(await start(), {'action': 'update', 'routine_id': new_id, 'expected_version': 1, 'task': task(target, 30, goal=GOAL_MARK)})
        saved = sorted(name for name in await routines() if name.startswith('Bad'))
        check("create and update keep the routine service's codes, and valid ones save with the run's starter as creator",
              'expert_not_found or routine_target_not_found, routine_scope_widened, timezone_unknown, routine_version_conflict; saved v1 then v2',
              (refused, saved, created.outcome.value, creator == ACTOR, (updated.output or {}).get('version')),
              refused['wider tools'] == 'routine_scope_widened' and refused['timezone'] == 'timezone_unknown'
              and refused['stale'] == 'routine_version_conflict' and refused['foreign target'] not in (None, 'approval_pending')
              and saved == [] and created.outcome.value == 'succeeded' and creator == ACTOR and (updated.output or {}).get('version') == 2)

        # pause and resume set enabled, and a paused routine refuses run.
        rid = str(mine[1].id)
        _, paused = await approved(await start(), {'action': 'pause', 'routine_id': rid})
        _, paused_run = await approved(await start(), {'action': 'run', 'routine_id': rid})
        after_pause = (await routines())[mine[1].name]
        _, resumed = await approved(await start(), {'action': 'resume', 'routine_id': rid})
        check('pause disables, run on a paused routine is refused, and resume enables',
              'paused, routine_paused, enabled false, then resumed', ((paused.output or {}).get('status'), paused_run.code, after_pause, (resumed.output or {}).get('status')),
              (paused.output or {}).get('status') == 'paused' and paused_run.code == 'routine_paused' and after_pause[0] is False
              and (resumed.output or {}).get('status') == 'resumed' and (await routines())[mine[1].name][0] is True)

        # run admits one occurrence now, by the scheduled path's rules.
        scope, first = await approved(await start(), {'action': 'run', 'routine_id': rid})
        out = first.output or {}
        admitted = (await (await db.execute("select count(*) from public.routine_occurrences where routine_id = %s and status = 'admitted'", (mine[1].id,))).fetchone())[0]
        _, overlap = await approved(await start(), {'action': 'run', 'routine_id': rid})
        await db.execute("update public.runs set status = 'cancelled' where id = %s", (out.get('run_id'),))
        ready['code'] = 'credentials_required'
        _, blocked = await approved(await start(), {'action': 'run', 'routine_id': rid})
        ready['code'] = 'ready'
        calls = (await (await db.execute('select count(*) from app_private.model_invocations where run_id = %s', (out.get('run_id'),))).fetchone())[0]
        check('run admits one occurrence now, is skipped while that run is active, and is blocked without a key',
              'admitted with run_id, 1 occurrence; skipped_overlap; blocked credentials_required; 0 model calls',
              (out.get('status'), bool(out.get('run_id')), admitted, (overlap.output or {}).get('status'), (blocked.output or {}).get('status'), (blocked.output or {}).get('reason'), calls),
              out.get('status') == 'admitted' and out.get('run_id') and admitted == 1 and (overlap.output or {}).get('status') == 'skipped_overlap'
              and (blocked.output or {}).get('status') == 'blocked' and (blocked.output or {}).get('reason') == 'credentials_required' and calls == 0)

        # remove marks a routine removed and keeps its history.
        _, removed = await approved(await start(), {'action': 'remove', 'routine_id': rid})
        row = await (await db.execute('select removed_at is not null, enabled from public.routines where id = %s', (mine[1].id,))).fetchone()
        scope = await start()
        listed_after = [item['name'] for item in ((await gateway.execute(db, scope, 'cronjob', {'action': 'list'})).output or {}).get('routines', [])]
        await db.execute("update public.routines set evaluated_until = clock_timestamp() - interval '3 hours' where id = %s", (mine[1].id,))
        await evaluate_routines(db, lambda _: credential_check(None, WORKSPACE))
        history = await (await db.execute('select (select count(*) from public.routine_versions where routine_id = %s), '
                                          '(select count(*) from public.routine_occurrences where routine_id = %s)', (mine[1].id, mine[1].id))).fetchone()
        _, gone = await approved(await start(), {'action': 'pause', 'routine_id': rid})
        _, reused = await approved(await start(), {'action': 'create', 'name': mine[1].name, 'task': task(target)})
        check('remove hides the routine, stops evaluation, keeps its history, refuses later actions and frees its name',
              'removed_at set, disabled, in neither list, history kept, routine_not_found, name reused',
              ((removed.output or {}).get('status'), row, mine[1].name in listed_after, mine[1].name in await routines(), history, gone.code, reused.outcome.value),
              (removed.output or {}).get('status') == 'removed' and row == (True, False) and mine[1].name not in listed_after
              and history[0] >= 1 and history[1] >= 2 and gone.code == 'routine_not_found' and reused.outcome.value == 'succeeded'
              and mine[1].name in await routines())

        # Granted only through an Expert.
        bare = await start(expert=None)
        denied = await gateway.execute(db, bare, 'cronjob', {'action': 'list'})
        none_requested = (await (await db.execute('select count(*) from public.approval_requests where run_id = %s', (bare.run_id,))).fetchone())[0]
        check('a run with no Expert behind it is refused before anything', 'expert_grant_required, 0 approvals',
              (denied.code, none_requested), denied.code == 'expert_grant_required' and none_requested == 0)

        # Only public fields reach the tool-use record.
        rows = await (await db.execute("select input_public, output_public from app_private.tool_uses where tool_id = 'cronjob' "
                                       "and run_id in (select id from public.runs where workspace_id = %s)", (WORKSPACE,))).fetchall()
        events = await (await db.execute("select payload::text from public.run_events where payload->>'type' like 'tool.use.%%' "
                                         "and run_id in (select id from public.runs where workspace_id = %s)", (WORKSPACE,))).fetchall()
        listing = await list_tool_uses(db, WORKSPACE, scope.run_id)
        texts = [json.dumps(r) for r in rows] + [e[0] for e in events] + [listing.model_dump_json() if listing else '']
        keys_in = set().union(*[set((r[0] or {}).keys()) for r in rows])
        keys_out = set().union(*[set((r[1] or {}).keys()) for r in rows])
        leaked = [mark for mark in (GOAL_MARK, INPUT_MARK) if any(mark in text for text in texts)]
        check('tool uses keep only action, routine_id and name in, and routine_id, status and run_id out',
              'input keys within {action, routine_id, name}; output within {routine_id, status, run_id}; no goal or input text',
              (sorted(keys_in), sorted(keys_out), leaked, len(rows)),
              keys_in <= {'action', 'routine_id', 'name'} and keys_out <= {'routine_id', 'status', 'run_id'} and leaked == [] and len(rows) > 10)
    print(json.dumps({'cases': cases}))


asyncio.run(main())
