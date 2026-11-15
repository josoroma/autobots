"""The install's process supervision in scripts/local_app.py, on a fake process table (SQLI-10).

No process is started or signalled: FakeProcesses stands in for ps, lsof, pgrep, kill and the clock. The cases are
the rules the Makefile used to keep in shell: a reused pid, a stray copy, a drain that runs out without a KILL, the
pinned locale and zone, and a port held by someone else.
"""
from __future__ import annotations

import contextlib
import http.client
import io
import os
import signal
import sys
import tempfile
import threading
import unittest
from collections.abc import Mapping, Sequence
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import local_app  # noqa: E402

STARTED = 'Sun Nov 15 10:00:00 2026'


class FakeProcesses:
    def __init__(self) -> None:
        self.started: dict[int, str] = {}
        self.ports: dict[int, list[int]] = {}
        self.patterns: dict[str, list[int]] = {}
        self.ancestors: set[int] = {os.getpid()}
        self.signals: list[tuple[int, str]] = []
        self.spawned: list[tuple[list[str], dict[str, str]]] = []
        self.replies: set[str] = set()
        self.slept = 0.0
        # How many polls a terminated process takes to exit, or None to never exit.
        self.exits_after: int | None = 0
        self.next_pid = 4242

    def start_time(self, pid: int) -> str:
        return self.started.get(pid, '')

    def listening(self, port: int) -> list[int]:
        return list(self.ports.get(port, []))

    def matching(self, pattern: str) -> list[int]:
        return list(self.patterns.get(pattern, []))

    def ours(self) -> set[int]:
        return set(self.ancestors)

    def alive(self, pid: int) -> bool:
        if pid not in self.started:
            return False
        if self.exits_after is not None and any(signalled == pid for signalled, _ in self.signals):
            if self.exits_after <= 0:
                del self.started[pid]
                return False
            self.exits_after -= 1
        return True

    def terminate(self, pid: int) -> None:
        self.signals.append((pid, 'TERM'))

    def spawn(self, argv: Sequence[str], env: Mapping[str, str], log: Path) -> int:
        pid = self.next_pid
        self.spawned.append((list(argv), dict(env)))
        self.started[pid] = STARTED
        return pid

    def answers(self, url: str) -> bool:
        return url in self.replies

    def sleep(self, seconds: float) -> None:
        self.slept += seconds


