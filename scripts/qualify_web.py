#!/usr/bin/env python3
"""Run the real API and Next.js processes on loopback and drive them with a real browser.

Builds the web app, starts the API with an arranged membership and two web servers, one pointed at a
closed port, and runs the browser suite. Every value is generated for this run. No model is called,
no database is needed, and nothing is installed.

Exit codes: 0 passed, 1 a test failed, 2 prerequisite unavailable. `--retain <dir>` copies screenshots.
Passing establishes neither H1 nor product acceptance.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import time
from urllib import error as urlerror, request as urlrequest

import base64
import hashlib
import hmac

from harness_lib import fingerprint, project_root, reduced_env
from suites import WEB_SUITES
from toolchain import Unavailable, child_env, find_tools

REPORT = Path('.checks/web/qualification.json')
BROWSERS = Path('.cache/ms-playwright')
WORKSPACE_A = 'a0000000-0000-4000-8000-000000000001'
USER_A, USER_B = 'a1111111-1111-4111-8111-111111111111', 'b2222222-2222-4222-8222-222222222222'


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(('127.0.0.1', 0))
        return int(probe.getsockname()[1])


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()


def session_token(secret: str, user: str) -> str:
    claims = {'sub': user, 'aud': 'authenticated', 'role': 'authenticated', 'exp': int(time.time()) + 1800}
    signing = f"{b64(json.dumps({'alg': 'HS256', 'typ': 'JWT'}).encode())}.{b64(json.dumps(claims).encode())}"
    return f'{signing}.{b64(hmac.new(secret.encode(), signing.encode(), hashlib.sha256).digest())}'


def session_cookie(access_token: str) -> str:
    """The value @supabase/ssr stores: its own encoding, with the token signed by the arranged secret."""
    session = {'access_token': access_token, 'refresh_token': 'fixture', 'token_type': 'bearer', 'expires_in': 1800,
               'expires_at': int(time.time()) + 1800, 'user': {'id': USER_A, 'aud': 'authenticated', 'app_metadata': {}, 'user_metadata': {}, 'created_at': ''}}
    return 'base64-' + b64(json.dumps(session).encode())


def wait_until_up(url: str, process: subprocess.Popen, seconds: float = 60.0) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise Unavailable(f'a service exited early with {process.returncode}')
        try:
            with urlrequest.urlopen(url, timeout=2):
                return
        except urlerror.HTTPError:
            return
        except OSError:
            time.sleep(0.25)
    raise Unavailable(f'a service did not answer within {seconds} seconds')


def stop(process: subprocess.Popen) -> None:
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)


def start(argv: Sequence[str], env: Mapping[str, str], cwd: Path) -> subprocess.Popen:
    return subprocess.Popen(list(argv), env=dict(env), cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, start_new_session=True)


def summarize(path: Path) -> tuple[list[dict], dict]:
    data = json.loads(path.read_text())
    cases = []
    def walk(suite: Mapping) -> None:
        for spec in suite.get('specs', []):
            for test in spec.get('tests', []):
                results = test.get('results', [])
                cases.append({'id': spec['title'], 'file': suite.get('file', ''), 'status': results[-1]['status'] if results else 'not_run',
                              'class': 'disposable', 'model_transport': 'none'})
        for child in suite.get('suites', []):
            walk(child)
    for suite in data.get('suites', []):
        walk(suite)
    return cases, data.get('stats', {})


def run_problems(path: Path, returncode: int) -> list[str]:
    """Why a browser run doesn't count, though every case it reported may have passed."""
    problems = [f'exit {returncode}'] if returncode else []
    if not path.exists():
        return [*problems, 'no report']
    if json.loads(path.read_text()).get('errors'):
        problems.append('errors outside any test')
    if not summarize(path)[0]:
        problems.append('no tests ran')
    return problems


