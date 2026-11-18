"""Provider tools through the real gateway and record, against fake transports. JSON cases through checklib, one
scenario at a time (refactor plan R-66, TDBC-06).

US-14.6 onward: a call past a ceiling is refused before any request, an allowed one returns
labelled, size-capped output and is recorded as a tool use with public fields only. US-14.21: a paged
search is one metered tool use that records its pages.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any
from uuid import UUID, uuid4

import httpx
import psycopg
from autobots.adapters.google_reader import google_crawl_tool, google_extract_tool
from autobots.adapters.jina import jina_tools
from autobots.adapters.market_data import market_tools
from autobots.adapters.remote_files import store_remote_file_tool
from autobots.adapters.serpapi import google_search_tool
from autobots.adapters.tavily import tavily_tools
from autobots.application import tool_switches
from autobots.application.code_tools import CODE_TOOLS
from autobots.application.runs import admit_run
from autobots.application.tool_definitions import ToolRegistry, ToolScope
from autobots.application.tool_gateway import ToolGateway
from autobots.application.tool_uses import METERED_TOOL_CALLS, list_tool_uses
from autobots.application.tools import READ_CSV, READ_RUN_FILE, READ_RUN_FILE_V2
from autobots.application.worker_leases import claim_next
from autobots.contracts.plans import InputDocument
from autobots.domain.models import resolve_role_policy
from checklib import Cases, run_check, run_scenarios

URL = os.environ['AUTOBOTS_DATABASE_URL']
WORKSPACE = UUID(sys.argv[1])
requests: list[str] = []


async def resolve(host: str, _: int) -> list[str]:
    return ['93.184.215.14']


def tavily(request: httpx.Request) -> httpx.Response:
    requests.append(request.url.path)
    page = 'word ' * 60_000
    return httpx.Response(200, json={'results': [{'title': 'Colón', 'url': 'https://example.com/a?session=s3cret', 'content': page}] * 2})


def jina(request: httpx.Request) -> httpx.Response:
    requests.append(f'jina:{request.url.host}')
    page = json.loads(request.content).get('page') if request.url.host == 's.jina.ai' else None
    if page is not None:
        # search_web version 2 names its page (US-14.21): ten distinct results each, long enough to be cut.
        requests.append(f'jina:page{page}')
        return httpx.Response(200, json={'data': [{'title': f'Colón {n}', 'url': f'https://example.com/{n}', 'description': 'paged result text ' * 300}
                                                  for n in range((page - 1) * 10, page * 10)]})
    if request.url.host == 's.jina.ai':
        return httpx.Response(200, json={'data': [{'title': 'Colón', 'url': 'https://example.com/a', 'description': 'about colones'}] * 3})
    return httpx.Response(200, json={'data': {'url': 'https://example.com/a?token=abc', 'title': 'A', 'content': 'page text body',
                                              'links': {'One': 'https://example.com/1'}}})


def serpapi(request: httpx.Request) -> httpx.Response:
    """US-14.22: SerpApi's Google search, ten distinct results a page, each reply naming a next page."""
    start = int(request.url.params.get('start', '0'))
    requests.append(f'serpapi:start{start}')
    results = [{'position': n - start + 1, 'title': f'Colón {n}', 'link': f'https://example.com/g{n}', 'snippet': 'google result text ' * 300}
               for n in range(start, start + 10)]
    return httpx.Response(200, json={'organic_results': results, 'serpapi_pagination': {'next': 'https://serpapi.com/search.json'}})


def site(request: httpx.Request) -> httpx.Response:
    """US-14.23: one site's robots.txt and pages, read directly, and SerpApi's map of it."""
    if request.url.host == 'serpapi.com':
        requests.append('serpapi:map')
        links = [f'https://example.com/read{n}' for n in range(3)]
        return httpx.Response(200, json={'organic_results': [{'position': n + 1, 'title': 't', 'link': link} for n, link in enumerate(links)]})
    requests.append(f'site:{request.url.path}')
    if request.url.path == '/robots.txt':
        return httpx.Response(200, text='User-agent: *\nAllow: /\n', headers={'content-type': 'text/plain'})
    body = '<html><head><title>Colón page</title></head><body><article><h1>Colón page</h1>' + '<p>' + 'directly read page text ' * 80 + '</p></article></body></html>'
    return httpx.Response(200, text=body, headers={'content-type': 'text/html'})


async def no_wait(_: float) -> None:
    return None


