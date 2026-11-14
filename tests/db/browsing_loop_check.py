"""US-14.14 on a real database: the browsing loop's steps through real admission. JSON cases.

The model is scripted and the pages are scripted, so nothing leaves this Mac. The middleware,
admission, ledger and run usage are the real ones, on the run's frozen researcher route.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any
from uuid import UUID, uuid4

import psycopg
from autobots.adapters.loop_middleware import (
    AdmittedModel,
    LoopMiddleware,
    LoopStopped,
    ModelRoute,
    UnadmittedModelCall,
)
from autobots.application.browsing_loop import ACTION_TOOLS, Link, PageView, admitted_steps, browse
from autobots.application.model_attempts import FailureClass, ProviderFailure
from autobots.application.run_usage import RootLimits, ensure_usage
from autobots.application.runs import admit_run
from autobots.application.tool_gateway import ToolScope
from autobots.application.worker_leases import claim_next
from autobots.domain.models import resolve_role_policy
from goal_loop_script import ROUTE, Script, calls

URL = os.environ['AUTOBOTS_DATABASE_URL']
WORKSPACE = UUID(sys.argv[1])
RESEARCHER = ModelRoute('researcher', 'openrouter_sol', 'openai/gpt-6.1-sol', 1000)
SITE = {
    'https://example.com/': PageView(url='https://example.com/', title='Example Domain', text='This domain is for use in examples.',
                                      links=(Link(text='More information', url='https://www.iana.org/help/example-domains'),)),
    'https://www.iana.org/help/example-domains': PageView(url='https://www.iana.org/help/example-domains', title='Example Domains',
                                                          text='Reserved by RFC 2606.'),
}
cases: list[dict[str, Any]] = []


def check(name: str, expected: str, observed: object, passed: bool) -> None:
    cases.append({'id': name, 'expected': expected, 'observed': str(observed)[:700], 'passed': bool(passed)})


class Pages:
    def __init__(self) -> None:
        self.at = ''

    async def view(self) -> PageView:
        return SITE[self.at]

    async def go(self, url: str) -> None:
        self.at = url

    async def scroll(self) -> None:
        return None


def permitted(url: str) -> bool:
    return url.startswith(('https://example.com/', 'https://www.iana.org/'))


async def main() -> None:
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        async def value(sql: str, *values: object) -> Any:
            return (await (await db.execute(sql, values)).fetchone())[0]

        async def started(limit: int = 1_000_000) -> tuple[LoopMiddleware, UUID]:
            await db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null where status <> 'done'")
            admitted = await admit_run(db, workspace_id=WORKSPACE, actor_id=uuid4(), idempotency_key=str(uuid4()), goal_text='Browse',
                                       limit_micro_usd=limit, policy=resolve_role_policy())
            lease = await claim_next(db, worker_id='browse', lease_seconds=300)
            await db.execute("update public.runs set status = 'running' where id = %s", (lease.run_id,))
            # As `run_goal` does before its first call, which browsing runs inside.
            await ensure_usage(db, lease.run_id)
            scope = ToolScope(WORKSPACE, lease.run_id, lease.generation, {})
            return LoopMiddleware(db, scope, RootLimits(), ROUTE, sleep=lambda _: asyncio.sleep(0), slot_wait_seconds=2), admitted.run_id

        async def go(middleware: LoopMiddleware, model: Script) -> Any:
            return await browse(Pages(), admitted_steps(middleware, model, RESEARCHER), task='What is example.com for?',
                                start_url='https://example.com/', permitted=permitted, max_steps=10, max_seconds=120)

        # Three steps, each one admitted call on the researcher route.
        middleware, run_id = await started()
        frozen = await value("select policy_snapshot->'bindings'->>'researcher' from public.runs where id = %s", run_id)
        model = Script(items=[calls(('open_link', {'number': 1, 'notes': 'IANA'})), calls(('scroll', {})),
                              calls(('finish', {'summary': 'Reserved for documentation.'}))], seen=[], bound=[])
        outcome = await go(middleware, model)
        rows = await (await db.execute(
            'select role, profile, wire_id, status, reserved_micro_usd, charged_micro_usd, tool_names from app_private.model_invocations '
            'where run_id = %s order by attempt', (run_id,))).fetchall()
        usage = await value('select model_calls from app_private.run_usage where run_id = %s', run_id)
        check('three browsing steps are three admitted calls on the frozen researcher route',
              'researcher frozen on Sol; 3 succeeded invocations on openrouter_sol, each reserved and charged, tools recorded; 3 model calls; done',
              (frozen, rows, usage, outcome.stopped, outcome.summary),
              frozen == 'openrouter_sol' and len(rows) == 3 and usage == 3 and outcome.stopped == 'done'
              and all(row[:4] == ('researcher', 'openrouter_sol', 'openai/gpt-6.1-sol', 'succeeded') and row[4] > 0 and row[5] == 100 for row in rows)
              and [row[6] for row in rows] == [['open_link'], ['scroll'], ['finish']] and outcome.summary == 'Reserved for documentation.')
        shown = [str(seen[-1].content) for seen in model.seen]
        check('each step shows the page as text with its numbered links, and offers exactly the four actions as tools',
              'address, title, text and [1] link on the first step; four tools bound', (shown[0][:200], model.bound),
              'Address: https://example.com/' in shown[0] and 'Title: Example Domain' in shown[0] and '[1] More information' in shown[0]
              and 'Address: https://www.iana.org/help/example-domains' in shown[1] and len(model.seen) == 3
              and model.bound == [[str(tool) for tool in ACTION_TOOLS]])

        # An uncertain outcome stays pending reconciliation and isn't sent again.
        middleware, run_id = await started()
        model = Script(items=[ProviderFailure(FailureClass.PARTIAL_STREAM, accumulated_output='par'), calls(('finish', {'summary': 'x'}))], seen=[], bound=[])
        try:
            await go(middleware, model)
            stopped = 'continued'
        except LoopStopped as stop:
            stopped = stop.code
        status = await value('select status from app_private.model_invocations where run_id = %s', run_id)
        reserved = await value('select reserved_micro_usd from app_private.model_invocations where run_id = %s', run_id)
        check('an uncertain step stays reserved, pending reconciliation, and is not redispatched', 'partial_stream, uncertain, reserved, 1 call',
              (stopped, status, reserved, len(model.seen)), stopped == 'partial_stream' and status == 'uncertain' and reserved > 0 and len(model.seen) == 1)

        # An exhausted budget refuses the step before anything is sent.
        middleware, run_id = await started(limit=10)
        model = Script(items=[calls(('finish', {'summary': 'x'}))], seen=[], bound=[])
        try:
            await go(middleware, model)
            refused = 'sent'
        except LoopStopped as stop:
            refused = stop.code
        invocations = await value('select count(*) from app_private.model_invocations where run_id = %s', run_id)
        check('a step past the run budget is refused before it is sent', 'a budget refusal, no invocation, the model never called',
              (refused, invocations, len(model.seen)), refused.startswith('budget') and invocations == 0 and len(model.seen) == 0)

        # No model path outside admission.
        model = Script(items=[calls(('finish', {'summary': 'x'}))], seen=[], bound=[])
        guarded = AdmittedModel(delegate=model).bind_tools(ACTION_TOOLS, tool_choice='any')
        try:
            await guarded.ainvoke('read the page')
            outside = 'answered'
        except UnadmittedModelCall:
            outside = 'unadmitted'
        check('a model call outside admission fails as unadmitted and never reaches the model', 'unadmitted, 0 calls',
              (outside, len(model.seen)), outside == 'unadmitted' and len(model.seen) == 0)
    print(json.dumps({'cases': cases}))


asyncio.run(main())