class Supervision(unittest.TestCase):
    def setUp(self) -> None:
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.processes = FakeProcesses()
        self.app = local_app.LocalApp(self.root / 'run', self.root / 'logs', self.processes)
        self.output = self.enterContext(contextlib.redirect_stdout(io.StringIO()))

    def printed(self) -> str:
        return self.output.getvalue()

    def track(self, name: str, pid: int, recorded: str = STARTED) -> None:
        (self.root / 'run').mkdir(exist_ok=True)
        (self.root / 'run' / f'{name}.pid').write_text(f'{pid}\n{recorded}\n')

    def test_a_tracked_process_counts_only_while_its_start_time_matches(self) -> None:
        self.processes.started[100] = STARTED
        self.track('worker', 100)
        self.assertEqual(self.app.running('worker'), 100)
        # After a reboot the pid belongs to something else, started at another time.
        self.processes.started[100] = 'Mon Nov 16 08:00:00 2026'
        self.assertIsNone(self.app.running('worker'))
        del self.processes.started[100]
        self.assertIsNone(self.app.running('worker'))

    def test_a_pid_file_the_makefile_wrote_is_still_read(self) -> None:
        """Processes running when this moved out of the Makefile were tracked by its `echo` and `ps` lines."""
        self.processes.started[100] = STARTED
        (self.root / 'run').mkdir()
        (self.root / 'run/api.pid').write_text(f'100\n{STARTED}   \n')
        self.assertEqual(self.app.running('api'), 100)

    def test_a_start_writes_the_pid_and_its_start_time(self) -> None:
        self.assertEqual(self.app.start('api', ['python', '-m', 'uvicorn'], {'A': '1'}, 8001), 0)
        self.assertEqual((self.root / 'run/api.pid').read_text(), f'4242\n{STARTED}\n')
        self.assertEqual(self.processes.spawned, [(['python', '-m', 'uvicorn'], {'A': '1'})])
        self.assertIn('api: started', self.printed())

    def test_a_running_process_is_not_started_twice(self) -> None:
        self.processes.started[100] = STARTED
        self.track('api', 100)
        self.assertEqual(self.app.start('api', ['python'], {}, 8001), 0)
        self.assertEqual(self.processes.spawned, [])
        self.assertIn('api: already running', self.printed())

    def test_a_start_is_refused_beside_an_untracked_copy_and_stops_nothing(self) -> None:
        self.processes.patterns[local_app.STRAY_PATTERNS['worker']] = [555, 556]
        self.assertEqual(self.app.start('worker', ['python', '-m', 'autobots.operations.worker'], {}, None), 1)
        self.assertEqual((self.processes.spawned, self.processes.signals), ([], []))
        self.assertIn('worker: refused. pid 555 556 looks like a copy of the worker that this install does not track', self.printed())
        self.assertIn('Stop it with: kill -TERM 555 556', self.printed())
        # A port held by another server refuses the API the same way.
        self.processes.ports[8001] = [777]
        self.assertEqual(self.app.start('api', ['python'], {}, 8001), 1)

    def test_this_process_and_its_parents_are_not_strays(self) -> None:
        """Their command lines name the worker they start, so a pattern matches them too."""
        self.processes.patterns[local_app.STRAY_PATTERNS['worker']] = [os.getpid(), 900]
        self.processes.ancestors = {os.getpid(), 900}
        self.assertEqual(self.app.strays('worker', None), [])
        self.assertEqual(self.app.strays('unknown', None), [])

    def test_a_worker_that_exits_at_once_fails_its_start(self) -> None:
        def spawn_and_die(argv: Sequence[str], env: Mapping[str, str], log: Path) -> int:
            return 4343  # Never seen with a start time, as a process that already exited.

        self.processes.spawn = spawn_and_die  # type: ignore[method-assign]  # a stand-in for one that dies
        self.assertEqual(self.app.start('worker', ['python'], {}, None, settle=2), 1)
        self.assertIn(f"worker: exited. Read {self.root / 'logs/worker.log'}", self.printed())
        self.assertEqual(self.processes.slept, 2)

    def test_a_stop_sends_term_and_waits_out_the_drain(self) -> None:
        self.processes.started[100] = STARTED
        self.track('worker', 100)
        self.processes.exits_after = 3
        self.assertEqual(self.app.stop('worker', None), 0)
        self.assertEqual(self.processes.signals, [(100, 'TERM')])
        self.assertIn('worker: stopped', self.printed())
        self.assertFalse((self.root / 'run/worker.pid').exists())

    def test_a_drain_past_its_bound_is_reported_and_never_killed(self) -> None:
        self.processes.started[100] = STARTED
        self.track('worker', 100)
        self.processes.exits_after = None
        self.assertEqual(self.app.stop('worker', None), 1)
        self.assertEqual(self.processes.signals, [(100, 'TERM')])
        self.assertEqual(self.processes.slept, local_app.STOP_SECONDS - 1)
        self.assertIn(f'worker: still running after {local_app.STOP_SECONDS} seconds, pid 100', self.printed())
        # The pid file stays, so the next stop or status still finds it.
        self.assertTrue((self.root / 'run/worker.pid').exists())

    def test_a_stop_reports_an_untracked_copy_and_leaves_it_running(self) -> None:
        self.processes.ports[3000] = [888]
        self.assertEqual(self.app.stop('web', 3000), 0)
        self.assertEqual(self.processes.signals, [])
        self.assertIn('web: not running', self.printed())
        self.assertIn('web: pid 888 looks like one this install does not track, so it was left running.', self.printed())

    def test_awaiting_needs_our_own_process_on_the_port_and_a_reply(self) -> None:
        self.processes.started[100] = STARTED
        self.track('api', 100)
        url = 'http://127.0.0.1:8001/'
        self.processes.replies.add(url)
        self.processes.ports[8001] = [999]  # Another project's server holds the port.
        self.assertEqual(self.app.wait_until_answering('api', 8001, url), 1)
        self.assertEqual(self.processes.slept, local_app.AWAIT_TRIES - 1)
        self.assertIn('api: not answering at http://127.0.0.1:8001/. Something else may hold the port.', self.printed())
        self.processes.ports[8001] = [100]
        self.assertEqual(self.app.wait_until_answering('api', 8001, url), 0)
        self.assertIn('api: answering at http://127.0.0.1:8001/', self.printed())

    def test_awaiting_a_process_that_exited_fails_at_once(self) -> None:
        self.assertEqual(self.app.wait_until_answering('api', 8001, 'http://127.0.0.1:8001/'), 1)
        self.assertEqual(self.processes.slept, 0)

    def test_status_names_each_process(self) -> None:
        self.processes.started[100] = STARTED
        self.track('api', 100)
        self.app.status(['api', 'web'])
        self.assertEqual(self.printed(), 'api: running, pid 100\nweb: not running\n')


