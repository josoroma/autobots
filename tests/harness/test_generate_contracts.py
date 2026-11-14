"""The generator as a pure function, including client operations no real route exercises yet."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import generate_contracts as generate  # noqa: E402

DOCUMENT = {
    'components': {'schemas': {
        'Status': {'enum': ['open', 'closed'], 'type': 'string'},
        'Item': {'type': 'object', 'additionalProperties': False, 'required': ['id', 'status'],
                 'properties': {'id': {'type': 'string', 'format': 'uuid'},
                                'status': {'$ref': '#/components/schemas/Status'},
                                'note': {'anyOf': [{'type': 'string'}, {'type': 'null'}]},
                                'tags': {'type': 'array', 'items': {'type': 'string'}},
                                'version': {'const': 1}}}}},
    'paths': {'/v1/items/{id}': {'get': {'operationId': 'get_item', 'responses': {'200': {'content': {
        'application/json': {'schema': {'$ref': '#/components/schemas/Item'}}}}}}}},
}


class Generation(unittest.TestCase):
    def test_types_and_parsers(self):
        text = generate.typescript_client(DOCUMENT)
        self.assertTrue(text.startswith(generate.HEADER))
        self.assertIn('export type Status = "open" | "closed";', text)
        self.assertIn('  id: string;', text)
        self.assertIn('  status: Status;', text)
        self.assertIn('  note?: string | null;', text)
        self.assertIn('  tags?: string[];', text)
        self.assertIn('  version?: 1;', text)
        self.assertIn('export function parseItem(value: unknown): Item {', text)

    def test_an_operation_validates_its_response(self):
        text = generate.typescript_client(DOCUMENT)
        self.assertIn('export async function get_item(options: ClientOptions, id: string, request?: RequestOptions): Promise<Item> {', text)
        # No ErrorResponse in this contract, so no envelope parser is referenced (R-02).
        self.assertIn(', undefined, request, undefined));', text)
        self.assertIn('return parseItem(await requestJson(options, "GET", `/v1/items/${encodeURIComponent(id)}`, undefined, request, undefined));', text)

    def test_a_route_without_a_response_model_is_refused(self):
        bad = {'responses': {'200': {'content': {}}}, 'operationId': 'x'}
        with self.assertRaises(ValueError):
            generate.operation('/v1/x', 'get', bad)

    def test_output_is_deterministic(self):
        self.assertEqual(generate.typescript_client(DOCUMENT), generate.typescript_client(json.loads(json.dumps(DOCUMENT))))

    def test_versioned_artifacts_exist_and_are_marked_generated(self):
        self.assertTrue((ROOT / generate.CLIENT).read_text().startswith(generate.HEADER))
        self.assertIn('RunSummary', json.loads((ROOT / generate.OPENAPI).read_text())['components']['schemas'])

    def test_a_map_is_typed_by_its_value_schema(self):
        # R-03: a role's profile is a ModelProfileId, not unknown.
        schema = {'type': 'object', 'additionalProperties': {'$ref': '#/components/schemas/ModelProfileId'}}
        self.assertEqual(generate.typescript_type(schema), 'Record<string, ModelProfileId>')
        self.assertEqual(generate.typescript_type({'type': 'object'}), 'Record<string, unknown>')

    def test_the_runtime_lists_every_keyword_the_contract_uses(self):
        known = generate.runtime_keywords(ROOT)
        self.assertTrue({'minItems', 'maxItems', 'additionalProperties', 'title'} <= known)
        document = json.loads((ROOT / 'contracts/generated/openapi.json').read_text())
        self.assertEqual(generate.unknown_keywords(document, known), [])

    def test_a_keyword_the_runtime_does_not_enforce_is_refused(self):
        document = {'components': {'schemas': {'Tags': {
            'type': 'object', 'properties': {'tags': {'type': 'array', 'uniqueItems': True,
                                                      'items': {'type': 'string', 'multipleOf': 2}}}}}}}
        self.assertEqual(generate.unknown_keywords(document, generate.runtime_keywords(ROOT)),
                         ['multipleOf', 'uniqueItems'])

    def test_a_missing_environment_is_a_prerequisite_error(self):
        with tempfile.TemporaryDirectory() as directory:
            scripts = Path(directory) / 'scripts'
            scripts.mkdir()
            for name in ('generate_contracts.py', 'harness_lib.py'):
                shutil.copy2(ROOT / 'scripts' / name, scripts / name)
            result = subprocess.run([sys.executable, str(scripts / 'generate_contracts.py'), 'check'],
                                    capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 2)
            self.assertIn('prepared Python environment', result.stderr)


if __name__ == '__main__':
    unittest.main()
