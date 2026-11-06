"""The GitHub connector through the real gateway, approvals and receipts, with a fake GitHub. JSON cases."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import httpx
import psycopg

from autobots.adapters.github_issues import REPOSITORY_VARIABLE, TOKEN_VARIABLE, TOOL_ID, github_issue_tool, marker
from autobots.application.approvals import decide
from autobots.application.runs import admit_run
from autobots.application.tool_gateway import ToolGateway, ToolRegistry, ToolScope
from autobots.application.worker_leases import claim_next
from autobots.domain.models import resolve_role_policy
from autobots.domain.tools import EXPERT_TOOLS, PLAN_TOOLS

URL = os.environ['AUTOBOTS_DATABASE_URL']
WORKSPACE = UUID(sys.argv[1])
ACTOR = uuid4()
TOKEN = 'arranged-connector-token'
ENV = {REPOSITORY_VARIABLE: 'owner/throwaway', TOKEN_VARIABLE: TOKEN}
cases = []


def check(name: str, expected: str, observed: object, passed: bool) -> None:
    cases.append({'id': name, 'expected': expected, 'observed': str(observed), 'passed': bool(passed)})


class FakeGithub:
    """`mode` is what the next create does: ok, lose_ack (created, reply lost) or never (lost before it)."""

    def __init__(self) -> None:
        self.mode, self.readback = 'ok', 200
        self.posts: list[str] = []
        self.issues: list[dict[str, Any]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.method == 'GET':
            return httpx.Response(self.readback, json=self.issues if self.readback == 200 else {'message': 'arranged'})
        body = json.loads(request.content)
        self.posts.append(body['body'])
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
    registry.register(github_issue_tool(httpx.MockTransport(github), ENV))
    gateway = ToolGateway(registry)
    granted = {TOOL_ID: EXPERT_TOOLS[TOOL_ID]}

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
        wrong = await gateway.execute(db, ToolScope(WORKSPACE, run, lease.generation, {TOOL_ID: 2}), TOOL_ID, issue('version'))
        check('another version of the grant is refused too', 'denied, 0 requests', (wrong.outcome.value, wrong.code, len(github.posts)), wrong.outcome.value == 'denied' and not github.posts)
        elsewhere = await gateway.execute(db, scope, TOOL_ID, {**issue('elsewhere'), 'repository': 'other/repo'})
        check('an argument naming another repository is refused', 'invalid_arguments, 0 requests', (elsewhere.code, len(github.posts)), elsewhere.code == 'invalid_arguments' and not github.posts)
        receipts = await value('select count(*) from app_private.tool_receipts where run_id = %s', run)
        check('and none of those left a receipt', '0', receipts, receipts == 0)

        # Approval first, then exactly one effect, and a repeat comes from the receipt.
        pending = await gateway.execute(db, scope, TOOL_ID, issue('first'))
        check('a call waits for approval, with nothing sent', 'approval_pending, 0 requests', (pending.code, len(github.posts)), pending.code == 'approval_pending' and not github.posts)
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


try:
    asyncio.run(main())
finally:
    print(json.dumps({'cases': cases}))
