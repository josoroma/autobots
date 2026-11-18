"""US-14.18 and Decision 0025: Settings → Keys & vars, the GitHub pair, the approval binding and the
browsing switch per workspace. JSON cases.

Runs on a disposable database with a fake GitHub transport and no model, so no request leaves this
process and every token is a fixture. The executor's qualification is arranged in this process
only, as the scenarios say "an executor that reports qualified".
"""
from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import httpx
import psycopg
from autobots.adapters import tool_registry
from autobots.adapters.github_issues import github_issue_tool
from autobots.adapters.github_pulls import github_pull_request_tool
from autobots.adapters.github_reads import github_read_tools
from autobots.application import browsing_tool
from autobots.application.approvals import decide
from autobots.application.credentials.master_key import create_master_key
from autobots.application.experts import ExpertRefused, create_expert
from autobots.application.provider_settings import InvalidKey, ProviderContext, StaleVersion
from autobots.application.runs import admit_run
from autobots.application.tool_catalog import ToolsUnavailable
from autobots.application.tool_definitions import ToolRegistry, ToolScope
from autobots.application.tool_gateway import ToolGateway
from autobots.application.tool_key_settings import ToolKeySettings
from autobots.application.tool_keys import key_sources
from autobots.application.worker_inference import CatalogCache, InferenceSource, frozen_policy
from autobots.application.worker_leases import claim_next
from autobots.contracts.experts import ExpertConfig
from autobots.domain.models import PROFILES
from autobots.domain.tools import PLAN_TOOLS

URL = os.environ['AUTOBOTS_DATABASE_URL']
WORKSPACE_A = UUID(sys.argv[1])
ENV_TOKEN = 'github_pat_fixtureEnvironment0001'
SAVED_TOKEN = 'github_pat_fixtureSavedInSettings01'
SECRETS = (ENV_TOKEN, SAVED_TOKEN)
POLICY = frozen_policy({'version': 1, 'bindings': {'executor': 'openrouter_terra', 'researcher': 'openrouter_sol'}})
CATALOG = {'data': [{'id': p.wire_id, 'canonical_slug': p.canonical_id, 'supported_parameters': ['max_tokens', 'tools', 'tool_choice'],
                     'pricing': {'prompt': '0.000002', 'completion': '0.00001'}} for p in PROFILES.values()]}
cases: list[dict[str, Any]] = []


def check(name: str, expected: str, observed: object, passed: bool) -> None:
    cases.append({'id': name, 'expected': expected, 'observed': str(observed)[:700], 'passed': bool(passed)})


def token_label(header: str) -> str:
    token = header.removeprefix('Bearer ')
    return {ENV_TOKEN: 'environment token', SAVED_TOKEN: 'saved token'}.get(token, 'other')


