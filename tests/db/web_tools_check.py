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

from autobots.adapters.jina import jina_tools
from autobots.adapters.remote_files import store_remote_file_tool
from autobots.application.tools import READ_CSV, READ_RUN_FILE, READ_RUN_FILE_V2
from autobots.contracts.plans import InputDocument
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


def jina(request: httpx.Request) -> httpx.Response:
    requests.append(f'jina:{request.url.host}')
    if request.url.host == 's.jina.ai':
        return httpx.Response(200, json={'data': [{'title': 'Colón', 'url': 'https://example.com/a', 'description': 'about colones'}] * 3})
    return httpx.Response(200, json={'data': {'url': 'https://example.com/a?token=abc', 'title': 'A', 'content': 'page text body',
                                              'links': {'One': 'https://example.com/1'}}})


def remote(request: httpx.Request) -> httpx.Response:
    requests.append(f'remote:{request.url.path}')
    if request.url.path == '/rates.csv':
        return httpx.Response(200, text='day,rate\n2026-11-01,512.3\n', headers={'content-type': 'text/csv; charset=utf-8'})
    if request.url.path == '/logo.png':
        return httpx.Response(200, content=b'\x89PNG', headers={'content-type': 'image/png'})
    return httpx.Response(200, content=b'x' * (1_048_576 + 10), headers={'content-type': 'text/plain'})


async def main() -> None:
    registry = ToolRegistry()
    for tool in tavily_tools(httpx.MockTransport(tavily), environ={'TAVILY_API_KEY': 'tvly-fixtureDB0123456'}, resolver=resolve):
        registry.register(tool)
    for tool in jina_tools(httpx.MockTransport(jina), environ={'JINA_API_KEY': 'jina_fixtureDB0123456'}, resolver=resolve):
        registry.register(tool)
    for tool in (READ_RUN_FILE, READ_RUN_FILE_V2, READ_CSV, store_remote_file_tool(httpx.MockTransport(remote), resolve)):
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

        # US-14.7: Jina's two tools, on a run of their own.
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

        # US-14.9: attached inputs, paged reads, CSV and a guarded store.
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
    print(json.dumps({'cases': cases}))


asyncio.run(main())
