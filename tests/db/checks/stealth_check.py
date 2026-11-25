"""The stealth browser live on a disposable stack, Decision 0038 Z1 to Z13: what it says it is, which browser and
engine each Expert's call runs on, its refusal while it isn't qualified, a changed user agent, checks that clear,
stay or ask a person, and what it draws and records. JSON cases, whose ids are among browser_qualification.REQUIRED_STEALTH_CASES.

browse_goal goes through the real gateway, approvals, admission, model endpoint, relay and executor. The model is
scripted, so no inference provider is called. The browser reaches only Decision 0018's qualification hosts. The
executor's own refusals on this image are tests/db/checks/browser_executor_check.py, run with `stealth`.

No real bot check is met. Each is arranged on https://example.com/ by its address alone, and the challenge host is
arranged as example.org (Decision 0018).
"""
from __future__ import annotations

import asyncio
import os
import re
import sys
import time
from itertools import pairwise
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
POLICIES = ('DownloadRestrictions', 'AllowFileSelectionDialogs', 'PasswordManagerEnabled', 'AutofillCreditCardEnabled',
            'AutofillAddressEnabled')
WALK = ("(()=>{function w(n,o){if(!n)return;if(n.shadowRoot)w(n.shadowRoot,o);for(const c of n.childNodes){"
        "if(c.nodeType===3&&c.textContent.trim())o.push(c.textContent.trim());w(c,o);}}const o=[];w(document.body,o);return o.join(' | ')})()")
DISGUISE = ("cdp('Emulation.setUserAgentOverride', userAgent='Mozilla/5.0 Fake/1')\n"
            "goto_url('https://example.com/?disguised')\nimport time; time.sleep(1)")

# The challenge host these checks arrange, and pages that show a check by its address alone.
CHALLENGE = 'example.org'
HOME = "goto_url('https://example.com/')\nwait_for_load()\nimport time; time.sleep(1)\n"
CHL = 'https://example.com/cdn-cgi/challenge-platform/h/b/orchestrate/chl_page/v1'
# A check that is the page: the script a Cloudflare challenge loads from the site's own host.
SHOWS = ("js(\"(()=>{const s=document.createElement('script');s.src='%s';document.head.appendChild(s);%s return 'ok'})()\")\n"
         'import time; time.sleep(3)')
CLEARS = SHOWS % (CHL, "setTimeout(()=>{location.href='https://example.com/?cleared'},9000);")
STAYS = SHOWS % (CHL, '')
FRAME = "js(\"document.body.insertAdjacentHTML('beforeend','<iframe src=%s></iframe>'); 'ok'\")\nimport time; time.sleep(2)"
TURNSTILE = FRAME % 'https://challenges.cloudflare.com/cdn-cgi/challenge-platform/h/b/turnstile/if'
PERSON = FRAME % '/recaptcha/api2/bframe?k=x'
PARTS = (FRAME % 'https://example.org/') + (
    "\njs(\"(()=>{const s=document.createElement('script');s.src='https://example.org/x.js';document.head.appendChild(s);return 'ok'})()\")"
    '\ntime.sleep(2)')
AS_A_PAGE = "js(\"location.href='https://example.org/'\")\nimport time; time.sleep(2)"


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


async def policies(rig: Rig) -> None:
    session = await rig.executor.start('stealth', 1, (), stealth=Stealth(ZONE))
    try:
        cdp = await Cdp.connect(await session.websocket_url())
        target = (await cdp.send('Target.createTarget', {'url': 'chrome://policy'}))['result']['targetId']
        page = (await cdp.send('Target.attachToTarget', {'targetId': target, 'flatten': True}))['result']['sessionId']
        await asyncio.sleep(3)
        shown = (await cdp.send('Runtime.evaluate', {'expression': WALK, 'returnByValue': True}, page))['result']['result']['value']
        await cdp.close()
    finally:
        await rig.executor.stop(session)
    applied = [name for name in POLICIES if re.search(rf'{name} \| (3|false) \| Platform \| Machine \| Mandatory \| (OK|Deprecated)', shown)]
    rig.cases.check("Chrome applies the box's managed policy", 'downloads, file selection, the password manager and card and address autofill off',
                    applied, applied == list(POLICIES))


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

