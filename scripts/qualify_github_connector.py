#!/usr/bin/env python3
"""Live GitHub qualifications. Nothing in `verify.py` runs this, and each suite refuses without --live.

`issue` (US-7.2, the default) qualifies the issue connector against a throwaway private repository. It reads
its token from a file and closes the one issue it opens.

`studio` (US-15.16) qualifies the four read tools, labels on `create_github_issue` version 2, and
`github_open_pull_request` on the configured repository. Before any request it needs two things:
GITHUB_REPOSITORY and GITHUB_TOKEN in the given env file, of which only those two are read, into this process;
and the owner's recorded authorization naming that repository and a request cap. Every request is counted
before it is sent, and none is sent past the cap. It runs in two phases. `review` reads only and saves the pull
request's approval detail for the owner. `apply` runs once with the review the owner approved, and closes or
deletes what it made.

Both suites refuse a classic token with broad scopes or a public repository, never print or save the token, and
use no model and no database. Exit 0 passed, 1 a case failed, 2 refused or a prerequisite is missing.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

OUT = Path('.checks/github-connector')
STUDIO_OUT = Path('.checks/github-studio')
STUDIO_STORY = 'US-15.16'
# Requests kept back so a pass stopped by the cap can still close and delete what it made.
CLEANUP_RESERVE = 3


def unsafe_target(scopes: str | None, private: bool) -> str:
    """Why this target must not be written to. A fine-grained token reports no scopes at all."""
    if scopes and scopes.strip():
        return 'this token has broad classic scopes; use a fine-grained token limited to this repository'
    if not private:
        return 'this repository is public; use a throwaway private repository'
    return ''


async def qualify(repository: str, token: str) -> tuple[int, dict]:
    import httpx
    from autobots.adapters.github_issues import (
        API_URL,
        REPOSITORY_VARIABLE,
        TOKEN_VARIABLE,
        github_issue_tool,
        marker,
    )
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
            except Exception as error:  # noqa: BLE001 - a refused credential is judged by its typed code
                check('a rejected credential creates nothing', 'github_refused_401', error, str(error) == 'github_refused_401')
        except Exception as error:  # noqa: BLE001 - only the type is reported, since a message could hold anything
            # Only the type: a report is saved, and a message could hold anything.
            check('the qualification ran to its end', 'no error', type(error).__name__, False)
        finally:
            if number is not None:
                closed = await http.patch(f'/repos/{repository}/issues/{number}', json={'state': 'closed', 'state_reason': 'not_planned'})
                check('the qualification closes what it opened', '200', closed.status_code, closed.status_code == 200)
    failed = [case['id'] for case in cases if not case['passed']]
    report = {'schema_version': 'autobots.github-connector/v1', 'completed_at_utc': datetime.now(UTC).isoformat(), 'evidence_class': 'live',
              'repository': repository, 'issue': number, 'cases': cases, 'failed': failed,
              'not_established': ['H1', 'product acceptance', 'a real lost acknowledgment, which only the fake transport arranges', 'the gateway, in tests/db/connector_check.py']}
    return (1 if failed else 0), report


# --- US-15.16: the studio suite ---------------------------------------------------------------------------


class Refused(Exception):
    """A prerequisite is missing, so nothing is sent."""


class CapReached(Exception):
    """The next request would pass the authorized cap, so it isn't sent."""


def studio_environment(env_file: Path) -> tuple[str, str]:
    """Only GITHUB_REPOSITORY and GITHUB_TOKEN, from the owner's env file. Neither is printed."""
    from autobots.application.credentials.precedence import parse_dotenv

    try:
        values = parse_dotenv(env_file.read_text())
    except OSError as error:
        raise Refused(f'the env file could not be read: {type(error).__name__}') from None
    repository = values.get('GITHUB_REPOSITORY', '').strip()
    token = values.get('GITHUB_TOKEN', '').strip()
    if not repository or not token:
        raise Refused('GITHUB_REPOSITORY and GITHUB_TOKEN must both be set in the env file')
    return repository, token


