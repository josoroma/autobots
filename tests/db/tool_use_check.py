"""US-14.3 on a real database: every dispatch is recorded, projected and fenced. JSON cases."""
from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import sys
from typing import Any
from uuid import UUID, uuid4

import psycopg
from autobots.application.runs import admit_run
from autobots.application.tool_gateway import ToolDefinition, ToolGateway, ToolRegistry, ToolScope
from autobots.application.tool_uses import METERED_TOOL_CALLS, list_tool_uses
from autobots.application.tools import CALCULATE, READ_RUN_FILE, SAVE_ARTIFACT
from autobots.application.worker_leases import claim_next
from autobots.contracts.runs import RunEvent
from autobots.domain.models import resolve_role_policy
from autobots.domain.tool_catalog import CostClass, ToolGroup, ToolProvider
from autobots.domain.tools import OperationClass
from pydantic import BaseModel, ConfigDict

URL = os.environ['AUTOBOTS_DATABASE_URL']
WORKSPACE = UUID(sys.argv[1])
FAKE_KEY = 'zz-fixture-key-7Q2W9E4R1T6Y'
cases: list[dict[str, Any]] = []
requests: list[str] = []


def check(name: str, expected: str, observed: object, passed: bool) -> None:
    cases.append({'id': name, 'expected': expected, 'observed': str(observed), 'passed': bool(passed)})


