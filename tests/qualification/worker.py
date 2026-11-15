"""The real product worker, with one change: the GitHub connector's destination is a recording fake.

Approval tasks exercise the real gateway, approvals and receipts, and can't touch a real repository.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import httpx
from autobots.adapters import tool_registry
from autobots.adapters.github_issues import REPOSITORY_VARIABLE, TOKEN_VARIABLE, github_issue_tool
from autobots.operations.worker import main

SINK = Path(os.environ['AUTOBOTS_TEST_SINK'])


def stored() -> list[dict]:
    return [json.loads(line) for line in SINK.read_text().splitlines()] if SINK.exists() else []


def handle(request: httpx.Request) -> httpx.Response:
    if request.method == 'GET':
        return httpx.Response(200, json=list(reversed(stored())))
    issue = json.loads(request.content)
    number = len(stored()) + 1
    issue.update(number=number, html_url=f'https://github.invalid/owner/fixture/issues/{number}')
    with SINK.open('a') as sink:
        sink.write(json.dumps(issue) + '\n')
    return httpx.Response(201, json=issue)


tool_registry.GITHUB_ISSUE = github_issue_tool(httpx.MockTransport(handle), {REPOSITORY_VARIABLE: 'owner/fixture', TOKEN_VARIABLE: 'arranged-not-a-token'})
asyncio.run(main())
