"""US-14.12 live on a disposable stack: browse_goal through the real gateway, approval, loop
middleware, admission and isolated executor, reaching example.com with a scripted model. JSON cases.

The model is scripted, so no inference provider is called. The executor is the real one, so the
browser does reach https://example.com/ (Decision 0018, the qualification host).
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import psycopg
from langchain_core.messages import AIMessage

sys.path.insert(0, str(Path(__file__).parent))
from autobots.adapters import loop_middleware
from autobots.adapters.browser_executor import BrowserExecutor
from autobots.adapters.loop_middleware import LoopMiddleware, ModelRoute
from autobots.application import browsing_tool
from autobots.application.approvals import decide
from autobots.application.experts import ExpertRefused, create_expert
from autobots.application.run_usage import RootLimits, ensure_usage
from autobots.application.runs import admit_run
from autobots.application.tool_catalog import all_descriptors, catalog_registry
from autobots.application.tool_gateway import ToolGateway, ToolRegistry, ToolScope
from autobots.application.worker_leases import claim_next
from autobots.contracts.experts import ExpertConfig
from autobots.domain.models import resolve_role_policy
from autobots.domain.tools import PLAN_TOOLS
from goal_loop_script import ROUTE, Script, calls, say

URL = os.environ['AUTOBOTS_DATABASE_URL']
WORKSPACE = UUID(sys.argv[1])
ACTOR = uuid4()
RESEARCHER = ModelRoute('researcher', 'openrouter_sol', 'openai/gpt-6.1-sol', 1000)
GRANT = {**PLAN_TOOLS, 'browse_goal': 1}
cases: list[dict[str, Any]] = []


def check(name: str, expected: str, observed: object, passed: bool) -> None:
    cases.append({'id': name, 'expected': expected, 'observed': str(observed)[:900], 'passed': bool(passed)})


def containers() -> list[str]:
    listed = subprocess.run(['docker', 'ps', '-a', '--filter', 'label=autobots.browser', '--format', '{{.Names}}'],
                            capture_output=True, text=True, check=False)
    return [name for name in listed.stdout.split() if name]


def act(name: str, **args: Any) -> AIMessage:
    return calls((name, args))


def slow(seconds: float, message: AIMessage) -> Any:
    def answer() -> AIMessage:
        time.sleep(seconds)
        return message
    return answer


async def main() -> None:
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        async def value(sql: str, *values: object) -> Any:
            return (await (await db.execute(sql, values)).fetchone())[0]

        # Unqualified: the owner's switch is off.
        os.environ.pop(browsing_tool.ENABLE, None)
        planned = next(item for item in all_descriptors({}) if item.tool_id == 'browse_goal')
        try:
            await create_expert(db, workspace_id=WORKSPACE, actor_id=ACTOR, idempotency_key=str(uuid4()), name=f'Off {uuid4().hex[:6]}',
                                config=ExpertConfig(tools=['browse_goal']))
            refused = 'saved'
        except ExpertRefused as refusal:
            refused = refusal.code if hasattr(refusal, 'code') else str(refusal)
        providers = {item.provider for item in all_descriptors({})}
        check('while unqualified, browse_goal is disabled by policy, unregistered, and an Expert naming it is refused',
              'disabled_by_policy with its repair reason, provider autobots, not registered, expert_tool_unavailable, TC-03 providers only',
              (planned.availability, planned.availability_reason, planned.provider, planned.registered, refused, sorted(providers)),
              planned.availability == 'disabled_by_policy' and planned.availability_reason == 'isolated_executor_not_qualified'
              and planned.provider == 'autobots' and not planned.registered and catalog_registry().get('browse_goal', 1) is None
              and 'expert_tool_unavailable' in refused
              and providers <= {'autobots', 'tavily', 'jina', 'yahoo_finance', 'world_bank', 'github'})

        os.environ[browsing_tool.ENABLE] = 'enabled'
        check('the executor is qualified on this Mac, and the owner turned browsing on', 'ready', browsing_tool.executor_ready(),
              browsing_tool.executor_ready())
        expert = await create_expert(db, workspace_id=WORKSPACE, actor_id=ACTOR, idempotency_key=str(uuid4()), name=f'Browser {uuid4().hex[:6]}',
                                     config=ExpertConfig(tools=['browse_goal']))
        executor = BrowserExecutor()

        async def start(expert_id: UUID | None) -> UUID:
            await db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null where status <> 'done'")
            binding = SimpleNamespace(session_id=None, expert_id=expert_id, version=1 if expert_id else None, instructions='', tools=GRANT)
            run = (await admit_run(db, workspace_id=WORKSPACE, actor_id=ACTOR, idempotency_key=str(uuid4()), goal_text='Browse',
                                   limit_micro_usd=1_000_000, policy=resolve_role_policy(), binding=binding)).run_id
            await ensure_usage(db, run)
            return run

        async def claimed(run: UUID) -> ToolScope:
            lease = await claim_next(db, worker_id='browse', lease_seconds=600)
            assert lease is not None and lease.run_id == run, lease
            await db.execute("update public.runs set status = 'running' where id = %s", (run,))
            return ToolScope(WORKSPACE, run, lease.generation, GRANT)

        async def execute(scope: ToolScope, model: Script, arguments: dict[str, Any]) -> Any:
            registry = ToolRegistry()
            runtime = browsing_tool.BrowsingRuntime(executor, model, RESEARCHER, settle=2.0)
            registry.register(browsing_tool.browse_tool(runtime))
            middleware = LoopMiddleware(db, scope, RootLimits(), ROUTE, sleep=lambda _: asyncio.sleep(0), slot_wait_seconds=2)
            token = loop_middleware._MIDDLEWARE.set(middleware)
            try:
                return await ToolGateway(registry).execute(db, scope, 'browse_goal', arguments)
            finally:
                loop_middleware._MIDDLEWARE.reset(token)

        async def approved(run: UUID, scope: ToolScope, model: Script, arguments: dict[str, Any]) -> tuple[Any, ToolScope]:
            pending = await execute(scope, model, arguments)
            assert pending.code == 'approval_pending', pending
            row = await (await db.execute('select id, argument_hash from public.approval_requests where run_id = %s and status = %s '
                                          'order by created_at desc limit 1', (run, 'pending'))).fetchone()
            await decide(db, workspace_id=WORKSPACE, actor_id=ACTOR, approval_id=row[0], idempotency_key=str(uuid4()),
                         decision='approve', argument_hash=row[1])
            scope = await claimed(run)
            return await execute(scope, model, arguments), scope

        base = {'task': 'What is example.com for?', 'start_url': 'https://example.com/', 'allowed_domains': ['example.com']}

        # Granted other than through an Expert: refused with a typed code, nothing started.
        run = await start(None)
        scope = await claimed(run)
        model = Script(items=[act('finish', summary='x')], seen=[], bound=[])
        plain = await execute(scope, model, base)
        check('a run with no Expert behind it is refused, with no container and no model call', 'denied expert_grant_required, 0 containers, 0 calls',
              (plain.outcome.value, plain.code, containers(), len(model.seen)),
              plain.outcome.value == 'denied' and plain.code == 'expert_grant_required' and not containers() and not model.seen)

        # Through an Expert: it waits for a person, showing what it will do, and starts nothing.
        run = await start(expert.id)
        scope = await claimed(run)
        model = Script(items=[act('scroll', notes='A reserved example domain.'), act('finish', summary='Reserved for documentation examples.')],
                       seen=[], bound=[])
        pending = await execute(scope, model, base)
        shown = await (await db.execute('select arguments, operation_class from public.approval_requests where run_id = %s', (run,))).fetchone()
        invocations = await value('select count(*) from app_private.model_invocations where run_id = %s', run)
        check("an Expert's call waits for approval showing its task, start URL, domains and limits, with nothing started",
              'approval_pending; arguments with task, start_url, allowed_domains, max_steps, max_seconds; 0 containers, 0 calls',
              (pending.code, shown, containers(), invocations, len(model.seen)),
              pending.code == 'approval_pending' and shown[1] == 'arbitrary_execution'
              and {'task', 'start_url', 'allowed_domains', 'max_steps', 'max_seconds'} <= set(shown[0])
              and not containers() and invocations == 0 and not model.seen)
        row = await (await db.execute('select id, argument_hash from public.approval_requests where run_id = %s', (run,))).fetchone()
        await decide(db, workspace_id=WORKSPACE, actor_id=ACTOR, approval_id=row[0], idempotency_key=str(uuid4()), decision='approve', argument_hash=row[1])
        scope = await claimed(run)
        done = await execute(scope, model, base)
        output = done.output or {}
        uses = await (await db.execute('select outcome, code, metered, input_public, output_public, provider, tool_group from app_private.tool_uses '
                                       'where run_id = %s order by sequence_in_run', (run,))).fetchall()
        calls_made = await (await db.execute("select role, profile, status from app_private.model_invocations where run_id = %s", (run,))).fetchall()
        metered = [use for use in uses if use[2]]
        check('an approved browse of example.com is summarised, labelled third-party and recorded with public fields only',
              'succeeded, done, third_party, visited example.com without query, 2 steps, 2 researcher calls on Sol; one metered use with only the six public fields',
              (done.outcome.value, done.code, {key: output.get(key) for key in ('stopped', 'source', 'visited', 'steps', 'model_calls', 'summary', 'truncated')},
               metered, calls_made),
              done.outcome.value == 'succeeded' and output.get('stopped') == 'done' and output.get('source') == 'third_party'
              and output.get('visited') == ['https://example.com/'] and output.get('steps') == 2 and output.get('model_calls') == 2
              and output.get('summary') == 'Reserved for documentation examples.' and output.get('truncated') is False
              and len(metered) == 1 and metered[0][0] == 'succeeded' and metered[0][5] == 'autobots' and metered[0][6] == 'browsing'
              and set(metered[0][3]) == {'start_url', 'allowed_domains', 'max_steps'} and set(metered[0][4]) == {'stopped', 'steps', 'visited_count'}
              and metered[0][4]['visited_count'] == 1
              and len(calls_made) == 2 and all(call == ('researcher', 'openrouter_sol', 'succeeded') for call in calls_made))
        page_text = str(model.seen[0][-1].content) if model.seen else ''
        check('the model was shown the real page as text', 'Example Domain, its text and a numbered link', page_text[:300],
              'Title: Example Domain' in page_text and '[1]' in page_text)
        check('the session was removed when the call returned', 'no browser containers', containers(), not containers())

        # Refusals and limits, each its own approved call on a fresh Expert run.
        async def refused(label: str, items: list[Any], change: dict[str, Any]) -> dict[str, Any]:
            run = await start(expert.id)
            scope = await claimed(run)
            model = Script(items=items, seen=[], bound=[])
            result, _ = await approved(run, scope, model, {**base, 'task': f'{base["task"]} ({label})', **change})
            return {'outcome': result.outcome.value, 'code': result.code, **(result.output or {}), 'calls': len(model.seen), 'left': containers()}

        outside = await refused('outside', [act('scroll', notes='so far'), act('open_link', number=1), act('finish', summary='never')], {})
        check('following a link outside allowed_domains ends the call refused_action, keeping the summary so far', 'refused_action, so far, 2 calls',
              outside, outside['stopped'] == 'refused_action' and outside['summary'] == 'so far' and outside['calls'] == 2 and not outside['left'])
        typing = await refused('typing', [act('type_text', text='hello'), act('finish', summary='never')], {})
        check('a typing action ends the call refused_action at once, with nothing submitted', 'refused_action, 1 call',
              typing, typing['stopped'] == 'refused_action' and typing['calls'] == 1 and not typing['left'])
        proxied = await refused('proxy', [act('go_to', url='https://localtest.me/', notes='trying'), act('finish', summary='never')],
                                {'allowed_domains': ['example.com', 'localtest.me']})
        check('a navigation the egress proxy refuses (a public name that resolves to loopback) ends the call refused_action', 'refused_action, 1 call',
              proxied, proxied['stopped'] == 'refused_action' and proxied['calls'] == 1 and not proxied['left'])
        invalid = await refused('invalid', [say('I think it is an example.'), act('finish', summary='never')], {})
        check('an answer that is not one valid action ends the call invalid_action', 'invalid_action, 1 call',
              invalid, invalid['stopped'] == 'invalid_action' and invalid['calls'] == 1 and not invalid['left'])
        steps = await refused('steps', [act('scroll'), act('scroll'), act('scroll')], {'max_steps': 2})
        check('reaching max_steps stops the call max_steps', 'max_steps, 2 calls', steps,
              steps['stopped'] == 'max_steps' and steps['calls'] == 2 and steps['steps'] == 2 and not steps['left'])
        timed = await refused('seconds', [slow(7, act('scroll', notes='slow')), slow(7, act('scroll')), act('finish', summary='never')],
                              {'max_seconds': 10})
        check('reaching max_seconds stops the call max_seconds, keeping the summary so far', 'max_seconds, slow, 2 calls', timed,
              timed['stopped'] == 'max_seconds' and timed['summary'] == 'slow' and timed['calls'] == 2 and not timed['left'])
    print(json.dumps({'cases': cases}))


asyncio.run(main())
