"""The optional assistant adapter's status, and the verify report that records it (scripts/harness_lib.py,
scripts/verify.py).

Fixture adapter states cover arranged conditions only, and passing here shows nothing about whether events are
delivered. Allowlisted qualification literals make a later honest change fail on purpose: recording
qualification needs evidence and a deliberate change to the check. Split from test_assistant_assets.py by the
unit under test (refactor plan R-66, THRN-04).
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from harness_support import (
    HarnessTestCase,
    adapter_status,
    edit_json,
    harness_lib,
    report_state,
    valid_root,
    verify,
    version_stub,
    write_stub,
)

STATES = {'inactive', 'configured_unqualified'}


class AdapterStatusTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        base = Path(temporary.name).resolve()
        (base / 'root').mkdir()
        (base / 'bin').mkdir()
        self.root = valid_root(str(base / 'root'))
        self.bin = base / 'bin'

    def status(self, stub: Path, **arguments) -> dict:
        return adapter_status(self.root, lookup=lambda name: str(stub) if name == 'claude' else None, **arguments)

    def assert_status(self, status: dict, state: str, reason: str) -> None:
        # Whole values: `inactive` contains "active", and `configured_unqualified` contains "qualified".
        self.assertEqual(status['state'], state)
        self.assertEqual(status['reason'], reason)
        self.assertIn(status['state'], STATES)
        self.assertEqual(status['model_route'], 'not_checked')

    def test_empty_lookup_is_inactive(self):
        self.assert_status(adapter_status(self.root, lookup=lambda name: None), 'inactive', 'unavailable')

    def test_process_path_decides_availability(self):
        _stub, record = version_stub(self.bin)
        with mock.patch.dict(os.environ, {'PATH': str(self.bin)}):
            status = adapter_status(self.root)
        self.assert_status(status, 'configured_unqualified', 'delivery_unverified')
        self.assertEqual(record.read_text(), '--version\n')
        empty = self.bin / 'empty'
        empty.mkdir()
        with mock.patch.dict(os.environ, {'PATH': str(empty)}):
            self.assert_status(adapter_status(self.root), 'inactive', 'unavailable')

    def test_versions_compare_numerically(self):
        cases = {'2.1.200': ('inactive', 'version_below_minimum'),
                 '2.1.99': ('inactive', 'version_below_minimum'),
                 '2.1.295': ('configured_unqualified', 'delivery_unverified'),
                 '2.1.314': ('configured_unqualified', 'delivery_unverified'),
                 '2.1.1000': ('configured_unqualified', 'delivery_unverified')}
        for version, (state, reason) in cases.items():
            with self.subTest(version=version):
                stub, record = version_stub(self.bin, version)
                record.unlink(missing_ok=True)
                status = self.status(stub)
                self.assert_status(status, state, reason)
                self.assertEqual(status['observed_version'], version)
                self.assertEqual(status['minimum_version'], '2.1.295')
                self.assertEqual(record.read_text(), '--version\n')

    def test_failing_and_unparsable_versions(self):
        cases = {'failing': 'exit 3', 'failing with a version': "printf '2.1.314 (Claude Code)\\n'; exit 3",
                 'unparsable': "printf 'not a version\\n'", 'two parts': "printf '2.1 (Claude Code)\\n'",
                 'suffix': "printf '2.1.314-beta (Claude Code)\\n'", 'empty': ':'}
        for name, body in cases.items():
            with self.subTest(case=name):
                stub, record = write_stub(self.bin, body)
                record.unlink(missing_ok=True)
                status = self.status(stub)
                self.assert_status(status, 'inactive', 'version_unknown')
                self.assertNotIn('observed_version', status)
                self.assertEqual(record.read_text(), '--version\n')

    def test_unstartable_command_is_unknown(self):
        stub = self.bin / 'claude'
        stub.write_text('not a program\n')
        stub.chmod(0o644)
        self.assert_status(self.status(stub), 'inactive', 'version_unknown')

    def test_hanging_command_returns_promptly_and_leaves_nothing_running(self):
        pid_file = self.bin / 'pid'
        stub, record = write_stub(self.bin, f'echo $$ > "{pid_file}"\nsleep 30')
        began = time.monotonic()
        status = self.status(stub, timeout=0.3)
        self.assertLess(time.monotonic() - began, 5)
        self.assert_status(status, 'inactive', 'version_unknown')
        self.assertEqual(record.read_text(), '--version\n')
        group = int(pid_file.read_text())
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            try:
                os.killpg(group, 0)
            except ProcessLookupError:
                break
            time.sleep(0.05)
        else:
            self.fail('The stub process group is still running.')

    def test_probe_environment_carries_no_inherited_credential(self):
        seen = self.bin / 'seen'
        stub, _ = write_stub(self.bin, f'printf "%s" "${{AUTOBOTS_SENTINEL_CREDENTIAL-unset}}" > "{seen}"\n'
                                       "printf '2.1.314 (Claude Code)\\n'")
        with mock.patch.dict(os.environ, {'AUTOBOTS_SENTINEL_CREDENTIAL': 'present'}):
            self.status(stub)
        self.assertEqual(seen.read_text(), 'unset')

    def test_executable_path_is_not_recorded(self):
        stub, _ = version_stub(self.bin)
        status = self.status(stub)
        self.assertEqual(set(status), {'state', 'reason', 'minimum_version', 'observed_version', 'model_route'})
        self.assertNotIn(str(self.bin), json.dumps(status))

    def test_first_matching_condition_wins(self):
        stub, record = version_stub(self.bin, '2.1.200')
        edit_json(self.root / '.claude/autobots.json', lambda data: data['assistant'].pop('minimum_version_for_blocking_hook_failure'))
        (self.root / 'AGENTS.md').unlink()
        self.assert_status(adapter_status(self.root, lookup=lambda name: None), 'inactive', 'unavailable')
        self.assert_status(self.status(stub), 'inactive', 'minimum_unknown')
        self.assertFalse(record.exists())

    def test_invalid_configuration_is_inactive_and_runs_nothing(self):
        stub, record = version_stub(self.bin)
        (self.root / 'AGENTS.md').unlink()
        self.assert_status(self.status(stub), 'inactive', 'configuration_invalid')
        self.assertFalse(record.exists())

    def test_unreadable_configuration_is_inactive(self):
        stub, _ = version_stub(self.bin)
        (self.root / '.claude/autobots.json').write_text('{bad')
        self.assert_status(self.status(stub), 'inactive', 'minimum_unknown')


class ReportTests(HarnessTestCase):
    def test_runner_records_status_and_report_state_still_accepts_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = valid_root(directory)

            def passing_check(_root, name, argv):
                return {'id': name, 'class': 'static_or_fixture', 'model_transport': 'none', 'command_argv': argv,
                        'exit_code': 0, 'status': 'passed', 'output': 'Ran 1 test\n'}

            output = io.StringIO()
            with (mock.patch.object(verify, 'project_root', lambda: root),
                  mock.patch.object(verify, 'run_check', passing_check),
                  mock.patch.object(verify, 'adapter_status',
                                    lambda path: harness_lib.adapter_status(path, lookup=lambda _: None)),
                  mock.patch.object(sys, 'argv', ['verify.py', '--profile', 'harness']),
                  contextlib.redirect_stdout(output)):
                code = verify.main()
            self.assertEqual(code, 0)
            summary = json.loads(output.getvalue())
            self.assertEqual(summary['assistant_adapter'], {'state': 'inactive', 'reason': 'unavailable'})
            report = json.loads((root / '.checks/harness/latest.json').read_text())
            self.assertEqual(report['assistant_adapter'], {'state': 'inactive', 'reason': 'unavailable',
                                                           'minimum_version': '2.1.295', 'model_route': 'not_checked'})
            self.assertEqual(len(report['checks']), 3)
            self.assertIn('Claude event delivery', report['not_tested'])
            self.assertTrue(report_state(root)[0])


if __name__ == '__main__':
    unittest.main()
