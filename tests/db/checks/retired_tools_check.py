"""US-18.1 and Decision 0036 R2 to R6 on a real database: a retired tool in saved work and in runs in flight. JSON cases.

What was saved before inflation_rates was retired is arranged as that release saved it:
- **Expert versions:** stored rows naming the tool.
- **Runs:** admitted while the release's tool map still listed it, by recording that map as their contract.
- **A tool use:** recorded through a stand-in for the old tool, with its group and provider.

Each is reported as arranged. The model is scripted, and no request leaves this Mac. Published files go to an in-memory
store that keeps the real store's path rule.
"""
from __future__ import annotations

import asyncio
import json
import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

import httpx
import psycopg
from autobots.adapters import tool_registry
from autobots.adapters.market_data import market_tools
from autobots.adapters.object_storage import _scoped
from autobots.application import runs as run_admission
from autobots.application.experts import ExpertRefused, add_version, create_session, resolve_binding
from autobots.application.reconciliation import ResumeBlocked, require_resumable
from autobots.application.routines import create_routine, evaluate_routines
from autobots.application.run_lifecycle import LoopConfig
from autobots.application.runs import admit_run, apply_command
from autobots.application.tool_definitions import ToolRegistry, ToolScope
from autobots.application.tool_gateway import ToolGateway
from autobots.application.tool_uses import list_tool_uses
from autobots.application.worker_leases import claim_next
from autobots.application.workflow_executions import create_execution
from autobots.application.workflows import create_workflow, publish_version
from autobots.contracts.experts import ExpertConfig, SessionExpert
from autobots.contracts.routines import RoutineConfig, RoutineTarget
from autobots.contracts.workflows import WorkflowGraph
from autobots.domain.execution import current_contract
from autobots.domain.models import resolve_role_policy
from autobots.domain.runs import RunCommand
from autobots.operations.job_dispatch import process_next
from goal_loop_script import ROUTE, Script, calls, say

URL = os.environ['AUTOBOTS_DATABASE_URL']
RETIRED = 'inflation_rates'
SAVED = {'purpose': 'Saved before inflation_rates was retired.',
         'tools': ['market_history', RETIRED, 'save_artifact', 'publish_artifact']}
START = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
cases: list[dict[str, Any]] = []


def check(name: str, expected: str, observed: object, passed: bool) -> None:
    cases.append({'id': name, 'expected': expected, 'observed': str(observed)[:900], 'passed': bool(passed)})


