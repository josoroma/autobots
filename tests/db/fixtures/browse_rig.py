"""What a live browse_goal check shares: the real gateway, admission, endpoint and executor with a scripted model, one
Expert per browser, and what each session was started with. No provider is involved."""
from __future__ import annotations

import asyncio
import json
import subprocess
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

from autobots.adapters import browser_use_box, loop_middleware, tool_registry
from autobots.adapters.browser_cdp import RequestGuard
from autobots.adapters.browser_executor import BrowserExecutor, BrowserSession, Stealth
from autobots.adapters.loop_middleware import LoopMiddleware, ModelRoute
from autobots.application import browsing_tool
from autobots.application.approvals import decide
from autobots.application.experts import create_expert
from autobots.application.run_usage import RootLimits, ensure_usage
from autobots.application.runs import admit_run
from autobots.application.tool_definitions import ToolRegistry, ToolScope
from autobots.application.tool_gateway import ToolGateway
from autobots.application.worker_leases import claim_next
from autobots.contracts.experts import ExpertConfig
from autobots.domain.models import resolve_role_policy
from autobots.domain.tools import PLAN_TOOLS
from checklib import Cases
from goal_loop_script import ROUTE, Script, calls

RESEARCHER = ModelRoute('researcher', 'openrouter_sol', 'openai/gpt-6.1-sol', 1000)
GRANT = {**PLAN_TOOLS, 'browse_goal': 3}
BASE = {'task': 'What is example.com for?', 'start_url': 'https://example.com/', 'allowed_domains': ['example.com']}


def cell(code: str) -> Any:
    return calls(('python', {'code': code}))


def finish(result: str = 'done') -> Any:
    return calls(('finish', {'result': result, 'success': True}))


def script(*items: Any) -> Script:
    return Script(items=list(items), seen=[], bound=[])


def last_result(model: Script) -> str:
    """What browser-use reported of its last cell, as the next request showed the model."""
    return str(model.seen[-1][-1].content) if model.seen else ''


def engine(model: Script) -> str:
    names = ' '.join(str(tools) for tools in model.bound)
    return 'browser_use' if 'finish_from_repl' in names else 'loop' if 'open_link' in names else 'none'


class Watching(BrowserExecutor):
    """The real executor, recording each session's image, caps, limits and proxy log before it is removed."""

    def __init__(self, environ: dict[str, str]) -> None:
        super().__init__(environ=environ)
        self.sessions: list[str] = []
        self.inspected: dict[str, dict[str, Any]] = {}
        self.watched: list[float | None] = []
        self.specs: list[dict[str, Any]] = []
        self.logs: dict[str, list[dict[str, Any]]] = {}

    async def start(self, *args: Any, stealth: Stealth | None = None, **kwargs: Any) -> BrowserSession:
        chosen = {} if stealth is None else {'stealth': stealth}
        session = await super().start(*args, **chosen, **kwargs)
        self.sessions.append(session.name)
        self.inspected[session.name] = (await self.inspect(session))['browser']
        return session

    async def watch(self, session: BrowserSession, alive: Any, seconds: float | None = None, every: float = 1.0) -> str:
        self.watched.append(seconds)
        return await super().watch(session, alive, seconds, every)

    async def run_browser_use(self, session: BrowserSession, spec: dict[str, Any], seconds: float) -> str:
        self.specs.append(spec)
        return await super().run_browser_use(session, spec, seconds)

    async def stop(self, session: BrowserSession) -> None:
        if session.name not in self.logs:
            self.logs[session.name] = await self.proxy_log(session)
        await super().stop(session)

    def images(self) -> list[str]:
        return [self.inspected[name]['Config']['Image'] for name in self.sessions]


class Recorded(RequestGuard):
    """The worker's own guard of each browse on browser-use, kept so a check reads what it refused."""

    made: list[Recorded] = []  # noqa: RUF012 - one list for the process, which each browse appends to

    async def start(self) -> None:
        Recorded.made.append(self)
        await super().start()


def record_guards() -> None:
    browser_use_box.RequestGuard = Recorded  # type: ignore[misc]  # the check reads each browse's guard


class Store:
    """The run's private storage, in memory."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def put(self, path: str, content: bytes, media_type: str) -> bool:
        self.objects[path] = content
        return True

    async def get(self, path: str) -> bytes | None:
        return self.objects.get(path)

    async def remove(self, path: str) -> None:
        self.objects.pop(path, None)

    async def names(self, prefix: str) -> list[str]:
        return [name for name in self.objects if name.startswith(prefix)]


class Browsed(SimpleNamespace):
    """One call's result, its scripted model and its run."""

    result: Any
    model: Script
    run: UUID

    @property
    def output(self) -> dict[str, Any]:
        return self.result.output or {}