# The page is loaded before it is replaced, so nothing of its own is still arriving. A page that counts the nodes and attributes anything adds to it, then buttons and a field to press and type into. One button
# echoes what was typed, as a search page does.
PLANTED = 'planted secret words'
COUNTS = ("js(\"(()=>{document.body.innerHTML='<input id=ours aria-label=Search><button id=go>Go</button><button id=echo></button>'"
          "+Array.from({length:12},(_,i)=>'<button id=b'+i+'>Button '+i+'</button>').join('');"
          "document.getElementById('ours').addEventListener('input',(e)=>{document.getElementById('echo').textContent='Search for '+e.target.value});"
          "window.added=0;new MutationObserver((l)=>{for(const m of l){window.added+=[...m.addedNodes].filter((n)=>n.nodeType===1).length;"
          "if(m.type==='attributes')window.added++}}).observe(document,{subtree:true,childList:true,attributes:true});return 'ok'})()\")\n")
# Real mouse presses and inserted text, which are what browser-use highlights, then a scripted press of the echoing button.
TYPES = (f"import json; at = lambda i: json.loads(js(\"(()=>{{const r=document.getElementById('\"+i+\"').getBoundingClientRect();"
         f"return JSON.stringify([r.x+4,r.y+4])}})()\"))\n"
         f"click_at_xy(*at('ours'))\ntype_text('{PLANTED}')\ntime.sleep(1)\n"
         "js(\"document.getElementById('echo').click()\")\nclick_at_xy(*at('go'))\ntime.sleep(1)\n")
MANY = ''.join(f"js(\"document.getElementById('b{i}').click()\")\n" for i in range(12))
LEAVES = ("js(\"(()=>{document.body.insertAdjacentHTML('beforeend','<a id=n href=/?next aria-label=Onward>n</a>');"
          "document.getElementById('n').click();return 'ok'})()\")\nimport time; time.sleep(3)\nprint(page_info()['url'])")
SAW = "print('SAW', js(\"JSON.stringify([window.added, typeof nextTouched, Object.keys(window).filter((k)=>/autobots|touched/i.test(k))])\"))"


def reached(rig: Rig, since: int) -> tuple[list[str], list[str]]:
    """The hosts the sessions started after `since` reached, and those their proxies refused."""
    entries = [entry for name in rig.executor.sessions[since:] for entry in rig.executor.logs[name]]
    return (sorted({str(entry['host']) for entry in entries if entry.get('event') == 'allowed'}),
            sorted({str(entry['host']) for entry in entries if entry.get('event') == 'refused'}))


async def parts_only(rig: Rig) -> None:
    before = len(rig.executor.sessions)
    parts = await rig.browse('stealth', cell(HOME + PARTS), finish('Read.'))
    loaded, _ = reached(rig, before)
    Recorded.made.clear()
    page = await rig.browse('stealth', cell(HOME + AS_A_PAGE), finish('never'))
    rig.cases.check(
        'a challenge host loads as a part of a page, and going to it as a page ends the call refused_action',
        'the frame and script reach it and the call goes on; the navigation is refused, refused_action after 1 model call',
        (parts.output.get('stopped'), loaded, page.output.get('stopped'), len(page.model.seen), Recorded.made[-1].navigated),
        parts.output.get('stopped') == 'done' and loaded == ['example.com', 'example.org']
        and page.output.get('stopped') == 'refused_action' and len(page.model.seen) == 1
        and not any('example.org' in url for url in Recorded.made[-1].navigated))


async def check_clears(rig: Rig) -> None:
    moments: list[float] = []

    def shown() -> Any:
        moments.append(time.monotonic())
        return cell(HOME + CLEARS)

    def after() -> Any:
        moments.append(time.monotonic())
        return cell("print(page_info()['url'])")

    cleared = await rig.browse('stealth', shown, after, finish('Read.'))
    waited = moments[1] - moments[0]
    rig.cases.check(
        'a check that is the page clears by itself, with no model call meanwhile, and the browse goes on',
        'the second request answered only after the page moved on, 9 to 25 seconds later, then done with 3 model calls',
        (round(waited, 1), cleared.output.get('stopped'), cleared.output.get('model_calls'), last_result(cleared.model)[-120:]),
        9 <= waited < 25 and cleared.output.get('stopped') == 'done' and cleared.output.get('model_calls') == 3
        and '?cleared' in last_result(cleared.model))


