"""The stealth browser live on a disposable stack, Decision 0038 Z1 to Z6 and Z13: what it says it is, which browser and
engine each Expert's call runs on, its refusal while it isn't qualified, and a changed user agent. JSON cases, whose ids
are among browser_qualification.REQUIRED_STEALTH_CASES.

browse_goal goes through the real gateway, approvals, admission, model endpoint, relay and executor. The model is
scripted, so no inference provider is called. The browser reaches only Decision 0018's qualification hosts. The
executor's own refusals on this image are tests/db/checks/browser_executor_check.py, run with `stealth`.
"""
from __future__ import annotations

import asyncio
import os
import sys
from typing import Any
from uuid import UUID

import psycopg
from autobots.adapters.browser_cdp import Cdp
from autobots.adapters.browser_executor import Stealth
from autobots.application import browsing_tool
from browse_rig import (
    Recorded,
    Rig,
    Watching,
    cell,
    containers,
    engine,
    finish,
    flat,
    last_result,
    record_guards,
)
from checklib import Cases, run_check, run_scenarios
from goal_loop_script import calls

URL = os.environ['AUTOBOTS_DATABASE_URL']
WORKSPACE = UUID(sys.argv[1])
IMAGE = 'autobots-browser-stealth:local'
BOX = 'autobots-browser:local'
ZONE = 'America/Costa_Rica'
# Planted in the worker's environment, so nothing of it may be in the container.
WORKER_SECRETS = {'OPENROUTER_API_KEY': 'sk-or-v1-fixtureNEVERINSIDE', 'TAVILY_API_KEY': 'tvly-fixtureNEVERINSIDE',
                  'AUTOBOTS_DATABASE_URL': URL, 'GITHUB_TOKEN': 'ghp_fixtureNEVERINSIDE'}
# What a page can read. `brands` needs a secure context, which the fulfilled https page is.
READ = """(() => { const gl = document.createElement('canvas').getContext('webgl'); const e = gl && gl.getExtension('WEBGL_debug_renderer_info');
return {secure: isSecureContext, ua: navigator.userAgent, brands: (navigator.userAgentData?.brands || []).map((b) => b.brand),
screen: [screen.width, screen.height], languages: [...navigator.languages], webdriver: navigator.webdriver,
zone: Intl.DateTimeFormat().resolvedOptions().timeZone, renderer: e ? gl.getParameter(e.UNMASKED_RENDERER_WEBGL) : null}; })()"""
LEAVE = "(() => { localStorage.setItem('left', 'here'); document.cookie = 'left=here; max-age=3600'; return true; })()"
FOUND = "[localStorage.getItem('left'), document.cookie]"
DISGUISE = ("cdp('Emulation.setUserAgentOverride', userAgent='Mozilla/5.0 Fake/1')\n"
            "goto_url('https://example.com/?disguised')\nimport time; time.sleep(1)")


async def offline(executor: Watching, *expressions: str) -> list[Any]:
    """What a page reads in a stealth session that may reach no host. The worker's connection answers the page itself."""
    session = await executor.start('stealth', 1, (), stealth=Stealth(ZONE))
    try:
        cdp = await Cdp.connect(await session.websocket_url())
        target = (await cdp.send('Target.createTarget', {'url': 'about:blank'}))['result']['targetId']
        page = (await cdp.send('Target.attachToTarget', {'targetId': target, 'flatten': True}))['result']['sessionId']

        async def answer(message: dict[str, Any]) -> None:
            if message['method'] == 'Fetch.requestPaused':
                await cdp.send('Fetch.fulfillRequest', {'requestId': message['params']['requestId'], 'responseCode': 200,
                                                        'responseHeaders': [{'name': 'content-type', 'value': 'text/html'}],
                                                        'body': 'PHRpdGxlPng8L3RpdGxlPg=='}, message.get('sessionId'))

        cdp.handlers.append(answer)
        await cdp.send('Fetch.enable', {'patterns': [{'urlPattern': '*'}]}, page)
        await cdp.send('Page.navigate', {'url': 'https://fixture.example/'}, page)
        await asyncio.sleep(3)
        read = [(await cdp.send('Runtime.evaluate', {'expression': expression, 'returnByValue': True}, page))['result']['result'].get('value')
                for expression in expressions]
        read.append((await cdp.send('Storage.getCookies'))['result']['cookies'])
        await cdp.close()
        return read
    finally:
        await executor.stop(session)


async def says_what_it_is(rig: Rig) -> None:
    seen, cookies = await offline(rig.executor, READ)
    container = rig.executor.inspected[rig.executor.sessions[-1]]
    rig.cases.check(
        "the stealth browser says what it is, and names nothing it isn't",
        "Google Chrome with no Headless anywhere, a 1440 by 900 screen, the session's time zone, en-US, software WebGL named, "
        'no cookie, and no worker value in the container',
        (seen, cookies),
        seen['secure'] and 'Headless' not in flat(seen) and 'Google Chrome' in seen['brands'] and seen['screen'] == [1440, 900]
        and seen['zone'] == ZONE and seen['languages'] == ['en-US', 'en'] and 'SwiftShader' in str(seen['renderer'])
        and seen['webdriver'] is False and cookies == []
        and not any(secret in flat(container) for secret in WORKER_SECRETS.values()))


