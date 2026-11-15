#!/usr/bin/env python3
"""Start, await, stop and report the persistent install's native processes for `make` (SQLI-10).

The Makefile names each process and its command and stays the documented entry point; this script keeps the
rules that make starting and stopping them safe:

- A pid file holds the pid and that process's start time. A pid file can outlive a reboot, and its pid can then
  belong to something else, so the pid counts only while its start time matches. Both reads pin LC_ALL and TZ,
  so another shell's settings can't make a live worker, possibly a paid one, look stopped.
- A start is refused beside a copy this install doesn't track, which would clash on its port or run a second
  worker, and that copy is never stopped here.
- A stop sends TERM and waits out the worker's drain. It never sends KILL, because a step still running may be in
  a paid call; docs/engineering/runbooks/operations.md covers a cut-short drain.
- Awaiting a process: our own process has to hold the port, so another project's server on it doesn't count, and
  then any HTTP reply will do, as the API answers 401 without its credential.

A launched process gets the caller's environment, the install's app.env read as data, and with --keys the tool
keys and browsing switch from the repository's .env (scripts/tool_keys_env.py). No value from either file is
printed. Nothing here changes the database or removes a container or a volume. Exit codes: 0 done, 1 refused
or failed.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from http.client import HTTPException
from pathlib import Path
from typing import Protocol
from urllib import error, request

from harness_lib import parse_dotenv
from tool_keys_env import switch_values, tool_values

# What a stray copy looks like when it holds no port. The brackets keep this pattern from matching itself.
STRAY_PATTERNS = {'worker': 'autobots[.]operations[.]worker'}
# The locale and zone `ps` formats a start time in, for every read.
PINNED = {'LC_ALL': 'C', 'TZ': 'UTC'}
AWAIT_TRIES = 30
# The worker drains for up to 30 seconds.
STOP_SECONDS = 45


class Processes(Protocol):
    """The process table and the network, as this script uses them, so tests can stand in for both."""

    def start_time(self, pid: int) -> str: ...

    def listening(self, port: int) -> list[int]: ...

    def matching(self, pattern: str) -> list[int]: ...

    def ours(self) -> set[int]: ...

    def alive(self, pid: int) -> bool: ...

    def terminate(self, pid: int) -> None: ...

    def spawn(self, argv: Sequence[str], env: Mapping[str, str], log: Path) -> int: ...

    def answers(self, url: str) -> bool: ...

    def sleep(self, seconds: float) -> None: ...


def output(argv: Sequence[str], env: Mapping[str, str] | None = None) -> str:
    """What a read-only system command printed, or nothing when it failed or found nothing."""
    try:
        result = subprocess.run(list(argv), env=dict(env) if env is not None else None, capture_output=True, text=True, errors='replace',
                                timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return ''
    return result.stdout if result.returncode == 0 else ''


def pids(text: str) -> list[int]:
    return [int(item) for item in text.split() if item.isdigit()]


class System:
    """The real process table: ps, lsof, pgrep and signals."""

    def start_time(self, pid: int) -> str:
        return output(['ps', '-p', str(pid), '-o', 'lstart='], {**os.environ, **PINNED}).strip() if pid > 0 else ''

    def listening(self, port: int) -> list[int]:
        return pids(output(['lsof', '-nP', '-t', f'-iTCP:{port}', '-sTCP:LISTEN']))

    def matching(self, pattern: str) -> list[int]:
        return pids(output(['pgrep', '-f', pattern]))

    def ours(self) -> set[int]:
        """This process and its ancestors, whose command lines name what they start, so none is a stray copy."""
        found, pid = set(), os.getpid()
        while pid > 1 and pid not in found:
            found.add(pid)
            parent = pids(output(['ps', '-o', 'ppid=', '-p', str(pid)]))
            pid = parent[0] if parent else 0
        return found

    def alive(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    def terminate(self, pid: int) -> None:
        os.kill(pid, signal.SIGTERM)

    def spawn(self, argv: Sequence[str], env: Mapping[str, str], log: Path) -> int:
        """In the background, in its own session, ignoring hangups as nohup would, with no stdin and its output
        appended to `log`."""
        previous = signal.signal(signal.SIGHUP, signal.SIG_IGN)
        try:
            with log.open('a') as handle:
                process = subprocess.Popen(list(argv), env=dict(env), stdin=subprocess.DEVNULL, stdout=handle, stderr=subprocess.STDOUT,
                                           start_new_session=True)
        finally:
            signal.signal(signal.SIGHUP, previous)
        return process.pid

    def answers(self, url: str) -> bool:
        try:
            with request.urlopen(url, timeout=2):
                return True
        except error.HTTPError:
            return True
        except (error.URLError, OSError, ValueError, HTTPException):
            # No reply yet, as curl saw it: refused, timed out, or a connection closed before its status line.
            return False

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


class LocalApp:
    """The install's processes, each tracked by its pid file under `run_dir` and logging under `log_dir`."""

    def __init__(self, run_dir: Path, log_dir: Path, processes: Processes) -> None:
        self.run_dir, self.log_dir, self.processes = run_dir, log_dir, processes

    def pid_file(self, name: str) -> Path:
        return self.run_dir / f'{name}.pid'

    def log(self, name: str) -> Path:
        return self.log_dir / f'{name}.log'

    def running(self, name: str) -> int | None:
        """The tracked pid while it is still the process that was started, or None."""
        try:
            lines = self.pid_file(name).read_text().splitlines()
        except OSError:
            return None
        if len(lines) < 2 or not lines[0].strip().isdigit():
            return None
        pid = int(lines[0].strip())
        started = self.processes.start_time(pid)
        return pid if started and started == lines[1].strip() else None

    def strays(self, name: str, port: int | None) -> list[int]:
        """Processes that look like this one without being the tracked one: a copy started outside this file, or one
        whose pid file was lost."""
        if port is not None:
            found = self.processes.listening(port)
        elif name in STRAY_PATTERNS:
            found = self.processes.matching(STRAY_PATTERNS[name])
        else:
            return []
        excluded = self.processes.ours()
        return [pid for pid in found if pid not in excluded]

    def start(self, name: str, argv: Sequence[str], env: Mapping[str, str] | Callable[[], Mapping[str, str]], port: int | None,
              settle: float = 0) -> int:
        """Start `argv` unless it runs or a stray copy holds its place. `env` may be a function, called only when a
        process really starts, so a running one never needs the install's files."""
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        if self.running(name) is not None:
            print(f'{name}: already running')
        elif held := ' '.join(str(pid) for pid in self.strays(name, port)):
            print(f'{name}: refused. pid {held} looks like a copy of the {name} that this install does not track, so a new one would clash with it.')
            print(f'  See it with: ps -o pid,lstart,command -p {held}')
            print(f'  Stop it with: kill -TERM {held} (a worker drains for up to 30 seconds), then run this again.')
            return 1
        else:
            try:
                resolved = env() if callable(env) else env
            except OSError:
                print(f"{name}: the install's app.env could not be read. Use: make install", file=sys.stderr)
                return 1
            try:
                pid = self.processes.spawn(argv, resolved, self.log(name))
            except OSError as problem:
                print(f'{name}: could not start: {type(problem).__name__}')
                return 1
            self.pid_file(name).write_text(f'{pid}\n{self.processes.start_time(pid)}\n')
            print(f'{name}: started')
        if settle:
            self.processes.sleep(settle)
            if self.running(name) is None:
                print(f'{name}: exited. Read {self.log(name)}')
                return 1
        return 0

    def wait_until_answering(self, name: str, port: int, url: str) -> int:
        tries = 0
        while True:
            pid = self.running(name)
            if pid is not None and pid in self.processes.listening(port) and self.processes.answers(url):
                print(f'{name}: answering at {url}')
                return 0
            tries += 1
            if tries >= AWAIT_TRIES or self.running(name) is None:
                print(f'{name}: not answering at {url}. Something else may hold the port. Read {self.log(name)}')
                return 1
            self.processes.sleep(1)

    def stop(self, name: str, port: int | None) -> int:
        pid = self.running(name)
        if pid is not None:
            try:
                self.processes.terminate(pid)
            except ProcessLookupError:
                pass  # It exited since it was read as running, so it is stopped, as the shell's kill -0 found.
            waited = 0
            while self.processes.alive(pid):
                waited += 1
                if waited >= STOP_SECONDS:
                    # The pid file stays, so the next stop or status still finds it.
                    print(f'{name}: still running after {STOP_SECONDS} seconds, pid {pid}. Read {self.log(name)}')
                    return 1
                self.processes.sleep(1)
            print(f'{name}: stopped')
        else:
            print(f'{name}: not running')
            if held := ' '.join(str(stray) for stray in self.strays(name, port)):
                print(f'{name}: pid {held} looks like one this install does not track, so it was left running.')
                print(f'  See it with: ps -o pid,lstart,command -p {held}. Stop it with: kill -TERM {held}')
        self.pid_file(name).unlink(missing_ok=True)
        return 0

    def status(self, names: Sequence[str]) -> int:
        for name in names:
            pid = self.running(name)
            print(f'{name}: running, pid {pid}' if pid is not None else f'{name}: not running')
        return 0


