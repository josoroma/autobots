"""US-14.5 on a disposable stack: a provider key reaches its adapter's HTTP client and nothing else,
and an Expert saved while a key was set is arranged for the browser suite to admit without it."""
from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import pickle
import sys
from collections.abc import Mapping
from typing import Any
from uuid import UUID, uuid4

import httpx
import psycopg
from autobots.adapters.provider_http import http_client
from autobots.adapters.tool_middleware import GatewayMiddleware, visible_tools
from autobots.application.experts import create_expert, create_session
from autobots.application.runs import admit_run
from autobots.application.tool_catalog import tool_catalog
from autobots.application.tool_gateway import (
    ToolContext,
    ToolDefinition,
    ToolFailed,
    ToolGateway,
    ToolRegistry,
    ToolScope,
)
from autobots.application.worker_leases import claim_next
from autobots.contracts.experts import ExpertConfig, SessionExpert
from autobots.domain.models import resolve_role_policy
from autobots.domain.tool_catalog import CostClass, KeyRequirement, ToolGroup, ToolProvider
from autobots.domain.tools import OperationClass
from deepagents import create_deep_agent
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import BaseModel, ConfigDict

URL = os.environ['AUTOBOTS_DATABASE_URL']
WORKSPACE = UUID(sys.argv[1])
FAKE_KEY = 'tvly-fixtureQ7W2E9R4T1Y6'
cases: list[dict[str, Any]] = []
seen_headers: list[str] = []


def check(name: str, expected: str, observed: object, passed: bool) -> None:
    cases.append({'id': name, 'expected': expected, 'observed': str(observed), 'passed': bool(passed)})


