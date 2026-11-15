"""The generator as a pure function, including client operations no real route exercises yet."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

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


ITEM = {'application/json': {'schema': {'$ref': '#/components/schemas/Item'}}}
BFF = [{'in': 'header', 'name': name, 'required': False, 'schema': {'anyOf': [{'type': 'string'}, {'type': 'null'}]}}
       for name in ('x-autobots-internal', 'x-autobots-workspace', 'authorization')]
PARAMETERS = {
    'components': DOCUMENT['components'],
    'paths': {
        '/v1/items': {
            'get': {'operationId': 'listItems', 'responses': {'200': {'content': ITEM}}, 'parameters': [
                {'in': 'query', 'name': 'status', 'required': False, 'schema': {'$ref': '#/components/schemas/Status'}},
                {'in': 'query', 'name': 'q', 'required': False,
                 'schema': {'anyOf': [{'type': 'string'}, {'type': 'null'}]}},
                {'in': 'query', 'name': 'limit', 'schema': {'type': 'integer', 'default': 10}}, *BFF]},
            'post': {'operationId': 'createItem', 'responses': {'201': {'content': ITEM}},
                     'requestBody': {'content': ITEM}, 'parameters': [
                         {'in': 'header', 'name': 'Idempotency-Key', 'required': True,
                          'schema': {'type': 'string', 'minLength': 1}}, *BFF]},
        },
        '/v1/items/search': {'get': {'operationId': 'searchItems', 'responses': {'200': {'content': ITEM}},
                                     'parameters': [{'in': 'query', 'name': 'q', 'required': True,
                                                     'schema': {'type': 'string'}}]}},
    },
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
                                                      'items': {'type': 'string', 'multipleOf': 2}},
                                             'mail': {'type': 'string', 'format': 'email'},
                                             'day': {'type': 'string', 'format': 'date'}}}}}}
        self.assertEqual(generate.unknown_keywords(document, generate.runtime_keywords(ROOT)),
                         ['format:email', 'multipleOf', 'uniqueItems'])

    def test_a_query_is_a_typed_argument_written_in_the_contracts_order(self):
        # R-48: the browser reads through the generated functions, filters included.
        text = generate.typescript_client(PARAMETERS)
        self.assertIn('export type ListItemsQuery = {\n  status?: Status | undefined;\n  q?: string | null | undefined;\n'
                      '  limit?: number | undefined;\n};\n', text)
        self.assertIn('export async function listItems(options: ClientOptions, query?: ListItemsQuery, '
                      'request?: RequestOptions): Promise<Item> {\n  return parseItem(await requestJson(options, "GET", '
                      '`/v1/items${queryString(query, ["status", "q", "limit"])}`, undefined, request, undefined));\n}\n', text)

    def test_a_required_query_must_be_passed(self):
        text = generate.typescript_client(PARAMETERS)
        self.assertIn('export type SearchItemsQuery = {\n  q: string;\n};\n', text)
        self.assertIn('export async function searchItems(options: ClientOptions, query: SearchItemsQuery, '
                      'request?: RequestOptions): Promise<Item> {', text)

    def test_a_declared_header_is_a_typed_argument_and_the_bffs_are_not(self):
        # The BFF sets the bearer, the internal token and the workspace from the session.
        text = generate.typescript_client(PARAMETERS)
        self.assertIn('export type CreateItemHeaders = {\n  "Idempotency-Key": string;\n};\n', text)
        self.assertIn('export async function createItem(options: ClientOptions, body: Item, headers: CreateItemHeaders, '
                      'request?: RequestOptions): Promise<Item> {\n  return parseItem(await requestJson(options, "POST", '
                      '`/v1/items`, body, withHeaders(request, headers), undefined));\n}\n', text)
        for name in generate.BFF_HEADERS:
            self.assertNotIn(name, text.lower())

    def test_an_optional_query_before_a_required_argument_is_still_an_argument(self):
        document = json.loads(json.dumps(PARAMETERS))
        create = document['paths']['/v1/items']['post']
        create['parameters'].append({'in': 'query', 'name': 'dry_run', 'required': False, 'schema': {'type': 'boolean'}})
        text = generate.typescript_client(document)
        self.assertIn('export async function createItem(options: ClientOptions, query: CreateItemQuery | undefined, '
                      'body: Item, headers: CreateItemHeaders, request?: RequestOptions): Promise<Item> {', text)

    def test_a_parameter_type_that_takes_a_schemas_name_is_refused(self):
        document = json.loads(json.dumps(PARAMETERS))
        document['components']['schemas']['ListItemsQuery'] = {'type': 'string'}
        with self.assertRaises(ValueError):
            generate.typescript_client(document)

    def test_two_operation_ids_that_normalize_alike_are_refused(self):
        document = json.loads(json.dumps(PARAMETERS))
        document['paths']['/v1/other'] = {'get': {'operationId': 'list-items', 'responses': {'200': {'content': ITEM}}}}
        with self.assertRaisesRegex(ValueError, 'listItems is already emitted'):
            generate.typescript_client(document)

    def test_an_operation_named_like_a_parser_is_refused(self):
        document = json.loads(json.dumps(PARAMETERS))
        document['paths']['/v1/other'] = {'get': {'operationId': 'parseItem', 'responses': {'200': {'content': ITEM}}}}
        with self.assertRaisesRegex(ValueError, 'parseItem is already emitted'):
            generate.typescript_client(document)

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
