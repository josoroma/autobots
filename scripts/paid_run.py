"""One paid run's decisions and shared mechanics, for the four entry points that spend real money under
the shared cap: `persistent_install.py goal` and `examples`, `live_goal.py` and `qualify_release.py`
(refactor plan R-23, SCRP-03).

The decisions are pure: watchdog_verdict, settlement and goal_exit_code. PaidSession holds the
mechanics: the live-key helper (autobots.operations.live_key, in its own process so no script holds
the key), the runtime role's SQL, which answers None when it can't be read and never '', the owner's
sign-in, and the one worker that has inference on. Each entry point still refuses without `--paid`;
the persistent install also calls refuse_other_work and takes its reservation on the shared ledger
(`reserve`) before any request. The watchdog SIGKILLs the worker past its limit, after
UNREADABLE_POLL_LIMIT unreadable spend polls in a row (Decision 0028 E2), and when a poll raises, so the
worker is never left running unwatched. A run that can still go on holds its whole reservation.
tests/harness/test_paid_run.py proves all of it with fakes, and no paid run.

It needs only the standard library at import. `reserve` loads the service's ledger, so the entry points
that reserve run with the service's interpreter.
"""
from __future__ import annotations

import importlib
import json
import signal
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, MutableMapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, NamedTuple, Protocol, TypedDict
from urllib import error, request

from qualification.children import CHECK_PYTHON, SERVICE_SOURCE
from qualification.errors import Refused, Unavailable

LIVE_KEY = 'autobots.operations.live_key'
INFERENCE_SWITCH = 'AUTOBOTS_WORKER_INFERENCE'
ACTIVE = frozenset({'queued', 'running', 'verifying', 'cancelling'})
TERMINAL = frozenset({'succeeded', 'failed', 'cancelled'})
POLL_SECONDS = 3.0
# Decision 0028 E2: this many unreadable spend polls in a row stop the worker, as a cap breach does.
UNREADABLE_POLL_LIMIT = 3
# OpenRouter's usage figure can lag, so the after-run read waits. It checks the ledger, never replaces it.
KEY_USAGE_LAG_SECONDS = 60.0
WORKER_STOP_SECONDS = 60
HELPER_SECONDS = 120
HTTP_SECONDS = 30
HELPER_ERROR_SHOWN = 300
# The worker claims whatever is queued, in any workspace, so a paid run first asks what else is there.
OTHER_WORK = ("select (select count(*) from app_private.run_jobs where status in ('queued', 'claimed')) "
              "+ (select count(*) from public.routines where enabled);")

# The service's ledger entry (autobots.operations.paid.ledger LedgerState and LedgerEntry),
# typed here by shape: the scripts load the service at run time, from its own interpreter.
LedgerState = Literal['reserved', 'settled', 'usage_unreported', 'uncertain', 'not_started', 'run_not_finished']


class LedgerEntry(TypedDict):
    label: str
    worst_case: int
    reported: int | None
    state: LedgerState
    at: str


class Ledger(Protocol):
    """The shared ledger on disk (autobots.operations.paid.ledger.Ledger, Decision 0009)."""

    cap: int

    def reserve(self, label: str, worst_case: int) -> LedgerEntry: ...

    def settle(self, entry: LedgerEntry, reported: int | None, state: LedgerState) -> None: ...

    def committed(self) -> int: ...


class Database(Protocol):
    """A stack whose runtime role answers SQL (app_db.AppStack)."""

    def runtime(self, statements: str) -> subprocess.CompletedProcess[str]: ...


class Worker(Protocol):
    """The part of a worker process a paid run uses (subprocess.Popen)."""

    def poll(self) -> int | None: ...

    def send_signal(self, sig: int) -> None: ...

    def wait(self, timeout: float | None = None) -> int: ...

    def kill(self) -> None: ...


# Starts the worker with the given arguments and these variables on top of its stack's environment.
Spawn = Callable[[list[str], dict[str, str]], Worker]
Report = MutableMapping[str, Any]
WatchVerdict = Literal['continue', 'unreadable', 'over_cap', 'spend_unreadable']
WatchEnd = Literal['finished', 'timed_out', 'worker_exited', 'over_cap', 'spend_unreadable', 'watch_failed']
STOPS: frozenset[str] = frozenset({'over_cap', 'spend_unreadable', 'watch_failed'})