def markets(request: httpx.Request) -> httpx.Response:
    requests.append(f'market:{request.url.host}')
    if request.url.host == 'api.worldbank.org':
        return httpx.Response(200, json=[{'page': 1}, [{'countryiso3code': 'EMU', 'date': '2024', 'value': 2.36}]])
    return httpx.Response(200, json={'chart': {'result': [{'meta': {'currency': 'USD'}, 'timestamp': [1761955200, 1762041600],
                                                           'indicators': {'quote': [{'close': [100.0, 101.0]}]}}], 'error': None}})


def remote(request: httpx.Request) -> httpx.Response:
    requests.append(f'remote:{request.url.path}')
    if request.url.path == '/rates.csv':
        return httpx.Response(200, text='day,rate\n2026-11-01,512.3\n', headers={'content-type': 'text/csv; charset=utf-8'})
    if request.url.path == '/logo.png':
        return httpx.Response(200, content=b'\x89PNG', headers={'content-type': 'image/png'})
    return httpx.Response(200, content=b'x' * (1_048_576 + 10), headers={'content-type': 'text/plain'})


def gateway_over_fakes() -> ToolGateway:
    """Every provider tool these scenarios call, each over its fake transport."""
    registry = ToolRegistry()
    for tool in tavily_tools(httpx.MockTransport(tavily), environ={'TAVILY_API_KEY': 'tvly-fixtureDB0123456'}, resolver=resolve):
        registry.register(tool)
    for tool in jina_tools(httpx.MockTransport(jina), environ={'JINA_API_KEY': 'jina_fixtureDB0123456'}, resolver=resolve):
        registry.register(tool)
    registry.register(google_search_tool(httpx.MockTransport(serpapi), environ={'SERPAPI_API_KEY': 'serpapi_fixtureDB0123456'}))
    registry.register(google_extract_tool(httpx.MockTransport(site), resolve, no_wait, lambda: 0.0))
    registry.register(google_crawl_tool(httpx.MockTransport(site), {'SERPAPI_API_KEY': 'serpapi_fixtureDB0123456'}, resolve, no_wait, lambda: 0.0))
    for tool in CODE_TOOLS:
        registry.register(tool)
    for tool in market_tools(httpx.MockTransport(markets)):
        registry.register(tool)
    for tool in (READ_RUN_FILE, READ_RUN_FILE_V2, READ_CSV, store_remote_file_tool(httpx.MockTransport(remote), resolve)):
        registry.register(tool)
    return ToolGateway(registry)


class Tools:
    """One connection and the gateway each scenario calls through."""

    def __init__(self, db: Any, cases: Cases, gateway: ToolGateway) -> None:
        self.db, self.cases, self.gateway = db, cases, gateway


async def tavily_calls_are_bounded_and_recorded(ctx: Tools) -> None:
    """US-14.6: bounded calls against a fake transport, on a run of their own."""
    check, db, gateway = ctx.cases.check, ctx.db, ctx.gateway
    await db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null where status <> 'done'")
    admitted = await admit_run(db, workspace_id=WORKSPACE, actor_id=uuid4(), idempotency_key=str(uuid4()), goal_text='web tools', limit_micro_usd=1000, policy=resolve_role_policy())
    lease = await claim_next(db, worker_id='web-tools', lease_seconds=120)
    assert lease is not None
    scope = ToolScope(WORKSPACE, admitted.run_id, lease.generation, {'tavily_search': 1}, ('outputs',))

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


async def jina_calls_are_bounded_and_recorded(ctx: Tools) -> None:
    """US-14.7: Jina's two tools, on a run of their own."""
    check, db, gateway = ctx.cases.check, ctx.db, ctx.gateway
    await db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null where status <> 'done'")
    admitted = await admit_run(db, workspace_id=WORKSPACE, actor_id=uuid4(), idempotency_key=str(uuid4()), goal_text='jina tools', limit_micro_usd=1000, policy=resolve_role_policy())
    lease = await claim_next(db, worker_id='web-tools', lease_seconds=120)
    assert lease is not None
    scope = ToolScope(WORKSPACE, admitted.run_id, lease.generation, {'search_web': 1, 'extract_website_content': 1}, ('outputs',))
    requests.clear()
    past = await gateway.execute(db, scope, 'search_web', {'query': 'colones', 'max_results': 11})
    check('a Jina search past its ceiling is refused before any request', 'invalid_arguments, 0 requests',
          (past.code, len(requests)), past.code == 'invalid_arguments' and requests == [])
    found = await gateway.execute(db, scope, 'search_web', {'query': 'colones', 'max_results': 2})
    page = await gateway.execute(db, scope, 'extract_website_content', {'url': 'https://example.com/a?token=abc'})
    check('search and extract return third-party output', 'succeeded x2, third_party',
          (found.outcome.value, page.outcome.value, (page.output or {}).get('source')),
          found.outcome.value == page.outcome.value == 'succeeded' and (found.output or {}).get('source') == 'third_party'
          and (page.output or {}).get('source') == 'third_party' and len((found.output or {}).get('results', [])) == 2)
    listed = await list_tool_uses(db, WORKSPACE, admitted.run_id)
    uses = listed.uses if listed else []
    shape = [(use.tool_id, use.outcome, use.provider, use.group) for use in uses]
    check('each Jina call is recorded as a tool use', 'denied, then search and extract succeeded, Jina',
          shape, shape == [('search_web', 'denied', 'jina', 'web_search'), ('search_web', 'succeeded', 'jina', 'web_search'),
                           ('extract_website_content', 'succeeded', 'jina', 'web_extraction')])
    check("the extract's record keeps its URL without the query, and no page text", 'url without ?token, title, counts',
          (uses[2].input_public, uses[2].output_public) if len(uses) > 2 else None,
          len(uses) > 2 and uses[2].input_public == {'url': 'https://example.com/a'}
          and uses[2].output_public == {'url': 'https://example.com/a', 'title': 'A', 'link_count': 1, 'truncated': False}
          and 'page text body' not in uses[2].model_dump_json() and 'jina_' not in uses[2].model_dump_json())


