"""After a real upgrade from a prior release's data: semantics kept, or blocked honestly. JSON cases."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
from typing import Any
from uuid import UUID, uuid4

import psycopg
from autobots.adapters.checkpoints import ADAPTER_STATEMENTS, adapter_identity, identity_of
from autobots.adapters.loop_middleware import ModelRoute
from autobots.adapters.object_storage import SupabaseObjectStore
from autobots.application.goal_loop import LoopConfig, process_next
from autobots.application.runs import admit_run, apply_command
from autobots.domain.execution import current_contract
from autobots.domain.models import resolve_role_policy
from autobots.domain.runs import Actor, RunCommand
from goal_loop_script import DONE_A, SAVE, TASK_A, Script, calls, say
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from pydantic import SecretStr

# The prior release froze its saved runs on the model that was then the default, as Decision 0006 keeps.
ROUTE = ModelRoute('executor', 'openrouter_deepseek_flash', 'fixture/model', 1000)

URL = os.environ['AUTOBOTS_DATABASE_URL']
PLAN = ('propose_plan', {'tasks': [TASK_A]})
PUBLISH = ('publish_artifact', {'path': 'outputs/a.md', 'version': 1})
cases: list[dict[str, Any]] = []


def check(name: str, expected: str, observed: object, passed: bool) -> None:
    cases.append({'id': name, 'expected': expected, 'observed': str(observed), 'passed': bool(passed)})


def never() -> Any:
    raise AssertionError('a model was built for a run that must not continue')


def fixture(items: list[Any]) -> Any:
    return lambda: Script(items=list(items), seen=[], bound=[])


async def bindings(db: Any) -> str:
    cursor = await db.execute("select id, policy_snapshot, expert_id, expert_version, session_id from public.runs where id::text = any(%s) order by id", (BINDING_RUNS,))
    return hashlib.sha256(json.dumps(await cursor.fetchall(), default=str, sort_keys=True).encode()).hexdigest()


BINDING_RUNS: list[UUID] = []


async def main(workspace: UUID, queued: UUID, second: UUID, before_hash: str) -> None:
    BINDING_RUNS.extend(json.loads(os.environ['AUTOBOTS_PRIOR_RUNS']))
    store = SupabaseObjectStore(os.environ['AUTOBOTS_STORAGE_BASE'], SecretStr(os.environ['AUTOBOTS_STORAGE_SERVICE']))
    config = LoopConfig(route=ROUTE, object_store=store, sleep=lambda _: asyncio.sleep(0), lease_seconds=30)
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        async def value(sql: str, *values: object) -> Any:
            return (await (await db.execute(sql, values)).fetchone())[0]

        async def state(run: UUID) -> str:
            return await value('select status from public.runs where id = %s', run)

        hashed = await bindings(db)
        check('original bindings are byte-for-byte unchanged by the upgrade', before_hash[:16], hashed[:16], hashed == before_hash)
        contract = await value('select execution_contract from public.runs where id = %s', queued)
        check('a saved run gets its contract from the migration', 'graph state 1, tools recorded, marked', contract.get('recorded_by'), contract.get('graph_state') == 1 and contract.get('tools') and contract.get('recorded_by') == 'upgrade')

        # A changed workspace default, and a worker configured for it, don't reach a saved run.
        await db.execute("update app_private.model_policies set default_profile = 'openrouter_terra' where workspace_id = %s", (workspace,))
        other = ModelRoute('executor', 'openrouter_terra', 'fixture/changed', 1000)
        invocations = await value('select count(*) from app_private.model_invocations')
        refused = await process_next(db, URL, 'changed-route', fixture([calls(PLAN)]), LoopConfig(route=other, sleep=lambda _: asyncio.sleep(0), lease_seconds=30))
        added = await value('select count(*) from app_private.model_invocations') - invocations
        check('a worker on another model leaves a saved run paused, not failed', 'paused, route_not_bound, no call', f'{await state(queued)}, {refused.code if refused else None}, {added} calls', await state(queued) == 'paused' and refused is not None and refused.code == 'route_not_bound' and added == 0)
        unchanged = await bindings(db)
        check('and its frozen binding is still the original', before_hash[:16], unchanged[:16], unchanged == before_hash)
        await db.execute("update app_private.model_policies set default_profile = 'openrouter_deepseek_flash' where workspace_id = %s", (workspace,))
        version = await value('select version from public.runs where id = %s', queued)
        await apply_command(db, workspace_id=workspace, run_id=queued, command=RunCommand.RESUME, actor=Actor.USER, expected_version=version)

        # Compatible: the prior release's queued job runs to completion on this release.
        result = await process_next(db, URL, 'upgraded', fixture([calls(PLAN), calls(SAVE), calls(PUBLISH), calls(DONE_A), say('finished')]), config)
        check('a queued job from the prior release finishes here on its original model', 'succeeded', f'{await state(queued)}, {result.code if result else None}', await state(queued) == 'succeeded')

        # Blocked honestly, with no model built, however the release changed.
        for label, patch in (('a changed tool', {'graph_state': 1, 'tools': {**current_contract()['tools'], 'save_artifact': 0}}), ('an unreadable graph state', {'graph_state': 99, 'tools': {}})):
            run = (await admit_run(db, workspace_id=workspace, actor_id=uuid4(), idempotency_key=str(uuid4()), goal_text='Blocked goal', limit_micro_usd=1_000_000, policy=resolve_role_policy())).run_id
            await db.execute('update public.runs set execution_contract = %s where id = %s', (json.dumps(patch), run))
            calls_before = await value('select count(*) from app_private.model_invocations')
            result = await process_next(db, URL, 'blocked', never, config)
            added = await value('select count(*) from app_private.model_invocations') - calls_before
            checkpoints = await value("select count(*) from agent_runtime.checkpoints c join public.runs r on r.checkpoint_thread_id = c.thread_id where r.id = %s", run)
            check(f'{label} pauses the run and builds no model', 'paused, incompatible_version, nothing added', f'{await state(run)}, {result.code if result else None}, {added} calls, {checkpoints} checkpoints', await state(run) == 'paused' and result is not None and result.code == 'incompatible_version' and added == 0 and checkpoints == 0)
            shown = await value('select stop_reason from app_private.run_usage where run_id = %s', run)
            check(f'{label} records why', 'incompatible_version', shown, shown == 'incompatible_version')
            version = await value('select version from public.runs where id = %s', run)
            await apply_command(db, workspace_id=workspace, run_id=run, command=RunCommand.CANCEL, actor=Actor.USER, expected_version=version)
            check(f'{label} leaves the owner able to cancel', 'cancelled', await state(run), await state(run) == 'cancelled')
            linked = await admit_run(db, workspace_id=workspace, actor_id=uuid4(), idempotency_key=str(uuid4()), goal_text='Blocked goal', limit_micro_usd=1_000_000, policy=resolve_role_policy(), continues_run_id=run) if await state(run) == 'cancelled' else None
            check(f'{label} can continue as a linked new run on current semantics', 'a new run with the current contract', bool(linked), linked is not None)
            if linked is not None:
                recorded = await value('select execution_contract from public.runs where id = %s', linked.run_id)
                check('the linked run records the current contract', 'current', recorded == current_contract(), recorded == current_contract())
                await db.execute("update app_private.run_jobs set status = 'done' where run_id = %s", (linked.run_id,))

        # Decision 0004: a run frozen on a retired model stops, and nothing rewrites it to another.
        retired = (await admit_run(db, workspace_id=workspace, actor_id=uuid4(), idempotency_key=str(uuid4()), goal_text='Frozen on a retired model', limit_micro_usd=1_000_000, policy=resolve_role_policy())).run_id
        await db.execute("update public.runs set policy_snapshot = jsonb_set(policy_snapshot, '{bindings,executor}', '\"openrouter_astra\"') where id = %s", (retired,))
        calls_before = await value('select count(*) from app_private.model_invocations')
        result = await process_next(db, URL, 'after-retirement', fixture([calls(PLAN)]), config)
        frozen = await value("select policy_snapshot -> 'bindings' ->> 'executor' from public.runs where id = %s", retired)
        added = await value('select count(*) from app_private.model_invocations') - calls_before
        check('a run frozen on a retired model stops with no call, and keeps its binding', 'paused, route_not_bound, no call, still astra', (await state(retired), result.code if result else None, added, frozen), await state(retired) == 'paused' and result is not None and result.code == 'route_not_bound' and added == 0 and frozen == 'openrouter_astra')

        # A new admission records its contract.
        fresh = (await admit_run(db, workspace_id=workspace, actor_id=uuid4(), idempotency_key=str(uuid4()), goal_text='New goal', limit_micro_usd=1_000_000, policy=resolve_role_policy())).run_id
        recorded = await value('select execution_contract from public.runs where id = %s', fresh)
        check('a new admission records the current contract', 'current', recorded == current_contract(), recorded == current_contract())
        await db.execute("update app_private.run_jobs set status = 'done' where run_id = %s", (fresh,))
        _ = second
    print(json.dumps({'cases': cases}))


async def adapter(migrator_url: str, runtime_url: str) -> None:
    """The real adapter's own setup, in a scratch schema, against what the migration owns."""
    from langgraph.checkpoint.postgres.base import BasePostgresSaver
    version, fingerprint = adapter_identity()
    columns = ("select table_name, column_name, data_type, is_nullable, coalesce(column_default, '') from information_schema.columns "
               "where table_schema = %s order by 1, 2")
    async with await psycopg.AsyncConnection.connect(migrator_url, autocommit=True) as db:
        await db.execute('create schema adapter_probe')
        try:
            async with await psycopg.AsyncConnection.connect(migrator_url, autocommit=True, prepare_threshold=0, row_factory=dict_row, options='-c search_path=adapter_probe') as probe:
                await AsyncPostgresSaver(probe).setup()
            actual = await (await db.execute(columns, ('adapter_probe',))).fetchall()
            owned = await (await db.execute(columns, ('agent_runtime',))).fetchall()
            actual_tables = {row[0] for row in actual}
            owned_rows = [row for row in owned if row[0] in actual_tables]
            check('the migration-owned tables match what the adapter itself creates', f'{len(actual)} columns the same', f'{len(owned_rows)} columns, same {actual == owned_rows}', actual == owned_rows and actual)
            steps = await (await db.execute('select count(*) from adapter_probe.checkpoint_migrations')).fetchone()
            recorded = await (await db.execute('select count(*) from agent_runtime.checkpoint_migrations')).fetchone()
            check('the recorded adapter migrations cover its list', str(steps[0]), recorded[0], steps[0] == recorded[0] == len(BasePostgresSaver.MIGRATIONS))
            # Arranged: a release that adds one step. The same comparison and the identity both notice.
            await db.execute('alter table adapter_probe.checkpoints add column arranged_new_column text')
            drifted = await (await db.execute(columns, ('adapter_probe',))).fetchall()
            changed = identity_of(version, [*BasePostgresSaver.MIGRATIONS, 'ALTER TABLE checkpoints ADD COLUMN arranged_new_column text'], ADAPTER_STATEMENTS)
            check('a changed release is noticed before it runs (arranged)', 'schema differs and identity differs', f'{drifted != owned_rows}, {changed != fingerprint}', drifted != owned_rows and changed != fingerprint)
        finally:
            await db.execute('drop schema adapter_probe cascade')
    async with await psycopg.AsyncConnection.connect(runtime_url, autocommit=True) as db:
        qualified = await (await db.execute('select count(*) from agent_runtime.adapter_qualifications where fingerprint = %s and package_version = %s', (fingerprint, version))).fetchone()
        check('the installed adapter is recorded as qualified', '1', qualified[0], qualified[0] == 1)
        for label, statement in (('create a table in the adapter schema', 'create table agent_runtime.intruder (id int)'), ('alter a checkpoint table', 'alter table agent_runtime.checkpoints add column x text'),
                                 ('qualify an adapter itself', "insert into agent_runtime.adapter_qualifications (fingerprint, package_version, migrations) values ('x', 'x', 0)")):
            try:
                await db.execute(statement)
                outcome = 'allowed'
            except psycopg.errors.InsufficientPrivilege:
                outcome = 'denied'
            check(f'the runtime role cannot {label}', 'denied', outcome, outcome == 'denied')
        path = await (await db.execute("select to_regclass('public.checkpoints') is null")).fetchone()
        check('no checkpoint table leaks into public', 'none', path[0], path[0] is True)
    async with await psycopg.AsyncConnection.connect(runtime_url, autocommit=True, prepare_threshold=0, row_factory=dict_row, options='-c search_path=agent_runtime') as saver_db:
        schema = await (await saver_db.execute('select current_schema() as schema')).fetchone()
        check('the saver resolves to the private schema', 'agent_runtime', schema['schema'], schema['schema'] == 'agent_runtime')
    print(json.dumps({'cases': cases}))


if __name__ == '__main__':
    if sys.argv[1] == 'upgrade':
        asyncio.run(main(UUID(sys.argv[2]), UUID(sys.argv[3]), UUID(sys.argv[4]), sys.argv[5]))
    else:
        asyncio.run(adapter(sys.argv[2], sys.argv[3]))
