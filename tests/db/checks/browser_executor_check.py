"""US-14.13 live: the isolated browser executor on Docker, with real runs on a disposable database.

Run by scripts/qualify_browser_executor.py. A scripted driver, not a model, issues CDP commands.
The one public host requested is https://example.com/ (Decision 0018). JSON cases on stdout.

With `stealth` as its last argument, every session's browser is the stealth one (Decision 0038 Z6), so each refusal is
observed again on its image.
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
from autobots.adapters.browser_executor import (
    BrowserExecutor,
    BrowserSession,
    Cdp,
    ExecutorConfig,
    ModelLink,
    RequestGuard,
    Stealth,
    attempt_alive,
    lease_alive,
)
from autobots.adapters.model_endpoint import ModelEndpoint, Reply
from autobots.application.runs import admit_run, apply_command
from autobots.application.tool_definitions import ToolScope
from autobots.application.worker_leases import claim_next
from autobots.domain.models import resolve_role_policy
from autobots.domain.runs import RunCommand

URL = os.environ['AUTOBOTS_DATABASE_URL']
WORKSPACE = UUID(sys.argv[1])
DB_PORT, GATEWAY_PORT = int(sys.argv[2]), int(sys.argv[3])
STEALTH = sys.argv[4:] == ['stealth']
IMAGE = 'autobots-browser-stealth:local' if STEALTH else 'autobots-browser:local'
ALLOWED = 'https://example.com/'
# Decision 0018: the only hosts this check may reach.
HOSTS = ('example.com', 'example.org')
# For containment the private targets are listed too, so it's the address check that refuses them.
LISTED_PRIVATE = ('127.0.0.1', '::1', 'host.docker.internal', '172.17.0.1', '10.0.0.1', '192.168.1.1', '172.16.0.1',
                  '100.64.0.1', '169.254.169.254', 'localtest.me', 'nip.io')
everything_allowed: list[str] = []
# What a worker holds. None of it may reach a container.
WORKER_SECRETS = {'OPENROUTER_API_KEY': 'sk-or-v1-fixtureNEVERINSIDE', 'TAVILY_API_KEY': 'tvly-fixtureNEVERINSIDE',
                  'JINA_API_KEY': 'jina_fixtureNEVERINSIDE', 'AUTOBOTS_DATABASE_URL': URL, 'GITHUB_TOKEN': 'ghp_fixtureNEVERINSIDE'}
cases: list[dict[str, Any]] = []


def check(name: str, expected: str, observed: object, passed: bool) -> None:
    cases.append({'id': name, 'expected': expected, 'observed': str(observed)[:900], 'passed': bool(passed)})


class Executor(BrowserExecutor):
    """The executor under check, with the checked browser in every session."""

    async def start(self, run_id: Any, generation: int, allowed_hosts: tuple[str, ...], model: ModelLink | None = None,
                    stealth: Stealth | None = None) -> BrowserSession:
        return await super().start(run_id, generation, allowed_hosts, model, Stealth('America/Costa_Rica') if STEALTH else stealth)


class Page:
    def __init__(self, cdp: Cdp, session: str) -> None:
        self.cdp, self.session = cdp, session

    @classmethod
    async def open(cls, cdp: Cdp) -> Page:
        targets = (await cdp.send('Target.getTargets'))['result']['targetInfos']
        page = next(target for target in targets if target['type'] == 'page')
        attached = await cdp.send('Target.attachToTarget', {'targetId': page['targetId'], 'flatten': True})
        return cls(cdp, attached['result']['sessionId'])

    async def go(self, url: str, settle: float = 2.0) -> tuple[str | None, str]:
        reply = await self.cdp.send('Page.navigate', {'url': url}, self.session)
        await asyncio.sleep(settle)
        return reply.get('result', {}).get('errorText'), await self.eval('location.href + " | " + document.title')

    async def eval(self, expression: str) -> Any:
        reply = await self.cdp.send('Runtime.evaluate', {'expression': expression, 'awaitPromise': True, 'returnByValue': True}, self.session)
        return reply.get('result', {}).get('result', {}).get('value')


async def remember(executor: BrowserExecutor, session: BrowserSession) -> None:
    everything_allowed.extend(str(entry.get('host')) for entry in await executor.proxy_log(session) if entry.get('event') == 'allowed')


async def browse(executor: BrowserExecutor, session: BrowserSession) -> tuple[Cdp, RequestGuard, Page]:
    cdp = await Cdp.connect(await session.websocket_url())
    guard = RequestGuard(cdp)
    await guard.start()
    return cdp, guard, await Page.open(cdp)


async def containment(executor: BrowserExecutor) -> None:
    session = await executor.start('qualification', 1, HOSTS + LISTED_PRIVATE)
    try:
        cdp, guard, page = await browse(executor, session)
        error, shown = await page.go(ALLOWED)
        log = await executor.proxy_log(session)
        allowed = [entry for entry in log if entry.get('event') == 'allowed' and entry.get('host') == 'example.com']
        check('an allowed page loads through the proxy, connected to the address it checked', 'Example Domain, an allowed entry with a public address',
              (error, shown, allowed[:1]), error is None and 'Example Domain' in shown and bool(allowed)
              and all(str(entry.get('address', '')).count('.') == 3 or ':' in str(entry.get('address', '')) for entry in allowed))

        async def refused(url: str) -> tuple[str | None, str]:
            return await page.go(url, settle=1.5)

        await page.go('https://example.net/', settle=1.5)
        log = await executor.proxy_log(session)
        unlisted = [entry.get('reason') for entry in log if entry.get('host') == 'example.net']
        background = [entry for entry in log if 'google' in str(entry.get('host')) or 'gvt1' in str(entry.get('host'))]
        check('only the hosts a call names are reached', 'example.net refused host_not_allowed; no background host allowed',
              (unlisted, background[:3]), unlisted and set(unlisted) == {'host_not_allowed'}
              and not any(entry.get('event') == 'allowed' for entry in background))

        local = {url: await refused(url) for url in (
            'https://127.0.0.1/', f'https://127.0.0.1:{DB_PORT}/', f'https://127.0.0.1:{GATEWAY_PORT}/', 'https://[::1]/',
            'https://host.docker.internal/', f'https://host.docker.internal:{DB_PORT}/', 'https://172.17.0.1/')}
        reasons = {(entry.get('host'), entry.get('reason')) for entry in await executor.proxy_log(session) if entry.get('event') == 'refused'}
        check("loopback, the Docker host and the stack's ports are refused", 'every navigation fails by address or port, none loads',
              (local, sorted(reasons, key=str)[:12]), all(error is not None and 'chrome-error' in shown for error, shown in local.values())
              and ('127.0.0.1', 'host_refused') in reasons and ('127.0.0.1', 'port_refused') in reasons
              and ('host.docker.internal', 'host_refused') in reasons and ('172.17.0.1', 'host_refused') in reasons)
        private = {url: await refused(url) for url in (
            'https://10.0.0.1/', 'https://192.168.1.1/', 'https://172.16.0.1/', 'https://100.64.0.1/',
            'https://169.254.169.254/latest/meta-data/', 'https://localtest.me/', 'https://127.0.0.1.nip.io/')}
        reasons = {(entry.get('host'), entry.get('reason')) for entry in await executor.proxy_log(session) if entry.get('event') == 'refused'}
        check('private, metadata and loopback-resolving names are refused', 'every navigation fails by the address check, none loads',
              private, all(error is not None and 'chrome-error' in shown for error, shown in private.values())
              and all((host, 'host_refused') in reasons for host in ('10.0.0.1', '169.254.169.254', 'localtest.me', '127.0.0.1.nip.io', '100.64.0.1')))

        await page.go(ALLOWED)
        await page.eval("location.href = 'https://169.254.169.254/latest/meta-data/'")
        await asyncio.sleep(2)
        landed = await page.eval('location.href')
        check('a script-driven redirect to a private address is refused', 'not on the metadata page', landed,
              'chrome-error' in str(landed) or str(landed).startswith(ALLOWED))

        await page.go(ALLOWED)
        sub = await page.eval("""(async () => {
          const out = {};
          try { await fetch('https://10.0.0.1/'); out.fetch = 'loaded'; } catch (e) { out.fetch = 'refused'; }
          out.image = await new Promise((done) => { const i = new Image(); i.onload = () => done('loaded'); i.onerror = () => done('refused');
            i.src = 'https://169.254.169.254/latest/meta-data/x.png'; });
          out.socket = await new Promise((done) => { try { const w = new WebSocket('wss://localtest.me/');
            w.onopen = () => done('open'); w.onerror = () => done('refused'); } catch (e) { done('refused'); } });
          out.plain = await new Promise((done) => { try { const w = new WebSocket('ws://127.0.0.1:%d/');
            w.onopen = () => done('open'); w.onerror = () => done('refused'); } catch (e) { done('refused'); } });
          return out; })()""" % GATEWAY_PORT)  # noqa: UP031 - a JavaScript template, whose braces an f-string would need escaped
        check('subresources and a WebSocket to private addresses are refused', 'fetch, image and sockets refused', sub,
              sub == {'fetch': 'refused', 'image': 'refused', 'socket': 'refused', 'plain': 'refused'})

        error, shown = await page.go('file:///etc/passwd', settle=1.5)
        check('a file URL is refused', 'blocked, no file content', (error, shown), error is not None and 'root:x' not in shown)

        downloads: list[str] = []

        async def downloaded(message: dict[str, Any]) -> None:
            if message['method'] in ('Browser.downloadWillBegin', 'Browser.downloadProgress'):
                downloads.append(json.dumps(message['params'])[:200])

        cdp.handlers.append(downloaded)
        await page.go(ALLOWED)
        await page.eval("""(() => { const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob(['payload']));
          a.download = 'payload.txt'; document.body.appendChild(a); a.click(); return true; })()""")
        await asyncio.sleep(2)
        files = await executor._docker('exec', f'{session.name}-browser', 'sh', '-c', 'ls -A /tmp/Downloads 2>/dev/null; find /tmp -name payload.txt', check=False)
        check('a download is refused', 'no payload.txt anywhere, any download event denied', (files.strip(), downloads),
              'payload.txt' not in files and all('completed' not in event for event in downloads))

        await page.go(ALLOWED)
        posted = await page.eval("""(async () => { try { await fetch('https://example.com/', {method: 'POST', body: 'x'}); return 'sent'; }
          catch (e) { return 'refused'; } })()""")
        check('a request with a body is refused', 'refused by the guard', (posted, guard.refused[-1:]),
              posted == 'refused' and any(item['method'] == 'POST' for item in guard.refused))

        log = await executor.proxy_log(session)
        hosts = [str(entry.get('host', '')) for entry in log if 'host' in entry]
        keys = sorted({key for entry in log for key in entry})
        check('the proxy logs hosts, never paths or queries', 'hosts only, no / ? or # in any', (keys, hosts[:6]),
              bool(hosts) and not any(mark in host for host in hosts for mark in '/?#')
              and set(keys) <= {'at', 'event', 'host', 'reason', 'address', 'bytes'} and 'meta-data' not in json.dumps(log))
        await cdp.close()
    finally:
        await remember(executor, session)
        await executor.stop(session)

    capped = Executor(ExecutorConfig(max_requests=1), environ=dict(os.environ))
    session = await capped.start('qualification', 1, HOSTS)
    try:
        cdp, _, page = await browse(capped, session)
        first = await page.go(ALLOWED)
        second = await page.go('https://example.org/')
        reasons = [entry.get('reason') for entry in await capped.proxy_log(session)]
        await cdp.close()
    finally:
        await remember(capped, session)
        await capped.stop(session)
    small = Executor(ExecutorConfig(max_bytes=2_000), environ=dict(os.environ))
    session = await small.start('qualification', 1, HOSTS)
    try:
        cdp, _, page = await browse(small, session)
        third = await page.go(ALLOWED)
        events = [entry.get('event') for entry in await small.proxy_log(session)]
        await cdp.close()
    finally:
        await remember(small, session)
        await small.stop(session)
    check('the request and byte caps are enforced', 'second request refused request_cap; byte cap cut the page',
          (first[1], second, reasons, third, events), 'request_cap' in reasons and second[0] is not None
          and 'byte_cap' in events and 'Example Domain' not in third[1])


async def isolation() -> None:
    executor = Executor(environ={**os.environ, **WORKER_SECRETS})
    session = await executor.start('qualification', 1, HOSTS)
    try:
        info = await executor.inspect(session)
        browser, proxy = info['browser'], info['proxy']
        host = browser['HostConfig']
        text = json.dumps(info)
        layers = json.loads(await executor._docker('image', 'inspect', '--format', '{{json .RootFS.Layers}}', IMAGE))
        base = json.loads(await executor._docker('image', 'inspect', '--format', '{{json .RootFS.Layers}}',
                                                 'mcr.microsoft.com/playwright@sha256:1507cbfc550a63a6b7396791ca4f00df17beb56342d2447b3f106c306f525579'))
        observed = {'user': browser['Config']['User'], 'readonly': host['ReadonlyRootfs'], 'cap_drop': host['CapDrop'], 'security': host['SecurityOpt'],
                    'memory': host['Memory'], 'cpus': host['NanoCpus'], 'pids': host['PidsLimit'], 'tmpfs': host['Tmpfs'], 'mounts': browser['Mounts'],
                    'binds': host['Binds'], 'networks': list(browser['NetworkSettings']['Networks']), 'browser_ports': host['PortBindings'],
                    'proxy_ports': proxy['HostConfig']['PortBindings'], 'env': browser['Config']['Env']}
        leaked = [name for name, value in WORKER_SECRETS.items() if name in text or value in text]
        check('nothing of the host enters the container', 'pwuser, read-only, no capabilities, caps, tmpfs, no mounts, internal network, no secret',
              (observed, leaked), observed['user'] == 'pwuser' and observed['readonly'] is True and observed['cap_drop'] == ['ALL']
              and observed['security'] == ['no-new-privileges'] and observed['memory'] == 1024 ** 3 and observed['cpus'] == 10 ** 9
              and observed['pids'] == (512 if STEALTH else 256) and observed['tmpfs'] == {'/tmp': 'rw,size=256m,mode=1777'} and observed['mounts'] == []
              and not observed['binds'] and observed['networks'] == [f'{session.name}-net'] and not observed['browser_ports']
              and all(binding['HostIp'] == '127.0.0.1' for binding in observed['proxy_ports']['9223/tcp']) and 'docker.sock' not in text
              and not leaked and layers[:len(base)] == base)
        async with httpx.AsyncClient(trust_env=False, timeout=10) as client:
            bare = (await client.get(f'http://127.0.0.1:{session.port}/json/version')).status_code
            wrong = (await client.get(f'http://127.0.0.1:{session.port}/not-the-token/json/version')).status_code
            right = (await client.get(f'{session.base}/json/version')).status_code
        check('the CDP gate needs the session token', '403, 403, 200', (bare, wrong, right), (bare, wrong, right) == (403, 403, 200))
    finally:
        await executor.stop(session)


async def relay() -> None:
    """Decision 0035 Y7: the box reaches the worker's model endpoint only through the sidecar's relay, which adds the token.
    The endpoint answers a fixed reply, so no model is called."""
    async def fixed(body: Any) -> Reply:
        return Reply({'object': 'chat.completion', 'relayed': True})

    async with ModelEndpoint(fixed) as endpoint:
        executor = Executor(environ={**os.environ, **WORKER_SECRETS})
        session = await executor.start('qualification', 1, HOSTS, ModelLink(endpoint.port, endpoint.token))
        try:
            async def from_box(url: str) -> str:
                script = (f"fetch({json.dumps(url)},{{method:'POST',headers:{{'content-type':'application/json'}},body:'{{}}'}})"
                          ".then(r=>r.text().then(t=>console.log(r.status+' '+t))).catch(e=>console.log('unreachable '+e.message))")
                return (await executor._docker('exec', f'{session.name}-browser', 'node', '-e', script)).strip()

            relayed = await from_box('http://proxy:9300/v1/chat/completions')
            other = await from_box('http://proxy:9300/v1/models')
            direct = await from_box(f'http://host.docker.internal:{endpoint.port}/v1/chat/completions')
            browser_env = json.dumps((await executor.inspect(session))['browser']['Config']['Env'])
            async with httpx.AsyncClient(trust_env=False, timeout=10) as client:
                stranger = (await client.post(f'http://127.0.0.1:{endpoint.port}/v1/chat/completions', json={})).status_code
            check('the box reaches the model endpoint only through the relay, which adds the token it never holds',
                  '200 relayed through proxy:9300; 404 for another path; the host port unreachable from the box; 401 without the token; '
                  'no token in the browser container',
                  (relayed, other[:3], direct[:11], stranger),
                  relayed.startswith('200 ') and '"relayed": true' in relayed and other.startswith('404') and direct.startswith('unreachable')
                  and stranger == 401 and endpoint.token not in browser_env)
        finally:
            await executor.stop(session)


async def ownership(db: Any) -> None:
    async def scoped() -> ToolScope:
        await db.execute("update app_private.run_jobs set status = 'done', lease_owner = null, lease_expires_at = null where status <> 'done'")
        admitted = await admit_run(db, workspace_id=WORKSPACE, actor_id=uuid4(), idempotency_key=str(uuid4()), goal_text='browse',
                                   limit_micro_usd=1000, policy=resolve_role_policy())
        lease = await claim_next(db, worker_id='browser-executor', lease_seconds=300)
        assert lease is not None
        return ToolScope(WORKSPACE, admitted.run_id, lease.generation, {})

    async def always() -> bool:
        return True

    narrow = Executor(ExecutorConfig(memory='512m'), environ=dict(os.environ))
    session = await narrow.start('qualification', 1, HOSTS)
    watcher = asyncio.create_task(narrow.watch(session, always, every=0.5))
    # A process in the container allocates past the cap, so the kernel's OOM kill is deterministic.
    await narrow._docker('exec', '-d', f'{session.name}-browser', 'node', '-e',
                         'const a = []; for (;;) a.push(Buffer.alloc(64 * 1024 * 1024, 1));', check=False)
    reason = await asyncio.wait_for(watcher, 60)
    check('the memory cap ends the session', 'memory_cap, containers removed', (reason, await narrow.exists(session)),
          reason == 'memory_cap' and not await narrow.exists(session))

    executor = Executor(environ=dict(os.environ))
    session = await executor.start('qualification', 1, HOSTS)
    watcher = asyncio.create_task(executor.watch(session, always, every=0.5))
    # A runaway that keeps forking, as a page's processes would, holds the container at its limit.
    await executor._docker('exec', '-d', f'{session.name}-browser', 'sh', '-c', 'while :; do sleep 60 & done', check=False)
    reason = await asyncio.wait_for(watcher, 60)
    check('the process cap ends the session', 'process_cap, containers removed', (reason, await executor.exists(session)),
          reason == 'process_cap' and not await executor.exists(session))

    session = await executor.start('qualification', 1, HOSTS)
    reason = await asyncio.wait_for(executor.watch(session, always, seconds=3, every=0.5), 60)
    check('the time cap ends the session', 'time_cap, containers removed', (reason, await executor.exists(session)),
          reason == 'time_cap' and not await executor.exists(session))

    scope = await scoped()
    session = await executor.start(scope.run_id, scope.generation, HOSTS)
    watcher = asyncio.create_task(executor.watch(session, lambda: attempt_alive(db, scope), every=0.5))
    await asyncio.sleep(1.5)
    version = (await (await db.execute('select version from public.runs where id = %s', (scope.run_id,))).fetchone())[0]
    await apply_command(db, workspace_id=WORKSPACE, run_id=scope.run_id, command=RunCommand.CANCEL, expected_version=version)
    reason = await asyncio.wait_for(watcher, 30)
    check('a cancelled run ends the session', 'attempt_ended, containers removed', (reason, await executor.exists(session)),
          reason == 'attempt_ended' and not await executor.exists(session))

    scope = await scoped()
    session = await executor.start(scope.run_id, scope.generation, HOSTS)
    watcher = asyncio.create_task(executor.watch(session, lambda: attempt_alive(db, scope), every=0.5))
    await asyncio.sleep(1.5)
    await db.execute("update app_private.run_jobs set lease_expires_at = clock_timestamp() - interval '1 second' where run_id = %s", (scope.run_id,))
    reason = await asyncio.wait_for(watcher, 30)
    check('a lost lease ends the session', 'attempt_ended, containers removed', (reason, await executor.exists(session)),
          reason == 'attempt_ended' and not await executor.exists(session))

    crashed = await scoped()
    left = await executor.start(crashed.run_id, crashed.generation, HOSTS)
    await db.execute("update app_private.run_jobs set lease_expires_at = clock_timestamp() - interval '1 second' where run_id = %s", (crashed.run_id,))
    live = await scoped()
    kept = await executor.start(live.run_id, live.generation, HOSTS)
    removed = await executor.sweep(lease_alive(db))
    check('the sweeper removes what a crashed worker left', "the crashed attempt's session removed, the live one kept",
          (removed, await executor.exists(left), await executor.exists(kept)),
          left.name in removed and kept.name not in removed and not await executor.exists(left) and await executor.exists(kept))
    await executor.stop(kept)


async def main() -> None:
    executor = Executor(environ=dict(os.environ))
    await containment(executor)
    await isolation()
    await relay()
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        await ownership(db)
    check('no host outside the qualification hosts was reached', 'only example.com or example.org allowed', sorted(set(everything_allowed)),
          bool(everything_allowed) and set(everything_allowed) <= set(HOSTS))
    print(json.dumps({'cases': cases}))


if __name__ == '__main__':
    asyncio.run(main())