class LookupInput(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    query: str
    url: str
    note: str = ''


class LookupOutput(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    title: str
    page_text: str


async def lookup(arguments: LookupInput, _: Any) -> LookupOutput:
    """Stands in for a provider: the key goes to the transport only, here a list."""
    key = os.environ.get('FIXTURE_LOOKUP_KEY', '')
    requests.append(f'Bearer {key} {arguments.query}')
    return LookupOutput(title='Result', page_text=f'third-party page text for {arguments.query}')


LOOKUP = ToolDefinition(
    tool_id='fixture_lookup', version=1, title='Fixture lookup', description='fixture',
    input_model=LookupInput, output_model=LookupOutput, operation_class=OperationClass.READ_ONLY,
    handler=lookup, group=ToolGroup.WEB_SEARCH, provider=ToolProvider.TAVILY, network=True,
    cost_class=CostClass.METERED_PROVIDER, public_input_fields=('query', 'url'), public_output_fields=('title',))


async def scan(db: Any, value: str) -> list[str]:
    """Every table in the application's schemas, as text, for the value."""
    cursor = await db.execute(
        "select table_schema, table_name from information_schema.tables where table_type = 'BASE TABLE' "
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
    os.environ['FIXTURE_LOOKUP_KEY'] = FAKE_KEY
    log = io.StringIO()
    handler = logging.StreamHandler(log)
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.DEBUG)
    registry = ToolRegistry()
    for tool in (CALCULATE, READ_RUN_FILE, SAVE_ARTIFACT, LOOKUP):
        registry.register(tool)
    gateway = ToolGateway(registry)
    grants = {'calculate': 1, 'read_run_file': 1, 'save_artifact': 1, 'fixture_lookup': 1}
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        async def running() -> ToolScope:
            await db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null where status <> 'done'")
            admitted = await admit_run(db, workspace_id=WORKSPACE, actor_id=uuid4(), idempotency_key=str(uuid4()), goal_text='tool uses', limit_micro_usd=1000, policy=resolve_role_policy())
            lease = await claim_next(db, worker_id='tool-uses', lease_seconds=120)
            return ToolScope(WORKSPACE, admitted.run_id, lease.generation, grants, ('inputs', 'outputs'))

        # Scenario: Record every dispatch.
        scope = await running()
        tasks = [{'id': 't1', 'title': 'Add the totals', 'depends_on': [], 'criteria': [], 'tools': ['calculate', 'read_run_file'], 'expected_evidence': 'a sum'},
                 {'id': 't2', 'title': 'Save the note', 'depends_on': [], 'criteria': [], 'tools': ['save_artifact'], 'expected_evidence': 'a file'}]
        await db.execute("insert into app_private.plan_versions (run_id, version, tasks) values (%s, 1, %s)", (scope.run_id, json.dumps(tasks)))
        await db.execute("insert into app_private.run_files (run_id, path, version, content, sha256, media_type, operation_id) "
                         "values (%s, 'inputs/a.md', 1, 'numbers', 'x', 'text/plain', %s)", (scope.run_id, str(uuid4())))
        pure = await gateway.execute(db, scope, 'calculate', {'operation': 'sum', 'values': [1, 2]})
        read = await gateway.execute(db, scope, 'read_run_file', {'path': 'inputs/a.md'})
        saved = await gateway.execute(db, scope, 'save_artifact', {'path': 'outputs/note.md', 'content': 'secret body text'})
        denied = await gateway.execute(db, scope, 'publish_artifact', {'path': 'outputs/note.md', 'version': 1})
        outcomes = (pure.outcome.value, read.outcome.value, saved.outcome.value, denied.code)
        check('the four calls behave as before', 'succeeded x3, tool_not_granted', outcomes, outcomes == ('succeeded', 'succeeded', 'succeeded', 'tool_not_granted'))
        listing = await list_tool_uses(db, WORKSPACE, scope.run_id)
        assert listing is not None
        uses = listing.uses
        shape = [(u.sequence_in_run, u.tool_id, u.tool_version, u.task_id, u.task_title, u.outcome, u.code) for u in uses]
        expected = [(1, 'calculate', 1, 't1', 'Add the totals', 'succeeded', None), (2, 'read_run_file', 1, 't1', 'Add the totals', 'succeeded', None),
                    (3, 'save_artifact', 1, 't2', 'Save the note', 'succeeded', None), (4, 'publish_artifact', None, None, None, 'denied', 'tool_not_granted')]
        check('each dispatch has one row in order, with its plan task, outcome and typed code', str(expected), shape, shape == expected)
        check('database times are recorded for each', 'requested <= finished', [(u.requested_at <= u.finished_at) if u.finished_at else None for u in uses],
              all(u.finished_at is not None and u.requested_at <= u.finished_at and u.duration_ms is not None for u in uses))
        check('groups are copied at dispatch', "general, files, files, None", [u.group for u in uses], [u.group for u in uses] == ['general', 'files', 'files', None])
        check('the effectful use carries its receipt', 'operation id of save', (uses[2].operation_id, saved.operation_id), uses[2].operation_id == saved.operation_id is not None and uses[0].operation_id is None)
        check('content stays out: digests and sizes only', 'no body text, a 64-hex digest and a size',
              (uses[2].input_public, uses[1].output_public, uses[1].output_bytes),
              uses[2].input_public == {'path': 'outputs/note.md', 'media_type': 'text/markdown'} and 'content' not in (uses[1].output_public or {})
              and len(uses[2].input_digest) == 64 and (uses[1].output_bytes or 0) > 0)
        cursor = await db.execute("select payload from public.run_events where run_id = %s and payload ->> 'type' like 'tool.use.%%' order by sequence", (scope.run_id,))
        events = [row[0] for row in await cursor.fetchall()]
        check('each use streams a started and a completed event', '8 events, alternating', [e['type'] for e in events],
              [e['type'] for e in events] == ['tool.use.started', 'tool.use.completed'] * 4)
        cursor = await db.execute("select run_id, sequence, schema_version, payload, occurred_at from public.run_events where run_id = %s and payload ->> 'type' like 'tool.use.%%'", (scope.run_id,))
        parsed = 0
        for row in await cursor.fetchall():
            RunEvent.model_validate({'schema_version': row[2], 'run_id': row[0], 'sequence': row[1], 'causal_ids': [], 'occurred_at': row[4], 'payload': row[3]})
            parsed += 1
        allowed = {'type', 'tool_use_id', 'tool_id', 'tool_version', 'group', 'task_id', 'outcome', 'code', 'duration_ms', 'operation_id'}
        check('events are the typed public envelope at schema version 1, with identifiers only', '8 parsed, no other field',
              (parsed, sorted({key for e in events for key in e} - allowed)), parsed == 8 and not ({key for e in events for key in e} - allowed))

        # Scenario: Public projection and events, with a fake key.
        found = await gateway.execute(db, scope, 'fixture_lookup', {'query': 'colones', 'url': 'https://example.com/a/b?token=abc#frag', 'note': 'private'})
        listing = await list_tool_uses(db, WORKSPACE, scope.run_id)
        assert listing is not None
        last = listing.uses[-1]
        check('only public fields are listed, a URL without query or fragment', "query, url without ?token, title only",
              (last.input_public, last.output_public),
              found.outcome.value == 'succeeded' and last.input_public == {'query': 'colones', 'url': 'https://example.com/a/b'} and last.output_public == {'title': 'Result'})
        check('the key reached the transport', 'one request with it', len(requests), len(requests) == 1 and FAKE_KEY in requests[0])
        hits = await scan(db, FAKE_KEY)
        check('the fake key is in no table, rows, events, receipts or checkpoints included', 'none', hits, hits == [])
        check('nor in any log line', 'absent', FAKE_KEY in log.getvalue(), FAKE_KEY not in log.getvalue())
        text_hits = await scan(db, 'third-party page text')
        check("a page's text isn't kept in the record", 'none', text_hits, text_hits == [])

        # Scenario: Fenced and budgeted.
        fenced = await running()
        before = await db.execute("select count(*) from app_private.tool_uses where run_id = %s", (fenced.run_id,))
        await db.execute("update app_private.run_jobs set lease_expires_at = clock_timestamp() - interval '1 second' where run_id = %s", (fenced.run_id,))
        lost = await gateway.execute(db, fenced, 'calculate', {'operation': 'sum', 'values': [1]})
        after = await db.execute("select count(*) from app_private.tool_uses where run_id = %s", (fenced.run_id,))
        counts = ((await before.fetchone())[0], (await after.fetchone())[0])
        check('a worker that lost its lease records nothing, and is refused', 'lease_lost, 0 -> 0', (lost.code, counts), lost.code == 'lease_lost' and counts == (0, 0))

        budget = await running()
        requests.clear()
        results = [await gateway.execute(db, budget, 'fixture_lookup', {'query': f'q{index}', 'url': 'https://example.com/'}) for index in range(METERED_TOOL_CALLS + 1)]
        codes = [result.code for result in results]
        check('the run tree makes 20 metered calls, and the 21st is denied before any request',
              '20 succeeded, then tool_budget_exceeded, 20 requests', (codes[-1], len(requests)),
              all(result.outcome.value == 'succeeded' for result in results[:-1]) and codes[-1] == 'tool_budget_exceeded' and len(requests) == METERED_TOOL_CALLS)
        free = await gateway.execute(db, budget, 'calculate', {'operation': 'sum', 'values': [1]})
        check('an unmetered tool still runs after the limit', 'succeeded', free.outcome.value, free.outcome.value == 'succeeded')
        tree = await list_tool_uses(db, WORKSPACE, budget.run_id)
        check('a root run lists its tree', '22 uses', len(tree.uses) if tree else None, tree is not None and len(tree.uses) == METERED_TOOL_CALLS + 2)
        page = await list_tool_uses(db, WORKSPACE, budget.run_id, limit=5)
        rest = await list_tool_uses(db, WORKSPACE, budget.run_id, after=page.next_cursor or 0, limit=50) if page else None
        check('the listing pages by cursor without repeats', '5 then 17', (len(page.uses) if page else None, len(rest.uses) if rest else None),
              page is not None and rest is not None and len(page.uses) == 5 and len(rest.uses) == 17 and page.uses[-1].id < rest.uses[0].id)
        other = await list_tool_uses(db, uuid4(), budget.run_id)
        check("another workspace can't list them", 'None', other, other is None)
    print(json.dumps({'cases': cases}))


asyncio.run(main())