@dataclass(frozen=True)
class Watch:
    """One poll's verdict, and how many polls in a row have now been unreadable."""

    verdict: WatchVerdict
    unreadable_polls: int


def parsed_spend(text: str | None) -> int | None:
    """A committed spend in micro-USD, or None when the answer is missing or isn't a whole number."""
    return int(text) if text is not None and text.isdigit() else None


def watchdog_verdict(committed: int | None, limit: int, unreadable_polls: int) -> Watch:
    """`committed` is None when this poll couldn't read it, and `unreadable_polls` counts the unreadable
    polls in a row before this one. Past the limit stops; so does the third unreadable poll in a row
    (Decision 0028 E2). A single unreadable poll is counted and the run goes on."""
    if committed is None:
        count = unreadable_polls + 1
        return Watch('spend_unreadable' if count >= UNREADABLE_POLL_LIMIT else 'unreadable', count)
    return Watch('over_cap' if committed > limit else 'continue', 0)


class Settlement(NamedTuple):
    reported: int | None
    state: LedgerState


def settlement(started: bool, finals: Mapping[str, str], charged: int | None) -> Settlement:
    """How a reservation settles. Nothing started releases it. Every run terminal with a known charge
    settles at that charge. Anything else holds the whole reservation, since a run that isn't finished
    can spend again on resume, and an unknown charge is never released (Decision 0028 E2)."""
    if not started:
        return Settlement(0, 'not_started')
    if finals and charged is not None and all(status in TERMINAL for status in finals.values()):
        return Settlement(charged, 'settled')
    return Settlement(None, 'run_not_finished')


def goal_exit_code(report: Mapping[str, Any], achieved: bool) -> int:
    """0 only when `achieved`, every after-run check ran, the key was found nowhere and the watchdog never
    fired. A spend that couldn't be read is a failed check. `achieved` is the outcome each entry point
    states: its run succeeded, for `goal` and `live_goal`; every example run finished, the workflow
    terminal or at its approval gate, for `examples` (persistent_install.examples_done)."""
    found = report.get('key_found')
    leaked = isinstance(found, dict) and any(found.values())
    clean = 'after_run_check_failed' not in report and not leaked and not report.get('watchdog_fired')
    return 0 if achieved and clean else 1


def refuse_other_work(found: str | None) -> None:
    """The worker claims whatever is queued, in any workspace, so anything else would spend unseen."""
    if found == '0':
        return
    if found is None or not found.isdigit():
        raise Refused('Could not read what else is queued, so nothing was sent')
    raise Refused(f'{found} other queued jobs or enabled routines would run on this paid worker. Settle them first. Nothing was sent')


def note_failed(report: Report, what: str) -> None:
    """Every check that couldn't run stays listed, and the exit code reads this."""
    earlier = report.get('after_run_check_failed')
    report['after_run_check_failed'] = f'{earlier}; {what}' if earlier else what


def http_json(method: str, url: str, headers: Mapping[str, str], body: Mapping[str, Any] | None = None) -> tuple[int, str]:
    data = None if body is None else json.dumps(body).encode()
    try:
        with request.urlopen(request.Request(url, data=data, method=method, headers=dict(headers)), timeout=HTTP_SECONDS) as reply:
            return int(reply.status), reply.read().decode(errors='replace')
    except error.HTTPError as failure:
        return failure.code, failure.read().decode(errors='replace')


def reserve(root: Path, path: Path, label: str, limit: int) -> tuple[Ledger, LedgerEntry]:
    """Before any request: the run's whole budget has to fit what's left of the shared cap (Decision 0009)."""
    if str(root / SERVICE_SOURCE) not in sys.path:
        sys.path.insert(0, str(root / SERVICE_SOURCE))
    trial = importlib.import_module('autobots.operations.reasoning_trial')
    ledgers = importlib.import_module('autobots.operations.paid.ledger')
    ledger: Ledger = ledgers.Ledger(path, trial.SHARED_CAP_MICRO_USD)
    try:
        return ledger, ledger.reserve(label, limit)
    except ledgers.CapReached:
        raise Refused(f'a run limited to {limit} micro-USD would take the shared ledger, at {ledger.committed()}, '
                      f'past {ledger.cap}. Nothing was sent') from None


