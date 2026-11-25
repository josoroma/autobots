#!/usr/bin/env python3
"""The owner's scoreboard: each address they name, opened once in each browser, with no model (US-20.4, Decision 0038 Z15).

    python3.12 scripts/browser_scoreboard.py https://example.com/ https://example.org/

It opens each address in the box's browser and in the stealth browser, in the same isolated executor a browse runs in:
the egress proxy allows only that address's site, and for the stealth browser the challenge hosts as parts of a page. It
presses, types and solves nothing. It records what happened:

- `opened`: a page of the site answered with a success status, and shows no check.
- `check`: a bot check or CAPTCHA was showing, or asked a person, when its time was up.
- `blocked`: the site answered with an error status, such as 403 or 503.
- `error`: nothing answered, or the browser could not be driven.

It keeps and prints the host, the browser, the result, the status, the bytes and the seconds. No path, query, title or
page text. Its report is .checks/browser-scoreboard/latest.json, which no check reads.

**Read a site's terms first.** A site opening is not permission from that site to automate it, and the stealth browser
is not for YouTube or Google (Z14). It is the owner's to run, and in no verification profile.

It re-runs itself with the service's interpreter. Exit codes: 0 every address was tried; 2 no address, or Docker, the
service's environment or an image is missing.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal, Protocol
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / 'services/agent'
PYTHON = SERVICE / '.venv/bin/python'
REPORT = ROOT / '.checks/browser-scoreboard/latest.json'
BROWSERS = ('box', 'stealth')
# How long a page has to answer, and how long one that answered is watched for a check.
OPEN_SECONDS = 30.0
WATCH_SECONDS = 5.0
POLL_SECONDS = 0.25
LIMIT = 20

Result = Literal['opened', 'check', 'blocked', 'error']


@dataclass(frozen=True)
class Opening:
    """What one opening showed: the document's status, or None when nothing answered, whether a check showed, and the
    bytes the page's own requests took."""

    status: int | None
    check: bool
    size: int


@dataclass(frozen=True)
class Score:
    host: str
    browser: str
    result: Result
    status: int | None
    bytes: int
    seconds: float


class Opener(Protocol):
    async def __call__(self, url: str, browser: str) -> Opening: ...


def result_of(opening: Opening) -> Result:
    if opening.check:
        return 'check'
    if opening.status is None:
        return 'error'
    return 'opened' if opening.status < 400 else 'blocked'


def host_of(address: str) -> str | None:
    """The host of a plain https address, or None for anything else."""
    parts = urlsplit(address)
    if parts.scheme != 'https' or parts.username or parts.password or not parts.hostname:
        return None
    return parts.hostname.lower()


async def scores(addresses: list[str], opener: Opener, clock: Any = time.monotonic) -> list[Score]:
    """Each address once in each browser, one at a time. An opening that fails is an `error`, and the rest go on."""
    found = []
    for address in addresses:
        host = host_of(address)
        assert host is not None, 'checked as the arguments were read'
        for browser in BROWSERS:
            began = clock()
            try:
                opening = await opener(address, browser)
            except Exception as error:  # noqa: BLE001 - one address that can't be opened never stops the rest
                print(f'{host} {browser}: {type(error).__name__}', file=sys.stderr)
                opening = Opening(None, False, 0)
            found.append(Score(host, browser, result_of(opening), opening.status, opening.size, round(clock() - began, 1)))
    return found


def table(found: list[Score]) -> str:
    """One row per host, with each browser's result."""
    rows = []
    for host in dict.fromkeys(score.host for score in found):
        for score in (s for s in found if s.host == host):
            status = '-' if score.status is None else str(score.status)
            rows.append(f'{host:40} {score.browser:8} {score.result:8} {status:>4} {score.bytes:>10} bytes {score.seconds:>6} s')
    return '\n'.join(rows)


def report(found: list[Score]) -> dict[str, Any]:
    return {'schema_version': 'autobots.browser-scoreboard/v1', 'model': 'none', 'scores': [asdict(score) for score in found],
            'not_established': ['permission from any site', 'that a site opens tomorrow', 'H1', 'product acceptance']}