class FakeGithub:
    """Answers the few reads and writes these tools make, and records each request's repository."""

    def __init__(self) -> None:
        self.requests: list[tuple[str, str, str]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        parts = request.url.path.split('/')
        repository = '/'.join(parts[2:4]) if len(parts) > 3 and parts[1] == 'repos' else ''
        self.requests.append((request.method, repository, token_label(request.headers.get('Authorization', ''))))
        rest = '/' + '/'.join(parts[4:])
        if request.method == 'GET' and rest == '/pulls':
            return httpx.Response(200, json=[])
        if request.method == 'GET' and rest == '/issues':
            return httpx.Response(200, json=[])
        if request.method == 'POST' and rest == '/issues':
            return httpx.Response(201, json={'number': 7, 'html_url': f'https://github.com/{repository}/issues/7'})
        if request.method == 'GET' and rest.startswith('/git/ref/heads/'):
            return httpx.Response(200, json={'object': {'sha': 'base-1'}})
        return httpx.Response(404, json={})


async def main() -> None:
    log = io.StringIO()
    logging.getLogger().addHandler(logging.StreamHandler(log))
    logging.getLogger().setLevel(logging.DEBUG)
    home = Path(tempfile.mkdtemp(prefix='autobots-keys-and-vars-'))
    key_file = home / 'secrets/master.key'
    create_master_key(key_file)
    config_root = home / 'config'
    config_root.mkdir()
    dotenv = config_root / '.env'
    dotenv.write_text('GITHUB_REPOSITORY=owner/dotenv\n')
    dotenv_before = dotenv.read_bytes()
    environ = {'GITHUB_REPOSITORY': 'owner/environment', 'GITHUB_TOKEN': ENV_TOKEN, 'AUTOBOTS_CONFIG_ROOT': str(config_root),
               'AUTOBOTS_PROVIDER_MASTER_KEY_FILE': str(key_file), 'NODE_ENV': 'development'}
    github = FakeGithub()
    registry = ToolRegistry()
    for tool in (*github_read_tools(httpx.MockTransport(github), environ), github_issue_tool(httpx.MockTransport(github), environ),
                 github_pull_request_tool(httpx.MockTransport(github), environ)):
        registry.register(tool)
    gateway = ToolGateway(registry)
    granted = {'github_list_pull_requests': 1, 'create_github_issue': 1, 'github_open_pull_request': 1}
    actor = uuid4()
    runs: list[UUID] = []
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        other = uuid4()
        await db.execute("insert into public.workspaces (id, name) values (%s, 'Keys and vars other')", (other,))
        await db.execute("update app_private.provider_credentials set status = 'deleted' "
                         "where workspace_id = %s and provider in ('tavily', 'jina', 'github') and status = 'active'", (WORKSPACE_A,))
        await db.execute('update app_private.tool_key_settings set value = null where workspace_id = %s', (WORKSPACE_A,))
        settings = ToolKeySettings(db, key_file, environ)

        async def state(workspace: UUID) -> dict[str, tuple[str | None, str | None, int]]:
            return {s.name: (s.source, s.value, s.version) for s in await settings.status(workspace)}

        async def start(workspace: UUID, tools: dict[str, int]) -> ToolScope:
            await db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null "
                             "where status <> 'done'")
            binding = SimpleNamespace(session_id=None, expert_id=None, version=None, instructions='', tools={**PLAN_TOOLS, **tools})
            run = (await admit_run(db, workspace_id=workspace, actor_id=actor, idempotency_key=str(uuid4()), goal_text='keys and vars',
                                   limit_micro_usd=1_000_000, policy=POLICY, binding=binding)).run_id
            runs.append(run)
            lease = await claim_next(db, worker_id='keys-and-vars', lease_seconds=120)
            assert lease is not None and lease.run_id == run
            return ToolScope(workspace, run, lease.generation, tools)

        async def approve(scope: ToolScope) -> ToolScope:
            row = await (await db.execute("select id, argument_hash from public.approval_requests where run_id = %s and status = 'pending' "
                                          "order by created_at desc limit 1", (scope.run_id,))).fetchone()
            await decide(db, workspace_id=scope.workspace_id, actor_id=actor, approval_id=row[0], idempotency_key=str(uuid4()),
                         decision='approve', argument_hash=row[1])
            lease = await claim_next(db, worker_id='keys-and-vars', lease_seconds=120)
            assert lease is not None and lease.run_id == scope.run_id, lease
            return ToolScope(scope.workspace_id, scope.run_id, lease.generation, scope.tools)

        async def read(workspace: UUID) -> tuple[str, str, str | None]:
            scope = await start(workspace, {'github_list_pull_requests': 1})
            github.requests.clear()
            result = await gateway.execute(db, scope, 'github_list_pull_requests', {})
            _method, repository, token = github.requests[-1] if github.requests else ('', '', 'none')
            return repository, token, result.code

        # Settings, then the environment, then .env; checks without a provider request.
        before = await state(WORKSPACE_A)
        check('with nothing saved, the repository and token come from the environment',
              'github_repository environment owner/environment, github_token environment and no value', (before['github_repository'], before['github_token']),
              before['github_repository'][:2] == ('environment', 'owner/environment') and before['github_token'][:2] == ('environment', None))
        bare = {**environ, 'GITHUB_REPOSITORY': ' '}
        dotenv_only = next(item for item in await ToolKeySettings(db, key_file, bare).status(WORKSPACE_A) if item.name == 'github_repository')
        check('a blank process value falls through to the configuration root .env',
              'github_repository environment owner/dotenv', (dotenv_only.source, dotenv_only.value),
              (dotenv_only.source, dotenv_only.value) == ('environment', 'owner/dotenv'))
        github.requests.clear()
        refused = []
        for name, value in (('github_token', 'has a space'), ('github_repository', 'not a repository'),
                            ('github_repository', 'https://evil.example/owner/repo'), ('browser_executor', 'on')):
            try:
                await settings.save(WORKSPACE_A, name, value, before[name][2])
                refused.append('saved')
            except InvalidKey:
                refused.append('refused')
        stale = None
        try:
            await settings.save(WORKSPACE_A, 'github_repository', 'owner/stale', before['github_repository'][2] + 5)
        except StaleVersion as error:
            stale = error.code
        check('malformed values and a stale version are refused, with no provider request',
              "4 refused, stale_version, 0 requests", (refused, stale, len(github.requests)),
              refused == ['refused'] * 4 and stale == 'stale_version' and github.requests == [])
        await settings.save(WORKSPACE_A, 'github_repository', 'owner/saved', before['github_repository'][2])
        await settings.save(WORKSPACE_A, 'github_token', SAVED_TOKEN, before['github_token'][2])
        saved = await state(WORKSPACE_A)
        check('saving advances each version, shows the value and never the token',
              'repository settings owner/saved, token settings and no value',
              (saved['github_repository'], saved['github_token']),
              saved['github_repository'] == ('settings', 'owner/saved', before['github_repository'][2] + 1)
              and saved['github_token'] == ('settings', None, before['github_token'][2] + 1))

        # GitHub tools resolve the token and repository per attempt from the run's workspace.
        mine, theirs = await read(WORKSPACE_A), await read(other)
        check("each workspace's read uses its own repository and token",
              "('owner/saved', 'saved token') and ('owner/environment', 'environment token')", (mine, theirs),
              mine == ('owner/saved', 'saved token', None) and theirs == ('owner/environment', 'environment token', None))
        await settings.remove(WORKSPACE_A, 'github_repository', saved['github_repository'][2])
        await settings.remove(WORKSPACE_A, 'github_token', saved['github_token'][2])
        after = await read(WORKSPACE_A)
        check('after removal, the next call uses the environment, and .env is unchanged',
              "('owner/environment', 'environment token'), .env unchanged", (after, dotenv.read_bytes() == dotenv_before),
              after == ('owner/environment', 'environment token', None) and dotenv.read_bytes() == dotenv_before)

        # An approved GitHub write keeps its repository.
        version = (await state(WORKSPACE_A))['github_repository'][2]
        await settings.save(WORKSPACE_A, 'github_repository', 'owner/a', version)
        issue = {'title': 'Bound', 'body': 'b'}
        pull = {'title': 'Bound', 'body': 'b', 'base': 'main', 'files': [{'path': 'docs/new.md', 'content': '# New\n'}]}
        scope = await start(WORKSPACE_A, granted)
        waiting = [(await gateway.execute(db, scope, 'create_github_issue', issue)).code]
        scope = await approve(scope)
        waiting.append((await gateway.execute(db, scope, 'github_open_pull_request', pull)).code)
        scope = await approve(scope)
        recorded = [row[0] for row in await (await db.execute(
            'select resource_target from public.approval_requests where run_id = %s order by created_at', (scope.run_id,))).fetchall()]
        await settings.save(WORKSPACE_A, 'github_repository', 'owner/b', version + 1)
        github.requests.clear()
        changed = [(await gateway.execute(db, scope, name, arguments)).code
                   for name, arguments in (('create_github_issue', issue), ('github_open_pull_request', pull))]
        check('a changed repository refuses both approved writes before any request',
              "approvals record owner/a; approval_target_changed twice; 0 requests", (recorded, changed, github.requests),
              waiting == ['approval_pending', 'approval_pending'] and recorded == ['GitHub repository owner/a'] * 2
              and changed == ['approval_target_changed'] * 2 and github.requests == [])
        await settings.save(WORKSPACE_A, 'github_repository', 'owner/a', version + 2)
        unchanged = await start(WORKSPACE_A, {'create_github_issue': 1})
        pending = (await gateway.execute(db, unchanged, 'create_github_issue', {'title': 'Kept', 'body': 'k'})).code
        unchanged = await approve(unchanged)
        github.requests.clear()
        ran = await gateway.execute(db, unchanged, 'create_github_issue', {'title': 'Kept', 'body': 'k'})
        writes = [(method, repository) for method, repository, _ in github.requests if method != 'GET']
        check('an approved write with an unchanged repository runs against it',
              "approval_pending, then succeeded, POST owner/a", (pending, ran.outcome.value, writes),
              pending == 'approval_pending' and ran.outcome.value == 'succeeded' and writes == [('POST', 'owner/a')])
        await settings.remove(WORKSPACE_A, 'github_repository', version + 3)

        # The browsing switch, per workspace, with an executor that reports qualified.
        browsing_tool.executor_qualified = lambda *_: True
        enabled = {**environ, 'AUTOBOTS_BROWSER_EXECUTOR': 'enabled'}
        switch = (await state(WORKSPACE_A))['browser_executor'][2]
        await settings.save(WORKSPACE_A, 'browser_executor', 'disabled', switch)

        async def browse_state(workspace: UUID, process: dict[str, str]) -> tuple[str, str, str, bool]:
            view = await key_sources(db, workspace, process)
            catalog = {t.tool_id: t.availability for t in tool_registry.catalog().catalog(view).tools}
            try:
                tool_registry.catalog().require_available(['browse_goal'], view)
                admitted = 'admitted'
            except ToolsUnavailable as error:
                admitted = error.code
            os.environ.pop('AUTOBOTS_BROWSER_EXECUTOR', None)
            os.environ.update({k: v for k, v in process.items() if k == 'AUTOBOTS_BROWSER_EXECUTOR'})
            try:
                await create_expert(db, workspace_id=workspace, actor_id=actor, idempotency_key=str(uuid4()),
                                    name=f'Browser {uuid4().hex[:6]}', config=ExpertConfig(tools=['browse_goal', 'save_artifact', 'publish_artifact']), catalog=tool_registry.catalog())
                expert = 'saved'
            except ExpertRefused as error:
                expert = error.code
            scope = await start(workspace, {'browse_goal': 1})
            lease = SimpleNamespace(run_id=scope.run_id, workspace_id=workspace)

            async def fetch() -> dict[str, Any]:
                return CATALOG

            context = ProviderContext(str(config_root), 'development', key_file, {}, None, fetch)  # type: ignore[arg-type]
            source = InferenceSource(URL, context, CatalogCache(fetch), browser=object())
            bound = await source._browsing(db, lease)  # type: ignore[arg-type]
            os.environ.pop('AUTOBOTS_BROWSER_EXECUTOR', None)
            return catalog.get('browse_goal', 'absent'), admitted, expert, bool(bound)

        off, on = await browse_state(WORKSPACE_A, enabled), await browse_state(other, enabled)
        check('a saved disabled switch turns browsing off for its workspace though the environment enables it',
              "A: disabled_by_policy, tool_unavailable, expert_tool_unavailable, not bound; other: available, admitted, saved, bound",
              (off, on), off == ('disabled_by_policy', 'tool_unavailable', 'expert_tool_unavailable', False)
              and on == ('available', 'admitted', 'saved', True))
        await settings.save(WORKSPACE_A, 'browser_executor', 'enabled', switch + 1)
        lit, dark = await browse_state(WORKSPACE_A, environ), await browse_state(other, environ)
        browsing_tool.executor_qualified = lambda *_: False
        unqualified = await browse_state(WORKSPACE_A, environ)
        check('a saved enabled switch turns browsing on for its workspace, only while the executor is qualified',
              "A: available, saved, bound; other: disabled_by_policy; unqualified A: disabled_by_policy, not bound",
              (lit, dark, unqualified), lit == ('available', 'admitted', 'saved', True) and dark[0] == 'disabled_by_policy'
              and dark[3] is False and unqualified[0] == 'disabled_by_policy' and unqualified[3] is False)
        await settings.remove(WORKSPACE_A, 'browser_executor', switch + 2)

        # The sealed token stays out of durable state.
        texts: list[str] = []
        for query in (
            'select t::text from app_private.tool_uses t where run_id = any(%s)',
            'select t::text from app_private.tool_receipts t where run_id = any(%s)',
            'select t::text from public.run_events t where run_id = any(%s)',
            'select t::text from public.runs t where id = any(%s)',
            'select t::text from app_private.run_jobs t where run_id = any(%s)',
            'select t::text from public.approval_requests t where run_id = any(%s)',
            'select t::text from app_private.tool_key_settings t where workspace_id = any(%s)',
        ):
            cursor = await db.execute(query, ([WORKSPACE_A, other] if 'tool_key_settings' in query else runs,))
            texts += [str(row[0]) for row in await cursor.fetchall()]
        cursor = await db.execute(
            "select count(*) filter (where position(convert_to(%s, 'utf8') in ciphertext) > 0), count(*) "
            "from app_private.provider_credentials where workspace_id = %s and provider = 'github'", (SAVED_TOKEN, WORKSPACE_A))
        plain, rows = await cursor.fetchone()
        leaked = [token_label('Bearer ' + secret) for secret in SECRETS if any(secret in text for text in texts) or secret in log.getvalue()]
        check('no token appears in tool uses, receipts, events, runs, jobs, approvals, settings or logs, and rows hold ciphertext only',
              'nothing leaked, 0 plaintext rows', (leaked, len(texts), plain, rows), leaked == [] and len(texts) > 0 and plain == 0 and rows >= 1)
    output = json.dumps({'cases': cases})
    if any(secret in output for secret in SECRETS):
        raise SystemExit('a fixture token reached this check output')
    print(output)


asyncio.run(main())
