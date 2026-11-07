"""Provider tools through the real gateway and record, against fake transports. JSON cases.

US-14.6 onward: a call past a ceiling is refused before any request, an allowed one returns
labelled, size-capped output and is recorded as a tool use with public fields only.
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

from autobots.adapters.tavily import tavily_tools
from autobots.application.runs import admit_run
from autobots.application.tool_gateway import ToolGateway, ToolRegistry, ToolScope
from autobots.application.tool_uses import list_tool_uses
from autobots.application.worker_leases import claim_next
from autobots.domain.models import resolve_role_policy

URL = os.environ['AUTOBOTS_DATABASE_URL']
WORKSPACE = UUID(sys.argv[1])
cases: list[dict[str, Any]] = []
requests: list[str] = []


def check(name: str, expected: str, observed: object, passed: bool) -> None:
    cases.append({'id': name, 'expected': expected, 'observed': str(observed), 'passed': bool(passed)})


async def resolve(host: str, _: int) -> list[str]:
    return ['93.184.215.14']


def tavily(request: httpx.Request) -> httpx.Response:
    requests.append(request.url.path)
    page = 'word ' * 60_000
    return httpx.Response(200, json={'results': [{'title': 'Colón', 'url': 'https://example.com/a?session=s3cret', 'content': page}] * 2})


async def main() -> None:
    registry = ToolRegistry()
    for tool in tavily_tools(httpx.MockTransport(tavily), environ={'TAVILY_API_KEY': 'tvly-fixtureDB0123456'}, resolver=resolve):
        registry.register(tool)
    gateway = ToolGateway(registry)
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        await db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null where status <> 'done'")
        admitted = await admit_run(db, workspace_id=WORKSPACE, actor_id=uuid4(), idempotency_key=str(uuid4()), goal_text='web tools', limit_micro_usd=1000, policy=resolve_role_policy())
        lease = await claim_next(db, worker_id='web-tools', lease_seconds=120)
        assert lease is not None
        scope = ToolScope(WORKSPACE, admitted.run_id, lease.generation, {'tavily_search': 1}, ('outputs',))

        # US-14.6: Bounded calls against a fake transport.
        past = await gateway.execute(db, scope, 'tavily_search', {'query': 'colones', 'max_results': 11})
        check('a Tavily search past its ceiling is refused before any request', 'invalid_arguments, 0 requests',
              (past.code, len(requests)), past.code == 'invalid_arguments' and requests == [])
        found = await gateway.execute(db, scope, 'tavily_search', {'query': 'colones', 'max_results': 2})
        output = found.output or {}
        check('an allowed search returns third-party text, cut to size with a notice', 'succeeded, third_party, truncated',
              (found.outcome.value, output.get('source'), output.get('truncated')),
              found.outcome.value == 'succeeded' and output.get('source') == 'third_party' and output.get('truncated') is True
              and 'instructions' in output.get('notice', '') and len(json.dumps(output).encode()) <= 500_000)
        listed = await list_tool_uses(db, WORKSPACE, admitted.run_id)
        uses = listed.uses if listed else []
        shape = [(use.tool_id, use.outcome, use.code, use.provider, use.group) for use in uses]
        check('both calls are recorded as tool uses', "denied invalid_arguments, then succeeded, Tavily, web search",
              shape, shape == [('tavily_search', 'denied', 'invalid_arguments', 'tavily', 'web_search'),
                               ('tavily_search', 'succeeded', None, 'tavily', 'web_search')])
        check('the record keeps public fields only, no page text or key', 'query and counts',
              (uses[1].input_public, uses[1].output_public) if len(uses) > 1 else None,
              len(uses) > 1 and uses[1].input_public == {'query': 'colones', 'search_depth': 'basic', 'max_results': 2, 'topic': 'general', 'time_range': None}
              and uses[1].output_public == {'result_count': 2, 'truncated': True}
              and 'word word' not in uses[1].model_dump_json() and 'tvly-' not in uses[1].model_dump_json())
        metered = await (await db.execute('select metered from app_private.tool_uses where run_id = %s order by id', (admitted.run_id,))).fetchall()
        check('only the dispatched call counts against the metered limit', '[False, True]', [row[0] for row in metered],
              [row[0] for row in metered] == [False, True])
    print(json.dumps({'cases': cases}))


asyncio.run(main())
