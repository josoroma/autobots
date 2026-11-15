"""The GitHub connector through the real gateway, approvals and receipts, with a fake GitHub. JSON cases."""
from __future__ import annotations

import asyncio
import base64
import json
import os
import sys
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import httpx
import psycopg
from autobots.adapters.github_issues import (
    REPOSITORY_VARIABLE,
    TOKEN_VARIABLE,
    TOOL_ID,
    github_issue_tool,
    marker,
)
from autobots.adapters.github_reads import github_read_tools
from autobots.application.approvals import decide
from autobots.application.runs import admit_run
from autobots.application.tool_definitions import ToolRegistry, ToolScope
from autobots.application.tool_gateway import ToolGateway
from autobots.application.tool_uses import list_tool_uses
from autobots.application.worker_leases import claim_next
from autobots.domain.models import resolve_role_policy
from autobots.domain.tools import EXPERT_TOOLS, PLAN_TOOLS

URL = os.environ['AUTOBOTS_DATABASE_URL']
WORKSPACE = UUID(sys.argv[1])
ACTOR = uuid4()
TOKEN = 'arranged-connector-token'
ENV = {REPOSITORY_VARIABLE: 'owner/throwaway', TOKEN_VARIABLE: TOKEN}
cases = []
FILE_TEXT = 'PRIVATE-FILE-TEXT that only the model may read\n'


def check(name: str, expected: str, observed: object, passed: bool) -> None:
    cases.append({'id': name, 'expected': expected, 'observed': str(observed), 'passed': bool(passed)})


