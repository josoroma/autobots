"""The paid-run decisions and mechanics in scripts/paid_run.py, and the four paid entry points that use
them, with a fake clock, fake SQL, a fake worker, a fake ledger and a fake stack. No Docker, no network, no
install and no model call (refactor plan R-23, SCRP-03).

Decision 0028 E2 is held end to end through the real `persistent_install.goal` and `examples` and
`live_goal.attempt`: three unreadable spend polls in a row stop the worker, the report records the spend
as unknown, the ledger entry stays held and the entry point exits non-zero. `qualify_release.run_task`
and its corpus total fail closed the same way: a goal whose spend can't be read, or that raises before
it is read, counts its whole budget and stops the corpus, and so does a missing protocol report.
"""
from __future__ import annotations

import ast
import contextlib
import io
import json
import os
import signal
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))

import live_goal  # noqa: E402
import paid_run  # noqa: E402
import persistent_install  # noqa: E402
import qualify_release  # noqa: E402
from paid_run import (  # noqa: E402
    PaidSession,
    Settlement,
    Unavailable,
    Watch,
    WatchResult,
    goal_exit_code,
    parsed_spend,
    refuse_other_work,
    settle,
    settlement,
    watchdog_verdict,
)

Answer = str | Exception | list[str | Exception | None] | None
SPEND = 'sum(coalesce(charged_micro_usd'
STATUS = 'select status from public.runs'
TASKS = json.loads((ROOT / 'tests/qualification/tasks.json').read_text())
API_TASKS = [task for task in TASKS if not task.get('mode')]
GOAL_LIMIT = qualify_release.GOAL_LIMIT_MICRO_USD


class FakeDatabase:
    """Answers a statement from the first rule whose fragment it contains. None fails the statement, as an
    unreachable database does, an exception is raised, as a psql call past its timeout raises Unavailable,
    and a list answers successive statements, its last answer repeating."""

    def __init__(self, rules: Mapping[str, Answer]) -> None:
        self.rules = {fragment: list(answer) if isinstance(answer, list) else [answer] for fragment, answer in rules.items()}
        self.statements: list[str] = []

    def runtime(self, statements: str) -> subprocess.CompletedProcess[str]:
        self.statements.append(statements)
        for fragment, answers in self.rules.items():
            if fragment in statements:
                answer = answers.pop(0) if len(answers) > 1 else answers[0]
                if isinstance(answer, Exception):
                    raise answer
                if answer is None:
                    return subprocess.CompletedProcess([], 1, '', 'connection refused')
                return subprocess.CompletedProcess([], 0, f'{answer}\n', '')
        raise AssertionError(f'no rule answers {statements!r}')


class FakeWorker:
    """A worker that runs until it is signalled, or exits by itself after `exits_after` polls."""

    def __init__(self, exits_after: int | None = None, stubborn: bool = False) -> None:
        self.signals: list[int] = []
        self.polls = 0
        self.code: int | None = None
        self.exits_after = exits_after
        self.stubborn = stubborn

    def poll(self) -> int | None:
        self.polls += 1
        if self.code is None and self.exits_after is not None and self.polls > self.exits_after:
            self.code = 1
        return self.code

    def send_signal(self, sig: int) -> None:
        self.signals.append(sig)
        if not (self.stubborn and sig == signal.SIGTERM):
            self.code = -sig

    def wait(self, timeout: float | None = None) -> int:
        if self.code is None:
            raise subprocess.TimeoutExpired('worker', timeout or 0)
        return self.code

    def kill(self) -> None:
        self.send_signal(signal.SIGKILL)


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.slept: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


class FakeLedger:
    cap = 1_000_000

    def __init__(self) -> None:
        self.settled: list[tuple[int | None, str]] = []

    def reserve(self, label: str, worst_case: int) -> dict:
        return {'label': label, 'worst_case': worst_case, 'reported': None, 'state': 'reserved', 'at': 'now'}

    def settle(self, entry: dict, reported: int | None, state: str) -> None:
        self.settled.append((reported, state))
        entry['state'] = state

    def committed(self) -> int:
        return 123


def session(database: FakeDatabase, worker: FakeWorker | None = None, clock: FakeClock | None = None,
            spawned: list[dict[str, str]] | None = None) -> PaidSession:
    clock = clock or FakeClock()

    def spawn(argv: list[str], extra: dict[str, str]) -> FakeWorker:
        if spawned is not None:
            spawned.append(extra)
        return worker or FakeWorker()

    made = PaidSession(ROOT, database, {'PYTHONPATH': 'service'}, spawn, clock=clock.monotonic, sleep=clock.sleep)
    if worker is not None:
        made.worker = worker
    return made


def quietly(call: Callable[[], object]) -> tuple[object, str, str]:
    """The call's result, or the Unavailable or Refused it raised, and what it printed."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            result = call()
        except (Unavailable, paid_run.Refused) as raised:
            result = raised
    return result, out.getvalue(), err.getvalue()


def signed_in(http: Callable[..., tuple[int, str]] | None = None) -> Callable[..., tuple[int, str]]:
    """paid_run.http_json for the owner's sign-in, and `http` for everything else."""
    def answer(method: str, url: str, headers: Mapping[str, str], body: Mapping | None = None) -> tuple[int, str]:
        if url.endswith('/auth/v1/token?grant_type=password'):
            return 200, '{"access_token": "token"}'
        if http is None:
            raise AssertionError(url)
        return http(method, url, headers, body)
    return answer


