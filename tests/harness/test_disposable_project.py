"""One lifecycle for every disposable qualification, in disposable_db.disposable_project, and one atomic report writer
(refactor plan R-65, SCRP-07, XDUP-13).

Docker is a recording stand-in: no engine is reached and nothing is created or removed. The cases are the ones the
copies diverged on: a listing that fails must not read as nothing left, a body that raises still removes the project,
and a second project the run owns is removed and checked too.
"""
from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Iterator, Sequence
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import disposable_db  # noqa: E402
from qualification import records  # noqa: E402
from qualification.errors import Refused, Unavailable  # noqa: E402
from qualification.records import Cases  # noqa: E402

PROJECT, RESTORED = 'autobots-disposable-a1b2c3d4', 'autobots-disposable-e5f6a7b8'


def completed(returncode: int = 0, stdout: str = '') -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], returncode, stdout, '')


class FakeDocker:
    """`docker` as disposable_db.run calls it. Listings can fail or show leftovers, per project."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.engine = 0
        self.failed_listing: str | None = None
        self.left: dict[str, str] = {}

    def run(self, argv: Sequence[str], _env: object, _timeout: float = 0, _stdin: str | None = None) -> subprocess.CompletedProcess[str]:
        self.calls.append(list(argv))
        if argv[:2] == ['docker', 'info']:
            return completed(self.engine)
        label = next((part.removeprefix('label=com.docker.compose.project=') for part in argv if part.startswith('label=com.docker.compose.project=')), None)
        kind = 'volume' if argv[1] == 'volume' else 'ps'
        if label is not None and self.failed_listing == kind:
            return completed(1)
        return completed(0, self.left.get(f'{kind}:{label}', ''))


class Lifecycle(unittest.TestCase):
    def setUp(self) -> None:
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.report = self.root / '.checks/x/qualification.json'
        self.report.parent.mkdir(parents=True)
        self.report.write_text('{"an": "earlier run"}')
        self.docker = FakeDocker()
        self.removed: list[str] = []
        self.snapshots = iter([['other a', 'other b'], ['other a', 'other b']])
        self.enterContext(mock.patch.object(disposable_db, 'run', self.docker.run))
        self.enterContext(mock.patch.object(disposable_db, 'remove_stack', lambda stack: self.removed.append(stack.target.project)))
        self.enterContext(mock.patch.object(disposable_db, 'other_resources', lambda _project: next(self.snapshots)))
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))

    def stack(self, project: str = PROJECT) -> disposable_db.Stack:
        return disposable_db.Stack(disposable_db.Target(project, 55400, 55401), self.root, self.root / 'compose.yaml')

    @contextlib.contextmanager
    def project(self, cases: Cases, **options: object) -> Iterator[disposable_db.DisposableRun]:
        with disposable_db.disposable_project(self.stack(), cases, report=self.report, **options) as owned:  # type: ignore[arg-type]  # fixture options
            yield owned

    def statuses(self, cases: Cases) -> dict[str, str]:
        return {record['id']: record['status'] for record in cases.records}

    def test_a_clean_run_records_both_cleanup_cases(self) -> None:
        cases = Cases()
        with self.project(cases):
            pass
        self.assertEqual(self.removed, [PROJECT])
        self.assertEqual(self.statuses(cases), {'cleanup removed the owned containers and volumes': 'passed',
                                                'other Docker resources are untouched': 'passed'})
        self.assertFalse(self.report.exists(), 'an earlier report is never left behind')

    def test_a_failed_listing_never_reads_as_nothing_left(self) -> None:
        for kind in ('volume', 'ps'):
            with self.subTest(kind):
                self.snapshots = iter([[], []])
                self.docker.failed_listing = kind
                cases = Cases()
                with self.assertRaisesRegex(Unavailable, 'could not list what cleanup left'), self.project(cases):
                    pass
                self.assertNotIn('cleanup removed the owned containers and volumes', self.statuses(cases))

    def test_leftovers_and_changed_neighbours_fail_their_cases(self) -> None:
        self.docker.left = {f'volume:{PROJECT}': f'{PROJECT}_db\n'}
        self.snapshots = iter([['other a'], ['other a restarted']])
        cases = Cases()
        with self.project(cases):
            pass
        self.assertEqual(self.statuses(cases), {'cleanup removed the owned containers and volumes': 'failed',
                                                'other Docker resources are untouched': 'failed'})

    def test_a_body_that_raises_still_removes_the_project_and_records_nothing(self) -> None:
        cases = Cases()
        with self.assertRaises(RuntimeError), self.project(cases):
            raise RuntimeError('a scenario crashed')
        self.assertEqual((self.removed, cases.records), ([PROJECT], []))

    def test_a_refused_target_reaches_no_docker_and_creates_nothing(self) -> None:
        cases = Cases()
        with self.assertRaises(Refused), disposable_db.disposable_project(self.stack('autobots-install'), cases, report=self.report):
            self.fail('the body ran')
        self.assertEqual((self.docker.calls, self.removed), ([], []))
        self.assertTrue(self.report.exists(), 'nothing at all happens to a refused target')

    def test_a_stopped_engine_is_reported_as_itself_before_any_check(self) -> None:
        self.docker.engine = 1
        prepared: list[bool] = []
        with self.assertRaisesRegex(Unavailable, 'Docker engine is not reachable'), \
                self.project(Cases(), prepare=lambda: prepared.append(True)):
            self.fail('the body ran')
        self.assertEqual((prepared, self.removed), ([], []))

    def test_a_refused_rendering_starts_nothing_and_removes_nothing(self) -> None:
        def refuse() -> None:
            raise Refused('service db publishes beyond loopback')

        with self.assertRaises(Refused), self.project(Cases(), prepare=refuse):
            self.fail('the body ran')
        self.assertEqual(self.removed, [])

    def test_a_second_owned_project_is_removed_first_and_checked_too(self) -> None:
        cases = Cases()
        with self.project(cases) as owned:
            owned.own(self.stack(RESTORED))
        self.assertEqual(self.removed, [RESTORED, PROJECT])
        self.assertEqual([record['id'] for record in cases.records].count('cleanup removed the owned containers and volumes'), 2)

    def test_only_a_disposable_target_can_be_owned(self) -> None:
        with self.assertRaises(Refused), self.project(Cases()) as owned:
            owned.own(self.stack('autobots-install'))
        self.assertEqual(self.removed, [PROJECT])

    def test_every_owned_project_is_tried_though_one_removal_fails(self) -> None:
        def remove(stack: disposable_db.Stack) -> None:
            self.removed.append(stack.target.project)
            if stack.target.project == RESTORED:
                raise Unavailable('the volume could not be removed')

        with mock.patch.object(disposable_db, 'remove_stack', remove), self.assertRaisesRegex(Unavailable, 'could not be removed'), \
                self.project(Cases()) as owned:
            owned.own(self.stack(RESTORED))
        self.assertEqual(self.removed, [RESTORED, PROJECT])


class AtomicReport(unittest.TestCase):
    def test_a_report_is_written_whole_with_its_trailing_newline(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'nested/qualification.json'
            records.write_report(path, {'schema_version': 'x/v1', 'cases': []})
            self.assertEqual(json.loads(path.read_text()), {'schema_version': 'x/v1', 'cases': []})
            self.assertTrue(path.read_text().endswith('}\n'))
            self.assertEqual(sorted(item.name for item in path.parent.iterdir()), ['qualification.json'])

    def test_a_report_that_cannot_be_written_leaves_the_last_one_and_no_partial_file(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'qualification.json'
            path.write_text('{"kept": true}\n')
            with self.assertRaises(TypeError):
                records.write_report(path, {'cases': [object()]})
            self.assertEqual(path.read_text(), '{"kept": true}\n')
            self.assertEqual(sorted(item.name for item in Path(folder).iterdir()), ['qualification.json'])


class EveryProfileQualifierUsesIt(unittest.TestCase):
    def test_no_profile_qualifier_lists_its_own_cleanup(self) -> None:
        """The copies diverged: only one checked its listing's exit code (SCRP-07). Now disposable_db.record_cleanup
        records that case, and nothing else does."""
        shared = (ROOT / 'scripts/disposable_db.py').read_text()
        self.assertEqual(shared.count("'cleanup removed the owned containers and volumes'"), 1)
        for name in ('supabase_stack', 'app_db', 'qualify_identity', 'qualify_persistent_apply', 'qualify_operations', 'qualify_backup',
                     'qualify_upgrade'):
            text = (ROOT / 'scripts' / f'{name}.py').read_text()
            with self.subTest(name):
                self.assertNotIn('cleanup removed the owned containers and volumes', text)
                self.assertNotIn('remove_stack(', text)
                self.assertNotIn("json.dumps({'schema_version'", text)


if __name__ == '__main__':
    unittest.main()