class FakeGithub:
    """`mode` is what the next create does: ok, lose_ack (created, reply lost) or never (lost before it)."""

    def __init__(self) -> None:
        self.mode, self.readback = 'ok', 200
        self.posts: list[str] = []
        self.payloads: list[dict[str, Any]] = []
        self.seen: list[httpx.Request] = []
        self.issues: list[dict[str, Any]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.seen.append(request)
        if request.method == 'GET' and '/contents/' in request.url.path:
            return httpx.Response(200, json={'type': 'file', 'size': len(FILE_TEXT), 'sha': 'arranged-sha',
                                             'content': base64.b64encode(FILE_TEXT.encode()).decode()})
        if request.method == 'GET' and request.url.path == '/search/issues':
            return httpx.Response(200, json={'items': [{'number': 1, 'title': 'Arranged', 'state': 'open', 'labels': [], 'html_url': 'u'}]})
        if request.method == 'GET' and request.url.path.endswith('/pulls'):
            return httpx.Response(200, json=[{'number': 4, 'title': 'Arranged PR', 'user': {'login': 'ada'}, 'merged_at': None, 'labels': [], 'html_url': 'u'}])
        if request.method == 'GET' and request.url.path.endswith('/actions/runs'):
            return httpx.Response(200, json={'workflow_runs': [{'id': 5, 'conclusion': 'success', 'head_sha': 'abc'}]})
        if request.method == 'GET':
            return httpx.Response(self.readback, json=self.issues if self.readback == 200 else {'message': 'arranged'})
        body = json.loads(request.content)
        self.posts.append(body['body'])
        self.payloads.append(body)
        if self.mode == 'never':
            self.mode = 'ok'
            raise httpx.ReadError('arranged')
        if self.mode == 'refuse':
            return httpx.Response(422, json={'message': 'arranged'})
        number = len(self.issues) + 1
        issue = {**body, 'number': number, 'html_url': f'https://github.com/owner/throwaway/issues/{number}'}
        self.issues.append(issue)
        if self.mode == 'lose_ack':
            self.mode = 'ok'
            raise httpx.ReadError('arranged')
        return httpx.Response(201, json=issue)


async def main() -> None:
    github = FakeGithub()
    registry = ToolRegistry()
    transport = httpx.MockTransport(github)
    registry.register(github_issue_tool(transport, ENV, settle_seconds=()))
    registry.register(github_issue_tool(transport, ENV, settle_seconds=(), version=2))
    for tool in github_read_tools(transport, ENV):
        registry.register(tool)
    gateway = ToolGateway(registry)
    # Version 1, as a run whose grants pinned it before version 2 existed (US-15.14).
    granted = {TOOL_ID: 1}

    def issue(title: str) -> dict[str, str]:
        return {'title': title, 'body': f'About {title}'}

    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        async def value(sql: str, *values: object) -> Any:
            return (await (await db.execute(sql, values)).fetchone())[0]

        async def start() -> tuple[UUID, Any]:
            await db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null where status <> 'done'")
            binding = SimpleNamespace(session_id=None, expert_id=None, version=None, instructions='', tools={**PLAN_TOOLS, **granted})
            run = (await admit_run(db, workspace_id=WORKSPACE, actor_id=ACTOR, idempotency_key=str(uuid4()), goal_text='File it', limit_micro_usd=1_000_000, policy=resolve_role_policy(), binding=binding)).run_id
            return run, await claim_next(db, worker_id='connector', lease_seconds=120)

        async def approve(run: UUID) -> None:
            row = await (await db.execute('select id, argument_hash from public.approval_requests where run_id = %s order by created_at desc limit 1', (run,))).fetchone()
            await decide(db, workspace_id=WORKSPACE, actor_id=ACTOR, approval_id=row[0], idempotency_key=str(uuid4()), decision='approve', argument_hash=row[1])

        async def resumed(run: UUID) -> ToolScope:
            """An approval returns the run to the queue, and a worker claims it again."""
            lease = await claim_next(db, worker_id='connector', lease_seconds=120)
            assert lease is not None and lease.run_id == run, lease
            return ToolScope(WORKSPACE, run, lease.generation, granted)

        run, lease = await start()
        scope = ToolScope(WORKSPACE, run, lease.generation, granted)

        # Out of scope: refused by the gateway, with nothing sent.
        ungranted = await gateway.execute(db, ToolScope(WORKSPACE, run, lease.generation, {}), TOOL_ID, issue('ungranted'))
        check('a run without the grant is refused before any request', 'denied, 0 requests', (ungranted.outcome.value, ungranted.code, len(github.posts)), ungranted.outcome.value == 'denied' and not github.posts)
        wrong = await gateway.execute(db, ToolScope(WORKSPACE, run, lease.generation, {TOOL_ID: 3}), TOOL_ID, issue('version'))
        check('another version of the grant is refused too', 'denied, 0 requests', (wrong.outcome.value, wrong.code, len(github.posts)), wrong.outcome.value == 'denied' and not github.posts)
        elsewhere = await gateway.execute(db, scope, TOOL_ID, {**issue('elsewhere'), 'repository': 'other/repo'})
        check('an argument naming another repository is refused', 'invalid_arguments, 0 requests', (elsewhere.code, len(github.posts)), elsewhere.code == 'invalid_arguments' and not github.posts)
        receipts = await value('select count(*) from app_private.tool_receipts where run_id = %s', run)
        check('and none of those left a receipt', '0', receipts, receipts == 0)

        # Approval first, then exactly one effect, and a repeat comes from the receipt.
        pending = await gateway.execute(db, scope, TOOL_ID, issue('first'))
        check('a call waits for approval, with nothing sent', 'approval_pending, 0 requests', (pending.code, len(github.posts)), pending.code == 'approval_pending' and not github.posts)
        waiting = await (await db.execute("select outcome, code, finished_at is not null from app_private.tool_uses where run_id = %s order by sequence_in_run desc limit 1", (run,))).fetchone()
        completed = await value("select count(*) from public.run_events where run_id = %s and payload->>'type' = 'tool.use.completed' and payload->>'code' = 'approval_pending'", run)
        check('the waiting call is recorded as finished, denied approval_pending, with its completed event', "('denied', 'approval_pending', True), 1 event",
              (waiting, completed), waiting == ('denied', 'approval_pending', True) and completed == 1)
        await approve(run)
        scope = await resumed(run)
        done = await gateway.execute(db, scope, TOOL_ID, issue('first'))
        check('an approved call creates one issue', 'succeeded, 1 request', (done.outcome.value, done.output, len(github.posts)), done.outcome.value == 'succeeded' and done.output['number'] == 1 and len(github.posts) == 1)
        check('its marker is the receipt\'s operation ID', 'the marker, in the body', done.operation_id, marker(done.operation_id) in github.posts[0])
        repeat = await gateway.execute(db, scope, TOOL_ID, issue('first'))
        check('a repeat answers from the receipt and sends nothing', 'replayed, still 1 request', (repeat.replayed, len(github.posts)), repeat.replayed and repeat.output == done.output and len(github.posts) == 1)
        changed = await gateway.execute(db, scope, TOOL_ID, issue('changed'))
        check('changed arguments need their own approval', 'approval_pending, still 1 request', (changed.code, len(github.posts)), changed.code == 'approval_pending' and len(github.posts) == 1)

        # Uncertain outcomes, each settled by reading back.
        await approve(run)
        scope = await resumed(run)
        github.mode = 'lose_ack'
        lost = await gateway.execute(db, scope, TOOL_ID, issue('changed'))
        check('a lost reply is unknown, and not retried', 'unknown, 2 requests', (lost.outcome.value, lost.code, len(github.posts)), lost.outcome.value == 'unknown' and len(github.posts) == 2)
        github.readback = 500
        blind = await gateway.execute(db, scope, TOOL_ID, issue('changed'))
        check('while a readback fails, it stays unknown and sends nothing', 'unknown, 2 requests', (blind.outcome.value, len(github.posts)), blind.outcome.value == 'unknown' and len(github.posts) == 2)
        github.readback = 200
        settled = await gateway.execute(db, scope, TOOL_ID, issue('changed'))
        check('a readback finds it, so no second issue', 'succeeded, 2 issues in all, 2 requests', (settled.outcome.value, len(github.issues), len(github.posts)), settled.outcome.value == 'succeeded' and settled.output['number'] == 2 and len(github.issues) == 2 and len(github.posts) == 2)

        await gateway.execute(db, scope, TOOL_ID, issue('never'))
        await approve(run)
        scope = await resumed(run)
        github.mode = 'never'
        unsent = await gateway.execute(db, scope, TOOL_ID, issue('never'))
        check('a reply lost before it arrived is unknown too', 'unknown', unsent.outcome.value, unsent.outcome.value == 'unknown')
        retried = await gateway.execute(db, scope, TOOL_ID, issue('never'))
        check('a readback finding nothing allows one new attempt', 'succeeded, exactly 3 issues', (retried.outcome.value, len(github.issues)), retried.outcome.value == 'succeeded' and len(github.issues) == 3)

        await gateway.execute(db, scope, TOOL_ID, issue('refused'))
        await approve(run)
        scope = await resumed(run)
        github.mode = 'refuse'
        refused = await gateway.execute(db, scope, TOOL_ID, issue('refused'))
        github.mode = 'ok'
        check('a clear refusal fails, with its code on the receipt', 'github_refused_422', (refused.outcome.value, refused.code), refused.outcome.value == 'failed' and refused.code == 'github_refused_422')
        code = await value("select failure_code from app_private.tool_receipts where operation_id = %s", refused.operation_id)
        check('and the receipt says so', 'github_refused_422', code, code == 'github_refused_422')

        # Nothing durable holds the token.
        leaks = 0
        for table in ('app_private.tool_receipts', 'public.approval_requests', 'public.run_events'):
            leaks += await value(f"select count(*) from {table} t where t.run_id = %s and t::text like %s", run, f'%{TOKEN}%')
        check('no receipt, approval or event holds the token', '0', leaks, leaks == 0)

        # US-15.14: version 2's labels, and version 1 unchanged above.
        check('version 1 created its issues with a title and body only', 'no labels sent', [sorted(p) for p in github.payloads[:1]],
              all(set(payload) == {'title', 'body'} for payload in github.payloads))
        granted = {TOOL_ID: EXPERT_TOOLS[TOOL_ID]}
        check('new grants get version 2', '2', EXPERT_TOOLS[TOOL_ID], EXPERT_TOOLS[TOOL_ID] == 2)
        run, lease = await start()
        scope = ToolScope(WORKSPACE, run, lease.generation, granted)
        ten = [f'label-{index}' for index in range(10)]
        posted, approvals_before = len(github.posts), await value('select count(*) from public.approval_requests where run_id = %s', run)
        eleven = await gateway.execute(db, scope, TOOL_ID, {**issue('eleven'), 'labels': [*ten, 'one-too-many']})
        approvals_after = await value('select count(*) from public.approval_requests where run_id = %s', run)
        check('eleven labels are refused before any approval request or request to GitHub', 'invalid_arguments, no approval, no request',
              (eleven.code, approvals_after - approvals_before, len(github.posts) - posted),
              eleven.code == 'invalid_arguments' and approvals_after == approvals_before and len(github.posts) == posted)
        pending = await gateway.execute(db, scope, TOOL_ID, {**issue('labelled'), 'labels': ten})
        check('ten labels wait for approval', 'approval_pending', pending.code, pending.code == 'approval_pending')
        await approve(run)
        scope = await resumed(run)
        labelled = await gateway.execute(db, scope, TOOL_ID, {**issue('labelled'), 'labels': ten})
        check('approved, version 2 creates the issue with those labels', 'succeeded, the ten labels sent',
              (labelled.outcome.value, github.payloads[-1].get('labels')), labelled.outcome.value == 'succeeded' and github.payloads[-1].get('labels') == ten)

        # The four read tools: no approval, recorded as read-only tool uses, on the configured repository only.
        reads = {name: 1 for name in ('github_list_pull_requests', 'github_list_workflow_runs', 'github_search_issues', 'github_read_file')}
        run, lease = await start()
        scope = ToolScope(WORKSPACE, run, lease.generation, reads)
        github.seen.clear()
        calls = {'github_list_pull_requests': {'state': 'open', 'limit': 5}, 'github_list_workflow_runs': {'limit': 5},
                 'github_search_issues': {'query': 'arranged'}, 'github_read_file': {'path': 'README.md'}}
        results = {name: await gateway.execute(db, scope, name, arguments) for name, arguments in calls.items()}
        check('each read succeeds without an approval', 'four succeeded, none pending',
              {name: (result.outcome.value, result.code) for name, result in results.items()},
              all(result.outcome.value == 'succeeded' for result in results.values()))
        check('every request targets only the configured repository', 'repos/owner/throwaway or a search pinned to it',
              sorted({request.url.path for request in github.seen}),
              all(request.url.path.startswith('/repos/owner/throwaway/') or
                  (request.url.path == '/search/issues' and 'repo:owner/throwaway' in request.url.params['q']) for request in github.seen))
        rows = await (await db.execute("select tool_id, outcome, operation_id, tool_group, output_public from app_private.tool_uses "
                                       "where run_id = %s order by sequence_in_run", (run,))).fetchall()
        check('each is recorded as a read-only tool use, with no operation identity', 'four rows, succeeded, no operation ID, connectors',
              [(row[0], row[1], row[2], row[3]) for row in rows],
              len(rows) == 4 and all(row[1] == 'succeeded' and row[2] is None and row[3] == 'connectors' for row in rows))
        receipts = await value('select count(*) from app_private.tool_receipts where run_id = %s', run)
        approvals = await value('select count(*) from public.approval_requests where run_id = %s', run)
        check('and none left a receipt or an approval request', '0, 0', (receipts, approvals), receipts == 0 and approvals == 0)
        file_row = next(row for row in rows if row[0] == 'github_read_file')
        check("a read file's tool use keeps its SHA and size, never its content", "sha and size, no content",
              file_row[4], file_row[4].get('sha') == 'arranged-sha' and file_row[4].get('size') == len(FILE_TEXT) and 'content' not in file_row[4])
        listed = await list_tool_uses(db, WORKSPACE, run)
        listed_text = json.dumps([item.model_dump(mode='json') for item in listed.uses])
        events = await value("select count(*) from public.run_events where run_id = %s and payload::text like %s", run, '%' + FILE_TEXT[:20] + '%')
        check('its listing and run events never hold the text', 'digest and size only, 0 events',
              (FILE_TEXT[:20] in listed_text, events), FILE_TEXT[:20] not in listed_text and events == 0)
        repository = await gateway.execute(db, scope, 'github_list_pull_requests', {'repository': 'other/repo'})
        check('a read naming a repository is refused before any request', 'invalid_arguments, no new request',
              (repository.code, len(github.seen)), repository.code == 'invalid_arguments' and len(github.seen) == 4)


try:
    asyncio.run(main())
finally:
    print(json.dumps({'cases': cases}))
