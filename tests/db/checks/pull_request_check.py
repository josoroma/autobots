"""US-15.15: github_open_pull_request through the real gateway and approvals, with a fake GitHub
that keeps branches, commits and pull requests in memory. No request reaches GitHub. JSON cases.

A worker that loses the run while it reads GitHub leaves the person's decision as it was (refactor
plan R-21, PADP-02).
"""
from __future__ import annotations

import base64
import json
import os
import sys
from collections.abc import Awaitable, Callable
from types import SimpleNamespace
from typing import Any
from urllib.parse import unquote
from uuid import UUID, uuid4

import httpx
import psycopg
from autobots.adapters.github_issues import marker
from autobots.adapters.github_pulls import TOOL_ID, branch_for, github_pull_request_tool
from autobots.application.approvals import DEFAULT_TTL_SECONDS, decide, list_approvals
from autobots.application.runs import admit_run
from autobots.application.tool_definitions import ToolRegistry, ToolScope
from autobots.application.tool_gateway import ToolGateway
from autobots.application.worker_leases import Lease, claim_next, claim_run
from autobots.contracts.approvals import ApprovalReviewDetail
from autobots.domain.models import resolve_role_policy
from autobots.domain.tools import PLAN_TOOLS
from autobots.persistence.rows import ApprovalListRow
from checklib import Cases, run_check

URL = os.environ['AUTOBOTS_DATABASE_URL']
WORKSPACE = UUID(sys.argv[1])
ACTOR = uuid4()
REPO = 'owner/throwaway'
ENV = {'GITHUB_REPOSITORY': REPO, 'GITHUB_TOKEN': 'arranged-pull-token'}
DECISION = ("select status, decided_by, decided_at, review_detail ->> 'base_sha', expires_at "
            'from public.approval_requests where run_id = %s')


class FakeGit:
    """Branches, commits with their files, and pull requests. `lose_pull` creates the next pull
    request and then loses the reply. `on_base_read` runs once, the next time main's head is read,
    before that reply returns."""

    def __init__(self) -> None:
        self.files = {'base-1': {'README.md': 'Hello\n', 'src/app.py': 'print(1)\n'}}
        self.heads = {'main': 'base-1'}
        self.trees: dict[str, dict[str, str]] = {}
        self.pulls: list[dict[str, Any]] = []
        self.requests: list[httpx.Request] = []
        self.lose_pull = False
        self.on_base_read: Callable[[], Awaitable[None]] | None = None

    def writes(self) -> list[str]:
        return [f'{r.method} {r.url.path}' for r in self.requests if r.method != 'GET']

    @staticmethod
    async def after(hook: Callable[[], Awaitable[None]], reply: httpx.Response) -> httpx.Response:
        await hook()
        return reply

    def __call__(self, request: httpx.Request) -> httpx.Response | Awaitable[httpx.Response]:
        """httpx.MockTransport awaits a reply that isn't a Response yet, which is how a hook runs."""
        self.requests.append(request)
        path = unquote(request.url.path).removeprefix(f'/repos/{REPO}')
        if request.method == 'GET' and path.startswith('/git/ref/heads/'):
            branch = path.removeprefix('/git/ref/heads/')
            head = self.heads.get(branch)
            reply = httpx.Response(200, json={'object': {'sha': head}}) if head else httpx.Response(404, json={})
            if branch == 'main' and self.on_base_read is not None:
                hook, self.on_base_read = self.on_base_read, None
                return self.after(hook, reply)
            return reply
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