def zone() -> str:
    """This Mac's time zone, which a workspace's browse would take from its settings."""
    target = str(Path('/etc/localtime').resolve())
    return target.split('/zoneinfo/', 1)[1] if '/zoneinfo/' in target else 'UTC'


async def open_in(executor: Any, url: str, browser: str) -> Opening:
    """One session of that browser, one navigation, and what the worker's own guard saw of it."""
    from autobots.adapters.browser_cdp import CHALLENGE_HOSTS, Cdp, Patience, RequestGuard
    from autobots.adapters.browser_executor import Stealth
    from autobots.application.browse_turns import site_of

    stealth = Stealth(zone(), CHALLENGE_HOSTS) if browser == 'stealth' else None
    host = host_of(url) or ''
    session = await executor.start('scoreboard', 1, (site_of(host),), **({} if stealth is None else {'stealth': stealth}))
    try:
        cdp = await Cdp.connect(await session.websocket_url())
        guard = RequestGuard(cdp, submits=True, patience=None if stealth is None else Patience(CHALLENGE_HOSTS))
        await guard.start()
        page = next(iter(guard.pages))
        status: list[int] = []
        sizes: list[int] = []

        async def seen(message: dict[str, Any]) -> None:
            params = message.get('params', {})
            if message['method'] == 'Network.loadingFinished':
                sizes.append(int(params.get('encodedDataLength', 0)))
            if message['method'] == 'Network.responseReceived' and params.get('type') == 'Document' \
                    and params.get('frameId') == guard.frames.get(page):
                status.append(int(params['response']['status']))

        cdp.handlers.append(seen)
        await cdp.send('Network.enable', {}, page)
        await asyncio.wait_for(cdp.send('Page.navigate', {'url': url}, page), OPEN_SECONDS)
        for _ in range(int(OPEN_SECONDS / POLL_SECONDS)):
            if status or guard.failed or guard.bot_checks:
                break
            await asyncio.sleep(POLL_SECONDS)
        await asyncio.sleep(WATCH_SECONDS)
        await guard.settle()
        check = bool(guard.bot_checks or guard.checking)
        await cdp.close()
        return Opening(status[-1] if status else None, check, sum(sizes))
    finally:
        await executor.stop(session)


def parsed(argv: list[str]) -> list[str] | None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('address', nargs='*', help='a plain https address, opened once in each browser')
    addresses: list[str] = parser.parse_args(argv).address
    bad = [host for host in addresses if host_of(host) is None]
    if not addresses or bad or len(addresses) > LIMIT:
        print(f'ERROR: name 1 to {LIMIT} plain https addresses' + (f'; {len(bad)} are not' if bad else ''), file=sys.stderr)
        return None
    return list(dict.fromkeys(addresses))


def main(argv: list[str]) -> int:
    addresses = parsed(argv)
    if addresses is None:
        return 2
    if os.environ.get('AUTOBOTS_SCOREBOARD') != 'service':
        if not PYTHON.exists():
            print("ERROR: the service's environment is not prepared", file=sys.stderr)
            return 2
        env = {name: os.environ[name] for name in ('PATH', 'HOME', 'DOCKER_HOST', 'DOCKER_CONTEXT', 'DOCKER_CONFIG') if name in os.environ}
        env |= {'AUTOBOTS_SCOREBOARD': 'service', 'PYTHONPATH': str(SERVICE / 'src'), 'PYTHONDONTWRITEBYTECODE': '1'}
        return subprocess.run([str(PYTHON), str(Path(__file__).resolve()), *addresses], env=env, check=False).returncode
    from autobots.adapters.browser_executor import BrowserExecutor, ExecutorUnavailable

    executor = BrowserExecutor()

    async def opener(url: str, browser: str) -> Opening:
        return await open_in(executor, url, browser)

    for image in (executor.config.browser_image, executor.config.proxy_image, executor.config.stealth_image):
        if subprocess.run(['docker', 'image', 'inspect', image], capture_output=True, check=False).returncode:
            print(f'ERROR: {image} is not built, or Docker is not reachable: make browser-images', file=sys.stderr)
            return 2
    try:
        found = asyncio.run(scores(addresses, opener))
    except ExecutorUnavailable as missing:
        print(f'ERROR: {missing}', file=sys.stderr)
        return 2
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report(found), indent=2) + '\n')
    print(table(found))
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