class Rig:
    """One workspace on a disposable database, with an Expert for each browser."""

    def __init__(self, db: Any, cases: Cases, workspace: UUID, executor: Watching, domains: list[str]) -> None:
        self.db, self.cases, self.workspace, self.executor, self.domains = db, cases, workspace, executor, domains
        self.actor = uuid4()
        self.store = Store()
        self.experts: dict[str, UUID] = {}
        self.stealth_qualified = True

    async def value(self, sql: str, *values: object) -> Any:
        return (await (await self.db.execute(sql, values)).fetchone())[0]

    async def set_yolo(self, on: bool) -> None:
        await self.db.execute('insert into app_private.browsing_settings (workspace_id, yolo) values (%s, %s) '
                              'on conflict (workspace_id) do update set yolo = excluded.yolo', (self.workspace, on))

    async def expert(self, browser: str) -> UUID:
        if browser not in self.experts:
            config = ExpertConfig.model_validate({'tools': ['browse_goal'], 'browse_domains': self.domains, 'browser': browser})
            made = await create_expert(self.db, workspace_id=self.workspace, actor_id=self.actor, idempotency_key=str(uuid4()),
                                       name=f'{browser} {uuid4().hex[:6]}', config=config, catalog=tool_registry.catalog())
            self.experts[browser] = made.id
        return self.experts[browser]

    async def start(self, browser: str) -> UUID:
        await self.db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null "
                              "where status <> 'done'")
        binding = SimpleNamespace(session_id=None, expert_id=await self.expert(browser), version=1, instructions='', tools=GRANT)
        run = (await admit_run(self.db, workspace_id=self.workspace, actor_id=self.actor, idempotency_key=str(uuid4()),
                               goal_text='Browse', limit_micro_usd=1_000_000, policy=resolve_role_policy(), binding=binding)).run_id
        await ensure_usage(self.db, run)
        return run

    async def claimed(self, run: UUID) -> ToolScope:
        lease = await claim_next(self.db, worker_id='browse-rig', lease_seconds=900)
        assert lease is not None and lease.run_id == run, lease
        await self.db.execute("update public.runs set status = 'running' where id = %s", (run,))
        return ToolScope(self.workspace, run, lease.generation, GRANT)

    async def execute(self, scope: ToolScope, model: Script, arguments: dict[str, Any]) -> Any:
        registry = ToolRegistry()
        runtime = browsing_tool.BrowsingRuntime(self.executor, model, RESEARCHER, settle=2.0, browser_use=lambda: True,
                                                stealth=lambda: self.stealth_qualified, store=self.store)
        for tool in browsing_tool.browse_tools(runtime):
            registry.register(tool)
        middleware = LoopMiddleware(self.db, scope, RootLimits(), ROUTE, sleep=lambda _: asyncio.sleep(0), slot_wait_seconds=2)
        token = loop_middleware._MIDDLEWARE.set(middleware)
        try:
            return await ToolGateway(registry).execute(self.db, scope, 'browse_goal', arguments)
        finally:
            loop_middleware._MIDDLEWARE.reset(token)

    async def browse(self, browser: str, *items: Any, **change: Any) -> Browsed:
        """One YOLO call of that browser's Expert, whose model answers `items` in order."""
        run = await self.start(browser)
        scope, model = await self.claimed(run), script(*items)
        return Browsed(result=await self.execute(scope, model, {**BASE, **change}), model=model, run=run)

    async def approved(self, browser: str, *items: Any, **change: Any) -> Browsed:
        """One call of that browser's Expert with YOLO off, approved by a person."""
        run = await self.start(browser)
        scope, model = await self.claimed(run), script(*items)
        pending = await self.execute(scope, model, {**BASE, **change})
        assert pending.code == 'approval_pending', pending
        row = await (await self.db.execute("select id, argument_hash from public.approval_requests where run_id = %s and status = 'pending'",
                                           (run,))).fetchone()
        await decide(self.db, workspace_id=self.workspace, actor_id=self.actor, approval_id=row[0], idempotency_key=str(uuid4()),
                     decision='approve', argument_hash=row[1])
        return Browsed(result=await self.execute(await self.claimed(run), model, {**BASE, **change}), model=model, run=run)

    async def shown(self, run: UUID) -> list[Any]:
        """Each browse's public input, as its tool row shows it."""
        rows = await (await self.db.execute("select input_public from app_private.tool_uses where run_id = %s and metered "
                                            'order by sequence_in_run', (run,))).fetchall()
        return [row[0] for row in rows]


def containers() -> list[str]:
    listed = subprocess.run(['docker', 'ps', '-a', '--filter', 'label=autobots.browser', '--format', '{{.Names}}'],
                            capture_output=True, text=True, check=False)
    return [name for name in listed.stdout.split() if name]


def flat(value: object) -> str:
    return json.dumps(value, default=str)