async def check_stays(rig: Rig) -> None:
    began = time.monotonic()
    stays = await rig.browse('stealth', cell(HOME + STAYS), finish('never'))
    took = time.monotonic() - began
    rig.cases.check(
        "a check that stays ends the call bot_check after its time, with nothing solved or retried",
        'bot_check after 20 seconds and 1 model call', (stays.output.get('stopped'), round(took, 1), len(stays.model.seen)),
        stays.output.get('stopped') == 'bot_check' and took >= 20 and len(stays.model.seen) == 1)


async def widget_and_person(rig: Rig) -> None:
    widget = await rig.browse('stealth', cell(HOME + TURNSTILE), finish('Read.'))
    began = time.monotonic()
    person = await rig.browse('stealth', cell(HOME + PERSON), finish('never'))
    took = time.monotonic() - began
    rig.cases.check(
        "a Turnstile frame on a page isn't a check, and one that asks a person ends the call bot_check at first sight",
        'done beside the Turnstile frame; bot_check after 1 model call, without the wait',
        (widget.output.get('stopped'), person.output.get('stopped'), len(person.model.seen), round(took, 1)),
        widget.output.get('stopped') == 'done' and person.output.get('stopped') == 'bot_check' and len(person.model.seen) == 1
        and took < 20)


async def nothing_solves(rig: Rig) -> None:
    before = len(rig.executor.sessions)
    met = await rig.browse('stealth', cell(HOME + PERSON), finish('never'))
    told = flat([[str(message.content) for message in messages] for messages in met.model.seen])
    pictures = any(isinstance(message.content, list) and any(part.get('type') != 'text' for part in message.content)
                   for messages in met.model.seen for message in messages)
    allowed, _ = reached(rig, before)
    rig.cases.check(
        'nothing solves a check: browser-use is told never to answer one, no request carries an image and no other host is reached',
        'told, no image, only the call\'s domain and the arranged challenge host',
        ('Never press, type into or answer a CAPTCHA' in told, pictures, allowed, rig.executor.specs[-1].get('stealth')),
        'Never press, type into or answer a CAPTCHA' in told and not pictures and set(allowed) <= {'example.com', 'example.org'}
        and rig.executor.specs[-1].get('stealth') is True)


async def box_unchanged(rig: Rig) -> None:
    before = len(rig.executor.sessions)
    began = time.monotonic()
    ended = [(await rig.browse('box', cell(HOME + show), finish('never'))).output.get('stopped') for show in (TURNSTILE, STAYS)]
    took = time.monotonic() - began
    parts = await rig.browse('box', cell(HOME + FRAME % 'https://example.org/'), finish('Read.'))
    _, refused = reached(rig, before)
    rig.cases.check(
        "the box's browser is unchanged: a check ends the call at first sight and the challenge hosts stay refused",
        'bot_check twice without the wait, and example.org refused by the proxy',
        (ended, round(took, 1), parts.output.get('stopped'), refused),
        ended == ['bot_check', 'bot_check'] and took < 40 and 'example.org' in refused and parts.output.get('stopped') == 'done')


async def recorded(rig: Rig, run: UUID) -> list[tuple[int, list[list[str]]]]:
    rows = await (await rig.db.execute('select s.step, s.touched from app_private.browse_steps s join app_private.tool_uses u '
                                       'on u.id = s.tool_use_id where u.run_id = %s order by s.step', (run,))).fetchall()
    return [(step, [[t['action'], t['kind'], t['label']] for t in touched]) for step, touched in rows]


