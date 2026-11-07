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
import re
import os
import socket
import time
from pathlib import Path
import sys
from urllib.parse import urlparse
from typing import Any

import httpx

REQUESTS = Path(os.environ['AUTOBOTS_TEST_REQUESTS'])
REJECTED_KEY = os.environ['AUTOBOTS_TEST_REJECTED_KEY']
LOOPBACK = {'127.0.0.1', '::1', 'localhost', b'127.0.0.1', b'::1', b'localhost', None}
real_getaddrinfo = socket.getaddrinfo


def record(entry: dict[str, Any]) -> None:
    with REQUESTS.open('a') as stream:
        stream.write(json.dumps(entry) + '\n')


# Set while the control below runs, so a real attempt to leave can't be mistaken for it.
CONTROL = [False]


def guarded_getaddrinfo(host: Any, *args: Any, **kwargs: Any) -> Any:
    if host not in LOOPBACK:
        record({'refused_host': host.decode() if isinstance(host, bytes) else str(host), 'control': CONTROL[0]})
        raise OSError('this check allows loopback only')
    return real_getaddrinfo(host, *args, **kwargs)


socket.getaddrinfo = guarded_getaddrinfo


def _port(name: str) -> int | None:
    value = os.environ.get(name, '')
    return urlparse(value).port if value else None


# What this process may connect to by itself: the stack, and nothing else. libpq connects in C, so
# the database never comes through here, and this sees what Python opens, such as an HTTP client.
ALLOWED_PORTS = {port for port in (_port('AUTOBOTS_DATABASE_URL'), _port('AUTOBOTS_STORAGE_BASE')) if port}


def guarded_connect(event: str, args: tuple) -> None:
    if event != 'socket.connect':
        return
    address = args[1]
    if isinstance(address, tuple) and address[0] in LOOPBACK and address[1] in ALLOWED_PORTS:
        return
    if isinstance(address, tuple):
        record({'refused_connect': f'{address[0]}:{address[1]}', 'control': CONTROL[0]})
        raise OSError('this check allows the stack only')


sys.addaudithook(guarded_connect)

from autobots.adapters.models.factory import default_sdk_client  # noqa: E402
from autobots.application.compaction import SUMMARY_MARKER  # noqa: E402
from autobots.domain.models import PROFILES, ModelProfileId  # noqa: E402
from autobots.operations.reasoning_trial import continuation_result  # noqa: E402
from autobots.operations.worker import main  # noqa: E402

RETRY_AFTER = 3
# Reaches an exception's message, and must never reach a log.
ARRANGED_REPLY_TEXT = 'arranged-reply-text-7f3a'
REASONING_MARKER = 'ARRANGED-REASONING-MARKER'
RETURNED: dict[str, dict[str, Any]] = {}
CONTENT = '# Totals\n\nTotal: 42\n'
TASK = {'id': 'report', 'title': 'Write the report', 'criteria': ['c1'], 'expected_evidence': 'the published report'}
EVIDENCE = [{'kind': 'artifact', 'reference': 'outputs/report.md'}]
STEPS = (('propose_plan', {'tasks': [TASK]}),
         ('save_artifact', {'path': 'outputs/report.md', 'content': CONTENT}),
         ('publish_artifact', {'path': 'outputs/report.md', 'version': 1}),
         ('complete_task', {'task_id': 'report', 'evidence': EVIDENCE, 'summary': 'Wrote and published the report.'}))
# Long enough in tool arguments to pass the compaction budget, which counts them.
LONG = 'x' * 6_000
COMPACT_STEPS = (STEPS[0], *(('save_artifact', {'path': f'outputs/part-{n}.md', 'content': LONG}) for n in range(6)), STEPS[1], STEPS[2], STEPS[3])
SUMMARY = 'ARRANGED-SUMMARY: six parts were saved.'
PART = {'id': 'k', 'title': 'Part', 'criteria': ['c1'], 'expected_evidence': 'a file'}
PART_EVIDENCE = [{'kind': 'artifact', 'reference': 'outputs/child-1/part.md'}]
CHILD_STEPS = (('propose_plan', {'tasks': [PART]}),
               ('save_artifact', {'path': 'outputs/child-1/part.md', 'content': 'part'}),
               ('publish_artifact', {'path': 'outputs/child-1/part.md', 'version': 1}),
               ('complete_task', {'task_id': 'k', 'evidence': PART_EVIDENCE, 'summary': 'done part'}))
PARENT_PLAN = ('propose_plan', {'tasks': [{'id': 'p', 'title': 'Delegate', 'criteria': ['c1'], 'expected_evidence': 'a result'}]})
POSITION: dict[str, int] = {}
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


def tool_call(name: str, arguments: dict[str, Any], number: int) -> dict[str, Any]:
    call = {'id': f'call-{number}', 'type': 'function', 'function': {'name': name, 'arguments': json.dumps(arguments)}}
    return {'finish_reason': 'tool_calls', 'message': {'role': 'assistant', 'content': None, 'tool_calls': [call]}}