def qualify(root: Path, retain: Path | None) -> int:
    (root / REPORT).unlink(missing_ok=True)
    tools = find_tools(root)
    python = root / 'services/agent/.venv/bin/python'
    web = root / 'apps/web'
    next_bin, playwright = web / 'node_modules/.bin/next', web / 'node_modules/.bin/playwright'
    browsers = root / BROWSERS
    if not python.exists() or not next_bin.exists() or not playwright.exists():
        raise Unavailable('not prepared, run scripts/toolchain.py bootstrap explicitly')
    if not any(browsers.glob('chromium-*')):
        raise Unavailable(f'no browser under {BROWSERS}; install the pinned one deliberately, see the runbook')
    output = root / '.checks/web/output'
    shutil.rmtree(output, ignore_errors=True)
    output.mkdir(parents=True)
    screenshots = root / '.checks/web/screenshots'
    shutil.rmtree(screenshots, ignore_errors=True)
    screenshots.mkdir(parents=True)
    base = {**child_env(root, tools, verifying=True), 'PLAYWRIGHT_BROWSERS_PATH': str(browsers)}
    built = subprocess.run([str(next_bin), 'build'], env=base, cwd=web, capture_output=True, text=True, errors='replace', timeout=300, check=False)
    if built.returncode:
        print(built.stdout[-1500:], built.stderr[-1500:], file=sys.stderr)
        return 1
    internal, jwt_secret = secrets.token_hex(32), secrets.token_hex(32)
    api_port, web_port, closed_web_port, closed_api_port = free_port(), free_port(), free_port(), free_port()
    api_url, web_url, unavailable_url = f'http://127.0.0.1:{api_port}', f'http://127.0.0.1:{web_port}', f'http://127.0.0.1:{closed_web_port}'
    api_env = {**reduced_env(), 'PYTHONPATH': str(root / 'services/agent/src'), 'PYTHONDONTWRITEBYTECODE': '1',
               'AUTOBOTS_INTERNAL_TOKEN': internal, 'AUTOBOTS_JWT_SECRET': jwt_secret,
               'AUTOBOTS_TEST_USER_A': USER_A, 'AUTOBOTS_TEST_WORKSPACE_A': WORKSPACE_A}
    web_env = {**base, 'AUTOBOTS_INTERNAL_TOKEN': internal, 'AUTOBOTS_API_URL': api_url, 'AUTOBOTS_ALLOWED_ORIGIN': web_url, 'NODE_ENV': 'production',
               'AUTOBOTS_SUPABASE_URL': f'http://127.0.0.1:{closed_api_port}', 'AUTOBOTS_SUPABASE_ANON_KEY': 'fixture-anon-key'}
    unavailable_env = {**web_env, 'AUTOBOTS_API_URL': f'http://127.0.0.1:{closed_api_port}', 'AUTOBOTS_ALLOWED_ORIGIN': unavailable_url}
    processes = []
    started_at = time.monotonic()
    report = output / 'playwright.json'
    try:
        processes.append(start([str(python), str(root / 'tests/web/fixture_api.py'), str(api_port)], api_env, root))
        processes.append(start([str(next_bin), 'start', '-H', '127.0.0.1', '-p', str(web_port)], web_env, web))
        processes.append(start([str(next_bin), 'start', '-H', '127.0.0.1', '-p', str(closed_web_port)], unavailable_env, web))
        wait_until_up(f'{api_url}/v1/health', processes[0])
        wait_until_up(web_url, processes[1])
        wait_until_up(unavailable_url, processes[2])
        test_env = {**base, 'AUTOBOTS_WEB_URL': web_url, 'AUTOBOTS_API_URL': api_url, 'AUTOBOTS_WEB_UNAVAILABLE_URL': unavailable_url,
                    'AUTOBOTS_TEST_INTERNAL_TOKEN': internal, 'AUTOBOTS_TEST_TOKEN_A': session_token(jwt_secret, USER_A),
                    'AUTOBOTS_TEST_SESSION_A': session_cookie(session_token(jwt_secret, USER_A)),
                    'AUTOBOTS_TEST_SESSION_B': session_cookie(session_token(jwt_secret, USER_B)),
                    'AUTOBOTS_TEST_SESSION_FORGED': session_cookie(session_token('wrong-secret-of-a-similar-length', USER_A)),
                    'AUTOBOTS_TEST_WORKSPACE_A': WORKSPACE_A,
                    'AUTOBOTS_WEB_REPORT': str(report), 'AUTOBOTS_WEB_OUTPUT': str(output / 'results'), 'AUTOBOTS_WEB_SCREENSHOTS': str(screenshots)}
        result = subprocess.run([str(playwright), 'test', *WEB_SUITES, '--config', 'playwright.config.ts'], env=test_env, cwd=web,
                                capture_output=True, text=True, errors='replace', timeout=500, check=False)
    finally:
        for process in processes:
            stop(process)
    if not report.exists():
        print(result.stdout[-2000:], result.stderr[-2000:], file=sys.stderr)
        raise Unavailable('the browser suite produced no report')
    cases, stats = summarize(report)
    failed = [case['id'] for case in cases if case['status'] != 'passed']
    skipped = int(stats.get('skipped', 0))
    passed = result.returncode == 0 and not failed and not skipped and bool(cases)
    if not passed:
        print(result.stdout[-3500:], file=sys.stderr)
    shots = sorted(path.name for path in screenshots.glob('*.png'))
    if retain is not None:
        retain.mkdir(parents=True, exist_ok=True)
        for name in shots:
            shutil.copy2(screenshots / name, retain / name)
    path = root / REPORT
    path.write_text(json.dumps({'schema_version': 'autobots.web-qualification/v1', 'completed_at_utc': datetime.now(timezone.utc).isoformat(),
                                'duration_seconds': round(time.monotonic() - started_at, 1), 'input_fingerprint': fingerprint(root),
                                'status': 'passed' if passed else 'failed', 'target_class': 'local processes with an arranged membership',
                                'stats': {'expected': stats.get('expected'), 'unexpected': stats.get('unexpected'), 'skipped': skipped},
                                'screenshots': shots, 'cases': cases,
                                'not_established': ['H1', 'product acceptance', 'real Auth sessions', 'real membership', 'manual zoom review']}, indent=2) + '\n')
    print(f"{'PASS' if passed else 'FAIL'}: {stats.get('expected')} browser tests passed, {stats.get('unexpected')} failed, {skipped} skipped.")
    return 0 if passed else 1


def main() -> int:
    root = project_root()
    retain = None
    if len(sys.argv) == 3 and sys.argv[1] == '--retain':
        retain = (root / sys.argv[2]).resolve()
        if not retain.is_relative_to(root / 'docs/engineering/evidence'):
            print('ERROR: --retain must name a directory under docs/engineering/evidence.', file=sys.stderr)
            return 2
    elif len(sys.argv) != 1:
        print('usage: qualify_web.py [--retain docs/engineering/evidence/<work item>]', file=sys.stderr)
        return 2
    try:
        return qualify(root, retain)
    except Unavailable as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
