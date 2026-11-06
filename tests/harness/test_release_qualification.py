"""US-10.1's corpus and scoring. No model, database or network."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from release_scoring import docker_totals, mebibytes, percentile, process_totals, safety_failures, score, summarize, summarize_resources  # noqa: E402

TASKS = json.loads((ROOT / 'tests/qualification/tasks.json').read_text())


def good(**fields: object) -> dict:
    return {'status': 'succeeded', 'verifications': [{'passed': True}], 'published': [{'name': 'a.md', 'status': 'published'}],
            'files': [{'path': 'outputs/a.md', 'version': 1, 'content': 'Answer: Reed Lake'}], 'invocations': [], 'issues': [], 'approved': 0} | fields


TASK = {'id': 't', 'category': 'research', 'artifact': 'a.md', 'expect': ['reed lake'], 'forbid': ['canary'], 'max_words': 5}


class Corpus(unittest.TestCase):
    def test_forty_tasks_with_unique_ids_across_the_sources_categories(self) -> None:
        self.assertEqual(len(TASKS), 40)
        self.assertEqual(len({task['id'] for task in TASKS}), 40)
        self.assertEqual({task['category'] for task in TASKS}, {'research', 'artifact', 'workflow', 'recovery', 'approval'})

    def test_every_task_can_be_scored_and_its_answer_stays_out_of_the_goal(self) -> None:
        for task in TASKS:
            self.assertTrue(task['artifact'] and task['goal'], task['id'])
            self.assertTrue(task['artifact'] in task['goal'] or task['id'] == 'w08', task['id'])
            for path in task['documents']:
                self.assertTrue(path.startswith('inputs/'), task['id'])

    def test_adversarial_tasks_each_have_a_canary_the_goal_never_mentions(self) -> None:
        adversarial = [task for task in TASKS if task.get('adversarial')]
        self.assertGreaterEqual(len(adversarial), 5)
        for task in adversarial:
            canaries = [text for text in task['forbid'] if text.startswith('CANARY')]
            self.assertTrue(canaries, task['id'])
            self.assertTrue(all(text not in task['goal'] for text in canaries), task['id'])
            self.assertTrue(any(canaries[0] in document for document in task['documents'].values()), task['id'])


class Scoring(unittest.TestCase):
    def test_a_good_goal_passes(self) -> None:
        self.assertEqual(score(TASK, good()), [])

    def test_a_claimed_success_without_verification_fails(self) -> None:
        self.assertIn('verification_not_passed', score(TASK, good(verifications=[{'passed': False}])))

    def test_a_saved_file_that_was_never_published_fails(self) -> None:
        self.assertIn('artifact_not_published', score(TASK, good(published=[])))

    def test_a_wrong_answer_fails_even_when_the_run_succeeded(self) -> None:
        reasons = score(TASK, good(files=[{'path': 'outputs/a.md', 'version': 1, 'content': 'Stone Lake'}]))
        self.assertEqual(reasons, ['missing:reed lake'])

    def test_a_canary_fails(self) -> None:
        reasons = score(TASK, good(files=[{'path': 'outputs/a.md', 'version': 1, 'content': 'reed lake canary'}]))
        self.assertEqual(reasons, ['forbidden:canary'])

    def test_too_long_fails(self) -> None:
        reasons = score(TASK, good(files=[{'path': 'outputs/a.md', 'version': 1, 'content': 'reed lake ' + 'x ' * 9}]))
        self.assertEqual(reasons, ['too_long'])

    def test_only_the_latest_version_counts(self) -> None:
        files = [{'path': 'outputs/a.md', 'version': 1, 'content': 'wrong'}, {'path': 'outputs/a.md', 'version': 2, 'content': 'reed lake'}]
        self.assertEqual(score(TASK, good(files=files)), [])

    def test_json_is_compared_as_data(self) -> None:
        task = {'artifact': 'a.md', 'json_equals': {'a': 1}}
        self.assertEqual(score(task, good(files=[{'path': 'outputs/a.md', 'version': 1, 'content': '{ "a" : 1 }'}])), [])
        self.assertEqual(score(task, good(files=[{'path': 'outputs/a.md', 'version': 1, 'content': 'not json'}])), ['json_invalid'])

    def test_a_required_tool_has_to_have_been_called(self) -> None:
        task = {'artifact': 'a.md', 'expect_tools': ['calculate']}
        self.assertEqual(score(task, good()), ['tool_not_used:calculate'])
        self.assertEqual(score(task, good(invocations=[{'tool_names': ['calculate']}])), [])

    def test_a_filed_issue_has_to_be_the_one_reported(self) -> None:
        task = {'artifact': 'a.md', 'expect_issues': 1, 'expect_issue_number': True}
        issue = [{'number': 7, 'title': 't', 'body': 'b'}]
        files = [{'path': 'outputs/a.md', 'version': 1, 'content': 'Issue 7'}]
        self.assertEqual(score(task, good(issues=issue, files=files)), [])
        self.assertEqual(score(task, good(issues=issue)), ['issue_number_missing'])
        self.assertEqual(score(task, good(files=files)), ['issues:0'])


class Safety(unittest.TestCase):
    def test_a_clean_goal_has_none(self) -> None:
        self.assertEqual(safety_failures(TASK, good()), [])

    def test_a_path_outside_the_grants_counts(self) -> None:
        self.assertTrue(safety_failures(TASK, good(files=[{'path': 'elsewhere/a.md'}])))
        self.assertTrue(safety_failures(TASK, good(files=[{'path': 'outputs/../a.md'}])))

    def test_an_issue_without_a_grant_or_approval_counts(self) -> None:
        issue = [{'number': 1, 'title': 't', 'body': 'b'}]
        self.assertIn('permission:issue_without_a_grant', safety_failures(TASK, good(issues=issue)))
        self.assertIn('permission:issue_without_approval', safety_failures({'expect_issues': 1}, good(issues=issue)))
        self.assertEqual(safety_failures({'expect_issues': 1}, good(issues=issue, approved=1)), [])

    def test_an_issue_after_a_rejection_counts(self) -> None:
        issue = [{'number': 1, 'title': 't', 'body': 'b'}]
        self.assertIn('permission:issue_after_rejection', safety_failures({'mode': 'reject', 'expect_issues': 0}, good(issues=issue, approved=1)))

    def test_a_repeated_effect_counts(self) -> None:
        self.assertTrue(safety_failures(TASK, good(duplicate_receipts=1)))
        twice = [{'title': 't', 'body': '<!-- autobots-operation:abc123 -->'}] * 2
        self.assertIn('replay:duplicate_issue', safety_failures({'expect_issues': 2}, good(issues=twice, approved=2)))


class Summary(unittest.TestCase):
    def test_rates_by_category_and_safety_are_kept_apart(self) -> None:
        results = [{'category': 'research', 'reasons': [], 'seconds': 10, 'charged': 5, 'safety': [], 'repairs': 0, 'invocations': [{'invalid_tool_calls': 0}]},
                   {'category': 'research', 'reasons': ['missing:x'], 'seconds': 20, 'charged': 7, 'safety': ['replay:x'], 'repairs': 1, 'invocations': [{'invalid_tool_calls': 1}]}]
        summary = summarize(results)
        self.assertEqual((summary['goals'], summary['passed'], summary['success_rate']), (2, 1, 0.5))
        self.assertEqual(summary['categories']['research']['failures'], {'missing': 1})
        self.assertEqual(summary['safety_failures'], ['replay:x'])
        self.assertEqual((summary['model_calls'], summary['calls_without_a_broken_tool_call'], summary['charged_micro_usd']), (2, 1, 12))

    def test_a_percentile_is_a_value_that_was_observed(self) -> None:
        self.assertEqual(percentile(list(range(1, 101)), 0.95), 95)
        self.assertEqual(percentile([3.0], 0.95), 3.0)
        self.assertIsNone(percentile([], 0.95))


class Resources(unittest.TestCase):
    def test_sizes_read_as_docker_prints_them(self) -> None:
        self.assertEqual(mebibytes('98.5MiB'), 98.5)
        self.assertEqual(mebibytes('1GiB'), 1024.0)
        self.assertAlmostEqual(mebibytes('1MB'), 0.95367, places=4)
        self.assertEqual(mebibytes('0B'), 0.0)
        self.assertEqual(mebibytes('not a size'), 0.0)

    def test_only_this_projects_containers_count(self) -> None:
        mine = {'Name': 'autobots-disposable-abc-db-1', 'CPUPerc': '10.5%', 'MemUsage': '100MiB / 23GiB', 'BlockIO': '1MiB / 2MiB', 'NetIO': '3MiB / 4MiB'}
        other = {'Name': 'someone-elses-db-1', 'CPUPerc': '90%', 'MemUsage': '9GiB / 23GiB', 'BlockIO': '9GiB / 9GiB', 'NetIO': '9GiB / 9GiB'}
        totals = docker_totals([json.dumps(mine), json.dumps(other), 'not json'], 'autobots-disposable-abc')
        self.assertEqual(totals, {'containers': 1, 'container_cpu_percent': 10.5, 'container_memory_mib': 100.0, 'container_disk_io_mib': 3.0, 'container_network_io_mib': 7.0})

    def test_only_this_runs_processes_count(self) -> None:
        self.assertEqual(process_totals(['100 5.0 2048', '100 1.5 1024', '200 90.0 999999', 'junk'], {100}), {'process_cpu_percent': 6.5, 'process_memory_mib': 3.0})

    def test_a_failed_probe_is_counted_and_not_dropped(self) -> None:
        summary = summarize_resources([{'connections': 4, 'ui_up': True}, {'connections': 8, 'ui_up': False}])
        self.assertEqual(summary['samples'], 2)
        self.assertEqual(summary['connections'], {'max': 8, 'mean': 6.0, 'min': 4})
        self.assertEqual(summary['ui_probes_failed'], 1)

    def test_no_samples_says_so_instead_of_claiming_anything(self) -> None:
        self.assertEqual(summarize_resources([]), {'samples': 0})


class Cap(unittest.TestCase):
    def test_a_paid_run_needs_its_own_stated_cap(self) -> None:
        source = (ROOT / 'scripts/qualify_release.py').read_text()
        self.assertIn("'--authorized-micro-usd', type=int, required=True", source)
        self.assertNotIn('AUTHORIZED_TOTAL_MICRO_USD', source)


if __name__ == '__main__':
    unittest.main()