def studio_authorization(path: Path, repository: str) -> dict:
    """The owner's recorded authorization for this story and this repository, with a positive cap."""
    try:
        recorded = json.loads(path.read_text())
    except (OSError, ValueError) as error:
        raise Refused(f'no readable recorded authorization: {type(error).__name__}') from None
    if not isinstance(recorded, dict) or recorded.get('story') != STUDIO_STORY:
        raise Refused(f'the authorization is not for {STUDIO_STORY}')
    if recorded.get('repository') != repository:
        raise Refused('the authorization does not name the configured repository')
    cap = recorded.get('max_requests')
    if not isinstance(cap, int) or isinstance(cap, bool) or cap < 1:
        raise Refused('the authorization records no request cap')
    if recorded.get('model_calls', 0) != 0:
        raise Refused('this suite makes no model calls, so an authorization for them does not fit')
    return recorded


def counting_transport(cap: int, ledger: dict) -> Any:
    """Counts each request in the ledger before it is sent, and refuses one past the cap.

    The ledger carries over between phases and reruns, so the cap covers every live request the
    authorization paid for. A reserve is kept so a pass stopped by the cap can still clean up."""
    import httpx

    class Counting(httpx.AsyncBaseTransport):
        def __init__(self) -> None:
            self.inner = httpx.AsyncHTTPTransport()
            self.cleaning = False

        @property
        def used(self) -> int:
            return int(ledger['used'])

        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            limit = cap if self.cleaning else cap - CLEANUP_RESERVE
            if self.used >= limit:
                raise CapReached(f'{self.used} of {cap} requests used')
            ledger['used'] = self.used + 1
            # Method and path only: a query can hold search text, and no header is kept.
            ledger['requests'].append(f'{request.method} {request.url.path}')
            return await self.inner.handle_async_request(request)

        async def aclose(self) -> None:
            # Each tool closes its own client, and so this transport, after every call. The pool stays open.
            return None

    return Counting()


class ApprovedReview:
    """Stands in for the approvals table: the review the owner approved, for the connector's own lookup."""

    def __init__(self, detail: dict) -> None:
        self.detail = detail
        self.returned_to_review = False

    async def execute(self, sql: str, _params: Any = None) -> Any:
        connection = self

        class Cursor:
            async def fetchone(self) -> Any:
                if sql.lstrip().startswith('select review_detail'):
                    return (connection.detail,)
                return None

        if 'set status = \'pending\'' in sql:
            self.returned_to_review = True
        return Cursor()


def _shape(model: Any) -> dict:
    """Field names and counts, not values: the record keeps what came back, not what it said."""
    data = model.model_dump()
    return {name: (f'{len(value)} items' if isinstance(value, list) else type(value).__name__) for name, value in data.items()}


def _write_redacted(path: Path, report: dict, token: str) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(report, indent=2)
    if token in text:
        return False
    path.write_text(text)
    return True


def _headers(token: str) -> dict:
    return {'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'}


async def _probe(http: Any, repository: str) -> dict:
    """The repository must answer, be private, and the token must have no classic scopes."""
    probe = await http.get(f'/repos/{repository}')
    if probe.status_code != 200:
        raise Refused(f'the repository answered {probe.status_code}')
    refusal = unsafe_target(probe.headers.get('x-oauth-scopes'), bool(probe.json().get('private')))
    if refusal:
        raise Refused(refusal)
    return probe.json()


async def studio_review(repository: str, token: str, authorization: dict, ledger: dict) -> tuple[int, dict]:
    import httpx
    from autobots.adapters.github_issues import API_URL, REPOSITORY_VARIABLE, TOKEN_VARIABLE
    from autobots.adapters.github_pulls import branch_for, github_pull_request_tool
    from autobots.application.tool_gateway import ToolFailed
    from autobots.contracts.tools import GithubOpenPullRequestInput

    transport = counting_transport(authorization['max_requests'], ledger)
    environ = {REPOSITORY_VARIABLE: repository, TOKEN_VARIABLE: token}
    async with httpx.AsyncClient(base_url=API_URL, headers=_headers(token), timeout=20, transport=transport) as http:
        base = str((await _probe(http, repository)).get('default_branch') or '')
    if not base:
        raise Refused('the repository has no default branch to propose against')
    operation = f'qualification-{uuid4().hex[:16]}'
    path = f'qualification/us-15-16-{operation[-8:]}.md'
    arguments = GithubOpenPullRequestInput(
        title='Autobots US-15.16 qualification',
        body='A throwaway pull request from the US-15.16 live qualification. It is closed unmerged and its branch deleted.',
        base=base,
        files=[{'path': path, 'content': f'# US-15.16 qualification\n\nOperation {operation}. Closed unmerged.\n'}],
    )
    tool = github_pull_request_tool(transport, environ)
    assert tool.review_detail is not None
    try:
        detail = await tool.review_detail(arguments)
    except ToolFailed as error:
        # GitHub answers 409 for a git ref in a repository with no commits: there is no head to branch from.
        raise Refused(f'the base branch {base} could not be read ({error}); a repository with no commits has no head to propose against') from None
    review = {'schema_version': 'autobots.github-studio-review/v1', 'repository': repository, 'operation_id': operation,
              'branch': branch_for(operation), 'arguments': arguments.model_dump(), 'review_detail': detail}
    return 0, review