async def fresh_profile(rig: Rig) -> None:
    left = await offline(rig.executor, LEAVE, FOUND)
    found = await offline(rig.executor, FOUND)
    rig.cases.check('each stealth session starts with a fresh profile', 'what one session stored is in no later one',
                    (left[:2], found), left[1] == ['here', 'left=here'] and found[0] == [None, ''] and found[1] == [])


async def either_engine(rig: Rig) -> None:
    executor = rig.executor
    executor.sessions.clear()
    executor.watched.clear()
    await rig.set_yolo(True)
    first = await rig.browse('stealth', cell("goto_url('https://example.com/')\nprint(js('navigator.userAgent'))"), finish('Read.'))
    said = last_result(first.model)
    await rig.set_yolo(False)
    second = await rig.approved('stealth', calls(('finish', {'summary': 'Reserved for documentation.'})))
    await rig.set_yolo(True)
    box = await rig.browse('box', cell("goto_url('https://example.com/')\nprint(js('navigator.userAgent'))"), finish('Read.'),
                           task='Use the stealth browser, and say which browser this is.')
    rows = [await rig.shown(browsed.run) for browsed in (first, second, box)]
    rig.cases.check(
        "a stealth Expert's browse runs on the stealth browser, and its tool row says so",
        "browser-use with YOLO on and the loop with it off, both on the stealth image with 512 processes and each engine's own "
        "limit, and browser: stealth in both rows; the box Expert's call on the box, whatever its task asks, with no browser in its row",
        ([engine(browsed.model) for browsed in (first, second, box)], executor.images(), executor.watched, rows, said[-200:]),
        [engine(browsed.model) for browsed in (first, second, box)] == ['browser_use', 'loop', 'browser_use']
        and [browsed.output.get('stopped') for browsed in (first, second, box)] == ['done', 'done', 'done']
        and executor.images() == [IMAGE, IMAGE, BOX] and executor.watched == [360, 180, 360]
        and [executor.inspected[name]['HostConfig']['PidsLimit'] for name in executor.sessions] == [512, 512, 256]
        and rows[0][-1].get('browser') == 'stealth' and rows[0][-1].get('typing') == 'on'
        and rows[1][-1].get('browser') == 'stealth' and 'typing' not in rows[1][-1]
        and 'browser' not in rows[2][-1] and 'Chrome/158' in said and 'Headless' not in said
        and 'HeadlessChrome' in last_result(box.model))


async def no_fallback(rig: Rig) -> None:
    executor = rig.executor
    before = len(executor.sessions)
    rig.stealth_qualified = False
    try:
        await rig.set_yolo(True)
        on = await rig.browse('stealth', finish('never'))
        await rig.set_yolo(False)
        off = await rig.approved('stealth', finish('never'))
    finally:
        rig.stealth_qualified = True
        await rig.set_yolo(True)
    rig.cases.check(
        "a stealth Expert is refused while the stealth browser isn't qualified, before any container",
        'stealth_browser_unqualified with YOLO on and off, no container started, no model called',
        ((on.result.code, off.result.code), len(executor.sessions) - before, len(on.model.seen) + len(off.model.seen)),
        on.result.code == 'stealth_browser_unqualified' and off.result.code == 'stealth_browser_unqualified'
        and len(executor.sessions) == before and not on.model.seen and not off.model.seen and not containers())


async def changed_user_agent(rig: Rig) -> None:
    Recorded.made.clear()
    browsed = await rig.browse('stealth', cell(DISGUISE), finish('never'))
    guard = Recorded.made[-1]
    rig.cases.check(
        'a changed user agent is refused and ends the call refused_action',
        'the navigation under it is refused, refused_action after 1 model call',
        (browsed.output.get('stopped'), len(browsed.model.seen), guard.disguised, guard.refused[-2:]),
        browsed.output.get('stopped') == 'refused_action' and len(browsed.model.seen) == 1 and guard.disguised >= 1
        and not any('disguised' in url for url in guard.navigated))


SCENARIOS = (says_what_it_is, fresh_profile, either_engine, no_fallback, changed_user_agent)


async def main(cases: Cases) -> None:
    os.environ[browsing_tool.ENABLE] = 'enabled'
    record_guards()
    executor = Watching({**os.environ, **WORKER_SECRETS})
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        await run_scenarios(cases, SCENARIOS, Rig(db, cases, WORKSPACE, executor, ['example.com']))
        cases.check("no stealth session's container is left", 'none', containers(), not containers())


if __name__ == '__main__':
    run_check(main, secrets=WORKER_SECRETS.values(), parent_timeout=1500)
