"""The product's own entry point over a fake transport: real SDK and adapter, nothing leaves this Mac.

`worker.main` is what `python -m autobots.operations.worker` runs. Only its HTTP transport and catalog
fetch are replaced, and only from Python, so no setting can do this to a real worker. Anything that
tries to resolve a hostname other than loopback is refused and recorded for the parent to report. An IP
literal wouldn't pass through this guard, and nothing here uses one except the disposable stack's address.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import socket
import time
from pathlib import Path
from typing import Any

import httpx

REQUESTS = Path(os.environ['AUTOBOTS_TEST_REQUESTS'])
REJECTED_KEY = os.environ['AUTOBOTS_TEST_REJECTED_KEY']
LOOPBACK = {'127.0.0.1', '::1', 'localhost', b'127.0.0.1', b'::1', b'localhost', None}
real_getaddrinfo = socket.getaddrinfo


def record(entry: dict[str, Any]) -> None:
    with REQUESTS.open('a') as stream:
        stream.write(json.dumps(entry) + '\n')


def guarded_getaddrinfo(host: Any, *args: Any, **kwargs: Any) -> Any:
    if host not in LOOPBACK:
        record({'refused_host': str(host)})
        raise OSError('this check allows loopback only')
    return real_getaddrinfo(host, *args, **kwargs)


socket.getaddrinfo = guarded_getaddrinfo

from autobots.adapters.models.factory import default_sdk_client  # noqa: E402
from autobots.domain.models import PROFILES, ModelProfileId  # noqa: E402
from autobots.operations.worker import main  # noqa: E402

RETRY_AFTER = 3
CONTENT = '# Totals\n\nTotal: 42\n'
TASK = {'id': 'report', 'title': 'Write the report', 'criteria': ['c1'], 'expected_evidence': 'the published report'}
EVIDENCE = [{'kind': 'artifact', 'reference': 'outputs/report.md'}]
STEPS = (('propose_plan', {'tasks': [TASK]}),
         ('save_artifact', {'path': 'outputs/report.md', 'content': CONTENT}),
         ('publish_artifact', {'path': 'outputs/report.md', 'version': 1}),
         ('complete_task', {'task_id': 'report', 'evidence': EVIDENCE, 'summary': 'Wrote and published the report.'}))
PRICES = {ModelProfileId.DEEPSEEK_FLASH: ('0.000001', '0.000002'), ModelProfileId.TERRA: ('0.000001', '0.000005')}


def fingerprint(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()[:12]


def next_reply(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """Each step follows what the tools really returned, so a refused tool can't look finished."""
    names = {call['id']: call['function']['name'] for message in messages for call in message.get('tool_calls') or []}
    replies = {names.get(message.get('tool_call_id')): json.loads(message['content']) for message in messages if message['role'] == 'tool'}
    for name, reply in replies.items():
        if reply.get('outcome') != 'succeeded':
            return {'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': f'{name} did not succeed'}}
    for name, arguments in STEPS:
        if name not in replies:
            call = {'id': f'call-{len(messages)}', 'type': 'function', 'function': {'name': name, 'arguments': json.dumps(arguments)}}
            return {'finish_reason': 'tool_calls', 'message': {'role': 'assistant', 'content': None, 'tool_calls': [call]}}
    return {'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': 'The report is ready.'}}


def handle(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    key = request.headers.get('authorization', '').removeprefix('Bearer ')
    goal = next((str(message['content']) for message in body['messages'] if message['role'] == 'user'), '')
    record({'url': str(request.url), 'goal': goal.splitlines()[0], 'model': body.get('model'), 'models': body.get('models'),
            'provider': body.get('provider'), 'max_tokens': body.get('max_tokens'), 'key': fingerprint(key), 'at': time.monotonic(),
            'tools': sorted(item['function']['name'] for item in body.get('tools') or [])})
    if key == REJECTED_KEY:
        return httpx.Response(401, json={'error': {'code': 401, 'message': 'arranged rejection'}})
    if '[malformed]' in goal:
        # What the SDK refuses to parse though the provider answered: it may have been charged.
        return httpx.Response(200, json={'error': {'code': 500, 'message': 'arranged'}})
    if '[limited]' in goal:
        return httpx.Response(429, json={'error': {'code': 429, 'message': 'arranged'}}, headers={'Retry-After': str(RETRY_AFTER)})
    usage = {'prompt_tokens': 5, 'completion_tokens': 7, 'total_tokens': 12, 'cost': 0.0001, 'completion_tokens_details': {'reasoning_tokens': 3}}
    choice = {'index': 0, **next_reply(body['messages'])}
    if '[cutoff]' in goal:
        # Cut off mid tool call, as a real model could be: its arguments aren't valid JSON.
        cut = {'id': 'call-cut', 'type': 'function', 'function': {'name': 'save_artifact', 'arguments': '{"path": "outputs/rep'}}
        choice = {'index': 0, 'finish_reason': 'length', 'message': {'role': 'assistant', 'content': None, 'tool_calls': [cut]}}
    return httpx.Response(200, json={'id': 'fake', 'object': 'chat.completion', 'created': 1, 'model': body['model'],
                                     'system_fingerprint': 'fake', 'choices': [choice], 'usage': usage})


def client_factory(key: str) -> Any:
    return default_sdk_client(key, async_http=httpx.AsyncClient(transport=httpx.MockTransport(handle)))


async def fetch_catalog() -> dict[str, Any]:
    return {'data': [{'id': PROFILES[profile].wire_id, 'canonical_slug': PROFILES[profile].canonical_id,
                      'supported_parameters': ['max_tokens', 'tools', 'tool_choice'],
                      'pricing': {'prompt': prompt, 'completion': completion}}
                     for profile, (prompt, completion) in PRICES.items()]}


if __name__ == '__main__':
    asyncio.run(main(client_factory=client_factory, fetch_catalog=fetch_catalog))