async def main(cases: Cases) -> None:
    check = cases.check
    git = FakeGit()
    registry = ToolRegistry()
    registry.register(github_pull_request_tool(httpx.MockTransport(git), ENV))
    gateway = ToolGateway(registry)
    granted = {TOOL_ID: 1}
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        async def row(sql: str, *values: object) -> tuple[Any, ...]:
            return tuple((await (await db.execute(sql, values)).fetchone()) or ())

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

        async def shown(run: UUID) -> ApprovalListRow:
            items = [item for item in await list_approvals(db, WORKSPACE, ('pending', 'approved')) if item.run_id == run]
            return items[0]

        # The approval shows each file's diff, and nothing has written.
        run, scope = await start()
        pending = await gateway.execute(db, scope, TOOL_ID, proposal('Tidy the readme'))
        item = await shown(run)
        detail = ApprovalReviewDetail.model_validate(item.review_detail)
        arguments = json.loads(item.arguments)
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
        with cases.scenario('a moved base'):
            run, scope = await start()
            await gateway.execute(db, scope, TOOL_ID, proposal('Moved base'))
            scope = await approve(run)
            git.files['base-2'] = {'README.md': 'Hello, changed upstream\n', 'src/app.py': 'print(2)\n'}
            git.heads['main'] = 'base-2'
            writes_before, pulls_before = len(git.writes()), len(git.pulls)
            moved = await gateway.execute(db, scope, TOOL_ID, proposal('Moved base'))
            again = await shown(run)
            renewed = ApprovalReviewDetail.model_validate(again.review_detail)
            readme = next(f for f in renewed.files if f.path == 'README.md')
            check('a moved base stops with base_moved and opens nothing', 'failed base_moved, no writes, no pull',
                  (moved.outcome.value, moved.code, len(git.writes()) - writes_before, len(git.pulls) - pulls_before),
                  moved.code == 'base_moved' and len(git.writes()) == writes_before and len(git.pulls) == pulls_before)
            check('the new approval shows the diff against the new head', 'pending, base-2, a diff from the upstream text',
                  (again.status, renewed.base_sha, readme.diff[:120]),
                  again.status == 'pending' and renewed.base_sha == 'base-2' and '-Hello, changed upstream' in readme.diff)
            # The run keeps running, and enters the decision wait when the call is tried again (Decision 0028 E1).
            check('after a moved base the run keeps running with its request pending, and waits only on a retry',
                  'running, pending',
                  await row('select r.status, a.status from public.runs r join public.approval_requests a on a.run_id = r.id '
                            'where r.id = %s', run),
                  lambda seen: seen == ('running', 'pending'))
            # One TTL for every return to pending, and the attempt settled so the next approval can send (R-21).
            check('the renewed request expires after DEFAULT_TTL_SECONDS, and the attempt is settled as base_moved',
                  f'expires in ({DEFAULT_TTL_SECONDS - 120}, {DEFAULT_TTL_SECONDS}] s; receipt failed, base_moved, reconciled',
                  await row('select extract(epoch from a.expires_at - clock_timestamp())::int, r.status, r.failure_code, '
                            'r.reconciled_at is not null from public.approval_requests a '
                            'join app_private.tool_receipts r on r.operation_id = a.operation_id where a.run_id = %s', run),
                  lambda seen: bool(seen) and DEFAULT_TTL_SECONDS - 120 < seen[0] <= DEFAULT_TTL_SECONDS
                  and seen[1:] == ('failed', 'base_moved', True))
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

        # The base moves, and while this worker reads GitHub its lease runs out and another worker
        # claims the run. The stale worker is refused before it changes anything (R-21, PADP-02).
        with cases.scenario('a lease lost during the reads'):
            run, scope = await start()
            await gateway.execute(db, scope, TOOL_ID, proposal('Stale owner'))
            scope = await approve(run)
            git.files['base-3'] = {'README.md': 'Hello, moved again\n', 'src/app.py': 'print(3)\n'}
            git.heads['main'] = 'base-3'
            decided = await row(DECISION, run)
            requested = await value("select count(*) from public.run_events where run_id = %s and payload ->> 'type' = 'approval.requested'", run)
            taken: list[Lease | None] = []

            async def take_over() -> None:
                async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as other:
                    await other.execute("update app_private.run_jobs set lease_expires_at = clock_timestamp() - interval '1 second' "
                                        'where run_id = %s', (run,))
                    taken.append(await claim_run(other, run, worker_id='pull-request-next', lease_seconds=120))

            git.on_base_read = take_over
            writes_before = len(git.writes())
            stale = await gateway.execute(db, scope, TOOL_ID, proposal('Stale owner'))
            newer = [lease.generation for lease in taken if lease is not None]
            check('a worker that lost the run while reading GitHub is refused, and writes nothing there',
                  f'lease_lost, 0 writes, another worker at a generation above {scope.generation}',
                  (stale.code, len(git.writes()) - writes_before, newer),
                  lambda seen: seen[0] == 'lease_lost' and seen[1] == 0 and len(seen[2]) == 1 and seen[2][0] > scope.generation)
            check("and leaves the person's decision as it was", f'unchanged: {decided}', await row(DECISION, run),
                  lambda seen: seen == decided and bool(decided) and decided[0] == 'approved')
            check('it settles no receipt, requests no new approval and leaves no gap in the event sequence',
                  f'receipt unreconciled; {requested} approval.requested; events = last sequence = event_sequence',
                  (await row('select status, reconciled_at is null from app_private.tool_receipts where run_id = %s', run),
                   await row("select count(*) filter (where payload ->> 'type' = 'approval.requested'), count(*), max(sequence), "
                             '(select event_sequence from public.runs where id = %s) from public.run_events where run_id = %s', run, run)),
                  lambda seen: seen[0][1:] == (True,) and seen[1][0] == requested and seen[1][1] == seen[1][2] == seen[1][3])
            # The attempt the lease refused wrote nothing, so the person's decision still stands for the
            # worker that owns the run now, which finds the base still moved and asks again.
            if newer:
                retried = await gateway.execute(db, ToolScope(WORKSPACE, run, newer[0], granted), TOOL_ID, proposal('Stale owner'))
                check("the run's new owner can use the decision the refused attempt left, and finds the base moved",
                      'base_moved, request pending again (not approval_consumed)',
                      (retried.code, (await row(DECISION, run) or ('',))[0]),
                      lambda seen: seen == ('base_moved', 'pending'))
            # The worker that claimed it lets go, so no later check can take this run.
            await db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null "
                             'where run_id = %s', (run,))


run_check(main, secrets=(ENV['GITHUB_TOKEN'],))
