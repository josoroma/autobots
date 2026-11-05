"""Target guards, with a fake `docker` that records calls. Real containers run only in the `db` profile."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import disposable_db as guard  # noqa: E402

PROJECT = 'autobots-disposable-abc'


class Identity(unittest.TestCase):
    def refused(self, target: guard.Target, env: dict | None = None) -> list[str]:
        return guard.identity_refusals(target, env or {})

    def test_a_marked_target_is_accepted(self):
        self.assertEqual(self.refused(guard.Target(PROJECT, 55400, 55401, (f'{PROJECT}_db',))), [])

    def test_persistent_and_foreign_identities_are_refused(self):
        for target in (guard.Target('autobots'), guard.Target('supabase_mentor'), guard.Target(''),
                       guard.Target('autobots-disposable-'), guard.Target('autobots-disposable-X;rm'),
                       guard.Target('x-autobots-disposable-abc'), guard.Target(PROJECT, 54322),
                       guard.Target(PROJECT, 54321), guard.Target(PROJECT, 5432), guard.Target(PROJECT, 55400, 54322),
                       guard.Target(PROJECT, 8080), guard.Target(PROJECT, volumes=('autobots_db-data',)),
                       guard.Target(PROJECT, volumes=('supabase_db_mentor',))):
            with self.subTest(target=target):
                self.assertTrue(self.refused(target))

    def test_environment_cannot_redirect_a_target(self):
        target = guard.Target(PROJECT, 55400)
        for env in ({'DATABASE_URL': 'postgres://u:private@127.0.0.1:54322/postgres'},
                    {'SUPABASE_DB_URL': 'postgres://u:private@127.0.0.1:54322/postgres'},
                    {'POSTGRES_URL': 'not a url'}, {'PGPORT': '54322'}, {'PGHOST': 'db.example'},
                    {'DATABASE_URL': 'postgres://u:private@prod.example:55400/postgres'}):
            with self.subTest(env=list(env)):
                reasons = self.refused(target, env)
                self.assertTrue(reasons)
                self.assertNotIn('private', ' '.join(reasons))
        self.assertEqual(self.refused(target, {'DATABASE_URL': 'postgres://u@127.0.0.1:55400/postgres'}), [])


class Rendered(unittest.TestCase):
    def rendered(self) -> dict:
        labels = {guard.TARGET_LABEL: 'disposable', guard.RUN_LABEL: PROJECT}
        return {'name': PROJECT,
                'services': {'db': {'image': 'x@sha256:0', 'pull_policy': 'never', 'labels': labels,
                                    'ports': [{'host_ip': '127.0.0.1', 'published': '55400', 'target': 5432}],
                                    'volumes': [{'type': 'volume', 'source': 'db'}]}},
                'volumes': {'db': {'name': f'{PROJECT}_db', 'labels': labels}}}

    def test_clean_rendering_passes(self):
        self.assertEqual(guard.rendered_refusals(self.rendered(), PROJECT), [])

    def test_each_unsafe_rendering_is_refused(self):
        def wildcard(data): data['services']['db']['ports'][0]['host_ip'] = '0.0.0.0'
        def persistent_port(data): data['services']['db']['ports'][0]['published'] = '54322'
        def external(data): data['volumes']['db']['external'] = True
        def other_volume(data): data['volumes']['db']['name'] = 'autobots_db-data'
        def unmarked(data): data['volumes']['db']['labels'] = {}
        def bind(data): data['services']['db']['volumes'][0]['type'] = 'bind'
        def floating(data): data['services']['db']['image'] = 'postgres:latest'
        def pulls(data): data['services']['db']['pull_policy'] = 'always'
        def unlabeled(data): data['services']['db']['labels'] = {}
        def renamed(data): data['name'] = 'autobots'
        def host_network(data): data['services']['db']['network_mode'] = 'host'
        for change in (wildcard, persistent_port, external, other_volume, unmarked, bind, floating, pulls, unlabeled, renamed, host_network):
            with self.subTest(change=change.__name__):
                data = self.rendered()
                change(data)
                self.assertTrue(guard.rendered_refusals(data, PROJECT))


class Commands(unittest.TestCase):
    """The real command line, with a fake `docker` on PATH, so a refusal is seen to precede any call."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.calls = Path(temporary.name) / 'calls'
        docker = Path(temporary.name) / 'docker'
        docker.write_text(f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{self.calls}"\nexit 1\n')
        docker.chmod(0o755)
        self.path = f"{temporary.name}{os.pathsep}{os.environ['PATH']}"

    def run_script(self, *arguments: str, **extra: str) -> subprocess.CompletedProcess:
        env = {'PATH': self.path, 'HOME': os.environ.get('HOME', ''), **extra}
        return subprocess.run([sys.executable, str(ROOT / 'scripts/disposable_db.py'), *arguments], env=env,
                              capture_output=True, text=True, timeout=20)

    def test_persistent_targets_are_refused_before_any_docker_call(self):
        for arguments in (('reset', '--project', 'autobots', '--db-port', '54322'),
                          ('cleanup', '--project', 'autobots'),
                          ('migrate', '--project', 'supabase_mentor', '--db-port', '54322'),
                          ('cleanup', '--project', PROJECT, '--volume', 'autobots_db-data'),
                          ('reset', '--project', PROJECT, '--db-port', '54322')):
            with self.subTest(arguments=arguments):
                result = self.run_script(*arguments)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn('REFUSED before any change', result.stderr)
                self.assertFalse(self.calls.exists(), 'docker was called')

    def test_environment_pointing_at_persistent_is_refused_before_any_call(self):
        result = self.run_script('reset', '--project', PROJECT, DATABASE_URL='postgres://u:private@127.0.0.1:54322/p')
        self.assertEqual(result.returncode, 1)
        self.assertNotIn('private', result.stderr)
        self.assertFalse(self.calls.exists())

    def test_docker_failure_is_a_prerequisite_error_on_a_valid_target(self):
        self.assertEqual(self.run_script('reset', '--project', PROJECT).returncode, 2)

    def test_missing_docker_is_a_prerequisite_error(self):
        env = {'PATH': '/nonexistent', 'HOME': os.environ.get('HOME', '')}
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/disposable_db.py'), 'qualify'], env=env,
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 2)
        self.assertIn('docker is not installed', result.stderr)


class Fixtures(unittest.TestCase):
    def test_seeds_hold_no_ddl_and_no_jobs(self):
        text = (ROOT / 'tests/db/seeds/fixtures.sql').read_text().lower()
        for word in ('create table', 'alter table', 'drop ', 'password', 'job'):
            self.assertNotIn(word, text)
        self.assertEqual(text.count('on conflict'), text.count('insert into'))

    def test_compose_pins_every_image_locally(self):
        text = (ROOT / guard.COMPOSE).read_text()
        self.assertEqual(text.count('pull_policy: never'), text.count('image:'))


if __name__ == '__main__':
    unittest.main()