async def paged_search_is_one_metered_use(ctx: Tools) -> None:
    """US-14.21: a three-page search_web version 2 call is one metered tool use that records its pages."""
    check, db, gateway = ctx.cases.check, ctx.db, ctx.gateway
    await db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null where status <> 'done'")
    admitted = await admit_run(db, workspace_id=WORKSPACE, actor_id=uuid4(), idempotency_key=str(uuid4()), goal_text='paged search', limit_micro_usd=1000, policy=resolve_role_policy())
    lease = await claim_next(db, worker_id='paged-search', lease_seconds=120)
    assert lease is not None
    scope = ToolScope(WORKSPACE, admitted.run_id, lease.generation, {'search_web': 2}, ('outputs',))
    requests.clear()
    found = await gateway.execute(db, scope, 'search_web', {'query': 'colones', 'max_results': 30})
    out = found.output or {}
    ranks = [item.get('rank') for item in out.get('results', [])]
    pages = [entry for entry in requests if entry.startswith('jina:page')]
    check('a three-page search returns 30 ranked results from pages 1 to 3', 'succeeded, ranks 1-30, page1-page3',
          (found.outcome.value, ranks[:1] + ranks[-1:], pages),
          found.outcome.value == 'succeeded' and ranks == list(range(1, 31)) and pages == ['jina:page1', 'jina:page2', 'jina:page3'])
    listed = await list_tool_uses(db, WORKSPACE, admitted.run_id)
    uses = listed.uses if listed else []
    metered = await (await db.execute('select metered from app_private.tool_uses where run_id = %s order by id', (admitted.run_id,))).fetchall()
    check('the call is one tool use, counted once against the metered limit', 'one search_web v2 use, metered once',
          ([(use.tool_id, use.tool_version, use.outcome) for use in uses], [row[0] for row in metered]),
          [(use.tool_id, use.tool_version, use.outcome) for use in uses] == [('search_web', 2, 'succeeded')]
          and [row[0] for row in metered] == [True])
    record = uses[0].model_dump_json() if uses else ''
    check('its record holds the paging counts, and no result text or key', '30 results, 3 pages, enough, none removed, no error, cut',
          uses[0].output_public if uses else None,
          bool(uses) and uses[0].output_public == {'result_count': 30, 'pages': 3, 'stopped': 'enough', 'duplicates_removed': 0,
                                                  'page_error': None, 'truncated': True}
          and uses[0].input_public == {'query': 'colones', 'max_results': 30}
          and 'paged result text' not in record and 'jina_' not in record)


