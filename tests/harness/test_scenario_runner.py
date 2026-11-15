"""A qualifier's scenarios run in their stated order, and one that crashes fails visibly without hiding the rest
(refactor plan R-65, SCRP-05). Refused and Unavailable keep their exit codes."""
from __future__ import annotations

import contextlib
import io
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import qualify_backup  # noqa: E402
import qualify_operations  # noqa: E402
import qualify_upgrade  # noqa: E402
from qualification.errors import Refused, Unavailable  # noqa: E402
from qualification.records import Cases  # noqa: E402
from qualification.scenarios import run_scenarios  # noqa: E402


def first(log: list[str], cases: Cases) -> None:
    log.append('first')
    cases.check('first case', 'yes', 'yes', True)


def crashes(log: list[str], _cases: Cases) -> None:
    log.append('crashes')
    raise KeyError('ready')


def after_it(log: list[str], _cases: Cases) -> None:
    log.append('after it')


def unavailable(_log: list[str], _cases: Cases) -> None:
    raise Unavailable('a fixture worker could not start')


def refused(_log: list[str], _cases: Cases) -> None:
    raise Refused('not a disposable target')


class Runner(unittest.TestCase):
    def setUp(self) -> None:
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))

    def test_scenarios_run_in_order_with_the_shared_context(self) -> None:
        log: list[str] = []
        cases = Cases()
        run_scenarios(log, cases, (first, after_it))
        self.assertEqual((log, cases.status), (['first', 'after it'], 'passed'))

    def test_a_crash_is_one_failed_case_and_every_later_scenario_is_shown_not_run(self) -> None:
        log: list[str] = []
        cases = Cases()
        run_scenarios(log, cases, (first, crashes, after_it, first))
        self.assertEqual(log, ['first', 'crashes'])
        self.assertEqual([(record['id'], record['status']) for record in cases.records],
                         [('first case', 'passed'), ('crashes ran', 'failed'), ('after it ran', 'failed'), ('first ran', 'failed')])
        self.assertIn("KeyError: 'ready'", cases.records[1]['observed'])
        self.assertEqual(cases.records[2]['observed'], 'not run, because crashes raised')
        self.assertEqual(cases.status, 'failed')

    def test_refused_and_unavailable_keep_their_exit_codes(self) -> None:
        for scenario, error in ((unavailable, Unavailable), (refused, Refused)):
            with self.subTest(error.__name__):
                cases = Cases()
                with self.assertRaises(error):
                    run_scenarios([], cases, (scenario, first))
                self.assertEqual(cases.records, [])

    def test_an_interrupt_is_never_swallowed(self) -> None:
        def interrupted(_log: list[str], _cases: Cases) -> None:
            raise KeyboardInterrupt

        with self.assertRaises(KeyboardInterrupt):
            run_scenarios([], Cases(), (interrupted,))


class Qualifiers(unittest.TestCase):
    """The operations profile's qualifiers state their order in one tuple of named scenarios."""

    def test_each_names_its_scenarios_in_order(self) -> None:
        for module, expected in ((qualify_operations, ('infrastructure', 'readiness', 'product_worker', 'drain', 'cut_short_drain',
                                                       'readiness_failures', 'shutdown', 'recovery', 'retention', 'process_logs')),
                                 (qualify_backup, ('source_content', 'refused_backups', 'backup_taken', 'refused_restores', 'restore',
                                                   'held_restore', 'released_restore', 'source_untouched')),
                                 (qualify_upgrade, ('prior_schema', 'prior_state', 'new_code_on_old_schema', 'forward_paths', 'upgrade',
                                                    'prior_checkpoint_continues', 'blocked_run_refused', 'unqualified_adapter'))):
            with self.subTest(module.__name__):
                self.assertEqual(tuple(scenario.__name__ for scenario in module.SCENARIOS), expected)

    def test_no_qualify_function_is_long_again(self) -> None:
        import ast
        for module in (qualify_operations, qualify_backup, qualify_upgrade):
            tree = ast.parse(Path(str(module.__file__)).read_text())
            sizes = {node.name: node.end_lineno - node.lineno + 1 for node in tree.body if isinstance(node, ast.FunctionDef) and node.end_lineno}
            with self.subTest(module.__name__):
                self.assertLess(sizes['qualify'], 40)
                self.assertLess(max(sizes.values()), 80)


if __name__ == '__main__':
    unittest.main()