def launch_env(base: Mapping[str, str], app_env: str, *, dotenv: str | None, node_bin: str, inference: str) -> dict[str, str]:
    """A launched process's environment: the caller's, then app.env's values, then with `dotenv` its tool keys and
    browsing switch only, then the service's source, the pinned Node first on the search path, no Next.js
    telemetry and the inference switch. Empty `inference` means off; only `enabled` turns on paid inference."""
    env = {**base, **parse_dotenv(app_env, 'app')}
    if dotenv is not None:
        env.update(tool_values(dotenv))
        env.update(switch_values(dotenv))
    path = env.get('PATH', '')
    env.update(PYTHONPATH='services/agent/src', NEXT_TELEMETRY_DISABLED='1', AUTOBOTS_WORKER_INFERENCE=inference,
               PATH=f'{node_bin}{os.pathsep}{path}' if node_bin else path)
    return env


def recorded(install_dir: Path, field: str) -> int:
    """Print one field of install.json, which holds no secret. Absent, it prints nothing and exits 1."""
    try:
        value = json.loads((install_dir / 'install.json').read_text())[field]
    except (OSError, ValueError, KeyError, TypeError):
        print(f'no install records {field} at {install_dir}', file=sys.stderr)
        return 1
    print(value)
    return 0


def parser() -> argparse.ArgumentParser:
    commands = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands.add_argument('--run-dir', type=Path)
    commands.add_argument('--log-dir', type=Path)
    verbs = commands.add_subparsers(dest='verb', required=True)
    start = verbs.add_parser('start')
    start.add_argument('name')
    start.add_argument('--port', type=int)
    start.add_argument('--env-file', type=Path, required=True)
    start.add_argument('--keys', type=Path, help='the .env file whose tool keys and browsing switch the process gets')
    start.add_argument('--inference', default='')
    start.add_argument('--node-bin', default='')
    start.add_argument('--settle', type=float, default=0)
    waiting = verbs.add_parser('await')
    waiting.add_argument('name')
    waiting.add_argument('--port', type=int, required=True)
    waiting.add_argument('--url', required=True)
    stop = verbs.add_parser('stop')
    stop.add_argument('name')
    stop.add_argument('--port', type=int)
    status = verbs.add_parser('status')
    status.add_argument('names', nargs='+')
    field = verbs.add_parser('recorded')
    field.add_argument('install_dir', type=Path)
    field.add_argument('field')
    return commands


