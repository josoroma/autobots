"""The API and worker processes an operations-style qualifier runs against its disposable stack (SCRP-06).

Moved from qualify_operations.py, which six scripts imported for them. The stack is described by what is used
of it, so this strictly typed module never loads app_db.py.
"""
from __future__ import annotations

import json
import os
import secrets
import signal
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import IO, Protocol
from urllib import error, request

from qualification.children import CHECK_PYTHON, launch, service_env
from qualification.errors import Unavailable

# Polled readiness ignores these, which a service that is still starting raises.
STARTING = (OSError, ValueError, KeyError)
# A tracing key the bootstrap must ignore, arranged in every process's environment.
TRACE_KEY = 'lsv2-planted-trace-key'


class RuntimeStack(Protocol):
    """What Ops uses of an app_db.AppStack."""

    runtime_password: str
    values: dict[str, str]

    def runtime(self, statements: str) -> subprocess.CompletedProcess[str]: ...


class Ops:
    """The API and worker processes of one qualifier run, each logging to its own local file."""

    def __init__(self, root: Path, stack: RuntimeStack, base: str, db_port: int, logs: Path) -> None:
        self.root, self.stack, self.base, self.logs = root, stack, base, logs
        self.url = f'postgresql://autobots_runtime:{stack.runtime_password}@127.0.0.1:{db_port}/postgres'
        self.internal = secrets.token_hex(24)
        self.processes: list[subprocess.Popen[bytes]] = []
        self.handles: list[IO[str]] = []
        self.env = service_env(root, self.url, AUTOBOTS_SUPABASE_URL=base, AUTOBOTS_SERVICE_ROLE_KEY=stack.values['SERVICE_ROLE_KEY'],
                               AUTOBOTS_STORAGE_BASE=base, AUTOBOTS_STORAGE_SERVICE=stack.values['SERVICE_ROLE_KEY'], AUTOBOTS_MIN_FREE_BYTES='1',
                               # Arranged: what a host might have exported. The bootstrap has to turn it off.
                               LANGSMITH_TRACING='true', LANGCHAIN_TRACING_V2='true', LANGSMITH_API_KEY=TRACE_KEY,
                               LANGSMITH_ENDPOINT='https://collector.example.invalid')

    def spawn(self, name: str, argv: list[str], extra: dict[str, str] | None = None) -> subprocess.Popen[bytes]:
        handle = (self.logs / f'{name}.log').open('a')
        self.handles.append(handle)
        process = subprocess.Popen(argv, env={**self.env, **(extra or {})}, cwd=self.root, stdin=subprocess.DEVNULL,
                                   stdout=handle, stderr=handle, start_new_session=True)
        self.processes.append(process)
        return process

    def api(self, port: int, config_root: Path, extra: dict[str, str] | None = None) -> subprocess.Popen[bytes]:
        api_env = {'AUTOBOTS_INTERNAL_TOKEN': self.internal, 'AUTOBOTS_JWT_SECRET': self.stack.values['JWT_SECRET'],
                   'AUTOBOTS_CONFIG_ROOT': str(config_root), 'NODE_ENV': 'production',
                   'AUTOBOTS_PROVIDER_MASTER_KEY_FILE': str(config_root / 'secrets/master.key'), **(extra or {})}
        return self.spawn(f'api-{port}', [str(self.root / CHECK_PYTHON), '-m', 'uvicorn', '--factory', 'autobots.api.main:create_configured_app',
                                          '--host', '127.0.0.1', '--port', str(port), '--no-access-log'], api_env)

    def fixture_worker(self, name: str, hold: float, drain: float, marker: Path, mode: str = 'fresh',
                       profile: str | None = None) -> subprocess.Popen[bytes]:
        return self.spawn(name, [str(self.root / CHECK_PYTHON), str(self.root / 'tests/db/operations_worker.py'), self.url, name, str(hold),
                                 str(drain), str(marker), mode],
                          {'AUTOBOTS_TEST_ROUTE_PROFILE': profile} if profile else None)

    def sql(self, statement: str) -> str:
        result = self.stack.runtime(statement)
        return result.stdout.strip().splitlines()[0] if result.returncode == 0 and result.stdout.strip() else ''

    def admit(self, workspace: str) -> str:
        result = launch([str(self.root / CHECK_PYTHON), str(self.root / 'tests/db/operations_check.py'), 'admit', workspace], env=self.env,
                        timeout=60, label='the fixture admission')
        lines = result.stdout.strip().splitlines()
        if result.returncode or not lines:
            raise Unavailable(f'the fixture job was not admitted: exit {result.returncode}: {result.stderr.strip()[-300:]}')
        return lines[-1]

    def stop_all(self) -> None:
        for process in self.processes:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(10)
        for handle in self.handles:
            handle.close()


def api_call(port: int, internal: str, token: str, method: str = 'GET', path: str = '/v1/operations/local-status',
             body: bytes | None = None, extra: dict[str, str] | None = None) -> tuple[int, str]:
    headers = {'X-Autobots-Internal': internal, 'Authorization': f'Bearer {token}', 'Content-Type': 'application/json', **(extra or {})}
    try:
        with request.urlopen(request.Request(f'http://127.0.0.1:{port}{path}', data=body, method=method, headers=headers), timeout=20) as reply:
            return int(reply.status), bytes(reply.read()).decode(errors='replace')
    except error.HTTPError as failure:
        return int(failure.code), bytes(failure.read()).decode(errors='replace')


def conditions(body: str) -> dict[str, str]:
    """Each readiness condition's code, by its name, from a local-status reply."""
    return {str(item['name']): str(item['code']) for item in json.loads(body)['conditions']}


def wait(check: Callable[[], object], seconds: float) -> bool:
    """Whether `check` held within `seconds`, polled every half second while the service it asks may be starting."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            if check():
                return True
        except STARTING:
            pass
        time.sleep(0.5)
    return False


def exited(process: subprocess.Popen[bytes], seconds: float) -> int | None:
    try:
        return process.wait(seconds)
    except subprocess.TimeoutExpired:
        return None


def durable_counts(ops: Ops) -> str:
    return ops.sql("select (select count(*) from public.runs) || '/' || (select count(*) from public.run_events) || '/' || "
                   "(select count(*) from app_private.tool_receipts) || '/' || (select count(*) from agent_runtime.checkpoints) || '/' || "
                   "(select count(*) from app_private.idempotency_receipts);")