def script_for(name: str, steps: tuple[tuple[str, dict[str, Any]], ...], final: str) -> dict[str, Any]:
    """Compaction takes earlier replies out of the model's view, so the position lives here."""
    number = POSITION.get(name, 0)
    POSITION[name] = number + 1
    if number < len(steps):
        return tool_call(*steps[number], number + 1000 * len(name))
    return {'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': final}}


def text_of(messages: list[dict[str, Any]]) -> str:
    return '\n'.join(str(message.get('content') or '') for message in messages)


def handle(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    key = request.headers.get('authorization', '').removeprefix('Bearer ')
    goal = next((str(message['content']) for message in body['messages'] if message['role'] == 'user'), '')
    everything = text_of(body['messages'])
    if '[compact]' in everything and SUMMARY_MARKER not in goal:
        goal = 'Write the report [compact]'
    if SUMMARY_MARKER in goal:
        goal = 'Summary of [compact-summary]'
    elif '[child-part]' in everything and '[parent]' not in goal:
        goal = 'Do the part [child-part]'
    if '[parent]' in everything and '[child-part]' not in goal:
        goal = 'Lead [parent]'
    record({'url': str(request.url), 'goal': goal.splitlines()[0], 'model': body.get('model'), 'models': body.get('models'),
            'provider': body.get('provider'), 'max_tokens': body.get('max_tokens'), 'key': fingerprint(key), 'at': time.monotonic(),
            'tools': sorted(item['function']['name'] for item in body.get('tools') or []),
            'fields': sorted(body), 'reasoning_field': body.get('reasoning')})
    if key == REJECTED_KEY:
        return httpx.Response(401, json={'error': {'code': 401, 'message': 'arranged rejection'}})
    if '[malformed]' in goal:
        # What the SDK refuses to parse though the provider answered: it may have been charged.
        return httpx.Response(200, json={'error': {'code': 500, 'message': ARRANGED_REPLY_TEXT}})
    if '[dropped]' in goal:
        raise httpx.RemoteProtocolError(ARRANGED_REPLY_TEXT)
    if '[limited]' in goal:
        return httpx.Response(429, json={'error': {'code': 429, 'message': 'arranged'}}, headers={'Retry-After': str(RETRY_AFTER)})
    usage = {'prompt_tokens': 5, 'completion_tokens': 7, 'total_tokens': 12, 'cost': 0.0001, 'completion_tokens_details': {'reasoning_tokens': 3}}
    choice = {'index': 0, **next_reply(body['messages'])}
    if '[compact-summary]' in goal:
        choice = {'index': 0, 'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': SUMMARY}}
    elif '[compact]' in goal:
        record({'goal': goal, 'saw_summary': SUMMARY in everything})
        choice = {'index': 0, **script_for('compact', COMPACT_STEPS, 'The report is ready.')}
    elif '[child-part]' in goal:
        choice = {'index': 0, **script_for('child', CHILD_STEPS, 'The part is done.')}
    elif '[parent]' in goal:
        expert = re.search(r'expert=([0-9a-f-]{36})', everything)
        assign = ('assign_specialist', {'expert_id': expert.group(1) if expert else '', 'goal': 'Do the part [child-part]'})
        choice = {'index': 0, **script_for('parent', (PARENT_PLAN, assign), 'The part came back.')}
    if '[reasoning]' in goal:
        for returned in RETURNED.values():
            comparison = continuation_result(returned, body['messages'])
            record({'goal': goal.splitlines()[0], 'reasoning': comparison.outcome, 'differences': list(comparison.differences)})
        if choice['finish_reason'] == 'tool_calls':
            number = len(body['messages'])
            choice['message'] = {**choice['message'], 'reasoning': f'{REASONING_MARKER} text {number}',
                                 'reasoning_details': [{'type': 'reasoning.encrypted', 'data': f'{REASONING_MARKER} second-first {number}', 'format': 'openai-responses-v1', 'index': 1},
                                                       {'type': 'reasoning.text', 'text': f'{REASONING_MARKER} first-second {number}', 'format': 'openai-responses-v1', 'index': 0}]}
            RETURNED[choice['message']['tool_calls'][0]['id']] = choice['message']
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


async def leave_on_purpose() -> None:
    """A client built outside the factory, as a stray dispatch would be. The guard has to see it."""
    CONTROL[0] = True
    try:
        # By name, then past the name lookup: a local model server, and a literal address.
        for url in ('https://openrouter.ai/api/v1/models', 'http://127.0.0.1:9/v1/chat/completions', 'http://198.51.100.1/v1/chat/completions'):
            try:
                async with httpx.AsyncClient() as stray:
                    await stray.get(url)
            except (OSError, httpx.HTTPError):
                pass
    finally:
        CONTROL[0] = False


if __name__ == '__main__':
    asyncio.run(leave_on_purpose())
    asyncio.run(main(client_factory=client_factory, fetch_catalog=fetch_catalog))