def settle(ledger: Ledger, entry: LedgerEntry, started: bool, finals: Mapping[str, str], charged: int | None, report: Report) -> None:
    """Settles a still-reserved entry by `settlement`, and reports where the ledger stands."""
    if entry['state'] == 'reserved':
        decided = settlement(started, finals, charged)
        ledger.settle(entry, decided.reported, decided.state)
    report['ledger_state'] = entry['state']
    report['shared_ledger_committed_micro_usd'] = ledger.committed()


@dataclass
class WatchResult:
    """How a watch ended, the runs' last statuses, each change of them, every unreadable spend poll and,
    for `watch_failed`, what the poll raised."""

    end: WatchEnd
    statuses: dict[str, str]
    timeline: list[dict[str, Any]]
    unreadable_polls: int
    worker_exit: int | None
    failure: str | None = None

    def record(self, report: Report) -> None:
        report['timeline'] = self.timeline
        report['unreadable_spend_polls'] = self.unreadable_polls
        if self.end in STOPS:
            report['watchdog_fired'] = True
            report['watchdog_stop'] = self.end
        if self.failure is not None:
            report['watch_failure'] = self.failure
        if self.end == 'worker_exited':
            report['worker_exited_early'] = self.worker_exit


def logged_spawn(root: Path, env: Mapping[str, str], log: Path) -> Spawn:
    """A worker in its own session, logging to `log`, with `env` and the given variables on top."""
    def spawn(argv: list[str], extra: dict[str, str]) -> Worker:
        with log.open('a') as handle:
            return subprocess.Popen(argv, env={**env, **extra}, cwd=root, stdin=subprocess.DEVNULL,
                                    stdout=handle, stderr=handle, start_new_session=True)
    return spawn