async def google_search_is_one_metered_use(ctx: Tools) -> None:
    """US-14.22: a three-page google_search call is one metered tool use that records its pages."""
    check, db, gateway = ctx.cases.check, ctx.db, ctx.gateway
    await db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null where status <> 'done'")
    admitted = await admit_run(db, workspace_id=WORKSPACE, actor_id=uuid4(), idempotency_key=str(uuid4()), goal_text='google search', limit_micro_usd=1000, policy=resolve_role_policy())
    lease = await claim_next(db, worker_id='google-search', lease_seconds=120)
    assert lease is not None
    scope = ToolScope(WORKSPACE, admitted.run_id, lease.generation, {'google_search': 1}, ('outputs',))
    requests.clear()
    found = await gateway.execute(db, scope, 'google_search', {'query': 'colones', 'max_results': 30})
    out = found.output or {}
    ranks = [item.get('rank') for item in out.get('results', [])]
    pages = [entry for entry in requests if entry.startswith('serpapi:')]
    check('a three-page Google search returns 30 ranked results from start 0, 10 and 20', 'succeeded, ranks 1-30, start0-start20',
          (found.outcome.value, ranks[:1] + ranks[-1:], pages),
          found.outcome.value == 'succeeded' and ranks == list(range(1, 31)) and pages == ['serpapi:start0', 'serpapi:start10', 'serpapi:start20'])
    listed = await list_tool_uses(db, WORKSPACE, admitted.run_id)
    uses = listed.uses if listed else []
    metered = await (await db.execute('select metered from app_private.tool_uses where run_id = %s order by id', (admitted.run_id,))).fetchall()
    check('the Google search is one tool use, counted once against the metered limit', 'one google_search v1 use, metered once',
          ([(use.tool_id, use.tool_version, use.outcome, use.provider) for use in uses], [row[0] for row in metered]),
          [(use.tool_id, use.tool_version, use.outcome, use.provider) for use in uses] == [('google_search', 1, 'succeeded', 'serpapi')]
          and [row[0] for row in metered] == [True])
    record = uses[0].model_dump_json() if uses else ''
    check('the Google search record holds the paging counts, and no result text or key', '30 results, 3 pages, enough, none removed, no error, cut',
          uses[0].output_public if uses else None,
          bool(uses) and uses[0].output_public == {'result_count': 30, 'pages': 3, 'stopped': 'enough', 'duplicates_removed': 0,
                                                  'page_error': None, 'truncated': True}
          and 'google result text' not in record and 'serpapi_fixture' not in record)


async def google_reading_is_one_metered_use_each(ctx: Tools) -> None:
    """US-14.23: google_extract and google_crawl through the gateway, one metered tool use each, with counts and no page text."""
    check, db, gateway = ctx.cases.check, ctx.db, ctx.gateway
    await db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null where status <> 'done'")
    admitted = await admit_run(db, workspace_id=WORKSPACE, actor_id=uuid4(), idempotency_key=str(uuid4()), goal_text='google reading', limit_micro_usd=1000, policy=resolve_role_policy())
    lease = await claim_next(db, worker_id='google-reading', lease_seconds=120)
    assert lease is not None
    scope = ToolScope(WORKSPACE, admitted.run_id, lease.generation, {'google_extract': 1, 'google_crawl': 1}, ('outputs',))
    requests.clear()
    extracted = await gateway.execute(db, scope, 'google_extract', {'urls': ['https://example.com/a', 'https://example.com/b']})
    crawled = await gateway.execute(db, scope, 'google_crawl', {'url': 'https://example.com', 'limit': 3})
    check('google_extract reads two pages and google_crawl maps once and reads three, directly', 'succeeded x2, 2 and 3 results, one map',
          ((extracted.output or {}).get('result_count'), (crawled.output or {}).get('result_count'), requests.count('serpapi:map')),
          extracted.outcome.value == crawled.outcome.value == 'succeeded' and (extracted.output or {}).get('result_count') == 2
          and (crawled.output or {}).get('result_count') == 3 and requests.count('serpapi:map') == 1)
    listed = await list_tool_uses(db, WORKSPACE, admitted.run_id)
    uses = listed.uses if listed else []
    metered = await (await db.execute('select metered from app_private.tool_uses where run_id = %s order by id', (admitted.run_id,))).fetchall()
    check('each Google read is one tool use, counted once against the metered limit', 'google_extract then google_crawl, metered once each',
          ([(use.tool_id, use.provider, use.outcome) for use in uses], [row[0] for row in metered]),
          [(use.tool_id, use.provider, use.outcome) for use in uses] == [('google_extract', 'direct', 'succeeded'), ('google_crawl', 'serpapi', 'succeeded')]
          and [row[0] for row in metered] == [True, True])
    record = ''.join(use.model_dump_json() for use in uses)
    check('their records hold counts, and no page text or key', 'counts only',
          [(use.input_public, use.output_public) for use in uses],
          len(uses) == 2 and uses[0].output_public == {'result_count': 2, 'truncated': False}
          and uses[1].output_public == {'base_url': 'https://example.com', 'result_count': 3, 'pages': 1, 'truncated': False}
          and 'directly read page text' not in record and 'serpapi_fixture' not in record)