class Query(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    query: str


class Found(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    titles: list[str]


KEY = KeyRequirement('fixture', ('FIXTURE_PROVIDER_KEY',))


class Scripted(GenericFakeChatModel):
    """Records what it was shown, as a prompt, so the key's absence there is observed."""

    shown: list[str] = []  # noqa: RUF012 - a pydantic field, whose default pydantic copies for each instance

    def bind_tools(self, tools: Any, **_: Any) -> Any:
        return self

    async def _agenerate(self, messages: Any, *args: Any, **kwargs: Any) -> Any:
        self.shown.append(repr(messages))
        return await super()._agenerate(messages, *args, **kwargs)


def answer(request: httpx.Request) -> httpx.Response:
    seen_headers.append(request.headers.get('authorization', ''))
    return httpx.Response(200, json={'results': [{'title': 'One'}, {'title': 'Two'}]})


def fixture_key(environ: Mapping[str, str]) -> str:
    """This attempt's key, or a typed failure naming the credential, never the value. A local copy of
    the shape the retired provider_key helper had (R-11), since this fixture tool reads the environment."""
    value = environ.get('FIXTURE_PROVIDER_KEY', '').strip()
    if not value:
        raise ToolFailed('fixture_key_missing')
    return value


async def search(arguments: Query, _: ToolContext) -> Found:
    """The shape every provider adapter takes: the key read in this attempt, for this client only."""
    key = fixture_key(os.environ)
    async with http_client('https://provider.invalid', timeout=20.0, headers={'Authorization': f'Bearer {key}'}, transport=httpx.MockTransport(answer)) as client:
        reply = await client.post('/search', json={'query': arguments.query})
    return Found(titles=[item['title'] for item in reply.json()['results']])


SEARCH = ToolDefinition(tool_id='fixture_search', version=1, title='Fixture search', description='Search a fixture provider.',
                        input_model=Query, output_model=Found, operation_class=OperationClass.READ_ONLY, handler=search,
                        group=ToolGroup.WEB_SEARCH, provider=ToolProvider.TAVILY, network=True, cost_class=CostClass.METERED_PROVIDER,
                        key_requirement=KEY, public_input_fields=('query',), public_output_fields=('titles',))


async def scan(db: Any, value: str) -> list[str]:
    cursor = await db.execute("select table_schema, table_name from information_schema.tables where table_type = 'BASE TABLE' "
                              "and table_schema in ('public', 'app_private', 'agent_runtime')")
    found = []
    for schema, table in await cursor.fetchall():
        try:
            hit = await db.execute(f'select count(*) from "{schema}"."{table}" t where t::text like %s', (f'%{value}%',))
            if (await hit.fetchone())[0]:
                found.append(f'{schema}.{table}')
        except psycopg.errors.InsufficientPrivilege:
            continue
    return found


async def main() -> None:
    log = io.StringIO()
    logging.getLogger().addHandler(logging.StreamHandler(log))
    logging.getLogger().setLevel(logging.DEBUG)
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        # Scenario: a key stays out of durable state, through a real Deep Agents loop and checkpointer.
        os.environ['FIXTURE_PROVIDER_KEY'] = FAKE_KEY
        await db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null where status <> 'done'")
        admitted = await admit_run(db, workspace_id=WORKSPACE, actor_id=uuid4(), idempotency_key=str(uuid4()), goal_text='Find two titles',
                                   limit_micro_usd=1000, policy=resolve_role_policy())
        lease = await claim_next(db, worker_id='provider-key', lease_seconds=120)
        assert lease is not None
        scope = ToolScope(WORKSPACE, admitted.run_id, lease.generation, {'fixture_search': 1}, ('outputs',))
        registry = ToolRegistry()
        registry.register(SEARCH)
        gateway = ToolGateway(registry)
        model = Scripted(messages=iter([
            AIMessage(content='', tool_calls=[{'name': 'fixture_search', 'args': {'query': 'colones'}, 'id': 'call-1', 'type': 'tool_call'}]),
            AIMessage(content='done')]))
        saver = InMemorySaver()
        agent = create_deep_agent(model=model, tools=visible_tools(gateway, scope), middleware=[GatewayMiddleware(gateway, db, scope)], checkpointer=saver)
        state = await agent.ainvoke({'messages': [('user', 'go')]}, {'configurable': {'thread_id': str(admitted.run_id)}})
        replies = [json.loads(message.content) for message in state['messages'] if message.type == 'tool']
        check('the tool ran through the loop with its key', 'succeeded, the key in the Authorization header',
              (replies[0]['outcome'] if replies else None, len(seen_headers)),
              bool(replies) and replies[0]['outcome'] == 'succeeded' and seen_headers == [f'Bearer {FAKE_KEY}'])
        tables = await scan(db, FAKE_KEY)
        places = {
            'graph state': repr(state),
            'prompts the model was shown': ''.join(model.shown),
            'checkpoints': repr(list(saver.storage.items())) + repr(pickle.dumps(dict(saver.storage))),
            'scope': repr(scope),
            'tool schema shown to the model': json.dumps(registry.catalog(scope)),
            'catalog': tool_catalog(os.environ, registry=registry).model_dump_json(),
            'log lines': log.getvalue(),
        }
        leaked = [*tables, *(place for place, text in places.items() if FAKE_KEY in text)]
        check('the key is in no table, graph state, prompt, checkpoint, scope, schema, catalog or log line', 'none', leaked, leaked == [])
        check('the tool input has no credential field', "['query']", list(Query.model_fields), list(Query.model_fields) == ['query'])

        # A missing key is a typed failure inside the attempt, naming the credential only.
        del os.environ['FIXTURE_PROVIDER_KEY']
        missing = await gateway.execute(db, scope, 'fixture_search', {'query': 'colones'})
        check('without its key the tool fails with a typed code and sends nothing', 'failed fixture_key_missing, 1 request',
              (missing.outcome.value, missing.code, len(seen_headers)),
              missing.outcome.value == 'failed' and missing.code == 'fixture_key_missing' and len(seen_headers) == 1)

        # Arranged for the browser: Experts saved while the GitHub variables were set. The suite's API has none.
        os.environ['GITHUB_REPOSITORY'], os.environ['GITHUB_TOKEN'] = 'fixture/repository', 'ghp_fixtureNotARealToken0000000000'
        actor = uuid4()
        keyed = await create_expert(db, workspace_id=WORKSPACE, actor_id=actor, idempotency_key=str(uuid4()), name=f'Keyed {uuid4().hex[:6]}',
                                    config=ExpertConfig(tools=['calculate', 'create_github_issue']))
        plain = await create_expert(db, workspace_id=WORKSPACE, actor_id=actor, idempotency_key=str(uuid4()), name=f'Plain {uuid4().hex[:6]}',
                                    config=ExpertConfig(tools=['calculate']))
        del os.environ['GITHUB_REPOSITORY'], os.environ['GITHUB_TOKEN']
        keyed_session = await create_session(db, workspace_id=WORKSPACE, actor_id=actor, idempotency_key=str(uuid4()), kind='direct',
                                             experts=[SessionExpert(expert_id=keyed.id)])
        plain_session = await create_session(db, workspace_id=WORKSPACE, actor_id=actor, idempotency_key=str(uuid4()), kind='direct',
                                             experts=[SessionExpert(expert_id=plain.id)])
        check('an Expert granting the connector was saved while it was configured', 'version 1 with create_github_issue',
              keyed.versions[-1].config.tools, 'create_github_issue' in keyed.versions[-1].config.tools)
    print(json.dumps({'cases': cases, 'browser_env': {
        'AUTOBOTS_TEST_KEYED_SESSION': str(keyed_session.id), 'AUTOBOTS_TEST_KEYED_EXPERT': str(keyed.id),
        'AUTOBOTS_TEST_PLAIN_SESSION': str(plain_session.id), 'AUTOBOTS_TEST_PLAIN_EXPERT': str(plain.id)}}))


asyncio.run(main())
