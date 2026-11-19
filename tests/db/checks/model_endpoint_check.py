"""US-17.2 and Decision 0035 Y7 on a real database: the browser box's model endpoint, each request one admitted
call on the run's frozen researcher route. JSON cases.

The model is scripted, so no inference provider is called. The middleware, admission, ledger and run usage are the
real ones. The endpoint listens on this Mac's loopback, and each request is sent to it over HTTP.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any
from uuid import UUID, uuid4

import httpx
import psycopg
from autobots.adapters.loop_middleware import LoopMiddleware, ModelRoute
from autobots.adapters.model_endpoint import ModelEndpoint, admitted_answer
from autobots.application.run_usage import RootLimits, ensure_usage
from autobots.application.runs import admit_run, apply_command
from autobots.application.tool_definitions import ToolScope
from autobots.application.worker_leases import claim_next
from autobots.domain.models import resolve_role_policy
from autobots.domain.runs import RunCommand
from goal_loop_script import ROUTE, Script, calls

URL = os.environ['AUTOBOTS_DATABASE_URL']
WORKSPACE = UUID(sys.argv[1])
RESEARCHER = ModelRoute('researcher', 'openrouter_sol', 'openai/gpt-6.1-sol', 1000)
REQUEST = {
    'model': 'gpt-6-luna',
    'messages': [{'role': 'system', 'content': 'Browse.'}, {'role': 'user', 'content': 'Read the guide.'}],
    'tools': [{'type': 'function', 'function': {'name': 'finish', 'parameters': {'type': 'object', 'properties': {}}}}],
    'tool_choice': 'required',
}
cases: list[dict[str, Any]] = []


def check(name: str, expected: str, observed: object, passed: bool) -> None:
    cases.append({'id': name, 'expected': expected, 'observed': str(observed)[:900], 'passed': bool(passed)})


async def main() -> None:
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        async def value(sql: str, *values: object) -> Any:
            return (await (await db.execute(sql, values)).fetchone())[0]

        async def started(limit: int = 1_000_000) -> tuple[LoopMiddleware, UUID]:
            await db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null where status <> 'done'")
            admitted = await admit_run(db, workspace_id=WORKSPACE, actor_id=uuid4(), idempotency_key=str(uuid4()), goal_text='Browse',
                                       limit_micro_usd=limit, policy=resolve_role_policy())
            lease = await claim_next(db, worker_id='model-endpoint', lease_seconds=300)
            await db.execute("update public.runs set status = 'running' where id = %s", (lease.run_id,))
            await ensure_usage(db, lease.run_id)
            scope = ToolScope(WORKSPACE, lease.run_id, lease.generation, {})
            return LoopMiddleware(db, scope, RootLimits(), ROUTE, sleep=lambda _: asyncio.sleep(0), slot_wait_seconds=2), admitted.run_id

        async def ask(middleware: LoopMiddleware, model: Script, *, token: bool = True, body: dict[str, Any] = REQUEST) -> httpx.Response:
            async with ModelEndpoint(admitted_answer(middleware, model, RESEARCHER)) as endpoint, httpx.AsyncClient(timeout=30) as client:
                headers = {'Authorization': f'Bearer {endpoint.token}'} if token else {}
                return await client.post(f'http://127.0.0.1:{endpoint.port}/v1/chat/completions', json=body, headers=headers)

        # One request is one admitted call on the frozen researcher route, whatever model it names.
        middleware, run_id = await started()
        model = Script(items=[calls(('finish', {'summary': 'done'}))], seen=[], bound=[])
        reply = await ask(middleware, model)
        rows = await (await db.execute(
            'select role, profile, wire_id, status, reserved_micro_usd, charged_micro_usd, tool_names from app_private.model_invocations '
            'where run_id = %s', (run_id,))).fetchall()
        usage = await value('select model_calls from app_private.run_usage where run_id = %s', run_id)
        body = reply.json()
        call = body['choices'][0]['message']['tool_calls'][0]['function'] if reply.status_code == 200 else {}
        check('one request is one admitted call on the frozen researcher route, whatever model it names, and the client gets no key',
              '200; one succeeded invocation on openrouter_sol, reserved and charged; 1 model call; finish answered; no key in the reply',
              (reply.status_code, rows, usage, body.get('model'), call),
              reply.status_code == 200 and len(rows) == 1 and rows[0][:4] == ('researcher', 'openrouter_sol', 'openai/gpt-6.1-sol', 'succeeded')
              and rows[0][4] > 0 and rows[0][5] > 0 and usage == 1 and body.get('model') == 'openai/gpt-6.1-sol'
              and call.get('name') == 'finish' and 'sk-or' not in reply.text and 'api_key' not in reply.text.lower())

        # Streamed, the same call comes back as a short stream that ends in [DONE].
        middleware, run_id = await started()
        model = Script(items=[calls(('finish', {'summary': 'done'}))], seen=[], bound=[])
        streamed = await ask(middleware, model, body={**REQUEST, 'stream': True, 'stream_options': {'include_usage': True}})
        events = [line[6:] for line in streamed.text.splitlines() if line.startswith('data: ')]
        check('a streamed request is the same one admitted call, answered as a stream', '200, event-stream, 3 chunks then [DONE], 1 invocation',
              (streamed.status_code, streamed.headers.get('content-type'), events[-1:], len(events),
               await value('select count(*) from app_private.model_invocations where run_id = %s', run_id)),
              streamed.status_code == 200 and streamed.headers.get('content-type') == 'text/event-stream' and events[-1] == '[DONE]'
              and len(events) == 4 and await value('select count(*) from app_private.model_invocations where run_id = %s', run_id) == 1)

        # Past the run's budget, refused with a typed reason before anything is sent.
        middleware, run_id = await started(limit=10)
        model = Script(items=[calls(('finish', {'summary': 'x'}))], seen=[], bound=[])
        poor = await ask(middleware, model)
        check('a request past the run budget is refused with a typed reason, and nothing reaches the model',
              '403 with a budget code, no invocation, the model never called',
              (poor.status_code, poor.json(), await value('select count(*) from app_private.model_invocations where run_id = %s', run_id), len(model.seen)),
              poor.status_code == 403 and str(poor.json()['error']['code']).startswith('budget')
              and await value('select count(*) from app_private.model_invocations where run_id = %s', run_id) == 0 and len(model.seen) == 0)

        # A cancelled run's request is refused too.
        middleware, run_id = await started()
        version = await value('select version from public.runs where id = %s', run_id)
        await apply_command(db, workspace_id=WORKSPACE, run_id=run_id, command=RunCommand.CANCEL, expected_version=version)
        model = Script(items=[calls(('finish', {'summary': 'x'}))], seen=[], bound=[])
        cancelled = await ask(middleware, model)
        check("a cancelled run's request is refused with a typed reason, and nothing reaches the model",
              '403 with a typed code, no invocation, the model never called',
              (cancelled.status_code, cancelled.json(), len(model.seen)),
              cancelled.status_code == 403 and bool(cancelled.json()['error']['code']) and len(model.seen) == 0
              and await value('select count(*) from app_private.model_invocations where run_id = %s', run_id) == 0)

        # Without the session's token, nothing is admitted.
        middleware, run_id = await started()
        model = Script(items=[calls(('finish', {'summary': 'x'}))], seen=[], bound=[])
        stranger = await ask(middleware, model, token=False)
        check('a request without the session token is refused before admission', '401 token_required, no invocation, the model never called',
              (stranger.status_code, stranger.json(), len(model.seen)),
              stranger.status_code == 401 and stranger.json()['error']['code'] == 'token_required' and len(model.seen) == 0
              and await value('select count(*) from app_private.model_invocations where run_id = %s', run_id) == 0)
    print(json.dumps({'cases': cases}))


asyncio.run(main())