async def a_run_in_progress_cannot_call_a_tool_turned_off(ctx: Tools) -> None:
    """US-14.24, Decision 0033 W2: the gateway refuses a call to a tool turned off for the workspace, before any request,
    and lets the next one through once it is back on."""
    check, db, gateway = ctx.cases.check, ctx.db, ctx.gateway
    await db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null where status <> 'done'")
    admitted = await admit_run(db, workspace_id=WORKSPACE, actor_id=uuid4(), idempotency_key=str(uuid4()), goal_text='switches', limit_micro_usd=1000, policy=resolve_role_policy())
    lease = await claim_next(db, worker_id='tool-switches', lease_seconds=120)
    assert lease is not None
    scope = ToolScope(WORKSPACE, admitted.run_id, lease.generation, {'google_search': 1}, ('outputs',))
    version = (await tool_switches.load(db, WORKSPACE)).get(('tool', 'google_search'), tool_switches.Switch()).version
    off = await tool_switches.change(db, WORKSPACE, 'tool', 'google_search', False, version)
    requests.clear()
    refused = await gateway.execute(db, scope, 'google_search', {'query': 'colones', 'max_results': 10})
    sent_while_off = [entry for entry in requests if entry.startswith('serpapi:')]
    await tool_switches.change(db, WORKSPACE, 'tool', 'google_search', True, off.version)
    allowed = await gateway.execute(db, scope, 'google_search', {'query': 'colones', 'max_results': 10})
    check('a call to a tool turned off is refused tool_turned_off before any request, and the next succeeds once it is on',
          'denied tool_turned_off with no SerpApi request, then succeeded',
          (refused.outcome.value, refused.code, sent_while_off, allowed.outcome.value),
          refused.outcome.value == 'denied' and refused.code == 'tool_turned_off' and sent_while_off == [] and allowed.outcome.value == 'succeeded')