def completed(argv: object = (), stdout: str = '', code: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(list(argv) if isinstance(argv, list | tuple) else [], code, stdout, '')


class WatchdogVerdict(unittest.TestCase):
    def test_a_readable_spend_within_the_limit_continues_and_ends_a_run_of_unreadable_polls(self) -> None:
        self.assertEqual(watchdog_verdict(100, 100, 2), Watch('continue', 0))

    def test_a_spend_past_the_limit_stops(self) -> None:
        self.assertEqual(watchdog_verdict(101, 100, 0), Watch('over_cap', 0))
        self.assertEqual(watchdog_verdict(101, 100, 2), Watch('over_cap', 0))

    def test_each_unreadable_poll_is_counted_and_the_third_in_a_row_stops(self) -> None:
        """Decision 0028 E2."""
        self.assertEqual([watchdog_verdict(None, 100, count) for count in (0, 1, 2)],
                         [Watch('unreadable', 1), Watch('unreadable', 2), Watch('spend_unreadable', 3)])

    def test_only_a_whole_number_is_a_spend(self) -> None:
        self.assertEqual([parsed_spend(text) for text in ('0', '250000')], [0, 250000])
        for text in (None, '', 'x', '1.5', '-3', '12 13'):
            self.assertIsNone(parsed_spend(text), text)


class SettlementDecision(unittest.TestCase):
    def test_nothing_started_releases_the_reservation(self) -> None:
        self.assertEqual(settlement(False, {}, None), Settlement(0, 'not_started'))
        self.assertEqual(settlement(False, {'goal': 'running'}, 500), Settlement(0, 'not_started'))

    def test_every_run_terminal_with_a_known_charge_settles_at_that_charge(self) -> None:
        self.assertEqual(settlement(True, {'goal 1': 'succeeded', 'workflow': 'failed'}, 900), Settlement(900, 'settled'))

    def test_an_unknown_charge_holds_the_whole_reservation(self) -> None:
        """Decision 0028 E2: held, never released, when the spend is unknown."""
        self.assertEqual(settlement(True, {'goal': 'succeeded'}, None), Settlement(None, 'run_not_finished'))

    def test_a_run_that_can_go_on_holds_the_whole_reservation(self) -> None:
        for finals in ({'goal': 'running'}, {'goal': 'succeeded', 'workflow': 'waiting_approval'}, {'goal': ''}, {}):
            self.assertEqual(settlement(True, finals, 900), Settlement(None, 'run_not_finished'), finals)


class ExitCode(unittest.TestCase):
    def test_only_an_achieved_outcome_with_every_check_clean_exits_zero(self) -> None:
        clean = {'key_found': {'durable_rows': 0, 'log_files': 0}}
        self.assertEqual(goal_exit_code(clean, achieved=True), 0)
        self.assertEqual(goal_exit_code(clean, achieved=False), 1)

    def test_each_failure_exits_non_zero(self) -> None:
        for report in ({'after_run_check_failed': 'the spend could not be read'}, {'key_found': {'durable_rows': 1, 'log_files': 0}},
                       {'key_found': {'durable_rows': 0, 'log_files': 2}}, {'watchdog_fired': True}):
            self.assertEqual(goal_exit_code(report, achieved=True), 1, report)


class OtherWork(unittest.TestCase):
    def test_an_unreadable_answer_refuses(self) -> None:
        refuse_other_work('0')
        for found in (None, '', 'x'):
            with self.assertRaisesRegex(paid_run.Refused, 'Could not read'):
                refuse_other_work(found)


class SessionMechanics(unittest.TestCase):
    def test_sql_is_none_when_unreadable_and_never_empty(self) -> None:
        paid = session(FakeDatabase({'fails': None, 'empty': '', 'seven': '7\nmore'}))
        self.assertIsNone(paid.sql('select fails'))
        self.assertIsNone(paid.sql('select empty'))
        self.assertEqual(paid.sql('select seven'), '7')

    def test_rows_are_none_when_unreadable(self) -> None:
        paid = session(FakeDatabase({'fails': None, 'row_to_json': '{"a": 1}'}))
        self.assertIsNone(paid.rows('select fails'))
        self.assertEqual(paid.rows('select a'), [{'a': 1}])

    def test_the_helper_runs_the_service_module_and_shows_only_its_last_error_line(self) -> None:
        failed = subprocess.CompletedProcess([], 1, '', 'Traceback (most recent call last):\n  File "x"\nValueError: no usage')
        with mock.patch.object(paid_run.subprocess, 'run', return_value=failed) as run:
            with self.assertRaisesRegex(Unavailable, '^usage failed: ValueError: no usage$'):
                session(FakeDatabase({})).helper('usage', 'key-file')
        argv = run.call_args.args[0]
        self.assertEqual(argv[1:], ['-m', 'autobots.operations.live_key', 'usage', 'key-file'])
        self.assertEqual(run.call_args.kwargs['env'], {'PYTHONPATH': 'service'})

    def test_only_the_worker_gets_the_inference_switch(self) -> None:
        spawned: list[dict[str, str]] = []
        paid = session(FakeDatabase({}), spawned=spawned)
        paid.start_worker(extra={'AUTOBOTS_TEST_SINK': 'sink'})
        self.assertEqual(spawned, [{'AUTOBOTS_TEST_SINK': 'sink', 'AUTOBOTS_WORKER_INFERENCE': 'enabled'}])
        self.assertNotIn('AUTOBOTS_WORKER_INFERENCE', paid.env)

    def test_a_worker_that_ignores_sigterm_is_killed_after_the_wait(self) -> None:
        worker = FakeWorker(stubborn=True)
        report: dict = {}
        session(FakeDatabase({}), worker).stop_worker(report)
        self.assertEqual(worker.signals, [signal.SIGTERM, signal.SIGKILL])
        self.assertEqual(report['worker_exit'], 'killed after 60 seconds')

    def test_sign_in_refuses_anything_but_a_token(self) -> None:
        with mock.patch.object(paid_run, 'http_json', return_value=(400, '{}')):
            with self.assertRaisesRegex(Unavailable, 'could not sign in: 400'):
                session(FakeDatabase({})).sign_in('http://base', 'anon', 'owner@x', 'password')
        with mock.patch.object(paid_run, 'http_json', return_value=(200, '{"access_token": "token"}')) as posted:
            self.assertEqual(session(FakeDatabase({})).sign_in('http://base', 'anon', 'owner@x', 'password'), 'token')
        self.assertEqual(posted.call_args.args[1], 'http://base/auth/v1/token?grant_type=password')


def watch(database: FakeDatabase, worker: FakeWorker, clock: FakeClock, limit: int = 100, seconds: float = 1000) -> tuple[WatchResult, str]:
    paid = session(database, worker, clock)
    result, _, err = quietly(lambda: paid.watch(lambda: {'status': paid.sql(f"{STATUS} where id = 'r';") or ''},
                                                lambda current: current['status'] not in paid_run.ACTIVE,
                                                limit, f'select {SPEND}, 0)) from x;', seconds))
    assert isinstance(result, WatchResult)
    return result, err


class Watchdog(unittest.TestCase):
    def test_three_unreadable_polls_in_a_row_kill_the_worker(self) -> None:
        """Decision 0028 E2: stopped as on a cap breach, each unreadable poll logged."""
        worker, clock = FakeWorker(), FakeClock()
        result, err = watch(FakeDatabase({STATUS: 'running', SPEND: None}), worker, clock)
        self.assertEqual((result.end, result.unreadable_polls), ('spend_unreadable', 3))
        self.assertEqual(worker.signals, [signal.SIGKILL])
        self.assertEqual(clock.slept, [3, 3])
        self.assertEqual(err.count('the committed spend could not be read'), 3)

    def test_one_unreadable_poll_is_logged_and_counted_and_the_run_goes_on(self) -> None:
        worker, clock = FakeWorker(), FakeClock()
        database = FakeDatabase({STATUS: ['running', 'running', 'running', 'succeeded'], SPEND: ['10', None, '20']})
        result, err = watch(database, worker, clock)
        self.assertEqual((result.end, result.unreadable_polls, worker.signals), ('finished', 1, []))
        self.assertEqual(result.timeline, [{'seconds': 0.0, 'status': 'running'}, {'seconds': 9.0, 'status': 'succeeded'}])
        self.assertEqual(err.count('the committed spend could not be read'), 1)

    def test_a_reading_between_unreadable_polls_starts_the_count_again(self) -> None:
        worker, clock = FakeWorker(), FakeClock()
        result, _ = watch(FakeDatabase({STATUS: 'running', SPEND: [None, None, '5', None, None, '6']}), worker, clock, seconds=18)
        self.assertEqual((result.end, result.unreadable_polls, worker.signals), ('timed_out', 4, []))

    def test_a_spend_past_the_limit_kills_the_worker(self) -> None:
        worker = FakeWorker()
        result, _ = watch(FakeDatabase({STATUS: 'running', SPEND: '101'}), worker, FakeClock())
        self.assertEqual((result.end, worker.signals), ('over_cap', [signal.SIGKILL]))

    def test_a_worker_that_exits_ends_the_watch(self) -> None:
        result, _ = watch(FakeDatabase({STATUS: 'running', SPEND: '1'}), FakeWorker(exits_after=0), FakeClock())
        self.assertEqual((result.end, result.worker_exit), ('worker_exited', 1))

    def test_a_poll_that_raises_kills_the_worker_and_says_why(self) -> None:
        """A psql call past its timeout raises Unavailable. The worker is never left running unwatched."""
        worker = FakeWorker()
        timeout = Unavailable('psql -h timed out after 180.0 seconds')
        result, err = watch(FakeDatabase({STATUS: 'running', SPEND: ['5', timeout]}), worker, FakeClock())
        self.assertEqual((result.end, result.failure, worker.signals), ('watch_failed', str(timeout), [signal.SIGKILL]))
        self.assertIn('the watch could not poll', err)
        report: dict = {}
        result.record(report)
        self.assertEqual((report['watchdog_fired'], report['watchdog_stop'], report['watch_failure']), (True, 'watch_failed', str(timeout)))

    def test_a_status_read_that_raises_is_a_failed_watch_too_and_shows_only_its_type(self) -> None:
        worker = FakeWorker()
        result, _ = watch(FakeDatabase({STATUS: ['running', OSError('/private/path')], SPEND: '5'}), worker, FakeClock())
        self.assertEqual((result.end, result.failure, worker.signals), ('watch_failed', 'OSError', [signal.SIGKILL]))
        self.assertEqual(goal_exit_code({'watchdog_fired': True}, achieved=True), 1)

    def test_the_report_says_why_the_watch_ended(self) -> None:
        report: dict = {}
        WatchResult('spend_unreadable', {'status': 'running'}, [{'seconds': 0.0, 'status': 'running'}], 3, None).record(report)
        self.assertEqual(report, {'timeline': [{'seconds': 0.0, 'status': 'running'}], 'unreadable_spend_polls': 3,
                                  'watchdog_fired': True, 'watchdog_stop': 'spend_unreadable'})
        report = {}
        WatchResult('worker_exited', {}, [], 0, 1).record(report)
        self.assertEqual(report['worker_exited_early'], 1)
        self.assertNotIn('watchdog_fired', report)


class SpendAfterTheRun(unittest.TestCase):
    def test_after_an_unreadable_stop_the_spend_stays_unknown_even_if_it_reads_again(self) -> None:
        """Decision 0028 E2."""
        report: dict = {}
        watched = WatchResult('spend_unreadable', {}, [], 3, None)
        self.assertIsNone(session(FakeDatabase({SPEND: '50'})).spend_after(watched, f'select {SPEND}', report))
        self.assertIsNone(report['committed_micro_usd'])
        self.assertIn('the spend could not be read', report['after_run_check_failed'])

    def test_a_readable_spend_is_the_charge(self) -> None:
        report: dict = {}
        watched = WatchResult('finished', {}, [], 0, None)
        self.assertEqual(session(FakeDatabase({SPEND: '50'})).spend_after(watched, f'select {SPEND}', report), 50)
        self.assertEqual(report, {'committed_micro_usd': 50})

    def test_a_spend_unreadable_after_the_run_is_a_failed_check(self) -> None:
        report: dict = {}
        watched = WatchResult('finished', {}, [], 0, None)
        self.assertIsNone(session(FakeDatabase({SPEND: None})).spend_after(watched, f'select {SPEND}', report))
        self.assertIn('the spend could not be read', report['after_run_check_failed'])


class LedgerSettlement(unittest.TestCase):
    def test_an_unknown_charge_is_held_and_the_report_shows_the_ledger(self) -> None:
        ledger, report = FakeLedger(), {}
        entry = ledger.reserve('goal', 1000)
        settle(ledger, entry, True, {'goal': 'running'}, None, report)
        self.assertEqual(ledger.settled, [(None, 'run_not_finished')])
        self.assertEqual(report, {'ledger_state': 'run_not_finished', 'shared_ledger_committed_micro_usd': 123})

    def test_an_entry_already_settled_is_left_alone(self) -> None:
        ledger, report = FakeLedger(), {}
        entry = ledger.reserve('goal', 1000)
        entry['state'] = 'not_started'
        settle(ledger, entry, True, {'goal': 'succeeded'}, 10, report)
        self.assertEqual(ledger.settled, [])


class AfterRunChecks(unittest.TestCase):
    def test_the_key_checks_wait_for_openrouter_and_record_counts(self) -> None:
        clock, report = FakeClock(), {}
        paid = session(FakeDatabase({}), clock=clock)
        answers = {'usage': '1.25', 'leaks': '0 1'}
        with mock.patch.object(paid, 'helper', side_effect=lambda command, *_: answers[command]):
            paid.after_run_checks(Path('key'), Path('logs'), report)
        self.assertEqual(clock.slept, [paid_run.KEY_USAGE_LAG_SECONDS])
        self.assertEqual(report, {'key_usage_after_usd': 1.25, 'key_found': {'durable_rows': 0, 'log_files': 1}})

    def test_a_check_that_could_not_run_stays_listed(self) -> None:
        report: dict = {}
        paid = session(FakeDatabase({}))
        with mock.patch.object(paid, 'helper', side_effect=Unavailable('usage failed: no route')):
            paid.after_run_checks(Path('key'), Path('logs'), report)
        self.assertEqual(report, {'after_run_check_failed': 'usage failed: no route'})


Http = Callable[..., tuple[int, str]]
HELPER = {'usage': '1.5', 'save': '', 'leaks': '0 0'}


def faked_session(made: PaidSession, clock: FakeClock, worker: FakeWorker | None = None) -> PaidSession:
    """The real session with only its clock, its helper and, when given, its worker faked, so no key or
    process leaves the test."""
    made.clock, made.sleep = clock.monotonic, clock.sleep
    made.helper = lambda command, *_: HELPER[command]
    if worker is not None:
        made.spawn = lambda argv, extra: worker
    return made


class InstallCommand(unittest.TestCase):
    """A paid `persistent_install` command as the owner runs it, on fakes: its real wiring, watchdog,
    settlement and exit, with only the database, the clock, the helper, the worker and HTTP faked."""

    def run_install(self, command: Callable[[persistent_install.Record, Path], int], rules: Mapping[str, Answer], worker: FakeWorker,
                    http: Http, limit: int, processes: Callable[..., subprocess.CompletedProcess[str]] | None = None) -> tuple[object, Path, FakeLedger, str]:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        install = Path(directory.name)
        for name in ('reports', 'logs'):
            (install / name).mkdir()
        record = persistent_install.Record('autobots-install', 'install-id', 1, 2, 3, 4, install)
        ledger, clock = FakeLedger(), FakeClock()
        built = persistent_install.install_session

        def install_session(*args: object, **kwargs: object) -> PaidSession:
            return faked_session(built(*args, **kwargs), clock, worker)

        values = {'app.env': {'AUTOBOTS_SUPABASE_URL': 'http://gateway', 'AUTOBOTS_SUPABASE_ANON_KEY': 'anon', 'AUTOBOTS_INTERNAL_TOKEN': 'internal'},
                  'owner.env': {'OWNER_EMAIL': 'owner@autobots.invalid', 'OWNER_PASSWORD': 'password'}}
        with mock.patch.object(persistent_install, 'reserve_goal', return_value=(ledger, ledger.reserve('install', limit))), \
             mock.patch.object(persistent_install, 'install_stack', return_value=FakeDatabase(rules)), \
             mock.patch.object(persistent_install, 'require_install'), \
             mock.patch.object(persistent_install, 'read_values', side_effect=lambda path: values[path.name]), \
             mock.patch.object(persistent_install, 'install_session', install_session), \
             mock.patch.object(persistent_install, 'http_json', signed_in(http)), mock.patch.object(paid_run, 'http_json', signed_in(http)), \
             mock.patch('subprocess.run', side_effect=processes or AssertionError('no process')), \
             mock.patch('subprocess.Popen', side_effect=AssertionError('no process')):
            outcome, _, err = quietly(lambda: command(record, install))
        return outcome, install, ledger, err

    @staticmethod
    def report(install: Path, kind: str) -> dict:
        [written] = (install / 'reports').glob(f'{kind}-*.json')
        return json.loads(written.read_text())


class InstallGoal(InstallCommand):
    """`persistent_install.goal`."""

    LIMIT = 1000

    def run_goal(self, status: Answer, spend: Answer, worker: FakeWorker) -> tuple[object, dict, FakeLedger, str]:
        rules: dict[str, Answer] = {
            'app_private.run_jobs': '0', "role = 'owner'": 'workspace', 'provider_credentials': '1',
            'clock_timestamp': '2026-11-14 10:00:00+00', STATUS: status, SPEND: spend, 'stop_reason': 'none',
            'run_verifications': 'true {}', 'public.artifacts': 'none', 'charged_micro_usd is null': '0',
            'select count(*) from app_private.model_invocations': '2', 'distinct profile': 'none', 'worker_heartbeats': '0'}

        def http(method: str, url: str, headers: Mapping[str, str], body: Mapping | None = None) -> tuple[int, str]:
            if url.endswith('/v1/runs'):
                return 202, '{"run_id": "run-1"}'
            raise AssertionError(url)

        outcome, install, ledger, err = self.run_install(
            lambda record, install: persistent_install.goal(ROOT, record, 'autobots-install', Path('key'), self.LIMIT, install / 'ledger.json', 'a goal', []),
            rules, worker, http, self.LIMIT)
        return outcome, self.report(install, 'goal'), ledger, err

    def test_spend_unreadable_for_three_polls_stops_the_worker_holds_the_ledger_and_fails(self) -> None:
        """Decision 0028 E2, end to end."""
        worker = FakeWorker()
        code, report, ledger, err = self.run_goal('running', None, worker)
        self.assertEqual(code, 1)
        self.assertEqual(worker.signals, [signal.SIGKILL])
        self.assertEqual((report['watchdog_stop'], report['unreadable_spend_polls']), ('spend_unreadable', 3))
        self.assertIsNone(report['committed_micro_usd'])
        self.assertIn('the spend could not be read', report['after_run_check_failed'])
        self.assertEqual(ledger.settled, [(None, 'run_not_finished')])
        self.assertEqual(report['ledger_state'], 'run_not_finished')
        self.assertEqual(err.count('the committed spend could not be read'), 3)

    def test_a_finished_goal_settles_at_its_charge_and_exits_zero(self) -> None:
        worker = FakeWorker()
        code, report, ledger, _ = self.run_goal(['running', 'succeeded'], '400', worker)
        self.assertEqual(code, 0)
        self.assertEqual(worker.signals, [signal.SIGTERM])
        self.assertEqual((report['status'], report['committed_micro_usd']), ('succeeded', 400))
        self.assertEqual(ledger.settled, [(400, 'settled')])
        self.assertEqual(report['key_found'], {'durable_rows': 0, 'log_files': 0})

    def test_a_poll_that_raises_stops_the_worker_and_the_report_keeps_why_when_a_later_read_raises(self) -> None:
        """A psql call past its timeout, during the watch and again after it: the worker is SIGKILLed, the
        reservation stays held and the report written on the way out says why the watch ended."""
        worker = FakeWorker()
        timeout = Unavailable('psql -h timed out after 180.0 seconds')
        raised, report, ledger, _ = self.run_goal(['running', timeout], timeout, worker)
        self.assertIs(raised, timeout)
        self.assertEqual(worker.signals, [signal.SIGKILL])
        self.assertEqual((report['watchdog_stop'], report['watch_failure'], report['failed_with']), ('watch_failed', str(timeout), 'Unavailable'))
        self.assertEqual(ledger.settled, [(None, 'run_not_finished')])


class InstallExamples(InstallCommand):
    """`persistent_install.examples`: two goal runs and a workflow under one reservation."""

    FINISHED: Mapping[str, Answer] = {'run-1': 'succeeded', 'run-2': 'failed', 'run-3': 'waiting_approval'}

    def run_examples(self, statuses: Mapping[str, Answer], spend: Answer, worker: FakeWorker, workflow: int = 201,
                     queued: Answer = '', invocations: Answer = '0') -> tuple[object, Path, FakeLedger, list[tuple[str, str]]]:
        rules: dict[str, Answer] = {
            "string_agg(r.id || ' ' || r.version": queued, 'root_run_id in (': invocations, 'app_private.run_jobs': '0',
            "role = 'owner'": 'workspace', 'provider_credentials': '1', 'from public.experts e join': '',
            'clock_timestamp': '2026-11-14 10:00:00+00', "status = 'succeeded'": '0', 'from public.experts where': 'expert-1',
            'from public.workflows': 'flow-1 1', **{f"public.runs where id = '{run}'": status for run, status in statuses.items()},
            'public.artifacts': 'none', 'distinct profile': 'none', 'approval_requests': '1', 'charged_micro_usd is null': '0',
            'select count(*) from app_private.model_invocations': '2', SPEND: spend}
        admitted = iter(['run-1', 'run-2'])
        requests: list[tuple[str, str]] = []

        def http(method: str, url: str, headers: Mapping[str, str], body: Mapping | None = None) -> tuple[int, str]:
            requests.append((method, url.removeprefix('http://127.0.0.1:3')))
            if url.endswith('/v1/sessions'):
                return 201, '{"id": "session-1"}'
            if url.endswith('/v1/runs'):
                return 202, json.dumps({'run_id': next(admitted)})
            if url.endswith('/v1/workflows/flow-1/executions'):
                return (201, '{"run_id": "run-3"}') if workflow == 201 else (workflow, '{"detail": "refused"}')
            if url.endswith('/cancel'):
                return 200, '{}'
            raise AssertionError(url)

        def concept_seed(argv: list[str], **options: object) -> subprocess.CompletedProcess[str]:
            if 'autobots.operations.concept_seed' not in argv:
                raise AssertionError(argv)
            return completed(argv, '{"seeded": true}\n')

        outcome, install, ledger, _ = self.run_install(
            lambda record, install: persistent_install.examples(ROOT, record, 'autobots-install', Path('key'), install / 'ledger.json'),
            rules, worker, http, persistent_install.EXAMPLES_LIMIT, concept_seed)
        return outcome, install, ledger, requests

    def test_finished_examples_with_a_known_spend_exit_zero_and_stay_held_at_the_approval_gate(self) -> None:
        """A failed example is still what the system did (Decision 0023 E6). The workflow can go on once
        the owner decides, so the reservation stays held."""
        worker = FakeWorker()
        code, install, ledger, requests = self.run_examples(self.FINISHED, '400', worker)
        report = self.report(install, 'examples')
        self.assertEqual(code, 0)
        self.assertEqual(worker.signals, [signal.SIGTERM])
        self.assertEqual(report['status'], {'goal 1': 'succeeded', 'goal 2': 'failed', 'workflow': 'waiting_approval'})
        self.assertEqual(report['committed_micro_usd'], 400)
        self.assertEqual(ledger.settled, [(None, 'run_not_finished')])
        self.assertIn(('POST', '/v1/workflows/flow-1/executions'), requests)

    def test_examples_cannot_exit_zero_with_an_unknown_spend(self) -> None:
        code, install, ledger, _ = self.run_examples(self.FINISHED, None, FakeWorker())
        report = self.report(install, 'examples')
        self.assertEqual(code, 1)
        self.assertIsNone(report['committed_micro_usd'])
        self.assertIn('the spend could not be read', report['after_run_check_failed'])
        self.assertEqual(ledger.settled, [(None, 'run_not_finished')])

    def test_examples_that_did_not_finish_exit_non_zero(self) -> None:
        """The watch timed out with a goal still running, everything else clean: not the outcome."""
        worker = FakeWorker()
        code, install, ledger, _ = self.run_examples({**self.FINISHED, 'run-1': 'running'}, '10', worker)
        report = self.report(install, 'examples')
        self.assertEqual(code, 1)
        self.assertEqual((report['status']['goal 1'], report['committed_micro_usd'], worker.signals), ('running', 10, [signal.SIGTERM]))
        self.assertNotIn('watchdog_fired', report)
        self.assertNotIn('after_run_check_failed', report)
        self.assertEqual(ledger.settled, [(None, 'run_not_finished')])

    def test_spend_unreadable_for_three_polls_stops_the_examples_worker_and_holds(self) -> None:
        """Decision 0028 E2."""
        worker = FakeWorker()
        code, install, ledger, _ = self.run_examples(dict.fromkeys(self.FINISHED, 'running'), None, worker)
        report = self.report(install, 'examples')
        self.assertEqual(code, 1)
        self.assertEqual((worker.signals, report['watchdog_stop']), ([signal.SIGKILL], 'spend_unreadable'))
        self.assertEqual(ledger.settled, [(None, 'run_not_finished')])

    def test_a_failure_before_the_worker_holds_the_reservation_when_the_invocation_count_is_unreadable(self) -> None:
        """The workflow is refused after both goal runs were admitted. Their runs are cancelled, and only a
        count that reads 0 calls for them releases the reservation."""
        worker = FakeWorker()
        raised, _, ledger, requests = self.run_examples(self.FINISHED, '0', worker, workflow=409, queued=['', '', 'run-1 1', 'run-2 1'], invocations=None)
        self.assertIsInstance(raised, Unavailable)
        self.assertEqual(ledger.settled, [(None, 'run_not_finished')])
        self.assertEqual([url for _, url in requests if url.endswith('/cancel')], ['/v1/runs/run-1/cancel', '/v1/runs/run-2/cancel'])
        self.assertEqual(worker.signals, [])

    def test_a_failure_before_the_worker_releases_the_reservation_when_no_call_was_made(self) -> None:
        raised, _, ledger, _ = self.run_examples(self.FINISHED, '0', FakeWorker(), workflow=409, queued=['', '', 'run-1 1', 'run-2 1'], invocations='0')
        self.assertIsInstance(raised, Unavailable)
        self.assertEqual(ledger.settled, [(0, 'not_started')])


class FakeStack:
    """A disposable stack (app_db.AppStack) whose runtime role answers from a FakeDatabase."""

    def __init__(self, database: FakeDatabase) -> None:
        self.database = database
        self.values = {'SERVICE_ROLE_KEY': 'service', 'ANON_KEY': 'anon', 'JWT_SECRET': 'secret'}
        self.migrator_password = self.runtime_password = ''

    def runtime(self, statements: str) -> subprocess.CompletedProcess[str]:
        return self.database.runtime(statements)

    def compose(self, *arguments: str, **options: object) -> subprocess.CompletedProcess[str]:
        return completed()

    def sql(self, statements: str) -> subprocess.CompletedProcess[str]:
        return completed()


class FakeOps:
    """What a disposable paid run uses of qualify_operations.Ops: its stack, environment and processes."""

    def __init__(self, stack: FakeStack, worker: FakeWorker) -> None:
        self.stack, self.worker = stack, worker
        self.base, self.url, self.internal = 'http://gateway', 'postgresql://runtime', 'internal'
        self.env = {'PATH': '/usr/bin', 'LANGSMITH_TRACING': 'true'}
        self.spawned: list[tuple[str, list[str], dict[str, str]]] = []
        self.processes: list[object] = []
        self.stopped = False

    def spawn(self, name: str, argv: list[str], extra: dict[str, str] | None = None) -> FakeWorker:
        self.spawned.append((name, argv, dict(extra or {})))
        return self.worker

    def api(self, port: int, config_root: Path, extra: dict[str, str] | None = None) -> None:
        return None

    def sql(self, statement: str) -> str:
        result = self.stack.runtime(statement)
        return result.stdout.strip().splitlines()[0] if result.returncode == 0 and result.stdout.strip() else ''

    def stop_all(self) -> None:
        self.stopped = True


@contextlib.contextmanager
def disposable_fakes(module: ModuleType, ops: FakeOps, clock: FakeClock, config: Path, api: Http,
                     processes: Callable[..., subprocess.CompletedProcess[str]], **extra: object) -> Iterator[list[object]]:
    """Everything a disposable paid entry point touches outside Python, faked: ports, Docker, the stack's
    setup, the owner's sign-up, the API, the clock and child processes. Yields the stacks it removed."""
    ports = iter(range(54001, 54010))
    removed: list[object] = []
    built = module.disposable_session

    def disposable_session(*args: object) -> PaidSession:
        return faked_session(built(*args), clock)

    def anything(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return completed()

    names = {'free_port': lambda *_: next(ports), 'generated_values': lambda *_: {}, 'AppStack': lambda *_, **__: ops.stack,
             'require_identity': anything, 'run': anything, 'require_images': anything, 'require_rendered': anything,
             'Ops': lambda *_: ops, 'other_resources': lambda _: [], 'fingerprint': lambda _: 'fingerprint', 'bootstrap': anything,
             'apply_migrations': lambda *_: ([], None), 'apply_bootstrap': lambda *_: ([], None), 'seed': anything,
             'bootstrap_owner': lambda *_: {'workspace_id': 'workspace'},
             'wait': anything, 'api_call': api, 'remove_stack': removed.append, 'disposable_session': disposable_session,
             'tempfile': SimpleNamespace(mkdtemp=lambda prefix: str(config)),
             'time': SimpleNamespace(monotonic=clock.monotonic, perf_counter=clock.monotonic, sleep=clock.sleep), **extra}
    with mock.patch.multiple(module, **names), mock.patch.object(paid_run, 'http_json', signed_in()), \
         mock.patch('subprocess.run', side_effect=processes), mock.patch('subprocess.Popen', side_effect=AssertionError('no process')):
        yield removed


def only_cleanup(argv: list[str], **options: object) -> subprocess.CompletedProcess[str]:
    """The one child process a disposable run may start under test: removing its own configuration."""
    if argv[:2] != ['rm', '-rf']:
        raise AssertionError(argv)
    return completed(argv)


class LiveGoal(unittest.TestCase):
    """`live_goal.attempt` as the owner runs it, on fakes: the real attempt and paid session."""

    LIMIT = 1000

    def attempt(self, status: Answer, spend: Answer, final: str, worker: FakeWorker) -> tuple[object, dict, FakeOps, list[object]]:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        out, config = Path(directory.name) / 'out', Path(directory.name) / 'config'
        config.mkdir()
        database = FakeDatabase({STATUS: status, SPEND: spend, 'limit_micro_usd from public.runs': json.dumps({'status': final, 'limit_micro_usd': self.LIMIT}),
                                 'row_to_json': ''})
        ops = FakeOps(FakeStack(database), worker)

        def api(port: int, internal: str, token: str, method: str = 'GET', path: str = '', body: bytes | None = None,
                extra: Mapping[str, str] | None = None) -> tuple[int, str]:
            if (method, path) == ('POST', '/v1/runs'):
                return 202, '{"run_id": "run-1"}'
            raise AssertionError(path)

        with disposable_fakes(live_goal, ops, FakeClock(), config, api, only_cleanup, OUT=out) as removed:
            code, _, _ = quietly(lambda: live_goal.attempt(ROOT, Path('key'), self.LIMIT))
        [written] = out.glob('result-*.json')
        return code, json.loads(written.read_text()), ops, removed

    def test_spend_unreadable_for_three_polls_stops_the_worker_and_exits_non_zero(self) -> None:
        """Decision 0028 E2: non-zero even though the run reads as succeeded once the worker is stopped."""
        worker = FakeWorker()
        code, report, ops, removed = self.attempt('running', None, 'succeeded', worker)
        self.assertEqual(code, 1)
        self.assertEqual(worker.signals, [signal.SIGKILL])
        self.assertEqual((report['watchdog_fired'], report['watchdog_stop'], report['unreadable_spend_polls']), (True, 'spend_unreadable', 3))
        self.assertIsNone(report['committed_micro_usd'])
        self.assertIn('the spend could not be read', report['after_run_check_failed'])
        self.assertEqual((ops.stopped, removed), (True, [ops.stack]))

    def test_a_succeeded_goal_with_a_known_spend_exits_zero_and_only_its_worker_has_inference(self) -> None:
        worker = FakeWorker()
        code, report, ops, _ = self.attempt(['running', 'succeeded'], '400', 'succeeded', worker)
        self.assertEqual(code, 0)
        self.assertEqual(worker.signals, [signal.SIGTERM])
        self.assertEqual((report['committed_micro_usd'], report['key_found']), (400, {'durable_rows': 0, 'log_files': 0}))
        [(name, argv, extra)] = ops.spawned
        self.assertEqual((name, argv[1:], extra['AUTOBOTS_WORKER_INFERENCE']), ('worker', ['-m', 'autobots.operations.worker'], 'enabled'))
        self.assertNotIn('AUTOBOTS_WORKER_INFERENCE', ops.env)
        self.assertNotIn('LANGSMITH_TRACING', ops.env)


def release_rules(status: Answer, invocations: Answer) -> dict[str, Answer]:
    return {STATUS: status, 'app_private.run_usage': '{"model_calls": 2, "tool_dispatches": 1, "repairs": 0, "stop_reason": "none"}',
            'select attempt, profile': invocations, 'argument_hash': '0', 'tool_receipts': '', 'run_verifications': '{"passed": true, "unmet": []}',
            'run_files': '', 'public.artifacts': '', 'select version from public.runs': '{"version": 3}'}


TWO_CALLS = '{"charged_micro_usd": 300, "reserved_micro_usd": 500}\n{"charged_micro_usd": null, "reserved_micro_usd": 700}'


def goal_stack(rules: Mapping[str, Answer], worker: FakeWorker | None = None,
               api: Http | None = None) -> tuple[qualify_release.GoalStack, list[tuple[str, str, object]]]:
    """A corpus goal's stack on fakes. Its API admits every goal as run-1 unless `api` answers."""
    clock = FakeClock()
    paid = session(FakeDatabase(rules), worker or FakeWorker(), clock)
    requests: list[tuple[str, str, object]] = []

    def call(method: str, path: str, body: dict | None = None) -> tuple[int, str]:
        requests.append((method, path, body))
        if api is not None:
            return api(method, path, body)
        if (method, path) == ('POST', '/v1/runs'):
            return 202, '{"run_id": "run-1"}'
        raise AssertionError(path)

    return qualify_release.GoalStack(ROOT, 'workspace', {'PATH': '/usr/bin'}, lambda statement: paid.sql(statement) or '', paid, call,
                                     lambda start: [], lambda: None, clock.monotonic, clock.sleep), requests


def real_goal(stack: qualify_release.GoalStack) -> Callable[[dict, int], dict]:
    """The real run_task on `stack`, starting no process."""
    def goal(task: dict, trial: int) -> dict:
        with mock.patch('subprocess.run', side_effect=AssertionError('no process')):
            return qualify_release.run_task(stack, task, trial)
    return goal


class ReleaseGoal(unittest.TestCase):
    """`qualify_release.run_task`, one corpus goal, on fakes."""

    def test_a_goal_is_admitted_through_the_api_and_settles_from_the_ledger(self) -> None:
        stack, requests = goal_stack(release_rules('succeeded', TWO_CALLS))
        task = API_TASKS[0]
        result = real_goal(stack)(task, 1)
        [(method, path, body)] = requests
        self.assertEqual((method, path), ('POST', '/v1/runs'))
        self.assertEqual(body, {'goal_text': task['goal'], 'limit_micro_usd': GOAL_LIMIT, 'required_artifacts': [{'name': task['artifact']}],
                                'input_documents': [{'path': path, 'content': content} for path, content in task['documents'].items()]})
        self.assertEqual((result['run_id'], result['status'], result['task'], result['trial']), ('run-1', 'succeeded', task['id'], 1))
        self.assertEqual((result['charged'], result['held'], result['spend_unknown']), (300, 700, False))

    def test_an_approval_task_is_admitted_by_the_helper(self) -> None:
        task = next(task for task in TASKS if task.get('mode') == 'approve')
        stack, requests = goal_stack(release_rules('succeeded', TWO_CALLS))
        with mock.patch('subprocess.run', return_value=completed([], 'admitting\nrun-7\n')) as admitted:
            result = qualify_release.run_task(stack, task, 2)
        self.assertEqual(admitted.call_args.args[0][2:5], ['workspace', str(GOAL_LIMIT), json.dumps(task)])
        self.assertEqual(admitted.call_args.kwargs['env'], {'PATH': '/usr/bin'})
        self.assertEqual((result['run_id'], requests), ('run-7', []))

    def test_unreadable_invocations_charge_the_whole_budget(self) -> None:
        """Decision 0028 E2: the cost summary never shows the goal cheaper than it may have been."""
        stack, _ = goal_stack(release_rules('succeeded', None))
        result = real_goal(stack)(API_TASKS[0], 1)
        self.assertEqual((result['charged'], result['held'], result['spend_unknown']), (GOAL_LIMIT, 0, True))

    def test_a_worker_that_exits_early_raises(self) -> None:
        stack, _ = goal_stack(release_rules('running', TWO_CALLS), worker=FakeWorker(exits_after=0))
        with self.assertRaisesRegex(Unavailable, 'the worker exited early: 1'):
            real_goal(stack)(API_TASKS[0], 1)


def fixed_goal(charged: int, held: int = 0) -> Callable[[dict, int], dict]:
    def goal(task: dict, trial: int) -> dict:
        return {'task': task['id'], 'trial': trial, 'charged': charged, 'held': held, 'spend_unknown': False, 'reasons': [], 'safety': [], 'seconds': 1.0}
    return goal


class ReleaseCorpus(unittest.TestCase):
    """`qualify_release.Corpus`, the running total under the user's cap, mostly driving the real run_task."""

    def run_corpus(self, corpus: qualify_release.Corpus, goal: Callable[[dict, int], dict], trials: int = 1) -> tuple[str, list[dict]]:
        kept: list[dict] = []
        stopped, _, _ = quietly(lambda: corpus.run(API_TASKS[:2], trials, goal, kept.append))
        assert isinstance(stopped, str)
        return stopped, kept

    def test_a_goal_whose_spend_cant_be_read_counts_its_whole_budget_and_stops_the_corpus(self) -> None:
        corpus = qualify_release.Corpus(10 * GOAL_LIMIT, 1000)
        stopped, kept = self.run_corpus(corpus, real_goal(goal_stack(release_rules('succeeded', None))[0]))
        self.assertIn(f"the spend of {API_TASKS[0]['id']}/1 could not be read", stopped)
        self.assertEqual((corpus.spent, len(kept), kept[0]['charged']), (1000 + GOAL_LIMIT, 1, GOAL_LIMIT))

    def test_a_goal_that_raises_counts_its_whole_budget(self) -> None:
        """The worker exits early, after calls that may have been paid."""
        corpus = qualify_release.Corpus(10 * GOAL_LIMIT, 1000)
        goal = real_goal(goal_stack(release_rules('running', TWO_CALLS), worker=FakeWorker(exits_after=0))[0])
        with self.assertRaises(Unavailable):
            corpus.run(API_TASKS[:2], 1, goal, lambda result: None)
        self.assertEqual(corpus.spent, 1000 + GOAL_LIMIT)
        self.assertEqual(corpus.interrupted, {'task': API_TASKS[0]['id'], 'trial': 1, 'counted_micro_usd': GOAL_LIMIT, 'failed_with': 'Unavailable'})
        self.assertEqual(corpus.interruption(), f"{API_TASKS[0]['id']}/1 stopped before its spend was read, so it counts its whole budget")
        self.assertEqual(corpus.results, [])

    def test_a_goal_whose_api_reply_isnt_json_counts_its_whole_budget(self) -> None:
        def api(method: str, path: str, body: object) -> tuple[int, str]:
            return (202, '{"run_id": "run-1"}') if path == '/v1/runs' else (502, '<html>bad gateway</html>')

        corpus = qualify_release.Corpus(10 * GOAL_LIMIT, 0)
        goal = real_goal(goal_stack(release_rules('waiting_approval', TWO_CALLS), api=api)[0])
        with self.assertRaises(json.JSONDecodeError):
            corpus.run(API_TASKS[:1], 1, goal, lambda result: None)
        self.assertEqual(corpus.spent, GOAL_LIMIT)
        self.assertEqual((corpus.interrupted or {}).get('failed_with'), 'JSONDecodeError')

    def test_the_next_goal_starts_only_if_its_whole_budget_fits(self) -> None:
        corpus = qualify_release.Corpus(GOAL_LIMIT + 500, 0)
        stopped, kept = self.run_corpus(corpus, fixed_goal(300), trials=2)
        self.assertEqual((stopped, corpus.spent, len(kept)), ('the next goal could pass the authorized total, at 600 micro-USD', 600, 2))

    def test_a_corpus_that_finishes_answers_no_stop(self) -> None:
        corpus = qualify_release.Corpus(10 * GOAL_LIMIT, 0)
        stopped, kept = self.run_corpus(corpus, fixed_goal(300, 200))
        self.assertEqual((stopped, corpus.spent, len(kept), corpus.interrupted), ('', 1000, 2, None))


PROTOCOL_REPORT = 'report-openai_gpt_6_1_terra-rerun.json'


def protocol_report(committed: object = 1200) -> str:
    return json.dumps({'summary': {}, 'calls': 4, 'committed_micro_usd': committed, 'reported_micro_usd': 1100, 'calls_without_a_reported_charge': 0,
                       'trials': [{'verdict': 'passed'}, {'verdict': 'failed'}]})


class ProtocolReport(unittest.TestCase):
    """`qualify_release.protocol_result`: only a readable report this run wrote gives the protocol's spend."""

    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.folder = Path(directory.name) / 'protocol'

    def test_a_missing_report_leaves_the_spend_unknown_and_stops(self) -> None:
        section, stopped = qualify_release.protocol_result(self.folder, qualify_release.protocol_reports(self.folder), 1)
        self.assertTrue(section['spend_unknown'])
        self.assertEqual(stopped, 'the protocol run left no readable report (exit 1), so its spend is unknown and no goal starts')

    def test_a_report_left_by_an_earlier_run_doesnt_count(self) -> None:
        self.folder.mkdir()
        (self.folder / PROTOCOL_REPORT).write_text(protocol_report())
        section, stopped = qualify_release.protocol_result(self.folder, qualify_release.protocol_reports(self.folder), 1)
        self.assertTrue(section['spend_unknown'])
        self.assertIn('no goal starts', stopped)

    def test_a_report_this_run_wrote_gives_its_spend(self) -> None:
        self.folder.mkdir()
        report = self.folder / PROTOCOL_REPORT
        report.write_text(protocol_report(5))
        earlier = qualify_release.protocol_reports(self.folder)
        report.write_text(protocol_report())
        later = earlier[report] + 1_000_000
        os.utime(report, ns=(later, later))
        section, stopped = qualify_release.protocol_result(self.folder, earlier, 0)
        self.assertEqual(stopped, '')
        self.assertEqual((section['committed_micro_usd'], section['cases'], section['passed']), (1200, 2, 1))

    def test_an_unreadable_report_leaves_the_spend_unknown(self) -> None:
        self.folder.mkdir()
        report = self.folder / PROTOCOL_REPORT
        for text in ('{not json', protocol_report(committed=None), protocol_report(committed='1200'), json.dumps({'calls': 1})):
            report.write_text(text)
            section, stopped = qualify_release.protocol_result(self.folder, {}, 0)
            self.assertTrue(section['spend_unknown'], text)
            self.assertIn('no goal starts', stopped)


class ReleaseAttempt(unittest.TestCase):
    """`qualify_release.attempt` as the owner runs it, on fakes: the protocol, the corpus, the benchmark
    and the report, with the stack, Docker, the API, the helper and the worker faked."""

    def attempt(self, worker: FakeWorker, rules: Mapping[str, Answer], protocol: bool) -> tuple[object, dict, FakeOps, list[dict]]:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        base = Path(directory.name)
        (base / 'config').mkdir()
        (base / 'tasks.json').write_text(json.dumps(API_TASKS[:2]))
        ops = FakeOps(FakeStack(FakeDatabase(rules)), worker)
        goals: list[dict] = []

        def api(port: int, internal: str, token: str, method: str = 'GET', path: str = '', body: bytes | None = None,
                extra: Mapping[str, str] | None = None) -> tuple[int, str]:
            if (method, path) == ('POST', '/v1/runs'):
                sent = json.loads(body or b'{}')
                if not sent['goal_text'].startswith('Benchmark'):
                    goals.append(sent)
                return 202, '{"run_id": "run-1"}'
            if path.endswith('/events'):
                return 200, '{"events": []}'
            if path.endswith('/cancel'):
                return 200, '{}'
            if method == 'GET' and path.startswith('/v1/runs/'):
                return 200, '{"version": 1}'
            raise AssertionError((method, path))

        def processes(argv: list[str], **options: object) -> subprocess.CompletedProcess[str]:
            if 'autobots.operations.route_qualification' in argv:
                return completed(argv, '', 1)
            if argv[:2] == ['docker', 'stats']:
                return completed(argv)
            return only_cleanup(argv)

        arguments = Namespace(out=str(base / 'out'), tasks=str(base / 'tasks.json'), trials=1, protocol=protocol, authorized_micro_usd=10 * GOAL_LIMIT,
                              ui=False, already_spent_micro_usd=7)
        with disposable_fakes(qualify_release, ops, FakeClock(), base / 'config', api, processes, SAMPLE_SECONDS=3600,
                              find_tools=lambda _: {}, child_env=lambda *_, **__: {}):
            code, _, _ = quietly(lambda: qualify_release.attempt(ROOT, arguments, Path('key')))
        return code, json.loads((base / 'out/report.json').read_text()), ops, goals

    def test_a_missing_protocol_report_stops_before_any_goal(self) -> None:
        code, report, ops, goals = self.attempt(FakeWorker(), {'row_to_json': ''}, protocol=True)
        self.assertEqual(code, 1)
        self.assertEqual((ops.spawned, goals), ([], []))
        self.assertTrue(report['protocol']['spend_unknown'])
        self.assertIn('the protocol run left no readable report (exit 1)', report['stopped'])
        self.assertEqual(report['spent_micro_usd'], 7)

    def test_a_goal_that_raises_is_in_the_reported_total_at_its_whole_budget(self) -> None:
        code, report, _, goals = self.attempt(FakeWorker(exits_after=0), release_rules('running', TWO_CALLS), protocol=False)
        self.assertEqual((code, len(goals)), (1, 1))
        self.assertEqual(report['spent_micro_usd'], 7 + GOAL_LIMIT)
        self.assertEqual(report['interrupted_goal']['counted_micro_usd'], GOAL_LIMIT)
        self.assertEqual(report['stopped'], f"the worker exited early: 1; {API_TASKS[0]['id']}/1 stopped before its spend was read, so it counts its whole budget")

    def test_a_goal_whose_spend_cant_be_read_is_in_the_cost_summary_at_its_whole_budget(self) -> None:
        code, report, _, goals = self.attempt(FakeWorker(), release_rules('succeeded', None), protocol=False)
        self.assertEqual((code, len(goals)), (1, 1))
        self.assertEqual(report['spent_micro_usd'], 7 + GOAL_LIMIT)
        self.assertEqual(report['cost_per_goal_micro_usd'], {'median': GOAL_LIMIT, 'max': GOAL_LIMIT, 'goals_at_their_whole_budget': 1})
        self.assertIn('could not be read', report['stopped'])


class LedgerShape(unittest.TestCase):
    """paid_run copies the service's ledger by shape (R-23): the scripts load the service at run time, so
    mypy can't compare the two, and this keeps them from drifting apart."""

    @staticmethod
    def shape(path: Path) -> tuple[list[str], list[tuple[str, str]], dict[str, str]]:
        """The ledger states, each entry field with its type, and the signatures of the ledger methods the
        scripts call."""
        states: list[str] = []
        fields: list[tuple[str, str]] = []
        methods: dict[str, str] = {}
        for node in ast.parse(path.read_text()).body:
            if isinstance(node, ast.Assign) and [ast.unparse(target) for target in node.targets] == ['LedgerState']:
                assert isinstance(node.value, ast.Subscript) and isinstance(node.value.slice, ast.Tuple), path
                states = [ast.literal_eval(element) for element in node.value.slice.elts]
            elif isinstance(node, ast.ClassDef) and node.name == 'LedgerEntry':
                fields = [(item.target.id, ast.unparse(item.annotation)) for item in node.body
                          if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name)]
            elif isinstance(node, ast.ClassDef) and node.name == 'Ledger':
                methods = {item.name: f'({ast.unparse(item.args)}) -> {ast.unparse(item.returns) if item.returns else None}'
                           for item in node.body if isinstance(item, ast.FunctionDef) and item.name in ('reserve', 'settle', 'committed')}
        return states, fields, methods

    def test_the_scripts_ledger_type_matches_the_services(self) -> None:
        service = self.shape(ROOT / 'services/agent/src/autobots/operations/route_qualification.py')
        self.assertEqual(self.shape(ROOT / 'scripts/paid_run.py'), service)
        self.assertIn('run_not_finished', service[0])
        self.assertIn(('reported', 'int | None'), service[1])
        self.assertEqual(sorted(service[2]), ['committed', 'reserve', 'settle'])


if __name__ == '__main__':
    unittest.main()
