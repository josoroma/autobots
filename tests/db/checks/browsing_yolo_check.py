"""US-17.1 and Decision 0035 Y1 to Y4: browsing's YOLO setting, its freezing at admission, the approval
waiver and the Expert's browse domains, through the real gateway, admission and approvals. JSON cases.

Runs on a disposable database with no model and no browser: the executor is a fake whose start refuses,
so a call that reaches it is seen without a container, and one that doesn't is seen by its count.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import psycopg
from autobots.adapters import tool_registry
from autobots.adapters.browser_executor import ExecutorUnavailable
from autobots.application import browsing_settings, browsing_tool
from autobots.application.experts import add_version, create_expert
from autobots.application.loop_admission import active_middleware
from autobots.application.runs import Inheritance, admit_run
from autobots.application.tool_definitions import ToolRegistry, ToolScope
from autobots.application.tool_gateway import ToolGateway
from autobots.application.worker_inference import frozen_policy
from autobots.application.worker_leases import claim_next
from autobots.contracts.experts import ExpertConfig
from autobots.domain.tools import PLAN_TOOLS

URL = os.environ['AUTOBOTS_DATABASE_URL']
WORKSPACE_A = UUID(sys.argv[1])
POLICY = frozen_policy({'version': 1, 'bindings': {'executor': 'openrouter_terra', 'researcher': 'openrouter_sol'}})
ARGS = {'task': 'Read the guide.', 'start_url': 'https://en.wikivoyage.org/', 'allowed_domains': ['en.wikivoyage.org']}
cases: list[dict[str, Any]] = []


def check(name: str, expected: str, observed: object, passed: bool) -> None:
    cases.append({'id': name, 'expected': expected, 'observed': str(observed)[:700], 'passed': bool(passed)})


class Executor:
    """Counts the calls that reach it and refuses them, so no container starts."""

    def __init__(self) -> None:
        self.reached = 0

    async def sweep(self, alive: Any) -> list[str]:
        self.reached += 1
        return []

    async def start(self, *_: Any) -> Any:
        raise ExecutorUnavailable('no container in this check')


class Middleware:
    async def admitted(self, request: Any, handler: Any, route: Any) -> Any:
        raise AssertionError('no model call is expected')


async def main() -> None:
    executor = Executor()
    runtime = browsing_tool.BrowsingRuntime(executor, object(), 'route')  # type: ignore[arg-type]  # fakes
    registry = ToolRegistry()
    registry.register(browsing_tool.browse_tool(runtime, qualified=lambda: True))
    gateway = ToolGateway(registry)
    # The catalog lets an Expert grant browse_goal only while the executor reports qualified.
    browsing_tool.executor_qualified = lambda *_: True
    os.environ['AUTOBOTS_BROWSER_EXECUTOR'] = 'enabled'
    actor = uuid4()
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        fresh = uuid4()
        await db.execute("insert into public.workspaces (id, name) values (%s, 'Browsing YOLO fresh')", (fresh,))

        async def expert(workspace: UUID, domains: list[str]) -> tuple[UUID, int]:
            made = await create_expert(db, workspace_id=workspace, actor_id=actor, idempotency_key=str(uuid4()),
                                       name=f'Browser {uuid4().hex[:6]}', catalog=tool_registry.catalog(),
                                       config=ExpertConfig(tools=['browse_goal'], browse_domains=domains))
            return made.id, made.latest_version

        async def admit(workspace: UUID, made: tuple[UUID, int], inherit: Inheritance | None = None) -> UUID:
            await db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null "
                             "where status <> 'done'")
            binding = SimpleNamespace(session_id=None, expert_id=made[0], version=made[1], instructions='',
                                      tools={**PLAN_TOOLS, 'browse_goal': 1})
            return (await admit_run(db, workspace_id=workspace, actor_id=actor, idempotency_key=str(uuid4()),
                                    goal_text='browsing yolo', limit_micro_usd=1_000_000, policy=POLICY,
                                    binding=binding, inherit=inherit)).run_id

        async def frozen(run: UUID) -> bool:
            (value,) = await (await db.execute('select browsing_yolo from public.runs where id = %s', (run,))).fetchone()
            return bool(value)

        async def call(workspace: UUID, run: UUID, args: dict[str, Any] = ARGS) -> tuple[str, int, int, dict[str, Any]]:
            lease = await claim_next(db, worker_id='browsing-yolo', lease_seconds=120)
            assert lease is not None and lease.run_id == run, lease
            before = executor.reached
            with active_middleware(Middleware()):  # type: ignore[arg-type]  # the handler needs one; no model is called
                result = await gateway.execute(db, ToolScope(workspace, run, lease.generation, {'browse_goal': 1}), 'browse_goal', args)
            (pending,) = await (await db.execute("select count(*) from public.approval_requests where run_id = %s", (run,))).fetchone()
            (shown,) = await (await db.execute('select input_public from app_private.tool_uses where run_id = %s '
                                               'order by sequence_in_run desc limit 1', (run,))).fetchone()
            return str(result.code), int(pending), executor.reached - before, shown

        # Y1: no row means on, for a new workspace and one that existed before the setting.
        new, existing = await browsing_settings.load(db, fresh), await browsing_settings.load(db, WORKSPACE_A)
        check('a new workspace and an existing one read the setting on at version 0, its notice unseen',
              'yolo on, version 0, notice unseen, for both', (new, existing),
              new == existing == browsing_settings.BrowsingSetting(True, 0, False))

        # Y1: Home's notice shows once. Marking it again changes nothing, and the setting's version doesn't move.
        once = await browsing_settings.notice_seen(db, fresh)
        twice = await browsing_settings.notice_seen(db, fresh)
        check('the notice is marked seen once, and marking it again keeps the setting and its version',
              'yolo on, version 1, notice seen, twice', (once, twice),
              once == twice == browsing_settings.BrowsingSetting(True, 1, True))

        # Y4: a stale write changes nothing; an owner's write at its version moves it.
        try:
            await browsing_settings.change(db, fresh, False, 0)
            stale = 'saved'
        except Exception as error:  # noqa: BLE001 - the case records which refusal it was
            stale = type(error).__name__
        check('a write at a stale version is refused and changes nothing', 'StaleVersion, still on',
              (stale, await browsing_settings.load(db, fresh)), stale == 'StaleVersion' and (await browsing_settings.load(db, fresh)).yolo)

        listed = await expert(WORKSPACE_A, ['wikivoyage.org'])
        unlisted = await expert(WORKSPACE_A, [])

        # Y2 and Y3: a YOLO call within its Expert's domains starts with no approval and records typing on.
        run = await admit(WORKSPACE_A, listed)
        code, pending, reached, shown = await call(WORKSPACE_A, run)
        check('a YOLO call within its Expert domains starts without approval, and its row shows typing on and its domains',
              'frozen on; reached the executor; no approval request; typing on with allowed_domains',
              (await frozen(run), code, pending, reached, shown),
              await frozen(run) and code == 'executor_unavailable' and pending == 0 and reached == 1
              and shown.get('typing') == 'on' and shown.get('allowed_domains') == ['en.wikivoyage.org'])

        # Y3: outside the list, or with no list, refused before the executor.
        run = await admit(WORKSPACE_A, listed)
        outside = await call(WORKSPACE_A, run, {**ARGS, 'start_url': 'https://www.google.com/', 'allowed_domains': ['google.com']})
        run = await admit(WORKSPACE_A, unlisted)
        missing = await call(WORKSPACE_A, run)
        check('under YOLO a domain outside the Expert list, or an Expert with none, is refused before the executor',
              'browse_domain_not_granted and browse_domains_missing, neither reaching the executor or asking',
              (outside[:3], missing[:3]),
              outside[:3] == ('browse_domain_not_granted', 0, 0) and missing[:3] == ('browse_domains_missing', 0, 0))

        # Y4: turning it off applies at the run's next call, which waits for approval and reaches nothing.
        run = await admit(WORKSPACE_A, listed)
        setting = await browsing_settings.load(db, WORKSPACE_A)
        await browsing_settings.change(db, WORKSPACE_A, False, setting.version)
        code, pending, reached, shown = await call(WORKSPACE_A, run)
        check('turned off after admission, the next call waits for approval', 'approval_pending, one request, executor not reached, no typing',
              (await frozen(run), code, pending, reached, shown),
              await frozen(run) and code == 'approval_pending' and pending == 1 and reached == 0 and 'typing' not in shown)

        # Y4: turning it on reaches only runs admitted after.
        frozen_off = await admit(WORKSPACE_A, listed)
        setting = await browsing_settings.load(db, WORKSPACE_A)
        await browsing_settings.change(db, WORKSPACE_A, True, setting.version)
        before = await call(WORKSPACE_A, frozen_off)
        after_run = await admit(WORKSPACE_A, listed)
        after = await call(WORKSPACE_A, after_run)
        check('turned on, a run admitted while it was off still waits, and a new run starts without approval',
              'old: frozen off, approval_pending; new: frozen on, no approval request',
              (await frozen(frozen_off), before[:3], await frozen(after_run), after[:3]),
              not await frozen(frozen_off) and before[:3] == ('approval_pending', 1, 0)
              and await frozen(after_run) and after[:3] == ('executor_unavailable', 0, 1))

        # Y4: a child keeps its parent's frozen value, whatever the workspace says now.
        parent = await admit(WORKSPACE_A, listed)
        setting = await browsing_settings.load(db, WORKSPACE_A)
        await browsing_settings.change(db, WORKSPACE_A, False, setting.version)
        (root,) = await (await db.execute('select coalesce(root_run_id, id) from public.runs where id = %s', (parent,))).fetchone()
        # A direct run with no session, so the child names none either.
        child = await admit(WORKSPACE_A, listed, Inheritance(parent, root, {}, {**PLAN_TOOLS, 'browse_goal': 1}, (), '',
                                                              None, listed[0], listed[1]))  # type: ignore[arg-type]
        check("a child run keeps its parent's frozen setting though the workspace turned it off",
              'parent on, child on', (await frozen(parent), await frozen(child)), await frozen(parent) and await frozen(child))
        setting = await browsing_settings.load(db, WORKSPACE_A)
        await browsing_settings.change(db, WORKSPACE_A, True, setting.version)

        # Y3: the list is part of an Expert version; a new one holds the change, the old one is as it was.
        made = await create_expert(db, workspace_id=WORKSPACE_A, actor_id=actor, idempotency_key=str(uuid4()),
                                   name=f'Guide {uuid4().hex[:6]}', catalog=tool_registry.catalog(),
                                   config=ExpertConfig(tools=['browse_goal']))
        revised = await add_version(db, workspace_id=WORKSPACE_A, actor_id=actor, expert_id=made.id,
                                    idempotency_key=str(uuid4()), expected_version=1, catalog=tool_registry.catalog(),
                                    config=ExpertConfig(tools=['browse_goal'], browse_domains=['en.wikivoyage.org']))
        versions = {v.version: v.config.browse_domains for v in revised.versions}
        check('adding browse domains makes version 2 with them, and version 1 keeps none', '{1: [], 2: [en.wikivoyage.org]}',
              versions, versions == {1: [], 2: ['en.wikivoyage.org']})

        # Decision 0038 Z1: the browser is part of a version too, and is left out while it is the box.
        async def stored(expert: UUID) -> list[Any]:
            return [row[0] for row in await (await db.execute(
                'select config from public.expert_versions where expert_id = %s order by version', (expert,))).fetchall()]

        stealthy = await add_version(db, workspace_id=WORKSPACE_A, actor_id=actor, expert_id=made.id,
                                     idempotency_key=str(uuid4()), expected_version=2, catalog=tool_registry.catalog(),
                                     config=ExpertConfig(tools=['browse_goal'], browse_domains=['en.wikivoyage.org'], browser='stealth'))
        browsers = {v.version: v.config.browser for v in stealthy.versions}
        held = [config.get('browser') for config in await stored(made.id)]
        check('a new version holds stealth, and the earlier versions are unchanged', '{1: box, 2: box, 3: stealth}, stored as none, none, stealth',
              (browsers, held), browsers == {1: 'box', 2: 'box', 3: 'stealth'} and held == [None, None, 'stealth'])
        read = {}
        for version in (2, 3):
            run = await admit(WORKSPACE_A, (made.id, version))
            read[version] = await browsing_settings.expert_browser(db, run)
        check('a run reads the browser of the version it was admitted with, and its workspace time zone', 'box for 2, stealth for 3, one time zone',
              read, (read[2].kind, read[3].kind) == ('box', 'stealth') and read[2].timezone == read[3].timezone)

        key, name = str(uuid4()), f'Boxed {uuid4().hex[:6]}'
        saved = await create_expert(db, workspace_id=WORKSPACE_A, actor_id=actor, idempotency_key=key, name=name,
                                    catalog=tool_registry.catalog(), config=ExpertConfig(tools=['browse_goal']))
        again = await create_expert(db, workspace_id=WORKSPACE_A, actor_id=actor, idempotency_key=key, name=name,
                                    catalog=tool_registry.catalog(), config=ExpertConfig(tools=['browse_goal'], browser='box'))
        kept = await add_version(db, workspace_id=WORKSPACE_A, actor_id=actor, expert_id=saved.id, idempotency_key=str(uuid4()),
                                 expected_version=1, catalog=tool_registry.catalog(),
                                 config=ExpertConfig(tools=['browse_goal'], purpose='Revised', browser='box'))
        check('an Expert on the box stores no browser, reads as box, and the same request again matches its receipt',
              'one Expert, box twice, no stored browser',
              (again.id == saved.id, [v.config.browser for v in kept.versions], [sorted(config) for config in await stored(saved.id)]),
              again.id == saved.id and [v.config.browser for v in kept.versions] == ['box', 'box']
              and not any('browser' in config for config in await stored(saved.id)))
    os.environ.pop('AUTOBOTS_BROWSER_EXECUTOR', None)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    finally:
        print(json.dumps({'cases': cases}))