async def file_tools_read_inputs_and_guard_stores(ctx: Tools) -> None:
    """US-14.9: attached inputs, paged reads, CSV and a guarded store."""
    check, db, gateway = ctx.cases.check, ctx.db, ctx.gateway
    await db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null where status <> 'done'")
    notes = ''.join(f'line {n}\n' for n in range(30))
    table = 'name,count,ok,day\nalpha,1,true,2026-11-01\nbeta,2,false,2026-11-02\ngamma,3.5,true,2026-11-03\n'
    admitted = await admit_run(db, workspace_id=WORKSPACE, actor_id=uuid4(), idempotency_key=str(uuid4()), goal_text='file tools', limit_micro_usd=1000,
                               policy=resolve_role_policy(), input_documents=(InputDocument(path='inputs/notes.md', content=notes, media_type='text/markdown'),
                                                                              InputDocument(path='inputs/data.csv', content=table, media_type='text/csv')))
    lease = await claim_next(db, worker_id='file-tools', lease_seconds=120)
    assert lease is not None
    stored = dict(await (await db.execute('select path, media_type from app_private.run_files where run_id = %s', (admitted.run_id,))).fetchall())
    check('attached inputs are stored with their media types', 'notes.md markdown, data.csv csv', stored,
          stored == {'inputs/notes.md': 'text/markdown', 'inputs/data.csv': 'text/csv'})
    scope = ToolScope(WORKSPACE, admitted.run_id, lease.generation, {'read_run_file': 2, 'read_csv': 1, 'store_remote_file': 1}, ('inputs', 'outputs'))
    page = await gateway.execute(db, scope, 'read_run_file', {'path': 'inputs/notes.md', 'offset': 10, 'limit': 5})
    out = page.output or {}
    check('read_run_file 2 returns the requested lines with media type, version, sha256, total lines and a cut flag',
          'lines 10-14 of 30, markdown, truncated', (out.get('content'), out.get('total_lines'), out.get('media_type'), out.get('truncated')),
          out.get('content') == ''.join(f'line {n}\n' for n in range(10, 15)) and out.get('total_lines') == 30 and out.get('media_type') == 'text/markdown'
          and out.get('truncated') is True and out.get('version') == 1 and len(out.get('sha256', '')) == 64)
    rows = await gateway.execute(db, scope, 'read_csv', {'path': 'inputs/data.csv', 'max_rows': 2})
    out = rows.output or {}
    check('read_csv returns columns with inferred types, bounded rows and a cut flag', 'string, number, boolean, date; 2 of 3 rows',
          (out.get('columns'), out.get('row_count'), out.get('truncated')),
          out.get('columns') == [{'name': 'name', 'inferred_type': 'string'}, {'name': 'count', 'inferred_type': 'number'},
                                 {'name': 'ok', 'inferred_type': 'boolean'}, {'name': 'day', 'inferred_type': 'date'}]
          and out.get('rows') == [['alpha', '1', 'true', '2026-11-01'], ['beta', '2', 'false', '2026-11-02']]
          and out.get('row_count') == 3 and out.get('truncated') is True)
    over = await gateway.execute(db, scope, 'read_csv', {'path': 'inputs/data.csv', 'max_rows': 501})
    check('read_csv past 500 rows is refused first', 'invalid_arguments', over.code, over.code == 'invalid_arguments')
    listed = await list_tool_uses(db, WORKSPACE, admitted.run_id)
    uses = {use.tool_id: use for use in (listed.uses if listed else []) if use.outcome == 'succeeded'}
    text = (uses['read_run_file'].model_dump_json() + uses['read_csv'].model_dump_json()) if {'read_run_file', 'read_csv'} <= set(uses) else ''
    check("the record keeps the reads' digests and sizes, never their content", 'no line text, no rows, sizes recorded',
          (uses['read_run_file'].output_public if 'read_run_file' in uses else None),
          text != '' and 'line 11' not in text and 'alpha' not in text and (uses['read_run_file'].output_bytes or 0) > 0
          and (uses['read_run_file'].output_public or {}).get('sha256') == (page.output or {}).get('sha256'))
    pinned = ToolScope(WORKSPACE, admitted.run_id, lease.generation, {'read_run_file': 1}, ('inputs', 'outputs'))
    old = await gateway.execute(db, pinned, 'read_run_file', {'path': 'inputs/notes.md'})
    check('a grant pinned to read_run_file 1 still gets version 1', 'succeeded, whole content, no paging fields',
          (old.outcome.value, sorted(old.output or {})), old.outcome.value == 'succeeded' and (old.output or {}).get('content') == notes
          and 'total_lines' not in (old.output or {}))

    requests.clear()
    saved = await gateway.execute(db, scope, 'store_remote_file', {'url': 'https://example.com/rates.csv', 'path': 'outputs/rates.csv'})
    out = saved.output or {}
    check('a guarded text URL is stored under outputs/', 'path, version 1, sha256, 26 bytes, text/csv',
          (saved.outcome.value, out), saved.outcome.value == 'succeeded' and out.get('path') == 'outputs/rates.csv' and out.get('version') == 1
          and out.get('media_type') == 'text/csv' and out.get('size_bytes') == len('day,rate\n2026-11-01,512.3\n') and len(out.get('sha256', '')) == 64)
    refusals = {}
    for name, arguments in (('refused URL', {'url': 'http://example.com/rates.csv', 'path': 'outputs/a.csv'}),
                            ('private URL', {'url': 'https://127.0.0.1/rates.csv', 'path': 'outputs/b.csv'}),
                            ('non-text type', {'url': 'https://example.com/logo.png', 'path': 'outputs/c.png'}),
                            ('over 1 MiB', {'url': 'https://example.com/big.txt', 'path': 'outputs/d.txt'}),
                            ('outside outputs/', {'url': 'https://example.com/rates.csv', 'path': 'inputs/e.csv'})):
        result = await gateway.execute(db, scope, 'store_remote_file', arguments)
        refusals[name] = (result.outcome.value, result.code)
    written = (await (await db.execute("select count(*) from app_private.run_files where run_id = %s and path like 'outputs/%%'", (admitted.run_id,))).fetchone())[0]
    check('each refused store has a typed code and writes nothing', 'url_scheme_refused, url_host_refused, media_type_refused, url_too_large, invalid_arguments; 1 file',
          (refusals, written), refusals == {'refused URL': ('failed', 'url_scheme_refused'), 'private URL': ('failed', 'url_host_refused'),
                                           'non-text type': ('failed', 'media_type_refused'), 'over 1 MiB': ('failed', 'url_too_large'),
                                           'outside outputs/': ('denied', 'invalid_arguments')} and written == 1)
    check('refused URLs were never requested', 'only the stored, png and big requests',
          sorted(requests), sorted(requests) == ['remote:/big.txt', 'remote:/logo.png', 'remote:/rates.csv'])


