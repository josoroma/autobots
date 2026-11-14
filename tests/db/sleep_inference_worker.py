"""The product's `worker.main` over a fake transport, slow enough that a real Mac sleep lands mid-run. US-11.10.

Only the HTTP transport and catalog are replaced, from Python, as in `product_inference_worker.py`, so
the worker, SDK, ledger, leases and checkpoints are all real. Each request is written down with both clocks
before its reply, so a call sent again after waking is visible. No request leaves this Mac.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Any

import httpx
from product_inference_worker import EVIDENCE, TASK, default_sdk_client, fetch_catalog, main, record

STEP_FILES = 16
CALL_SECONDS = float(os.environ.get('AUTOBOTS_TEST_CALL_SECONDS', '30'))
CONTENT = '# Totals\n\nTotal: 42\n'
STEPS = [('propose_plan', {'tasks': [TASK]})]
STEPS += [('save_artifact', {'path': f'outputs/step-{index}.md', 'content': f'Step {index}\n'}) for index in range(1, STEP_FILES + 1)]
STEPS += [('save_artifact', {'path': 'outputs/report.md', 'content': CONTENT}),
          ('publish_artifact', {'path': 'outputs/report.md', 'version': 1}),
          ('complete_task', {'task_id': 'report', 'evidence': EVIDENCE, 'summary': 'Wrote and published the report.'})]


def next_reply(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """Each step follows what the tools returned, so a refused or repeated one shows in the record."""
    results = [json.loads(message['content']) for message in messages if message['role'] == 'tool']
    for result in results:
        if result.get('outcome') != 'succeeded':
            return {'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': f"A step did not succeed: {result.get('code')}"}}
    if len(results) >= len(STEPS):
        return {'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': 'The report is ready.'}}
    name, arguments = STEPS[len(results)]
    call = {'id': f'call-{len(results)}', 'type': 'function', 'function': {'name': name, 'arguments': json.dumps(arguments)}}
    return {'finish_reason': 'tool_calls', 'message': {'role': 'assistant', 'content': None, 'tool_calls': [call]}}


async def handle(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    results = sum(message['role'] == 'tool' for message in body['messages'])
    started_wall, started_mono = time.time(), time.monotonic()
    record({'event': 'call_started', 'step': results, 'wall': started_wall, 'mono': started_mono})
    await asyncio.sleep(CALL_SECONDS)
    record({'event': 'call_replied', 'step': results, 'wall': time.time(), 'mono': time.monotonic(), 'started_wall': started_wall})
    usage = {'prompt_tokens': 5, 'completion_tokens': 7, 'total_tokens': 12, 'cost': 0.0001, 'completion_tokens_details': {'reasoning_tokens': 3}}
    choice = {'index': 0, **next_reply(body['messages'])}
    return httpx.Response(200, json={'id': 'fake', 'object': 'chat.completion', 'created': 1, 'model': body['model'],
                                     'system_fingerprint': 'fake', 'choices': [choice], 'usage': usage})


def client_factory(key: str) -> Any:
    return default_sdk_client(key, async_http=httpx.AsyncClient(transport=httpx.MockTransport(handle)))


if __name__ == '__main__':
    asyncio.run(main(client_factory=client_factory, fetch_catalog=fetch_catalog))
