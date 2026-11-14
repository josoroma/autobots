"""Preflight, rendering and vendoring guards. The real stack runs only in the `db` profile."""
from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import supabase_stack as stack  # noqa: E402

PROJECT = 'autobots-disposable-abc'


class Preflight(unittest.TestCase):
    def setUp(self):
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.addCleanup(self.listener.close)
        self.listener.bind(('127.0.0.1', 0))
        self.listener.listen()
        self.port = self.listener.getsockname()[1]

    def test_a_held_port_is_reported_and_its_owner_survives(self):
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/supabase_stack.py'), 'preflight', '--gateway-port', str(self.port),
                                 '--db-port', str(self.port)], capture_output=True, text=True, timeout=30,
                                env={**os.environ, 'PATH': os.environ['PATH']})
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(f'port {self.port} is held by', result.stdout)
        self.assertIn('nothing was stopped', result.stdout)
        probe = socket.create_connection(('127.0.0.1', self.port), timeout=2)  # The holder still accepts.
        probe.close()

    def test_a_wildcard_listener_is_a_conflict(self):
        wildcard = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.addCleanup(wildcard.close)
        wildcard.bind(('0.0.0.0', 0))
        wildcard.listen()
        self.assertTrue(stack.preflight({'gateway': wildcard.getsockname()[1]}))

    def test_a_free_port_passes(self):
        free = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        free.bind(('127.0.0.1', 0))
        port = free.getsockname()[1]
        free.close()
        self.assertEqual(stack.preflight({'gateway': port}), [])


class Rendering(unittest.TestCase):
    def rendered(self) -> dict:
        labels = {stack.TARGET_LABEL: 'disposable', stack.RUN_LABEL: PROJECT}
        service = {'image': 'x@sha256:0', 'pull_policy': 'never', 'labels': labels}
        services = {name: dict(service) for name in stack.REQUIRED_SERVICES}
        services['db'] = {**service, 'ports': [{'host_ip': '127.0.0.1', 'published': '55400', 'target': 5432}],
                          'volumes': [{'type': 'volume', 'source': 'data'},
                                      {'type': 'bind', 'read_only': True, 'source': str(ROOT / stack.UPSTREAM / 'volumes/db/jwt.sql')}]}
        services['api-gw'] = {**service, 'ports': [{'host_ip': '127.0.0.1', 'published': '55401', 'target': 8000}]}
        services['studio'] = {**service, 'environment': {'OPENAI_API_KEY': '', 'NEXT_TELEMETRY_DISABLED': '1'}}
        return {'services': services, 'volumes': {'data': {'name': f'{PROJECT}_data', 'labels': labels}}}

    def test_a_clean_rendering_passes(self):
        self.assertEqual(stack.rendered_refusals(self.rendered(), PROJECT, ROOT), [])

    def test_each_unsafe_rendering_is_refused(self):
        def wildcard(d): d['services']['db']['ports'][0].pop('host_ip')
        def extra_port(d): d['services']['db']['ports'].append({'host_ip': '0.0.0.0', 'published': '54322', 'target': 5432})
        def pooler(d): d['services']['supavisor'] = dict(d['services']['rest'])
        def raw_studio(d): d['services']['studio']['ports'] = [{'host_ip': '127.0.0.1', 'published': '54323', 'target': 3000}]
        def ai(d): d['services']['studio']['environment']['OPENAI_API_KEY'] = 'value'
        def telemetry(d): d['services']['studio']['environment'].pop('NEXT_TELEMETRY_DISABLED')
        def provider_key(d): d['services']['auth']['environment'] = {'OPENROUTER_API_KEY': 'x'}
        def fixed_name(d): d['services']['db']['container_name'] = 'supabase-db'
        def floating(d): d['services']['db']['image'] = 'supabase/postgres:latest'
        def writable(d): d['services']['db']['volumes'][1]['read_only'] = False
        def foreign(d): d['services']['db']['volumes'][1]['source'] = '/etc'
        def host_network(d): d['services']['db']['network_mode'] = 'host'
        def external(d): d['volumes']['data']['external'] = True
        def missing(d): del d['services']['meta']
        for change in (wildcard, extra_port, pooler, raw_studio, ai, telemetry, provider_key, fixed_name, floating, writable,
                       foreign, host_network, external, missing):
            with self.subTest(change=change.__name__):
                data = self.rendered()
                change(data)
                self.assertTrue(stack.rendered_refusals(data, PROJECT, ROOT))


class Vendoring(unittest.TestCase):
    def test_vendored_release_matches_its_recorded_hashes(self):
        record = json.loads((ROOT / stack.UPSTREAM / 'UPSTREAM.json').read_text())
        self.assertEqual(record['tag'], 'self-hosted/v0.8.3')
        self.assertEqual(record['commit'], 'bc27d2661edd09a5d0b8d76ce33da6d4071a756e')
        self.assertTrue(record['files'])
        for path, expected in record['files'].items():
            with self.subTest(path=path):
                self.assertEqual(hashlib.sha256((ROOT / stack.UPSTREAM / path).read_bytes()).hexdigest(), expected)

    def test_overlay_pins_every_required_image_by_digest(self):
        text = (ROOT / 'infra/supabase/compose.overlay.yaml').read_text()
        self.assertEqual(len(re.findall(r'image: \S+@sha256:[0-9a-f]{64}', text)), len(stack.REQUIRED_SERVICES))
        self.assertEqual(text.count('pull_policy: never'), len(stack.REQUIRED_SERVICES))

    def test_generated_values_replace_every_example_secret(self):
        generated = stack.generated_values(55400, 55401)
        examples = dict(line.split('=', 1) for line in (ROOT / stack.UPSTREAM / 'env.example').read_text().splitlines()
                        if '=' in line and not line.lstrip().startswith('#'))
        for name in stack.SECRET_NAMES:
            with self.subTest(name=name):
                self.assertTrue(generated[name])
                self.assertNotEqual(generated[name], examples.get(name))
                self.assertNotIn(name, stack.example_defaults(ROOT))
        self.assertEqual(generated['DISABLE_SIGNUP'], 'true')
        self.assertNotIn('COMPOSE_FILE', stack.example_defaults(ROOT))
        self.assertNotEqual(stack.generated_values(55400, 55401)['JWT_SECRET'], generated['JWT_SECRET'])

    def test_no_persistent_start_exists(self):
        source = (ROOT / 'scripts/supabase_stack.py').read_text()
        self.assertIn("choices=('preflight', 'qualify')", source)


if __name__ == '__main__':
    unittest.main()