async def market_data_counts_against_the_tree(ctx: Tools) -> None:
    """US-14.10: market data counts against the run tree's metered calls, 40 by Decision 0034 L3."""
    check, db, gateway = ctx.cases.check, ctx.db, ctx.gateway
    await db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null where status <> 'done'")
    admitted = await admit_run(db, workspace_id=WORKSPACE, actor_id=uuid4(), idempotency_key=str(uuid4()), goal_text='market data', limit_micro_usd=1000, policy=resolve_role_policy())
    lease = await claim_next(db, worker_id='market-tools', lease_seconds=120)
    assert lease is not None
    scope = ToolScope(WORKSPACE, admitted.run_id, lease.generation, {'market_history': 1, 'inflation_rates': 1}, ('outputs',))
    requests.clear()
    priced = [await gateway.execute(db, scope, 'market_history', {'symbols': ['BTC-USD']}) for _ in range(METERED_TOOL_CALLS - 1)]
    rates = await gateway.execute(db, scope, 'inflation_rates', {'countries': ['EMU'], 'start_year': 2024, 'end_year': 2024})
    late = await gateway.execute(db, scope, 'inflation_rates', {'countries': ['CRI'], 'start_year': 2024, 'end_year': 2024})
    wrong = await gateway.execute(db, scope, 'inflation_rates', {'countries': ['MEX'], 'start_year': 2024, 'end_year': 2024})
    out = rates.output or {}
    check(f'inflation is returned with its indicator and source, as the last of {METERED_TOOL_CALLS} metered calls', 'EMU 2024 2.36, FP.CPI.TOTL.ZG',
          (rates.outcome.value, out.get('countries'), out.get('indicator')),
          all(item.outcome.value == 'succeeded' for item in priced) and rates.outcome.value == 'succeeded'
          and out.get('countries') == [{'country': 'EMU', 'name': 'Euro area', 'rows': [{'year': 2024, 'inflation_pct': 2.36}]}]
          and out.get('indicator') == 'FP.CPI.TOTL.ZG' and 'World Bank' in out.get('source', ''))
    check('the next metered call is denied before any request, and another country is refused first',
          f'tool_budget_exceeded, invalid_arguments, {METERED_TOOL_CALLS} requests', (late.code, wrong.code, len(requests)),
          late.code == 'tool_budget_exceeded' and wrong.code == 'invalid_arguments' and len(requests) == METERED_TOOL_CALLS)
    listed = await list_tool_uses(db, WORKSPACE, admitted.run_id)
    last = [use for use in (listed.uses if listed else []) if use.tool_id == 'inflation_rates']
    check("the inflation call's record names its countries and source, not its values", 'countries, years, source',
          (last[0].input_public, last[0].output_public) if last else None,
          bool(last) and last[0].input_public == {'countries': ['EMU'], 'start_year': 2024, 'end_year': 2024}
          and (last[0].output_public or {}).get('indicator') == 'FP.CPI.TOTL.ZG' and '2.36' not in last[0].model_dump_json())