async def quiet_on_the_page(rig: Rig) -> None:
    quiet = await rig.browse('stealth', cell(HOME + COUNTS + TYPES + SAW), cell(MANY + "print('pressed')"), cell(LEAVES), finish('Read.'))
    steps = await recorded(rig, quiet.run)
    saw = next((str(message.content) for messages in quiet.model.seen for message in messages if 'SAW' in str(message.content)), '')
    rig.cases.check(
        'nothing is drawn on a stealth page and it sees no trace of the reading, while each step names what it pressed or typed into',
        'no node or attribute added by browser-use, no name of ours in the page, and the search field, the echo and the Go button by '
        'action, kind and label',
        (saw[-200:], steps[:2], quiet.output.get('stopped')),
        'undefined' in saw and '[0,' in saw.replace(' ', '').replace('\\', '') and quiet.output.get('stopped') == 'done'
        and ['typed', 'text input', 'Search'] in steps[1][1] and ['pressed', 'button', 'Go'] in steps[1][1]
        # A press that leaves the page is recorded too.
        and ['pressed', 'a', 'Onward'] in steps[3][1])
    everywhere = flat([steps, quiet.output, await rig.shown(quiet.run)])
    events = flat(await (await rig.db.execute('select payload from public.run_events where run_id = %s', (quiet.run,))).fetchall())
    rig.cases.check(
        'a step records ten elements at most, and never what was typed, though the page echoes it',
        'ten of twelve presses, the echo unnamed, and the planted words nowhere',
        ([len(touched) for _, touched in steps], [t for _, touched in steps for t in touched if t[2] == '']),
        max(len(touched) for _, touched in steps) == 10 and ['pressed', 'button', ''] in steps[1][1]
        and PLANTED not in everywhere and 'planted' not in events)
    # browser-use draws on its own thread, for a second.
    box = await rig.browse('box', cell(HOME + COUNTS + TYPES + SAW), finish('Read.'))
    drew = re.search(r'SAW \[(\d+)', next((str(message.content) for messages in box.model.seen for message in messages
                                           if 'SAW' in str(message.content) and 'window.added' not in str(message.content)), ''))
    rig.cases.check("the box keeps its highlights, and its steps name no element", "what browser-use draws on the page, and no touch",
                    (drew and drew.group(0), await recorded(rig, box.run)),
                    drew is not None and int(drew.group(1)) > 0 and all(touched == [] for _, touched in await recorded(rig, box.run)))


async def keeps_a_pace(rig: Rig) -> None:
    moments: list[float] = []

    def at(answer: Any) -> Any:
        def given() -> Any:
            moments.append(time.monotonic())
            return answer
        return given

    paced = await rig.browse('stealth', at(cell("print('a')")), at(cell("print('b')")), at(finish('Read.')))
    gaps = [round(b - a, 1) for a, b in pairwise(moments)]
    moments.clear()
    await rig.set_yolo(False)
    await rig.approved('stealth', at(calls(('scroll', {}))), at(calls(('scroll', {}))), at(calls(('finish', {'summary': 'Read.'}))))
    await rig.set_yolo(True)
    loop = [round(b - a, 1) for a, b in pairwise(moments)]
    rig.cases.check("a stealth browse's steps are at least 2 seconds apart on both engines", 'two gaps of 2 seconds or more on each',
                    (gaps, loop, paced.output.get('stopped')), len(gaps) == len(loop) == 2 and min(*gaps, *loop) >= 1.9)


SCENARIOS = (says_what_it_is, fresh_profile, policies, either_engine, no_fallback, changed_user_agent, parts_only, check_clears, check_stays,
             widget_and_person, nothing_solves, box_unchanged, quiet_on_the_page, keeps_a_pace)


async def main(cases: Cases) -> None:
    os.environ[browsing_tool.ENABLE] = 'enabled'
    browsing_tool.CHALLENGE_HOSTS = (CHALLENGE,)  # type: ignore[assignment]  # arranged
    record_guards()
    executor = Watching({**os.environ, **WORKER_SECRETS})
    async with await psycopg.AsyncConnection.connect(URL, autocommit=True) as db:
        await run_scenarios(cases, SCENARIOS, Rig(db, cases, WORKSPACE, executor, ['example.com']))
        cases.check("no stealth session's container is left", 'none', containers(), not containers())


if __name__ == '__main__':
    run_check(main, secrets=WORKER_SECRETS.values(), parent_timeout=1500)
