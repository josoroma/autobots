"""US-15.15: github_open_pull_request through the real gateway and approvals, with a fake GitHub
that keeps branches, commits and pull requests in memory. No request reaches GitHub. JSON cases."""
from __future__ import annotations

import asyncio
import base64
import json
import os
import sys
from types import SimpleNamespace
from typing import Any
from urllib.parse import unquote
from uuid import UUID, uuid4

import httpx
import psycopg
from autobots.adapters.github_issues import marker
from autobots.adapters.github_pulls import TOOL_ID, branch_for, github_pull_request_tool
from autobots.application.approvals import decide, list_approvals
from autobots.application.runs import admit_run
from autobots.application.tool_gateway import ToolGateway, ToolRegistry, ToolScope
from autobots.application.worker_leases import claim_next
from autobots.contracts.approvals import ApprovalReviewDetail
from autobots.domain.models import resolve_role_policy
from autobots.domain.tools import PLAN_TOOLS

URL = os.environ['AUTOBOTS_DATABASE_URL']
WORKSPACE = UUID(sys.argv[1])
ACTOR = uuid4()
REPO = 'owner/throwaway'
ENV = {'GITHUB_REPOSITORY': REPO, 'GITHUB_TOKEN': 'arranged-pull-token'}
cases: list[dict[str, Any]] = []


def check(name: str, expected: str, observed: object, passed: bool) -> None:
    cases.append({'id': name, 'expected': expected, 'observed': str(observed)[:600], 'passed': bool(passed)})


class FakeGit:
    """Branches, commits with their files, and pull requests. `lose_pull` creates the next pull
    request and then loses the reply."""

    def __init__(self) -> None:
        self.files = {'base-1': {'README.md': 'Hello\n', 'src/app.py': 'print(1)\n'}}
        self.heads = {'main': 'base-1'}
        self.trees: dict[str, dict[str, str]] = {}
        self.pulls: list[dict[str, Any]] = []
        self.requests: list[httpx.Request] = []
        self.lose_pull = False

    def writes(self) -> list[str]:
        return [f'{r.method} {r.url.path}' for r in self.requests if r.method != 'GET']

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = unquote(request.url.path).removeprefix(f'/repos/{REPO}')
        if request.method == 'GET' and path.startswith('/git/ref/heads/'):
            head = self.heads.get(path.removeprefix('/git/ref/heads/'))
            return httpx.Response(200, json={'object': {'sha': head}}) if head else httpx.Response(404, json={})
        if request.method == 'GET' and path.startswith('/contents/'):
            content = self.files.get(request.url.params['ref'], {}).get(path.removeprefix('/contents/'))
            if content is None:
                return httpx.Response(404, json={})
            return httpx.Response(200, json={'type': 'file', 'sha': 'blob', 'size': len(content),
                                             'content': base64.b64encode(content.encode()).decode()})
        if request.method == 'GET' and path.startswith('/git/commits/'):
            return httpx.Response(200, json={'sha': path.removeprefix('/git/commits/'), 'tree': {'sha': f"tree-of-{path.removeprefix('/git/commits/')}"}})
        if request.method == 'GET' and path == '/pulls':
            branch = request.url.params['head'].split(':', 1)[1]
            return httpx.Response(200, json=[p for p in self.pulls if p['head']['ref'] == branch])
        body = json.loads(request.content)
        if path == '/git/trees':
            tree = f'tree-{len(self.trees) + 1}'
            self.trees[tree] = {entry['path']: entry['content'] for entry in body['tree']}
            return httpx.Response(201, json={'sha': tree})
        if path == '/git/commits':
            commit = f'commit-{len(self.files)}'
            self.files[commit] = {**self.files[body['parents'][0]], **self.trees[body['tree']]}
            return httpx.Response(201, json={'sha': commit})
        if path == '/git/refs':
            self.heads[body['ref'].removeprefix('refs/heads/')] = body['sha']
            return httpx.Response(201, json={'ref': body['ref']})
        if path == '/pulls':
            number = len(self.pulls) + 1
            pull = {'number': number, 'html_url': f'https://github.com/{REPO}/pull/{number}', 'body': body['body'],
                    'base': body['base'], 'head': {'ref': body['head'], 'sha': self.heads[body['head']]}}
            self.pulls.append(pull)
            if self.lose_pull:
                self.lose_pull = False
                raise httpx.ReadError('arranged lost reply')
            return httpx.Response(201, json=pull)
        return httpx.Response(599)