@dataclass
class PaidSession:
    """One paid entry point's view of its stack: the helper, the runtime role's SQL and its one inference
    worker. `env` is the helper's environment; `spawn` adds the worker's own on top of its stack's."""

    root: Path
    database: Database
    env: dict[str, str]
    spawn: Spawn
    clock: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep
    worker: Worker | None = field(default=None)

    def helper(self, *argv: str) -> str:
        """One live-key command. A failure shows only its last stderr line: the exception's type and message."""
        done = subprocess.run([str(self.root / CHECK_PYTHON), '-m', LIVE_KEY, *argv], env=self.env, cwd=self.root,
                              capture_output=True, text=True, errors='replace', timeout=HELPER_SECONDS, check=False)
        if done.returncode:
            detail = done.stderr.strip().splitlines()[-1][:HELPER_ERROR_SHOWN] if done.stderr.strip() else 'no detail'
            raise Unavailable(f'{argv[0]} failed: {detail}')
        return done.stdout.strip()

    def sql(self, statement: str) -> str | None:
        """The first line of the answer, or None when the statement failed or answered nothing."""
        result = self.database.runtime(statement)
        lines = result.stdout.strip().splitlines() if result.returncode == 0 else []
        return lines[0] if lines else None

    def rows(self, statement: str) -> list[dict[str, Any]] | None:
        """Each row of `statement`, which has no closing semicolon, as JSON, so a value can't break the line
        format. None when the statement failed."""
        result = self.database.runtime(f'select row_to_json(t) from ({statement}) t;')
        if result.returncode:
            return None
        return [json.loads(line) for line in result.stdout.splitlines() if line.strip().startswith('{')]

    def sign_in(self, base: str, anon_key: str, email: str, password: str) -> str:
        """The owner's access token. The password goes only to the Auth service."""
        code, reply = http_json('POST', f'{base}/auth/v1/token?grant_type=password', {'apikey': anon_key, 'Content-Type': 'application/json'},
                                {'email': email, 'password': password})
        if code != 200:
            raise Unavailable(f'the owner could not sign in: {code}')
        return str(json.loads(reply)['access_token'])

    def start_worker(self, argv: Sequence[str] | None = None, extra: Mapping[str, str] | None = None) -> Worker:
        """The switch is on for this one process only, and it's on nowhere else."""
        command = list(argv) if argv is not None else [str(self.root / CHECK_PYTHON), '-m', 'autobots.operations.worker']
        self.worker = self.spawn(command, {**(extra or {}), INFERENCE_SWITCH: 'enabled'})
        return self.worker

    def stop_worker(self, report: Report) -> None:
        """SIGTERM, then SIGKILL if it hasn't exited within WORKER_STOP_SECONDS. A stopped worker is left alone."""
        worker = self.worker
        if worker is None or worker.poll() is not None:
            return
        worker.send_signal(signal.SIGTERM)
        try:
            report['worker_exit'] = worker.wait(WORKER_STOP_SECONDS)
        except subprocess.TimeoutExpired:
            worker.kill()
            report['worker_exit'] = f'killed after {WORKER_STOP_SECONDS} seconds'

    def watch(self, statuses: Callable[[], dict[str, str]], done: Callable[[dict[str, str]], bool], limit: int,
              spend_query: str, seconds: float) -> WatchResult:
        """Polls until `done`, the worker exits or `seconds` pass. Each poll reads the committed spend, and
        the watchdog SIGKILLs the worker when watchdog_verdict says stop. A poll that raises, such as a
        psql call past its timeout, would leave the worker spending unwatched, so it is SIGKILLed as on
        a cap breach and the watch ends `watch_failed`, with what was raised."""
        worker = self.worker
        if worker is None:
            raise Unavailable('no worker was started, so there is nothing to watch')
        began = self.clock()
        timeline: list[dict[str, Any]] = []
        current: dict[str, str] = {}
        last: dict[str, str] | None = None
        in_a_row = unreadable = 0
        try:
            while self.clock() - began < seconds:
                elapsed = round(self.clock() - began, 1)
                current = statuses()
                if current != last:
                    timeline.append({'seconds': elapsed, **current})
                    print(f'{round(elapsed)}s: {next(iter(current.values())) if len(current) == 1 else current}', flush=True)
                    last = current
                if done(current):
                    return WatchResult('finished', current, timeline, unreadable, None)
                verdict = watchdog_verdict(parsed_spend(self.sql(spend_query)), limit, in_a_row)
                in_a_row = verdict.unreadable_polls
                if verdict.verdict in ('unreadable', 'spend_unreadable'):
                    unreadable += 1
                    print(f'{round(elapsed)}s: the committed spend could not be read, {in_a_row} in a row; '
                          f'the worker stops at {UNREADABLE_POLL_LIMIT}', file=sys.stderr, flush=True)
                if verdict.verdict == 'over_cap' or verdict.verdict == 'spend_unreadable':
                    worker.send_signal(signal.SIGKILL)
                    return WatchResult(verdict.verdict, current, timeline, unreadable, None)
                code = worker.poll()
                if code is not None:
                    return WatchResult('worker_exited', current, timeline, unreadable, code)
                self.sleep(POLL_SECONDS)
        except (Unavailable, subprocess.SubprocessError, OSError) as problem:
            worker.send_signal(signal.SIGKILL)
            cause = str(problem) if isinstance(problem, Unavailable) else type(problem).__name__
            print(f'the watch could not poll, so the worker was stopped: {cause}', file=sys.stderr, flush=True)
            return WatchResult('watch_failed', current, timeline, unreadable, None, cause)
        return WatchResult('timed_out', current, timeline, unreadable, None)

    def spend_after(self, watched: WatchResult, spend_query: str, report: Report) -> int | None:
        """What the runs committed, read once the worker has stopped, or None when it's unknown, which is
        a failed check. After a stop on unreadable spend it stays unknown (Decision 0028 E2)."""
        spent = None if watched.end == 'spend_unreadable' else parsed_spend(self.sql(spend_query))
        report['committed_micro_usd'] = spent
        if spent is None:
            note_failed(report, 'the spend could not be read')
        return spent

    def after_run_checks(self, key_file: Path, logs: Path, report: Report) -> None:
        """The key's usage after the run, and the key in durable rows or logs, counted. Each failure stays listed."""
        self.sleep(KEY_USAGE_LAG_SECONDS)
        try:
            report['key_usage_after_usd'] = float(self.helper('usage', str(key_file)))
            durable, logged = self.helper('leaks', str(key_file), str(logs)).split()
            report['key_found'] = {'durable_rows': int(durable), 'log_files': int(logged)}
        except (Unavailable, ValueError, subprocess.SubprocessError, OSError) as problem:
            note_failed(report, str(problem) if isinstance(problem, Unavailable) else type(problem).__name__)
