"""The paid-run decisions and mechanics in scripts/paid_run.py, with a fake clock, fake SQL, a fake worker
and a fake ledger. No Docker, no network, no install and no model call (refactor plan R-23, SCRP-03).

Decision 0028 E2 is held end to end through `persistent_install.goal`: three unreadable spend polls in a
row stop the worker, the report records the spend as unknown, the ledger entry stays held and the entry
point exits non-zero.
"""
from __future__ import annotations

import contextlib
import io
import json
import signal
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Callable, Mapping
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))

import paid_run  # noqa: E402
import persistent_install  # noqa: E402
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

Answer = str | None | list[str | None]
SPEND = 'sum(coalesce(charged_micro_usd'
STATUS = 'select status from public.runs'


class FakeDatabase:
    """Answers a statement from the first rule whose fragment it contains. None fails the statement, as an
    unreachable database does, and a list answers successive statements, its last answer repeating."""

    def __init__(self, rules: Mapping[str, Answer]) -> None:
        self.rules = {fragment: list(answer) if isinstance(answer, list) else [answer] for fragment, answer in rules.items()}
        self.statements: list[str] = []

    def runtime(self, statements: str) -> subprocess.CompletedProcess[str]:
        self.statements.append(statements)
        for fragment, answers in self.rules.items():
            if fragment in statements:
                answer = answers.pop(0) if len(answers) > 1 else answers[0]
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
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        result = call()
    return result, out.getvalue(), err.getvalue()


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


class InstallGoal(unittest.TestCase):
    """`persistent_install.goal` as the owner runs it, on fakes: its real wiring, watchdog, settlement and exit."""

    LIMIT = 1000

    def run_goal(self, status: Answer, spend: Answer, worker: FakeWorker) -> tuple[int, dict, FakeLedger, str]:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        install = Path(directory.name)
        for name in ('reports', 'logs'):
            (install / name).mkdir()
        record = persistent_install.Record('autobots-install', 'install-id', 1, 2, 3, 4, install)
        database = FakeDatabase({
            'app_private.run_jobs': '0', "role = 'owner'": 'workspace', 'provider_credentials': '1',
            'clock_timestamp': '2026-11-14 10:00:00+00', STATUS: status, SPEND: spend, 'stop_reason': 'none',
            'run_verifications': 'true {}', 'public.artifacts': 'none', 'charged_micro_usd is null': '0',
            'select count(*) from app_private.model_invocations': '2', 'distinct profile': 'none', 'worker_heartbeats': '0'})
        ledger, clock = FakeLedger(), FakeClock()
        answers = {'usage': '1.5', 'leaks': '0 0'}
        built = persistent_install.install_session

        def install_session(*args: object, **kwargs: object) -> PaidSession:
            # The real wiring, with only the clock, the helper and the worker faked, so no key leaves the test.
            made = built(*args, **kwargs)
            made.clock, made.sleep = clock.monotonic, clock.sleep
            made.spawn = lambda argv, extra: worker
            made.helper = lambda command, *_: answers[command]
            return made

        def http(method: str, url: str, headers: Mapping[str, str], body: Mapping | None = None) -> tuple[int, str]:
            if url.endswith('/auth/v1/token?grant_type=password'):
                return 200, '{"access_token": "token"}'
            if url.endswith('/v1/runs'):
                return 202, '{"run_id": "run-1"}'
            raise AssertionError(url)

        values = {'app.env': {'AUTOBOTS_SUPABASE_URL': 'http://gateway', 'AUTOBOTS_SUPABASE_ANON_KEY': 'anon', 'AUTOBOTS_INTERNAL_TOKEN': 'internal'},
                  'owner.env': {'OWNER_EMAIL': 'owner@autobots.invalid', 'OWNER_PASSWORD': 'password'}}
        with mock.patch.object(persistent_install, 'reserve_goal', return_value=(ledger, ledger.reserve('install-goal', self.LIMIT))), \
             mock.patch.object(persistent_install, 'install_stack', return_value=database), \
             mock.patch.object(persistent_install, 'require_install'), \
             mock.patch.object(persistent_install, 'read_values', side_effect=lambda path: values[path.name]), \
             mock.patch.object(persistent_install, 'install_session', install_session), \
             mock.patch.object(persistent_install, 'http_json', http), mock.patch.object(paid_run, 'http_json', http), \
             mock.patch('subprocess.run', side_effect=AssertionError('no process')), \
             mock.patch('subprocess.Popen', side_effect=AssertionError('no process')):
            code, _, err = quietly(lambda: persistent_install.goal(ROOT, record, 'autobots-install', Path('key'), self.LIMIT,
                                                                    install / 'ledger.json', 'a goal', []))
        [written] = (install / 'reports').glob('goal-*.json')
        assert isinstance(code, int)
        return code, json.loads(written.read_text()), ledger, err

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


if __name__ == '__main__':
    unittest.main()


class LedgerShape(unittest.TestCase):
    def test_the_scripts_ledger_type_matches_the_services(self):
        """paid_run copies the service's ledger entry by shape (R-23), so the two can't drift apart."""
        import re

        def shape(path: Path) -> tuple[list[str], list[str]]:
            text = path.read_text()
            states = re.search(r'^LedgerState = Literal\[(.*?)\]', text, re.MULTILINE | re.DOTALL)
            entry = re.search(r'^class LedgerEntry\(TypedDict\):\n(.*?)(?=^\S)', text, re.MULTILINE | re.DOTALL)
            assert states is not None and entry is not None, path
            fields = re.findall(r'^    (\w+): ', entry.group(1), re.MULTILINE)
            return re.findall(r'["\'](\w+)["\']', states.group(1)), fields

        root = Path(__file__).resolve().parents[2]
        service = shape(root / 'services/agent/src/autobots/operations/route_qualification.py')
        self.assertEqual(shape(root / 'scripts/paid_run.py'), service)
        self.assertIn('run_not_finished', service[0])
