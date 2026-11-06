#!/usr/bin/env python3
"""US-7.2's live qualification: the connector against a throwaway private GitHub repository.

This writes to GitHub. It refuses without --live, and nothing in `verify.py` runs it. It also refuses a
classic token with broad scopes or a public repository, so a mistake can't reach anything that matters.
The token is read from a file and never printed or saved. It closes the issue it opened, with no model
and no database, as `tests/db/connector_check.py` covers the gateway. Exit 0 passed, 1 a case failed,
2 refused or a prerequisite is missing.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
from uuid import uuid4

OUT = Path('.checks/github-connector')


def unsafe_target(scopes: str | None, private: bool) -> str:
    """Why this target must not be written to. A fine-grained token reports no scopes at all."""
    if scopes and scopes.strip():
        return 'this token has broad classic scopes; use a fine-grained token limited to this repository'
    if not private:
        return 'this repository is public; use a throwaway private repository'
    return ''


async def qualify(repository: str, token: str) -> tuple[int, dict]:
    import httpx
    from autobots.adapters.github_issues import API_URL, REPOSITORY_VARIABLE, TOKEN_VARIABLE, github_issue_tool, marker
    from autobots.application.tool_gateway import NotDelivered, ToolContext, ToolScope
    from autobots.contracts.tools import CreateGithubIssueInput

    headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'}
    cases: list[dict] = []

    def check(name: str, expected: str, observed: object, passed: bool) -> None:
        cases.append({'id': name, 'expected': expected, 'observed': str(observed), 'passed': bool(passed)})
        print(f"{'PASS' if passed else 'FAIL'}: {name}: {observed}", flush=True)

    async with httpx.AsyncClient(base_url=API_URL, headers=headers, timeout=20, follow_redirects=False) as http:
        probe = await http.get(f'/repos/{repository}')
        if probe.status_code != 200:
            print(f'REFUSED, nothing written: the repository answered {probe.status_code}', file=sys.stderr)
            return 2, {}
        refusal = unsafe_target(probe.headers.get('x-oauth-scopes'), bool(probe.json().get('private')))
        if refusal:
            print(f'REFUSED, nothing written: {refusal}', file=sys.stderr)
            return 2, {}
        environ = {REPOSITORY_VARIABLE: repository, TOKEN_VARIABLE: token}
        tool = github_issue_tool(environ=environ)
        operation = f'qualification-{uuid4()}'
        context = ToolContext(None, ToolScope(uuid4(), uuid4(), 1, {}), operation)
        arguments = CreateGithubIssueInput(title='Autobots connector qualification', body='A throwaway issue from US-7.2. It closes itself.')
        number = None
        try:
            created = await tool.handler(arguments, context)
            number = created.number
            check('an authorized call creates an issue in the configured repository', f'an issue in {repository}', created.url, f'{repository}/issues/' in created.url)
            stored = (await http.get(f'/repos/{repository}/issues/{number}')).json()
            check('the issue carries its operation marker', 'the marker, in the body', marker(operation) in stored.get('body', ''), marker(operation) in stored.get('body', ''))
            assert tool.reconcile is not None
            started = time.monotonic()
            found = await tool.reconcile(arguments, context)
            check('a readback finds that same issue, as an uncertain outcome would need', str(number), f'{found.number}, after {time.monotonic() - started:.1f} s', found.number == number)
            found_again = await tool.reconcile(arguments, context)
            check('and a repeated readback creates nothing', str(number), found_again.number, found_again.number == number)
            issues = (await http.get(f'/repos/{repository}/issues', params={'state': 'all', 'per_page': 100})).json()
            marked = [issue['number'] for issue in issues if marker(operation) in (issue.get('body') or '')]
            check('so exactly one issue holds the marker', '1', len(marked), marked == [number])
            other = ToolContext(None, ToolScope(uuid4(), uuid4(), 1, {}), f'qualification-{uuid4()}')
            try:
                await tool.reconcile(arguments, other)
                check('a readback of an operation that never ran finds nothing', 'not delivered', 'found', False)
            except NotDelivered:
                check('a readback of an operation that never ran finds nothing', 'not delivered', 'not delivered', True)
            refused_tool = github_issue_tool(environ={REPOSITORY_VARIABLE: repository, TOKEN_VARIABLE: 'not-a-real-token'})
            try:
                await refused_tool.handler(arguments, context)
                check('a rejected credential creates nothing', 'github_refused_401', 'created', False)
            except Exception as error:
                check('a rejected credential creates nothing', 'github_refused_401', error, str(error) == 'github_refused_401')
        except Exception as error:
            # Only the type: a report is saved, and a message could hold anything.
            check('the qualification ran to its end', 'no error', type(error).__name__, False)
        finally:
            if number is not None:
                closed = await http.patch(f'/repos/{repository}/issues/{number}', json={'state': 'closed', 'state_reason': 'not_planned'})
                check('the qualification closes what it opened', '200', closed.status_code, closed.status_code == 200)
    failed = [case['id'] for case in cases if not case['passed']]
    report = {'schema_version': 'autobots.github-connector/v1', 'completed_at_utc': datetime.now(timezone.utc).isoformat(), 'evidence_class': 'live',
              'repository': repository, 'issue': number, 'cases': cases, 'failed': failed,
              'not_established': ['H1', 'product acceptance', 'a real lost acknowledgment, which only the fake transport arranges', 'the gateway, in tests/db/connector_check.py']}
    return (1 if failed else 0), report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', help='required: this writes to GitHub')
    parser.add_argument('--repository', required=True, help='owner/name of a throwaway private repository')
    parser.add_argument('--token-file', required=True, help='a file holding only a fine-grained token limited to that repository')
    arguments = parser.parse_args()
    if not arguments.live:
        print('REFUSED: this writes to GitHub, and needs --live', file=sys.stderr)
        return 2
    try:
        token = Path(arguments.token_file).read_text().strip()
    except OSError as error:
        print(f'ERROR: the token file could not be read: {type(error).__name__}', file=sys.stderr)
        return 2
    if not token:
        print('ERROR: the token file is empty', file=sys.stderr)
        return 2
    code, report = asyncio.run(qualify(arguments.repository, token))
    if report:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / 'qualification.json').write_text(json.dumps(report, indent=2))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