async def studio_apply(repository: str, token: str, authorization: dict, review: dict, ledger: dict) -> tuple[int, dict]:
    import httpx
    from autobots.adapters.github_issues import (
        API_URL,
        REPOSITORY_VARIABLE,
        TOKEN_VARIABLE,
        github_issue_tool,
        marker,
    )
    from autobots.adapters.github_pulls import branch_for, github_pull_request_tool
    from autobots.adapters.github_reads import github_read_tools
    from autobots.application.tool_gateway import ToolContext, ToolFailed, ToolScope
    from autobots.contracts.tools import CreateGithubIssueV2Input, GithubOpenPullRequestInput

    if review.get('repository') != repository:
        raise Refused('the approved review is for another repository')
    cap = authorization['max_requests']
    transport = counting_transport(cap, ledger)
    environ = {REPOSITORY_VARIABLE: repository, TOKEN_VARIABLE: token}
    cases: list[dict] = []

    def check(name: str, expected: str, observed: object, passed: bool) -> None:
        cases.append({'id': name, 'expected': expected, 'observed': str(observed), 'passed': bool(passed)})
        print(f"{'PASS' if passed else 'FAIL'}: {name}: {observed}", flush=True)

    operation = str(review['operation_id'])
    branch = branch_for(operation)
    arguments = GithubOpenPullRequestInput.model_validate(review['arguments'])
    approved = ApprovedReview(review['review_detail'])
    pr_context = ToolContext(approved, ToolScope(uuid4(), uuid4(), 1, {}), operation)
    issue_operation = f'qualification-{uuid4().hex[:16]}'
    issue_context = ToolContext(None, ToolScope(uuid4(), uuid4(), 1, {}), issue_operation)
    reads = {tool.tool_id: tool for tool in github_read_tools(transport, environ)}
    outputs: dict[str, Any] = {}
    issue_number = pull_number = None
    pull_attempted = False

    async def read_tool(tool_id: str, values: dict) -> Any:
        tool = reads[tool_id]
        out = await tool.handler(tool.input_model.model_validate(values), issue_context)
        valid = tool.output_model.model_validate(out.model_dump())
        outputs[tool_id] = _shape(valid)
        check(f'{tool_id} returns output its contract validates', tool.output_model.__name__, outputs[tool_id], True)
        return valid

    async with httpx.AsyncClient(base_url=API_URL, headers=_headers(token), timeout=30, transport=transport) as http:
        try:
            await _probe(http, repository)

            await read_tool('github_list_pull_requests', {'state': 'closed', 'limit': 5})
            await read_tool('github_list_workflow_runs', {'limit': 2})
            await read_tool('github_search_issues', {'query': 'qualification', 'state': 'closed'})

            issue = await github_issue_tool(transport, environ, version=2).handler(
                CreateGithubIssueV2Input(title='Autobots US-15.16 qualification', body='A throwaway issue from the US-15.16 live qualification. It closes itself.', labels=['documentation']),
                issue_context,
            )
            issue_number = issue.number
            check('create_github_issue version 2 creates an issue in the configured repository', f'an issue in {repository}', issue.url, f'{repository}/issues/' in issue.url)
            stored = (await http.get(f'/repos/{repository}/issues/{issue_number}')).json()
            labels = sorted(label.get('name') for label in stored.get('labels') or ())
            check('the issue carries its label', "['documentation']", labels, labels == ['documentation'])
            check('the issue carries its operation marker', 'the marker, in the body', marker(issue_operation) in (stored.get('body') or ''), marker(issue_operation) in (stored.get('body') or ''))

            # From here the branch may exist even if the pull request never opens, so cleanup tries it.
            pull_attempted = True
            opened = await github_pull_request_tool(transport, environ).handler(arguments, pr_context)
            pull_number = opened.number
            check('github_open_pull_request opens the approved pull request', f'a pull request in {repository} from {branch}', f'{opened.url} from {opened.branch}', f'{repository}/pull/' in opened.url and opened.branch == branch)
            pull = (await http.get(f'/repos/{repository}/pulls/{pull_number}')).json()
            check('the pull request carries its operation marker', 'the marker, in the body', marker(operation) in (pull.get('body') or ''), marker(operation) in (pull.get('body') or ''))
            base = pull.get('base') or {}
            check('it targets the approved base at the approved head', f"{arguments.base} at {review['review_detail']['base_sha'][:12]}",
                  f"{base.get('ref')} at {str(base.get('sha'))[:12]}",
                  base.get('ref') == arguments.base and base.get('sha') == review['review_detail']['base_sha'])
            changed = sorted(item.get('filename') for item in (await http.get(f'/repos/{repository}/pulls/{pull_number}/files')).json())
            expected_paths = sorted(item.path for item in arguments.files)
            check('it changes only the approved paths', str(expected_paths), changed, changed == expected_paths)
            check('nothing is merged', 'false', pull.get('merged'), pull.get('merged') is False)

            again = await github_pull_request_tool(transport, environ).handler(arguments, pr_context)
            check('a retry of the pull request returns the existing one', str(pull_number), again.number, again.number == pull_number)
            tool = github_pull_request_tool(transport, environ)
            assert tool.reconcile is not None
            found = await tool.reconcile(arguments, pr_context)
            check('a readback finds that same pull request', str(pull_number), found.number, found.number == pull_number)
            check('no approval was returned to review', 'false', approved.returned_to_review, not approved.returned_to_review)

            read = await read_tool('github_read_file', {'path': arguments.files[0].path, 'ref': branch})
            same = read.content == arguments.files[0].content
            check('github_read_file reads the committed file back unchanged', 'the approved content', 'equal' if same else 'different', same)
        except Refused:
            raise
        except CapReached as error:
            check('the pass stays inside the authorized cap', f'at most {cap} requests', str(error), False)
        except ToolFailed as error:
            # A typed code, never a message from GitHub.
            check('the qualification ran to its end', 'no error', f'ToolFailed {error}', False)
        except Exception as error:  # noqa: BLE001 - only the type is reported, since a message could hold anything
            check('the qualification ran to its end', 'no error', type(error).__name__, False)
        finally:
            transport.cleaning = True
            if pull_number is not None:
                closed = await http.patch(f'/repos/{repository}/pulls/{pull_number}', json={'state': 'closed'})
                check('the qualification closes its pull request', '200', closed.status_code, closed.status_code == 200)
            if pull_attempted:
                deleted = await http.delete(f'/repos/{repository}/git/refs/heads/{branch}')
                # 422: there was no branch to delete, which is only right if no pull request opened.
                gone = deleted.status_code == 204 or (deleted.status_code == 422 and pull_number is None)
                check('the qualification leaves no branch behind', '204, or 422 when none was made', deleted.status_code, gone)
            if issue_number is not None:
                closed = await http.patch(f'/repos/{repository}/issues/{issue_number}', json={'state': 'closed', 'state_reason': 'not_planned'})
                check('the qualification closes its issue', '200', closed.status_code, closed.status_code == 200)
    check('the pass stays inside the authorized cap', f'at most {cap} requests', f'{transport.used} of {cap}', transport.used <= cap)
    failed = [case['id'] for case in cases if not case['passed']]
    report = {'schema_version': 'autobots.github-studio/v1', 'story': STUDIO_STORY, 'completed_at_utc': datetime.now(UTC).isoformat(),
              'evidence_class': 'live', 'repository': repository, 'authorization': authorization.get('source'),
              'issue': issue_number, 'pull_request': pull_number, 'branch': branch, 'outputs': outputs,
              'requests_used': transport.used, 'request_cap': cap, 'requests': list(ledger['requests']),
              'cases': cases, 'failed': failed, 'model_calls': 0,
              'not_established': ['H1', 'product acceptance', 'the gateway, approvals table and worker, which tests/db/pull_request_check.py covers on fakes',
                                  'a real lost reply, which only a fake transport arranges', 'a moved base live, which the fake covers']}
    return (1 if failed else 0), report