class Environment(unittest.TestCase):
    def test_app_env_is_read_as_data_and_the_switches_are_the_makefiles(self) -> None:
        env = local_app.launch_env({'PATH': '/usr/bin', 'HOME': '/home/fixture'},
                                   "export AUTOBOTS_API_URL='http://127.0.0.1:8001'\nAUTOBOTS_INTERNAL_TOKEN=$(touch pwned)\n",
                                   dotenv=None, node_bin='/opt/node/bin', inference='enabled')
        self.assertEqual(env['AUTOBOTS_API_URL'], 'http://127.0.0.1:8001')
        self.assertEqual(env['AUTOBOTS_INTERNAL_TOKEN'], '$(touch pwned)')
        self.assertEqual(env['PATH'], f'/opt/node/bin{os.pathsep}/usr/bin')
        self.assertEqual((env['PYTHONPATH'], env['NEXT_TELEMETRY_DISABLED'], env['AUTOBOTS_WORKER_INFERENCE'], env['HOME']),
                         ('services/agent/src', '1', 'enabled', '/home/fixture'))

    def test_no_pinned_node_adds_nothing_to_the_search_path(self) -> None:
        env = local_app.launch_env({'PATH': '/usr/bin'}, '', dotenv=None, node_bin='', inference='')
        self.assertEqual(env['PATH'], '/usr/bin')


class CommandLine(unittest.TestCase):
    def test_the_makefiles_start_line_keeps_the_commands_own_options(self) -> None:
        processes = FakeProcesses()
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()):
            root = Path(folder)
            (root / 'app.env').write_text('AUTOBOTS_INTERNAL_TOKEN=arranged\n')
            code = local_app.main(['--run-dir', str(root / 'run'), '--log-dir', str(root / 'logs'), 'start', '--env-file', str(root / 'app.env'),
                                   '--inference', '', '--node-bin', '', 'api', '--port', '8001', '--keys', str(root / 'missing.env'), '--',
                                   'python', '-m', 'uvicorn', '--port', '8001', '--no-access-log'], processes)
        self.assertEqual(code, 0)
        argv, env = processes.spawned[0]
        self.assertEqual(argv, ['python', '-m', 'uvicorn', '--port', '8001', '--no-access-log'])
        self.assertEqual(env['AUTOBOTS_INTERNAL_TOKEN'], 'arranged')

    def test_a_missing_app_env_refuses_without_starting_anything(self) -> None:
        processes = FakeProcesses()
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stderr(io.StringIO()) as errors:
            code = local_app.main(['--run-dir', folder, '--log-dir', folder, 'start', '--env-file', f'{folder}/app.env', 'web', '--port', '3000', '--', 'next'],
                                  processes)
        self.assertEqual((code, processes.spawned), (1, []))
        self.assertIn('could not be read', errors.getvalue())

    def test_recorded_prints_one_field_and_nothing_when_absent(self) -> None:
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()) as printed, \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(local_app.main(['recorded', folder, 'project']), 1)
            (Path(folder) / 'install.json').write_text('{"project": "autobots-install", "api_port": 8001}')
            self.assertEqual(local_app.main(['recorded', folder, 'api_port']), 0)
        self.assertEqual(printed.getvalue(), '8001\n')

    def test_the_real_table_pins_locale_and_zone_for_start_times(self) -> None:
        with mock.patch.object(local_app, 'output', return_value=f'{STARTED}\n') as read:
            self.assertEqual(local_app.System().start_time(100), STARTED)
        (argv, env), = [call.args for call in read.call_args_list]
        self.assertEqual(argv, ['ps', '-p', '100', '-o', 'lstart='])
        self.assertEqual((env['LC_ALL'], env['TZ']), ('C', 'UTC'))
        self.assertEqual(local_app.System().start_time(0), '')

    def test_a_running_process_reads_no_install_file(self) -> None:
        processes = FakeProcesses()
        processes.started[100] = STARTED
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()) as printed:
            (Path(folder) / 'web.pid').write_text(f'100\n{STARTED}\n')
            code = local_app.main(['--run-dir', folder, '--log-dir', folder, 'start', '--env-file', f'{folder}/absent/app.env', 'web', '--port',
                                   '3000', '--', 'next'], processes)
        self.assertEqual((code, printed.getvalue(), processes.spawned), (0, 'web: already running\n', []))

    def test_a_reply_cut_off_before_its_status_line_is_a_retry(self) -> None:
        for failure in (http.client.BadStatusLine(''), http.client.RemoteDisconnected('closed'), ConnectionRefusedError()):
            with self.subTest(type(failure).__name__), mock.patch.object(local_app.request, 'urlopen', side_effect=failure):
                self.assertFalse(local_app.System().answers('http://127.0.0.1:8001/'))