def proposal(title: str, base: str = 'main', **extra: Any) -> dict[str, Any]:
    return {'title': title, 'body': f'Why: {title}', 'base': base,
            'files': [{'path': 'README.md', 'content': 'Hello, reviewed\n'}, {'path': 'docs/new.md', 'content': '# New\n'}], **extra}


async def main() -> None:
    git = FakeGit()
    registry = ToolRegistry()
    registry.register(github_pull_request_tool(httpx.MockTransport(git), ENV))
    gateway = ToolGateway(registry)
    granted = {TOOL_ID: 1}
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        async def value(sql: str, *values: object) -> Any:
            return (await (await db.execute(sql, values)).fetchone())[0]

        async def start() -> tuple[UUID, ToolScope]:
            await db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null where status <> 'done'")
            binding = SimpleNamespace(session_id=None, expert_id=None, version=None, instructions='', tools={**PLAN_TOOLS, **granted})
            run = (await admit_run(db, workspace_id=WORKSPACE, actor_id=ACTOR, idempotency_key=str(uuid4()), goal_text='Propose it',
                                   limit_micro_usd=1_000_000, policy=resolve_role_policy(), binding=binding)).run_id
            lease = await claim_next(db, worker_id='pull-request', lease_seconds=120)
            return run, ToolScope(WORKSPACE, run, lease.generation, granted)

        async def approve(run: UUID) -> ToolScope:
            row = await (await db.execute("select id, argument_hash from public.approval_requests where run_id = %s and status = 'pending' "
                                          "order by created_at desc limit 1", (run,))).fetchone()
            await decide(db, workspace_id=WORKSPACE, actor_id=ACTOR, approval_id=row[0], idempotency_key=str(uuid4()), decision='approve', argument_hash=row[1])
            lease = await claim_next(db, worker_id='pull-request', lease_seconds=120)
            assert lease is not None and lease.run_id == run, lease
            return ToolScope(WORKSPACE, run, lease.generation, granted)

        async def shown(run: UUID) -> dict[str, Any]:
            items = [item for item in await list_approvals(db, WORKSPACE, ('pending', 'approved')) if item['run_id'] == run]
            return items[0]

        # The approval shows each file's diff, and nothing has written.
        run, scope = await start()
        pending = await gateway.execute(db, scope, TOOL_ID, proposal('Tidy the readme'))
        item = await shown(run)
        detail = ApprovalReviewDetail.model_validate(item['review_detail'])
        arguments = json.loads(item['arguments'])
        files = {f.path: f for f in detail.files}
        check('a proposal waits for approval', 'approval_pending', pending.code, pending.code == 'approval_pending')
        check('the request shows the title, the base branch and each file\'s diff against the base', 'title, main at base-1, a modified and an added diff',
              (arguments['title'], detail.base_branch, detail.base_sha, {p: f.change for p, f in files.items()}),
              arguments['title'] == 'Tidy the readme' and detail.base_branch == 'main' and detail.base_sha == 'base-1'
              and files['README.md'].change == 'modified' and '-Hello' in files['README.md'].diff and '+Hello, reviewed' in files['README.md'].diff
              and files['docs/new.md'].change == 'added' and '+# New' in files['docs/new.md'].diff)
        check('no request that writes has been sent', 'only reads', git.writes(), git.writes() == [])

        # Bounded changes, refused before any approval request or request.
        sent, approvals = len(git.requests), await value('select count(*) from public.approval_requests where run_id = %s', run)
        many = proposal('Too many', files=[{'path': f'f{n}.txt', 'content': 'x'} for n in range(21)])
        large = proposal('Too large', files=[{'path': 'a.txt', 'content': 'x' * 600_000}, {'path': 'b.txt', 'content': 'y' * 600_000}])
        elsewhere = {**proposal('Elsewhere'), 'repository': 'other/repo'}
        refused = [await gateway.execute(db, scope, TOOL_ID, arguments) for arguments in (many, large, elsewhere)]
        after = await value('select count(*) from public.approval_requests where run_id = %s', run)
        check('21 files, more than 1 MiB and a repository argument are each refused before anything', 'invalid_arguments x3, no approval, no request',
              ([r.code for r in refused], after - approvals, len(git.requests) - sent),
              all(r.code == 'invalid_arguments' for r in refused) and after == approvals and len(git.requests) == sent)

        # Approved: its own branch, only the named paths, the marker, and no merge.
        scope = await approve(run)
        opened = await gateway.execute(db, scope, TOOL_ID, proposal('Tidy the readme'))
        branch = branch_for(opened.operation_id)
        tree = next(iter(git.trees.values())) if git.trees else {}
        pull = git.pulls[0] if git.pulls else {}
        check('it creates its branch autobots/<operation_id>', 'succeeded, the branch exists',
              (opened.outcome.value, branch in git.heads), opened.outcome.value == 'succeeded' and branch in git.heads and opened.output['branch'] == branch)
        check('it commits only the named paths', 'README.md and docs/new.md', sorted(tree), sorted(tree) == ['README.md', 'docs/new.md'])
        check('it opens the pull request with the operation ID as a marker', 'the marker in its body, base main',
              (pull.get('base'), marker(opened.operation_id) in pull.get('body', '')), pull.get('base') == 'main' and marker(opened.operation_id) in pull.get('body', ''))
        merges = [w for w in git.writes() if 'merge' in w]
        check('and offers no merge', 'no merge request, and no merge input', (merges, sorted(registry.get(TOOL_ID, 1).input_model.model_fields)),
              not merges and not any('merge' in name for name in registry.get(TOOL_ID, 1).input_model.model_fields))

        # A lost reply: the retry reads back the branch and its pull request, and opens no second.
        run, scope = await start()
        await gateway.execute(db, scope, TOOL_ID, proposal('Lost reply'))
        scope = await approve(run)
        git.lose_pull = True
        lost = await gateway.execute(db, scope, TOOL_ID, proposal('Lost reply'))
        posts_before = len([w for w in git.writes() if w.endswith('/pulls')])
        reads_before = len(git.requests)
        retried = await gateway.execute(db, scope, TOOL_ID, proposal('Lost reply'))
        read_back = [f'{r.method} {unquote(r.url.path)}' for r in git.requests[reads_before:]]
        posts_after = len([w for w in git.writes() if w.endswith('/pulls')])
        check('a lost reply is unknown', 'unknown', lost.outcome.value, lost.outcome.value == 'unknown')
        check('the retry reads back first and returns the existing pull request', 'succeeded, replayed, pull 2, no new write',
              (retried.outcome.value, retried.replayed, retried.output and retried.output['number'], read_back),
              retried.outcome.value == 'succeeded' and retried.replayed and retried.output['number'] == 2
              and all(line.startswith('GET') for line in read_back) and posts_after == posts_before)
        check('and opens no second one', 'exactly 2 pull requests in all', len(git.pulls), len(git.pulls) == 2)

        # A moved base: base_moved, nothing opened, and a new approval against the new head.
        run, scope = await start()
        await gateway.execute(db, scope, TOOL_ID, proposal('Moved base'))
        scope = await approve(run)
        git.files['base-2'] = {'README.md': 'Hello, changed upstream\n', 'src/app.py': 'print(2)\n'}
        git.heads['main'] = 'base-2'
        writes_before, pulls_before = len(git.writes()), len(git.pulls)
        moved = await gateway.execute(db, scope, TOOL_ID, proposal('Moved base'))
        again = await shown(run)
        renewed = ApprovalReviewDetail.model_validate(again['review_detail'])
        readme = next(f for f in renewed.files if f.path == 'README.md')
        check('a moved base stops with base_moved and opens nothing', 'failed base_moved, no writes, no pull',
              (moved.outcome.value, moved.code, len(git.writes()) - writes_before, len(git.pulls) - pulls_before),
              moved.code == 'base_moved' and len(git.writes()) == writes_before and len(git.pulls) == pulls_before)
        check('the new approval shows the diff against the new head', 'pending, base-2, a diff from the upstream text',
              (again['status'], renewed.base_sha, readme.diff[:120]),
              again['status'] == 'pending' and renewed.base_sha == 'base-2' and '-Hello, changed upstream' in readme.diff)
        # The model asks again, which waits on the renewed request, and a person approves it.
        waiting = await gateway.execute(db, scope, TOOL_ID, proposal('Moved base'))
        check('asking again waits on the renewed request', 'approval_pending', waiting.code, waiting.code == 'approval_pending')
        scope = await approve(run)
        reopened = await gateway.execute(db, scope, TOOL_ID, proposal('Moved base'))
        check('approved again, it opens against the new head', 'succeeded, on base-2',
              (reopened.outcome.value, reopened.code), reopened.outcome.value == 'succeeded' and git.files.get(git.heads[reopened.output['branch']], {}).get('src/app.py') == 'print(2)\n')
        leaks = 0
        for table in ('app_private.tool_receipts', 'public.approval_requests', 'public.run_events'):
            leaks += await value(f"select count(*) from {table} t where t.run_id = %s and t::text like %s", run, '%arranged-pull-token%')
        check('no receipt, approval or event holds the token', '0', leaks, leaks == 0)


try:
    asyncio.run(main())
finally:
    print(json.dumps({'cases': cases}))