def studio(arguments: argparse.Namespace) -> int:
    ledger_path = STUDIO_OUT / 'requests.json'
    try:
        repository, token = studio_environment(arguments.env_file)
        authorization = studio_authorization(arguments.authorization, repository)
    except Refused as error:
        print(f'REFUSED, nothing sent: {error}', file=sys.stderr)
        return 2
    # Every live request this authorization has paid for, across phases and reruns.
    try:
        ledger = json.loads(ledger_path.read_text())
    except (OSError, ValueError):
        ledger = {'used': 0, 'requests': []}
    try:
        return _studio_phase(arguments, repository, token, authorization, ledger)
    finally:
        if not _write_redacted(ledger_path, ledger, token):
            print('ERROR: the request ledger would hold the token, so it was not saved', file=sys.stderr)


def _studio_phase(arguments: argparse.Namespace, repository: str, token: str, authorization: dict, ledger: dict) -> int:
    try:
        review_path = STUDIO_OUT / 'review.json'
        if arguments.phase == 'review':
            code, review = asyncio.run(studio_review(repository, token, authorization, ledger))
            if not _write_redacted(review_path, review, token):
                print('ERROR: the review would hold the token, so it was not saved', file=sys.stderr)
                return 1
            detail = review['review_detail']
            print(f"Review saved for approval: {review['arguments']['title']} into {detail['base_branch']} at {detail['base_sha'][:12]}, branch {review['branch']}")
            for item in detail['files']:
                print(f"--- {item['path']} ({item['change']})\n{item['diff']}")
            print(f"{ledger['used']} of {authorization['max_requests']} requests used")
            return code
        if not arguments.approved_review:
            raise Refused('apply runs only with the review the owner approved, given as --approved-review')
        try:
            review = json.loads(arguments.approved_review.read_text())
        except (OSError, ValueError) as error:
            raise Refused(f'the approved review could not be read: {type(error).__name__}') from None
        code, report = asyncio.run(studio_apply(repository, token, authorization, review, ledger))
    except Refused as error:
        print(f'REFUSED, nothing sent past this point: {error}', file=sys.stderr)
        return 2
    report_path = STUDIO_OUT / 'qualification.json'
    report['cases'].append({'id': 'the redacted record holds no token', 'expected': 'absent', 'observed': 'absent', 'passed': True})
    if not _write_redacted(report_path, report, token):
        print('FAIL: the record would hold the token, so it was not saved', file=sys.stderr)
        return 1
    print(f"PASS: the redacted record holds no token: {report_path}")
    return code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--live', action='store_true', help='required: this sends requests to GitHub')
    parser.add_argument('--suite', choices=('issue', 'studio'), default='issue')
    parser.add_argument('--repository', help='issue: owner/name of a throwaway private repository')
    parser.add_argument('--token-file', help='issue: a file holding only a fine-grained token limited to that repository')
    parser.add_argument('--env-file', type=Path, default=Path('.env'), help='studio: where GITHUB_REPOSITORY and GITHUB_TOKEN are set')
    parser.add_argument('--authorization', type=Path, help="studio: the owner's recorded authorization")
    parser.add_argument('--phase', choices=('review', 'apply'), help='studio: review reads only; apply writes')
    parser.add_argument('--approved-review', type=Path, help='studio apply: the review the owner approved')
    arguments = parser.parse_args()
    if not arguments.live:
        print('REFUSED: this sends requests to GitHub, and needs --live', file=sys.stderr)
        return 2
    if arguments.suite == 'studio':
        if not arguments.authorization or not arguments.phase:
            print('REFUSED: the studio suite needs --authorization and --phase', file=sys.stderr)
            return 2
        return studio(arguments)
    if not arguments.repository or not arguments.token_file:
        print('REFUSED: the issue suite needs --repository and --token-file', file=sys.stderr)
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