def main(argv: Sequence[str] | None = None, processes: Processes | None = None) -> int:
    """Everything after the first `--` is the command to start, whose own options this never reads."""
    given = list(sys.argv[1:] if argv is None else argv)
    split = given.index('--') if '--' in given else len(given)
    arguments = parser().parse_args(given[:split])
    command = given[split + 1:]
    if arguments.verb == 'recorded':
        return recorded(arguments.install_dir, arguments.field)
    if arguments.run_dir is None or arguments.log_dir is None:
        print('local_app.py needs --run-dir and --log-dir', file=sys.stderr)
        return 1
    app = LocalApp(arguments.run_dir, arguments.log_dir, processes or System())
    if arguments.verb == 'start':
        if not command:
            print(f'{arguments.name}: no command to start', file=sys.stderr)
            return 1

        def environment() -> dict[str, str]:
            keys: Path | None = arguments.keys
            # No .env passes no key, as a blank value does.
            dotenv = (keys.read_text(errors='replace') if keys.is_file() else '') if keys is not None else None
            return launch_env(os.environ, arguments.env_file.read_text(), dotenv=dotenv, node_bin=arguments.node_bin,
                              inference=arguments.inference)

        return app.start(arguments.name, command, environment, arguments.port, arguments.settle)
    if arguments.verb == 'await':
        return app.wait_until_answering(arguments.name, arguments.port, arguments.url)
    if arguments.verb == 'stop':
        return app.stop(arguments.name, arguments.port)
    return app.status(arguments.names)


if __name__ == '__main__':
    raise SystemExit(main())