class Store:
    """The run's private storage, in memory, with the real store's path rule."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def put(self, path: str, content: bytes, media_type: str) -> bool:
        _scoped(path)
        if path in self.objects:
            return False
        self.objects[path] = content
        return True

    async def get(self, path: str) -> bytes | None:
        return self.objects.get(path)

    async def remove(self, path: str) -> None:
        self.objects.pop(path, None)

    async def names(self, prefix: str) -> list[str]:
        return [name for name in self.objects if name.startswith(prefix)]

    async def ping(self) -> None:
        return None


class OldProvider(StrEnum):
    """The provider the retired tool named, as its release recorded it."""

    WORLD_BANK = 'world_bank'


def never() -> Any:
    raise AssertionError('a model was built for a run that must not continue')


def chart(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={'chart': {'result': [{'meta': {'currency': 'USD'}, 'timestamp': [1761955200],
                                                           'indicators': {'quote': [{'close': [100.0]}]}}], 'error': None}})


def codes(model: Script) -> list[str]:
    """The codes of the tool results the model was shown."""
    found = []
    for turn in model.seen:
        for message in turn:
            if message.type == 'tool' and str(message.content).startswith('{'):
                found.append(str(json.loads(message.content).get('code')))
    return found


def finishing(path: str) -> list[Any]:
    """A plan, a saved and published file, and the task done."""
    return [calls(('propose_plan', {'tasks': [{'id': 't', 'title': 'Note the rates', 'criteria': ['c1'], 'expected_evidence': 'a note'}]})),
            calls(('save_artifact', {'path': path, 'content': 'Rates noted.'})),
            calls(('publish_artifact', {'path': path, 'version': 1})),
            calls(('complete_task', {'task_id': 't', 'evidence': [{'kind': 'artifact', 'reference': path}], 'summary': 'noted'})),
            say('Noted.')]


async def main() -> None:
    store = Store()
    config = LoopConfig(route=ROUTE, object_store=store, sleep=lambda _: asyncio.sleep(0), tool_set=tool_registry.build_registry)
    catalog = tool_registry.catalog()
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        async def value(sql: str, *values: object) -> Any:
            return (await (await db.execute(sql, values)).fetchone())[0]

        async def quiet() -> None:
            await db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null "
                             "where status <> 'done'")

        async def granted(run: UUID) -> list[str]:
            return sorted((await value('select spec from app_private.goal_specs where run_id = %s', run))['allowed_tools'])

        async def stored(expert: UUID, version: int) -> Any:
            return await value('select config from public.expert_versions where expert_id = %s and version = %s', expert, version)

        space, owner = uuid4(), uuid4()
        await db.execute('insert into public.workspaces (id, name) values (%s, %s)', (space, 'Retired tools'))
        await db.execute("insert into public.workspace_members (workspace_id, user_id, role) values (%s, %s, 'owner')", (space, owner))

        async def saved_expert(name: str) -> UUID:
            """An Expert version as the release before US-18.1 saved it, naming inflation_rates."""
            made = uuid4()
            await db.execute('insert into public.experts (id, workspace_id, name) values (%s, %s, %s)', (made, space, name))
            await db.execute('insert into public.expert_versions (expert_id, version, config, created_by) values (%s, 1, %s, %s)',
                             (made, json.dumps(SAVED), owner))
            return made

        # A revision drops it, and a name that never existed is still refused.
        revised = await saved_expert('Revised watcher')
        view = await add_version(db, workspace_id=space, actor_id=owner, expert_id=revised, idempotency_key=str(uuid4()),
                                 expected_version=1, config=ExpertConfig.model_validate(await stored(revised, 1)), catalog=catalog)
        try:
            await add_version(db, workspace_id=space, actor_id=owner, expert_id=revised, idempotency_key=str(uuid4()), expected_version=2,
                              config=ExpertConfig(tools=['inflation_rate', 'market_history']), catalog=catalog)
            unknown = 'saved'
        except ExpertRefused as refused:
            unknown = refused.code
        second, first = await stored(revised, 2), await stored(revised, 1)
        check('a revision drops it', 'version 2 with market_history and no inflation_rates, version 1 as stored, and a name that never '
              'existed refused expert_tool_not_available',
              (view.latest_version, second.get('tools'), first.get('tools'), unknown),
              view.latest_version == 2 and second.get('tools') == ['market_history', 'save_artifact', 'publish_artifact']
              and first == SAVED and unknown == 'expert_tool_not_available')

        # Saved Experts and routines still run.
        watcher = await saved_expert('Saved watcher')
        session = await create_session(db, workspace_id=space, actor_id=owner, idempotency_key=str(uuid4()), kind='direct',
                                       experts=[SessionExpert(expert_id=watcher)])
        binding = await resolve_binding(db, space, session.id)
        await quiet()
        by_session = (await admit_run(db, workspace_id=space, actor_id=owner, idempotency_key=str(uuid4()), goal_text='Note the rates',
                                      limit_micro_usd=1_000_000, policy=resolve_role_policy(), binding=binding)).run_id
        await quiet()
        await db.execute('update public.routines set enabled = false where enabled')
        routine = await create_routine(db, workspace_id=space, actor_id=owner, idempotency_key=str(uuid4()), name='Saved routine',
                                       config=RoutineConfig(target=RoutineTarget(kind='expert', id=watcher, version=1),
                                                            trigger={'kind': 'interval', 'minutes': 60}, goal='Note the rates'),
                                       budget_cap=None, now=START)

        async def ready(_: UUID) -> str:
            return 'ready'

        due = await evaluate_routines(db, ready, START + timedelta(hours=1), catalog=catalog)
        by_routine = await value('select run_id from public.routine_occurrences where routine_id = %s', routine.id)
        routine_config = await value('select config from public.routine_versions where routine_id = %s and version = 1', routine.id)
        await quiet()
        session_tools, routine_tools = await granted(by_session), (await granted(by_routine) if by_routine else [])
        check('saved Experts and routines still run', 'both admitted with market_history and without inflation_rates; the stored '
              'version and routine unchanged',
              (session_tools, due, routine_tools, await stored(watcher, 1) == SAVED, routine_config),
              'market_history' in session_tools and RETIRED not in session_tools and due == 1 and 'market_history' in routine_tools
              and RETIRED not in routine_tools and await stored(watcher, 1) == SAVED and routine_config.get('tools') is None)

        # A workflow's agent step still runs.
        flow = await create_workflow(db, workspace_id=space, actor_id=owner, idempotency_key=str(uuid4()), name='Saved rates')
        graph = WorkflowGraph.model_validate({'ir_version': 2, 'nodes': [
            {'id': 'in', 'block': 'input', 'version': 1, 'config': {'type': 'string'}},
            {'id': 'pull', 'block': 'agent', 'version': 1, 'config': {'expert_id': str(watcher)}, 'label': 'Pull the rates'},
            {'id': 'out', 'block': 'output', 'version': 1, 'config': {}}],
            'links': [{'source': 'in', 'source_port': 'value', 'target': 'pull', 'target_port': 'goal'},
                      {'source': 'pull', 'source_port': 'result', 'target': 'out', 'target_port': 'value'}]})
        await publish_version(db, workspace_id=space, actor_id=owner, workflow_id=flow.id, idempotency_key=str(uuid4()),
                              expected_version=0, graph=graph, source='user')
        execution = await create_execution(db, workspace_id=space, actor_id=owner, workflow_id=flow.id, idempotency_key=str(uuid4()),
                                           version=1, inputs={'in': 'Note the rates'})
        model = Script(items=finishing('outputs/child-1/rates.md'), seen=[], bound=[])
        for _ in range(8):
            await process_next(db, URL, 'retired-flow', lambda: model, config)
            status = await value('select status from public.runs where id = %s', execution.run_id)
            if status in ('succeeded', 'failed', 'cancelled', 'waiting_approval'):
                break
        child = await value('select child_run_id from app_private.assignments where parent_run_id = %s', execution.run_id)
        child_tools = await granted(child) if child else []
        check("a workflow's agent step still runs", 'the step granted market_history without inflation_rates, and the execution '
              'succeeded past it', (child_tools, status), 'market_history' in child_tools and RETIRED not in child_tools
              and status == 'succeeded')

        # History stays as it was: a tool use recorded through the old tool, as its release defined it.
        await quiet()
        recorded_run = (await admit_run(db, workspace_id=space, actor_id=owner, idempotency_key=str(uuid4()), goal_text='Old rates',
                                        limit_micro_usd=1_000_000, policy=resolve_role_policy())).run_id
        lease = await claim_next(db, worker_id='retired-history', lease_seconds=120)
        assert lease is not None
        old_tool = replace(market_tools(httpx.MockTransport(chart))[0], tool_id=RETIRED, provider=OldProvider.WORLD_BANK)
        registry = ToolRegistry()
        registry.register(old_tool)
        scope = ToolScope(space, recorded_run, lease.generation, {RETIRED: 1}, ('outputs',))
        await ToolGateway(registry).execute(db, scope, RETIRED, {'symbols': ['BTC-USD']})
        await quiet()
        row_sql = 'select to_jsonb(u) from app_private.tool_uses u where run_id = %s and tool_id = %s'
        history_before = await value(row_sql, recorded_run, RETIRED)

        # A run in flight carries on: admitted while the tool map listed inflation_rates, and granted it.
        def admitted_before(extra: dict[str, int]) -> Any:
            def contract() -> dict[str, Any]:
                recorded = current_contract()
                return {**recorded, 'tools': {**recorded['tools'], **extra}}
            return contract

        async def admit_old(extra: dict[str, int]) -> UUID:
            await quiet()
            original = run_admission.current_contract
            run_admission.current_contract = admitted_before(extra)  # type: ignore[assignment]  # the earlier release's tool map
            try:
                old = replace(binding, tools={**binding.tools, **extra})
                return (await admit_run(db, workspace_id=space, actor_id=owner, idempotency_key=str(uuid4()), goal_text='Note the rates',
                                        limit_micro_usd=1_000_000, policy=resolve_role_policy(), binding=old)).run_id
            finally:
                run_admission.current_contract = original  # type: ignore[assignment]  # restored

        async def command(run: UUID, which: RunCommand) -> str:
            """As the API applies it: a resume is checked first (api/run_command_routes.py)."""
            version = await value('select version from public.runs where id = %s', run)
            try:
                if which is RunCommand.RESUME:
                    await require_resumable(db, space, run)
                await apply_command(db, workspace_id=space, run_id=run, command=which, expected_version=version)
                return 'accepted'
            except ResumeBlocked as blocked:
                return blocked.code

        flying = await admit_old({RETIRED: 1})
        paused = await command(flying, RunCommand.PAUSE)
        resumed = await command(flying, RunCommand.RESUME)
        recorded_contract = await value('select execution_contract from public.runs where id = %s', flying)
        model = Script(items=[finishing('outputs/rates.md')[0], calls((RETIRED, {'countries': ['CRI'], 'start_year': 2024, 'end_year': 2024})),
                              *finishing('outputs/rates.md')[1:]], seen=[], bound=[])
        for _ in range(3):
            await process_next(db, URL, 'retired-flying', lambda: model, config)
            if await value('select status from public.runs where id = %s', flying) in ('succeeded', 'failed', 'cancelled'):
                break
        final = await value('select status from public.runs where id = %s', flying)
        refusal = await value('select code from app_private.tool_uses where run_id = %s and tool_id = %s', flying, RETIRED)
        shown = codes(model)
        offered = sorted({tool for bound in model.bound for tool in bound})
        check('a run in flight carries on', 'paused and resumed with inflation_rates v1 recorded and granted; the model never offered it; '
              'its call refused tool_not_registered and shown; the run succeeded',
              (paused, resumed, recorded_contract['tools'].get(RETIRED), RETIRED in await granted(flying), RETIRED in offered, refusal,
               shown, final),
              paused == 'accepted' and resumed == 'accepted' and recorded_contract['tools'].get(RETIRED) == 1
              and RETIRED in await granted(flying) and RETIRED not in offered and 'market_history' in offered
              and refusal == 'tool_not_registered' and 'tool_not_registered' in shown and final == 'succeeded')

        # A tool removed without being retired still stops a run, on claim and on resume.
        stopped = await admit_old({'old_tool': 1})
        calls_before = await value('select count(*) from app_private.model_invocations')
        claimed = await process_next(db, URL, 'retired-old', never, config)
        added = await value('select count(*) from app_private.model_invocations') - calls_before
        state = await value('select status from public.runs where id = %s', stopped)
        reason = await value('select stop_reason from app_private.run_usage where run_id = %s', stopped)
        blocked = await command(stopped, RunCommand.RESUME)
        check('a tool removed without being retired still stops a run', 'claimed: paused as incompatible_version before any model call; '
              'resumed: refused incompatible_version',
              (claimed.code if claimed else None, state, reason, added, blocked),
              claimed is not None and claimed.code == 'incompatible_version' and state == 'paused' and reason == 'incompatible_version'
              and added == 0 and blocked == 'incompatible_version')
        await command(stopped, RunCommand.CANCEL)

        # History stays as it was.
        listed = await list_tool_uses(db, space, recorded_run)
        use = next((item for item in (listed.uses if listed else []) if item.tool_id == RETIRED), None)
        history_after = await value(row_sql, recorded_run, RETIRED)
        check('history stays as it was', 'the inflation_rates row lists with version 1, group market_data, provider world_bank and '
              'succeeded, and its stored row is unchanged',
              (use.tool_version, use.group, use.provider, use.outcome) if use else None,
              use is not None and (use.tool_version, use.group, use.provider, use.outcome) == (1, 'market_data', 'world_bank', 'succeeded')
              and history_before is not None and history_after == history_before)
    print(json.dumps({'cases': cases}))


asyncio.run(main())
