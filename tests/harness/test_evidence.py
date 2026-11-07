"""Fixtures for completion validation, built from the real templates. They qualify no real work item."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import evidence  # noqa: E402

TEMPLATES = ROOT / 'docs/engineering/templates'
ITEM, EVIDENCE = 'US-9.9', 'run-1'


class Templates(unittest.TestCase):
    def test_manifest_template_is_visibly_unexecuted(self):
        data = json.loads((TEMPLATES / 'evidence-manifest.json').read_text())
        self.assertIs(data['template'], True)
        self.assertEqual(data['schema_version'], evidence.SCHEMA)
        self.assertEqual({check['status'] for check in data['checks']}, {'not_run'})
        self.assertEqual({check['observed'] for check in data['checks']}, {None})
        self.assertEqual(data['review']['outcome'], 'pending')
        self.assertEqual(set(data['fingerprint']), set(evidence.fingerprints(ROOT)))
        self.assertIn('expected', data['checks'][0])
        self.assertIn('findings', data['review'])
        self.assertIn('path', data['runbook'])

    def test_record_template_has_every_stage_and_no_results(self):
        content = (TEMPLATES / 'work-item.md').read_text()
        self.assertIn('Status: TEMPLATE', content)
        for section in evidence.SECTIONS:
            self.assertIn(f'## {section}\n', content)
        for field in ('{{work_item_id}}', '{{SPECS_id_and_PRD_requirement_ids}}', '{{source_manifest_sha256}}',
                      '{{findings}}', '{{runbook_link}}'):
            self.assertIn(field, content)

    def test_summary_and_runbook_templates_say_so(self):
        self.assertIn('TEMPLATE, not executed evidence', (TEMPLATES / 'evidence-summary.md').read_text())
        self.assertIn('TEMPLATE, not an exercised procedure', (TEMPLATES / 'runbook.md').read_text())
        summary = (TEMPLATES / 'evidence-summary.md').read_text()
        for field in ('{{expected}}', '{{observed}}', '{{status}}'):
            self.assertIn(field, summary)


class Completion(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        (self.root / 'scripts').mkdir()
        (self.root / 'scripts/code.py').write_text('x = 1\n')
        self.record = self.root / 'docs/engineering/work-items' / f'{ITEM}.md'
        self.directory = self.root / 'docs/engineering/evidence' / ITEM
        self.manifest_path = self.directory / f'{EVIDENCE}.json'
        self.runbook = self.root / 'docs/engineering/runbooks/fixture.md'
        for path in (self.record, self.manifest_path, self.runbook):
            path.parent.mkdir(parents=True, exist_ok=True)
        self.runbook.write_text('# Runbook: fixture\n\nExercised.\n')
        self.record.write_text(self.filled_record())
        (self.directory / 'summary.md').write_text(f'# {ITEM} evidence summary — {EVIDENCE}\n\nFixture.\n')
        self.write_manifest(self.valid_manifest())

    def filled_record(self) -> str:
        content = (TEMPLATES / 'work-item.md').read_text()
        content = re.sub(r'\{\{evidence_id\}\}', EVIDENCE, content)
        content = re.sub(r'\{\{[^}]+\}\}', 'filled', content)
        return content.replace('Status: TEMPLATE', 'Status: IN PROGRESS')

    def valid_manifest(self) -> dict:
        """The real template, filled in only as far as validation needs."""
        data = json.loads((TEMPLATES / 'evidence-manifest.json').read_text())
        check = data['checks'][0]
        check.update(id='check-1', requirement_ids=['SP-1'], target_ref='fixture', expected='exits 0', observed='exit 0',
                     status='passed', exit_code=0, command_argv=['tool'], started_at_utc='2026-11-05T00:00:00Z',
                     finished_at_utc='2026-11-05T00:00:01Z', source={'kind': 'manual'}, exercises_runbook=True,
                     artifacts=[self.artifact()])
        data.update(template=False, work_item_id=ITEM, evidence_id=EVIDENCE, requirement_ids=['SP-1'],
                    fingerprint=evidence.fingerprints(self.root), tool_versions={'python': '3.12.16'})
        data['review'].update(author_id='author', reviewer_id='reviewer', outcome='approved',
                              reviewed_fingerprint=evidence.fingerprints(self.root)['source_manifest_sha256'])
        data['runbook'] = {'path': 'docs/engineering/runbooks/fixture.md', 'exercised_evidence_ids': [EVIDENCE],
                           'revision_sha256': hashlib.sha256(self.runbook.read_bytes()).hexdigest()}
        data['raw_artifacts'] = {'local_root': f'.checks/{ITEM}/{EVIDENCE}/', 'availability': 'available',
                                 'retention': 'through acceptance'}
        return data

    def artifact(self) -> dict:
        log = self.root / f'.checks/{ITEM}/{EVIDENCE}/log.txt'
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text('observed output\n')
        return {'path': f'.checks/{ITEM}/{EVIDENCE}/log.txt', 'sha256': hashlib.sha256(log.read_bytes()).hexdigest()}

    def write_manifest(self, data: dict) -> None:
        self.manifest_path.write_text(json.dumps(data))

    def errors(self) -> list[str]:
        return evidence.completion_errors(self.root, ITEM)

    def rejected(self, needle: str, change) -> None:
        data = copy.deepcopy(self.valid_manifest())
        change(data)
        self.write_manifest(data)
        errors = self.errors()
        self.assertTrue(any(needle in error for error in errors), f'{needle!r} not in {errors}')

    def test_valid_record_passes_and_only_then_completes(self):
        self.assertEqual(self.errors(), [])
        self.assertEqual(evidence.main(['complete', ITEM, '--project-root', str(self.root)]), 0)
        self.assertIn('Status: COMPLETE', self.record.read_text())

    def test_template_values_are_rejected(self):
        self.rejected('is a template', lambda d: d.update(template=True))
        self.rejected('template placeholders', lambda d: d['checks'][0].update(expected='{{x}}'))

    def test_the_real_templates_cannot_complete(self):
        shutil.copy2(TEMPLATES / 'work-item.md', self.record)
        shutil.copy2(TEMPLATES / 'evidence-manifest.json', self.directory / 'x.json')
        before = self.record.read_text()
        self.assertEqual(evidence.main(['complete', ITEM, '--project-root', str(self.root)]), 1)
        self.assertEqual(self.record.read_text(), before)
        self.record.write_text(before.replace('{{evidence_id}}', 'x'))
        errors = self.errors()
        for needle in ('still a template', 'is a template', 'not_run', 'no reviewer', 'not approved'):
            self.assertTrue(any(needle in error for error in errors), f'{needle!r} not in {errors}')

    def test_stale_fingerprint_is_rejected_and_named(self):
        (self.root / 'scripts/code.py').write_text('x = 2\n')
        errors = self.errors()
        self.assertTrue(any('source_manifest_sha256 is stale' in error for error in errors), errors)
        self.assertTrue(any('verifier_sha256 is stale' in error for error in errors), errors)
        self.assertTrue(any('reviewed fingerprint' in error for error in errors), errors)

    def test_untracked_input_is_stale_but_later_records_are_not(self):
        self.record.write_text(self.record.read_text() + '\nA later note.\n')
        (self.root / 'SPECS.md').write_text('# Status changed\n')
        self.assertEqual(self.errors(), [])
        (self.root / 'scripts/untracked.py').write_text('y = 1\n')
        self.assertTrue(self.errors())

    def test_lockfile_and_config_changes_are_each_detected(self):
        for path, key in (('pnpm-lock.yaml', 'lockfiles_sha256'), ('.claude/settings.json', 'nonsecret_config_sha256'),
                          ('contracts/generated/a.json', 'generated_contracts_sha256')):
            with self.subTest(path=path):
                target = self.root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text('{}')
                self.assertTrue(any(key in error for error in self.errors()))
                self.write_manifest(self.valid_manifest())

    def test_skipped_and_unrun_checks_are_rejected(self):
        for status in ('skipped', 'not_run'):
            with self.subTest(status=status):
                self.rejected(f'was {status}', lambda d, s=status: d['checks'][0].update(
                    status=s, exit_code=None, observed=None, finished_at_utc=None))

    def test_failed_and_errored_checks_stay_visible(self):
        self.rejected('check-1: failed', lambda d: d['checks'][0].update(status='failed', exit_code=1))
        self.rejected('check-1: error', lambda d: d['checks'][0].update(status='error', exit_code=None))

    def test_inconsistent_status_and_result_are_rejected(self):
        self.rejected('passed contradicts', lambda d: d['checks'][0].update(exit_code=1))
        self.rejected('passed contradicts', lambda d: d['checks'][0].update(exit_code=None))
        self.rejected('failed contradicts', lambda d: d['checks'][0].update(status='failed', exit_code=0))
        self.rejected('contradicts a recorded', lambda d: d['checks'][0].update(status='skipped'))
        self.rejected('no observed', lambda d: d['checks'][0].update(observed=None))
        self.rejected('no command', lambda d: d['checks'][0].update(command_argv=[]))

    def test_requirement_without_passing_coverage_is_rejected(self):
        self.rejected('no passing check covers SP-2', lambda d: d.update(requirement_ids=['SP-1', 'SP-2']))

    def test_empty_suite_is_rejected(self):
        self.rejected('an empty suite', lambda d: d.update(checks=[]))

    def test_review_is_required_and_independent(self):
        self.rejected('no reviewer', lambda d: d['review'].update(reviewer_id=None))
        self.rejected('self-review', lambda d: d['review'].update(reviewer_id='author'))
        self.rejected('not approved', lambda d: d['review'].update(outcome='pending'))
        self.rejected('reviewed fingerprint', lambda d: d['review'].update(reviewed_fingerprint='0' * 64))

    def test_unresolved_blocking_finding_is_rejected(self):
        finding = {'id': 'F-1', 'severity': 'blocking', 'disposition': 'open'}
        self.rejected('F-1 is not resolved', lambda d: d['review'].update(findings=[finding]))
        data = self.valid_manifest()
        data['review']['findings'] = [{**finding, 'disposition': 'resolved'},
                                      {'id': 'F-2', 'severity': 'nonblocking', 'disposition': 'open'}]
        self.write_manifest(data)
        self.assertEqual(self.errors(), [])

    def test_runbook_must_be_current_and_exercised(self):
        self.rejected('was not exercised', lambda d: d['runbook'].update(exercised_evidence_ids=[]))
        self.rejected('not an existing file', lambda d: d['runbook'].update(path='../../outside.md'))
        self.rejected('does not match', lambda d: d['runbook'].update(revision_sha256='0' * 64))
        data = self.valid_manifest()
        self.runbook.write_text('TEMPLATE, not an exercised procedure\n')
        data['runbook']['revision_sha256'] = hashlib.sha256(self.runbook.read_bytes()).hexdigest()
        self.write_manifest(data)
        self.assertTrue(any('still a template' in error for error in self.errors()))

    def test_a_fake_model_cannot_satisfy_a_live_gate(self):
        self.rejected('fake model', lambda d: d['checks'][0].update(verification_class='live', model_transport='mock'))
        self.rejected('fake model', lambda d: d['checks'][0].update(verification_class='mock', model_transport='openrouter_live'))
        self.rejected('unknown verification', lambda d: d['checks'][0].update(verification_class='vibes'))

    def test_raw_artifacts_are_checked(self):
        missing = {'path': f'.checks/{ITEM}/{EVIDENCE}/gone.txt', 'sha256': '0' * 64}
        self.rejected('not_created contradicts', lambda d: d['raw_artifacts'].update(availability='not_created'))
        self.rejected('is recorded available and is missing', lambda d: d['checks'][0].update(artifacts=[missing]))
        self.rejected('needs a path', lambda d: d['checks'][0].update(artifacts=[{'path': '/etc/hosts', 'sha256': '0' * 64}]))
        self.rejected('retention', lambda d: d['raw_artifacts'].update(retention=None))
        wrong = {'path': f'.checks/{ITEM}/{EVIDENCE}/log.txt', 'sha256': '0' * 64}
        self.rejected('does not match its recorded hash', lambda d: d['checks'][0].update(artifacts=[wrong]))
        self.rejected('needs its artifacts available', lambda d: d['raw_artifacts'].update(availability='deleted'))

    def test_a_hand_written_result_is_not_evidence(self):
        self.rejected('names no run', lambda d: d['checks'][0].pop('source'))
        self.rejected('retains no artifact', lambda d: d['checks'][0].update(artifacts=[]))
        self.rejected('no valid verifier report', lambda d: d['checks'][0].update(
            source={'kind': 'report', 'profile': 'harness', 'check': 'tests'}))
        self.rejected('no live run record', lambda d: d['checks'][0].update(
            verification_class='live', model_transport='openrouter_live'))

    def test_exercise_needs_a_passing_check_that_says_so(self):
        self.rejected('no passing check with a retained artifact', lambda d: d['checks'][0].update(exercises_runbook=False))

    def test_tool_provider_keys_are_rejected(self):
        for key in ('tvly-fixture0123456789', 'jina_fixture0123456789', 'ghp_fixture0123456789abcdefgh',
                    'github_pat_fixture_0123456789abcdef'):
            self.rejected('recognizable secret', lambda d, key=key: d['checks'][0].update(observed=key))

    def test_recognizable_secrets_are_rejected(self):
        self.rejected('recognizable secret', lambda d: d['checks'][0].update(observed='sk-or-v1-abcdefghijkl'))
        self.write_manifest(self.valid_manifest())
        (self.directory / 'summary.md').write_text(f'{EVIDENCE} OPENROUTER_API_KEY=abc\n')
        self.assertTrue(any('summary: contains' in error for error in self.errors()))

    def test_missing_pieces_are_all_listed(self):
        self.write_manifest({'schema_version': evidence.SCHEMA})
        (self.directory / 'summary.md').unlink()
        errors = self.errors()
        for needle in ('is a template', 'source_manifest_sha256', 'no checks', 'review: missing',
                       'runbook: missing', 'raw_artifacts: missing', 'summary: is missing'):
            self.assertTrue(any(needle in error for error in errors), f'{needle!r} not in {errors}')

    def test_hand_written_complete_status_is_still_rejected(self):
        self.record.write_text(self.record.read_text().replace('Status: IN PROGRESS', 'Status: COMPLETE'))
        self.write_manifest({**self.valid_manifest(), 'template': True})
        self.assertEqual(evidence.main(['validate', ITEM, '--project-root', str(self.root)]), 1)

    def plan(self) -> dict:
        manual = {'id': 'exercise', 'requirement_ids': ['SP-1'], 'verification_class': 'disposable', 'model_transport': 'none',
                  'command_argv': ['sh', 'exercise.sh'], 'target_ref': 'fixture', 'expected': 'exit 0', 'observed': 'exit 0',
                  'status': 'passed', 'started_at_utc': 'a', 'finished_at_utc': 'b', 'exit_code': 0,
                  'exercises_runbook': True, 'artifacts': [self.artifact()]}
        return {'profiles': ['harness'], 'requirement_ids': ['SP-1'], 'default_requirements': ['SP-1'], 'requirements': {},
                'runbook': 'docs/engineering/runbooks/fixture.md', 'retention': 'through acceptance', 'manual_checks': [manual],
                'review': {'author_id': 'author', 'reviewer_id': 'reviewer', 'outcome': 'approved', 'findings': [],
                           'reviewed_fingerprint': evidence.fingerprints(self.root)['source_manifest_sha256']}}

    def write_report(self, checks: list[dict], **overrides: object) -> None:
        directory = self.root / '.checks/harness'
        directory.mkdir(parents=True, exist_ok=True)
        (directory / 'latest.json').write_text(json.dumps({
            'schema_version': evidence.REPORT_SCHEMA, 'template': False, 'profile': 'harness', 'status': 'passed',
            'inputs_unchanged_during_check': True, 'input_manifest': evidence.input_manifest(self.root),
            'python_version': '3.12.16', 'completed_at_utc': '2026-11-05T00:00:00Z', 'checks': checks, **overrides}))

    def passed_record(self, **extra: object) -> dict:
        return {'id': 'tests', 'class': 'mock', 'model_transport': 'none', 'status': 'passed', 'exit_code': 0,
                'command_argv': ['tool'], 'started_at_utc': 'a', 'finished_at_utc': 'b', **extra}

    def test_record_copies_checks_from_a_report_and_validate_accepts_it(self):
        self.write_report([{'id': 'project_configuration', 'class': 'static', 'model_transport': 'none', 'status': 'passed'},
                           self.passed_record(tests_executed=4, tests_skipped=0)])
        self.assertEqual(evidence.record_manifest(self.root, ITEM, EVIDENCE, self.plan()), [])
        self.assertEqual(self.errors(), [])
        data = json.loads(self.manifest_path.read_text())
        self.assertEqual(data['checks'][1]['observed'], 'status passed, exit 0, 4 tests executed, 0 skipped')
        self.assertEqual(data['checks'][1]['verification_class'], 'mock')
        self.assertEqual(data['checks'][0]['exit_code'], 0)
        self.assertEqual(data['reports']['harness']['status'], 'passed')
        self.assertEqual(data['runbook']['exercised_evidence_ids'], [EVIDENCE])

    def test_record_without_an_exercise_does_not_claim_one(self):
        self.write_report([self.passed_record()])
        plan = self.plan()
        plan['manual_checks'] = []
        self.assertEqual(evidence.record_manifest(self.root, ITEM, EVIDENCE, plan), [])
        self.assertTrue(any('was not exercised' in error for error in self.errors()))

    def test_record_keeps_failures_and_unrun_checks_visible_to_validate(self):
        self.write_report([self.passed_record(status='failed', exit_code=1), {'id': 'build', 'status': 'not_run'}], status='failed')
        self.assertEqual(evidence.record_manifest(self.root, ITEM, EVIDENCE, self.plan()), [])
        errors = self.errors()
        self.assertTrue(any('harness.tests: failed' in error for error in errors), errors)
        self.assertTrue(any('harness.build: was not_run' in error for error in errors), errors)

    def test_record_refuses_a_stale_missing_or_unstable_report(self):
        self.assertTrue(evidence.record_manifest(self.root, ITEM, EVIDENCE, self.plan()))
        self.write_report([self.passed_record()], inputs_unchanged_during_check=False)
        self.assertTrue(any('changed during' in p for p in evidence.record_manifest(self.root, ITEM, EVIDENCE, self.plan())))
        self.write_report([self.passed_record()], template=True)
        self.assertTrue(evidence.record_manifest(self.root, ITEM, EVIDENCE, self.plan()))
        self.write_report([self.passed_record()])
        (self.root / 'scripts/code.py').write_text('x = 2\n')
        problems = evidence.record_manifest(self.root, ITEM, EVIDENCE, self.plan())
        self.assertTrue(any('stale' in problem for problem in problems), problems)

    def test_a_cited_report_is_rechecked_by_validate(self):
        self.write_report([self.passed_record()])
        self.assertEqual(evidence.record_manifest(self.root, ITEM, EVIDENCE, self.plan()), [])
        self.assertEqual(self.errors(), [])
        data = json.loads(self.manifest_path.read_text())
        data['checks'][0]['verification_class'] = 'disposable'
        self.write_manifest(data)
        self.assertTrue(any('differs from the harness report' in error for error in self.errors()))
        data['checks'][0]['verification_class'] = 'mock'
        self.write_manifest(data)
        self.write_report([self.passed_record(status='failed', exit_code=1)], status='failed')
        self.assertTrue(any('differs from the harness report' in error for error in self.errors()))
        self.write_report([self.passed_record()], status='failed')
        self.assertTrue(any('report did not pass' in error for error in self.errors()), 'a manifest trimmed of a failing check')
        (self.root / '.checks/harness/latest.json').unlink()
        self.assertTrue(any('no valid verifier report' in error for error in self.errors()))

    def test_command_line_exit_codes(self):
        script = str(ROOT / 'scripts/evidence.py')
        def run(*arguments):
            return subprocess.run([sys.executable, script, *arguments, '--project-root', str(self.root)],
                                  capture_output=True, text=True, timeout=10)
        self.assertEqual(run('validate', ITEM).returncode, 0)
        self.assertEqual(run('validate', 'US-0.0').returncode, 1)
        self.assertEqual(run('validate').returncode, 2)
        self.assertEqual(run('validate', '../escape').returncode, 2)
        self.assertEqual(run('fingerprints').returncode, 0)


if __name__ == '__main__':
    unittest.main()