class ExitBeforeTerm(unittest.TestCase):
    def test_a_process_that_exits_before_its_term_is_stopped(self) -> None:
        processes = FakeProcesses()
        processes.started[100] = STARTED

        def gone(_pid: int) -> None:
            del processes.started[100]
            raise ProcessLookupError

        processes.terminate = gone  # type: ignore[method-assign]  # one that exited between the read and the signal
        with tempfile.TemporaryDirectory() as folder, contextlib.redirect_stdout(io.StringIO()) as printed:
            (Path(folder) / 'api.pid').write_text(f'100\n{STARTED}\n')
            code = local_app.LocalApp(Path(folder), Path(folder), processes).stop('api', 8001)
            self.assertFalse((Path(folder) / 'api.pid').exists())
        self.assertEqual((code, printed.getvalue()), (0, 'api: stopped\n'))


class RealProcessTable(unittest.TestCase):
    """System against the real ps, pgrep and signals, on a `sleep` this test starts and always ends. No service runs."""

    def test_a_started_process_is_tracked_found_and_stopped(self) -> None:
        seconds = str(2900 + os.getpid() % 97)
        folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        app = local_app.LocalApp(folder / 'run', folder / 'logs', local_app.System())
        self.enterContext(mock.patch.dict(local_app.STRAY_PATTERNS, {'sleeper': f'sl[e]ep {seconds}$'}))
        with contextlib.redirect_stdout(io.StringIO()) as printed:
            self.assertEqual(app.start('sleeper', ['sleep', seconds], {'PATH': os.environ.get('PATH', '/bin:/usr/bin')}, None), 0)
        pid = int((folder / 'run/sleeper.pid').read_text().split()[0])
        # This test started it, so it must reap it, as launchd would once local_app.py exits.
        reaper = threading.Thread(target=reap, args=(pid,), daemon=True)
        reaper.start()
        self.addCleanup(end, pid, reaper)
        self.assertIn('sleeper: started', printed.getvalue())
        self.assertEqual(app.running('sleeper'), pid)
        self.assertEqual(app.strays('sleeper', None), [pid])
        recorded = (folder / 'run/sleeper.pid').read_text()
        # The same pid with another start time, as after a reboot, is not this process.
        (folder / 'run/sleeper.pid').write_text(f'{pid}\nMon Jan  1 00:00:00 2001\n')
        self.assertIsNone(app.running('sleeper'))
        (folder / 'run/sleeper.pid').write_text(recorded)
        with contextlib.redirect_stdout(io.StringIO()) as printed:
            self.assertEqual(app.stop('sleeper', None), 0)
        self.assertEqual(printed.getvalue(), 'sleeper: stopped\n')
        self.assertFalse((folder / 'run/sleeper.pid').exists())
        self.assertIsNone(app.running('sleeper'))
        self.assertEqual(app.strays('sleeper', None), [])


def reap(pid: int) -> None:
    with contextlib.suppress(ChildProcessError):
        os.waitpid(pid, 0)


def end(pid: int, reaper: threading.Thread) -> None:
    with contextlib.suppress(ProcessLookupError):
        os.kill(pid, signal.SIGKILL)
    reaper.join(10)


class Makefile(unittest.TestCase):
    """Each target is a one-line call, and the shell that held these rules is gone (SQLI-10, SQLI-11)."""

    text = (ROOT / 'Makefile').read_text()

    def test_no_supervision_is_left_in_make_macros(self) -> None:
        for leftover in ('define launch', 'define halt', 'define await', 'stray_pids', 'lstart=', 'kill -TERM', 'nohup', '.nvm/versions'):
            with self.subTest(leftover):
                self.assertNotIn(leftover, self.text)

    def test_node_images_and_install_json_come_from_the_scripts_that_own_them(self) -> None:
        self.assertIn('NODE_BIN  = $(shell python3.12 scripts/toolchain.py node-bin 2>/dev/null)', self.text)
        self.assertIn('images:\n\t$(INSTALL) images\n', self.text)
        self.assertNotIn("python3.12 -c 'import json", self.text)
        self.assertEqual(self.text.count('scripts/local_app.py recorded'), 2)

    def test_build_and_the_web_start_fail_without_the_pinned_node(self) -> None:
        self.assertIn("test -n \"$$node_bin\" || { echo '$(NO_NODE)'; exit 1; }", self.text)
        self.assertIn("@test -n '$(NODE_BIN)' || { echo '$(NO_NODE)'; exit 1; }", self.text)


if __name__ == '__main__':
    unittest.main()