async def code_tools_stay_in_the_runs_files(ctx: Tools) -> None:
    """US-14.11: code tools over the run's own files."""
    check, db, gateway = ctx.cases.check, ctx.db, ctx.gateway
    await db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null where status <> 'done'")
    source = 'import os\n\ndef main():\n    return os.getcwd()\n' + 'y' * 700 + ' main\n'
    admitted = await admit_run(db, workspace_id=WORKSPACE, actor_id=uuid4(), idempotency_key=str(uuid4()), goal_text='code tools', limit_micro_usd=1000,
                               policy=resolve_role_policy(), input_documents=(InputDocument(path='inputs/app.py', content=source),))
    lease = await claim_next(db, worker_id='code-tools', lease_seconds=120)
    assert lease is not None
    other = await admit_run(db, workspace_id=WORKSPACE, actor_id=uuid4(), idempotency_key=str(uuid4()), goal_text='other run', limit_micro_usd=1000,
                            policy=resolve_role_policy(), input_documents=(InputDocument(path='inputs/secret.py', content='def main(): pass\n'),))
    grants = {'search_files': 1, 'read_code_file': 1, 'write_code_file': 1, 'patch_code_file': 1}
    scope = ToolScope(WORKSPACE, admitted.run_id, lease.generation, grants, ('inputs', 'outputs'))
    written = await gateway.execute(db, scope, 'write_code_file', {'path': 'outputs/app.py', 'content': 'x = 1\nx = 1\ny = 2\n'})
    found = await gateway.execute(db, scope, 'search_files', {'pattern': r'def \w+|main', 'path': 'inputs/', 'file_glob': '*.py', 'context': 1})
    out = found.output or {}
    paths = {match['path'] for match in out.get('matches', [])}
    lines = {match['line_number']: match['content'] for match in out.get('matches', [])}
    check("search_files finds matches in this run's files only, with context and a 500-character line cap",
          'app.py lines 3 and 5, line 5 cut to 500, no other run', (sorted(paths), sorted(lines), len(lines.get(5, ''))),
          found.outcome.value == 'succeeded' and paths == {'inputs/app.py'} and sorted(lines) == [3, 5] and len(lines[5]) == 500
          and out['matches'][0]['before'] == [''] and out['matches'][0]['after'] == ['    return os.getcwd()'])
    counted = await gateway.execute(db, scope, 'search_files', {'pattern': 'x', 'output_mode': 'count'})
    files = await gateway.execute(db, scope, 'search_files', {'pattern': 'app', 'target': 'files'})
    bad = await gateway.execute(db, scope, 'search_files', {'pattern': '(unclosed'})
    check('counts, file names and a bad pattern', '2 in outputs/app.py, both app.py files, invalid_pattern',
          ((counted.output or {}).get('total_count'), (files.output or {}).get('files'), bad.code),
          (counted.output or {}).get('total_count') == 2 and (files.output or {}).get('files') == ['inputs/app.py', 'outputs/app.py']
          and bad.code == 'invalid_pattern')
    read = await gateway.execute(db, scope, 'read_code_file', {'path': 'inputs/app.py', 'offset': 2, 'limit': 2})
    check('read_code_file returns numbered lines with paging', 'lines 3 and 4 of 5, truncated',
          (read.output or {}).get('lines'), (read.output or {}).get('lines') == [{'number': 3, 'text': 'def main():'}, {'number': 4, 'text': '    return os.getcwd()'}]
          and (read.output or {}).get('total_lines') == 5 and (read.output or {}).get('truncated') is True)

    async def versions() -> int:
        return (await (await db.execute("select count(*) from app_private.run_files where run_id = %s and path = 'outputs/app.py'", (admitted.run_id,))).fetchone())[0]

    before = await versions()
    absent = await gateway.execute(db, scope, 'patch_code_file', {'path': 'outputs/app.py', 'old_string': 'z = 3', 'new_string': 'z = 4'})
    ambiguous = await gateway.execute(db, scope, 'patch_code_file', {'path': 'outputs/app.py', 'old_string': 'x = 1', 'new_string': 'x = 9'})
    middle = await versions()
    exact = await gateway.execute(db, scope, 'patch_code_file', {'path': 'outputs/app.py', 'old_string': 'y = 2', 'new_string': 'y = 3'})
    every = await gateway.execute(db, scope, 'patch_code_file', {'path': 'outputs/app.py', 'old_string': 'x = 1', 'new_string': 'x = 9', 'replace_all': True})
    latest = (await (await db.execute("select content from app_private.run_files where run_id = %s and path = 'outputs/app.py' order by version desc limit 1", (admitted.run_id,))).fetchone())[0]
    check('a patch is exact or writes nothing', 'old_string_not_found, old_string_ambiguous, no new version; then versions 2 and 3',
          (absent.code, ambiguous.code, before, middle, (exact.output or {}).get('version'), (every.output or {}).get('replacements'), latest),
          written.outcome.value == 'succeeded' and absent.code == 'old_string_not_found' and ambiguous.code == 'old_string_ambiguous'
          and before == middle == 1 and (exact.output or {}).get('version') == 2 and (exact.output or {}).get('replacements') == 1
          and (every.output or {}).get('version') == 3 and (every.output or {}).get('replacements') == 2 and latest == 'x = 9\nx = 9\ny = 3\n'
          and len((exact.output or {}).get('sha256', '')) == 64)
    outside = [await gateway.execute(db, scope, tool, arguments) for tool, arguments in (
        ('write_code_file', {'path': 'inputs/app.py', 'content': 'evil'}),
        ('write_code_file', {'path': '../etc/passwd', 'content': 'evil'}),
        ('patch_code_file', {'path': 'inputs/app.py', 'old_string': 'os', 'new_string': 'sys'}))]
    inputs = (await (await db.execute("select count(*) from app_private.run_files where run_id = %s and path like 'inputs/%%'", (admitted.run_id,))).fetchone())[0]
    check('writes outside outputs/ are refused and nothing is written', 'invalid_arguments x3, inputs unchanged',
          ([result.code for result in outside], inputs), [result.code for result in outside] == ['invalid_arguments'] * 3 and inputs == 1)
    assert other.run_id != admitted.run_id


SCENARIOS = (
    tavily_calls_are_bounded_and_recorded,
    jina_calls_are_bounded_and_recorded,
    paged_search_is_one_metered_use,
    google_search_is_one_metered_use,
    google_reading_is_one_metered_use_each,
    a_run_in_progress_cannot_call_a_tool_turned_off,
    file_tools_read_inputs_and_guard_stores,
    market_data_counts_against_the_tree,
    code_tools_stay_in_the_runs_files,
)


async def main(cases: Cases) -> None:
    gateway = gateway_over_fakes()
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        context = Tools(db, cases, gateway)
        await run_scenarios(cases, SCENARIOS, context)


if __name__ == '__main__':
    # Its parent's Child entry in scripts/app_db.py gives it 180 seconds.
    run_check(main, parent_timeout=180)
