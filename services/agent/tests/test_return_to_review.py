"""A moved pull-request base returns the request to a person through approvals.py, fenced and in one
transaction (refactor plan R-21: PADP-02, XMOD-02, XDUP-02; Decision 0022 D15).

The database fake answers only what these paths read, and records each statement with the
transaction it ran in. tests/db/checks/pull_request_check.py runs the same path against Postgres.
"""

import asyncio
import base64
import contextlib
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from urllib.parse import unquote
from uuid import UUID, uuid4

import httpx
import pytest

from autobots.application.runs import LeaseLost
from autobots.application.sql import SqlParams
from autobots.application.tool_definitions import ToolContext, ToolFailed, ToolScope
from autobots.application.worker_leases import Lease
from autobots.contracts.github_tools import GithubOpenPullRequestInput
from sql_fakes import ScriptedRows

SOURCE = Path(__file__).resolve().parents[1] / "src/autobots"
REPOSITORY = "owner/throwaway"
TARGET = f"GitHub repository {REPOSITORY}"
ENV = {"GITHUB_REPOSITORY": REPOSITORY, "GITHUB_TOKEN": "arranged-pull-token"}
TOOL_ID = "github_open_pull_request"
OPERATION = "operation-1"
APPROVAL = UUID("00000000-0000-4000-8000-000000000001")
SCOPE = ToolScope(uuid4(), uuid4(), 3, {TOOL_ID: 1})
LEASE = Lease(SCOPE.run_id, SCOPE.workspace_id, 3, "worker", 1, "running")
APPROVED_DETAIL = {"base_branch": "main", "base_sha": "base-1", "files": []}
NEW_DETAIL = {"base_branch": "main", "base_sha": "base-2", "files": []}
PROPOSAL = GithubOpenPullRequestInput.model_validate(
    {
        "title": "Tidy the readme",
        "base": "main",
        "files": [{"path": "README.md", "content": "Hello, reviewed\n"}],
    }
)


class Ledger:
    """A worker's connection: whether its generation still holds the job, and whether the
    operation has an approved request. A transaction that raises is recorded as rolled back."""

    def __init__(self, *, owned: bool = True, approved: bool = True) -> None:
        self.owned = owned
        self.approved = approved
        self.statements: list[tuple[str, Any, int | None]] = []
        self.rolled_back: set[int] = set()
        self._opened = 0
        self._current: int | None = None

    @contextlib.asynccontextmanager
    async def transaction(self) -> AsyncIterator[None]:
        if self._current is not None:
            yield
            return
        self._opened += 1
        self._current = self._opened
        try:
            yield
        except BaseException:
            self.rolled_back.add(self._opened)
            raise
        finally:
            self._current = None

    async def execute(self, query: str, params: SqlParams | None = None, /) -> ScriptedRows:
        """Reads it has no answer for, such as the workspace's saved Keys & vars, find nothing."""
        self.statements.append((query, params, self._current))
        answer = self._answer(query)
        return ScriptedRows([] if answer is None else [answer])

    def _answer(self, query: str) -> tuple[Any, ...] | None:
        if "from app_private.run_jobs" in query:
            return (1,) if self.owned else None
        if "from public.approval_requests" in query and "for update" in query:
            return (APPROVAL,) if self.approved else None
        if "select resource_target, review_detail from public.approval_requests" in query:
            return (TARGET, APPROVED_DETAIL) if self.approved else None
        if "event_sequence = event_sequence + 1" in query:
            return (7,)
        return None

    def writes(self) -> list[tuple[str, Any, int | None]]:
        return [entry for entry in self.statements if entry[0].startswith(("update", "insert"))]


def kind(query: str) -> str:
    """What a statement does, in the words of the transition."""
    if "from app_private.run_jobs" in query:
        return "hold lease"
    if query.startswith("update public.approval_requests"):
        return "reopen request"
    if "public.approval_requests" in query and "for update" in query:
        return "lock request"
    if query.startswith("update app_private.tool_receipts"):
        return "settle receipt"
    if "event_sequence = event_sequence + 1" in query:
        return "next sequence"
    if query.startswith("insert into public.run_events"):
        return "append event"
    return "other"


@pytest.mark.asyncio
async def test_a_returned_request_commits_in_one_fenced_transaction() -> None:
    """The lease first, then the attempt's receipt settled, the request back to pending with the
    standard expiry and the new detail, and approval.requested appended, all committed at once."""
    from autobots.application.approvals import DEFAULT_TTL_SECONDS, return_to_review

    ledger = Ledger()
    returned = await return_to_review(
        ledger, SCOPE, operation_id=OPERATION, tool_id=TOOL_ID, detail=NEW_DETAIL
    )
    assert returned == APPROVAL
    assert [kind(query) for query, _, _ in ledger.statements] == [
        "hold lease",
        "lock request",
        "settle receipt",
        "reopen request",
        "next sequence",
        "append event",
    ]
    assert {transaction for _, _, transaction in ledger.statements} == {1}
    assert not ledger.rolled_back
    statements = {kind(query): params for query, params, _ in ledger.statements}
    assert statements["hold lease"] == (SCOPE.run_id, SCOPE.generation)
    assert statements["lock request"] == (OPERATION, SCOPE.run_id)
    assert statements["reopen request"] == (
        "pending",
        DEFAULT_TTL_SECONDS,
        json.dumps(NEW_DETAIL),
        APPROVAL,
        ["approved"],
    )
    assert statements["settle receipt"] == (OPERATION, SCOPE.run_id)
    assert json.loads(statements["append event"][2]) == {
        "type": "approval.requested",
        "approval_id": str(APPROVAL),
        "tool_id": TOOL_ID,
    }


@pytest.mark.asyncio
async def test_returning_to_review_makes_no_run_transition() -> None:
    """The run keeps running, and enters the decision wait only when the call is tried again
    (Decision 0028 E1): no run status, job or obligation is written, and no status event."""
    from autobots.application.approvals import return_to_review

    ledger = Ledger()
    await return_to_review(
        ledger, SCOPE, operation_id=OPERATION, tool_id=TOOL_ID, detail=NEW_DETAIL
    )
    written = [query for query, _, _ in ledger.writes()]
    assert not [query for query in written if "public.runs set status" in query]
    assert not [query for query in written if "run_obligations" in query or "run_jobs" in query]
    events = [
        json.loads(params[2])["type"]
        for query, params, _ in ledger.writes()
        if query.startswith("insert into public.run_events")
    ]
    assert events == ["approval.requested"]


@pytest.mark.asyncio
async def test_a_stale_generation_leaves_the_decision_untouched() -> None:
    """A worker whose generation isn't current reads its lease and writes nothing."""
    from autobots.application.approvals import return_to_review

    ledger = Ledger(owned=False)
    with pytest.raises(LeaseLost):
        await return_to_review(
            ledger, SCOPE, operation_id=OPERATION, tool_id=TOOL_ID, detail=NEW_DETAIL
        )
    assert [kind(query) for query, _, _ in ledger.statements] == ["hold lease"]
    assert ledger.rolled_back == {1}


@pytest.mark.asyncio
async def test_without_an_approved_request_nothing_is_written() -> None:
    """Only an approved request goes back to review, so its receipt stays as the attempt left it."""
    from autobots.application.approvals import return_to_review

    ledger = Ledger(approved=False)
    returned = await return_to_review(
        ledger, SCOPE, operation_id=OPERATION, tool_id=TOOL_ID, detail=NEW_DETAIL
    )
    assert returned is None
    assert ledger.writes() == []


@pytest.mark.parametrize("holder", [SCOPE, LEASE], ids=["tool scope", "lease"])
@pytest.mark.asyncio
async def test_hold_lease_fences_a_scope_or_a_lease(holder: ToolScope | Lease) -> None:
    from autobots.application import tool_gateway
    from autobots.application.worker_leases import hold_lease

    ledger = Ledger()
    await hold_lease(ledger, holder)
    query, params, _ = ledger.statements[0]
    assert "for share" in query and params == (holder.run_id, holder.generation)
    with pytest.raises(LeaseLost):
        await hold_lease(Ledger(owned=False), holder)
    # One implementation: the gateway's writers fence through the same function.
    assert tool_gateway.hold_lease is hold_lease


@pytest.mark.parametrize(
    ("status", "may_have_sent"),
    [(None, False), ("failed", False), ("started", True), ("unknown", True), ("succeeded", True)],
)
def test_only_a_failed_or_missing_receipt_says_nothing_was_sent(
    status: str | None, may_have_sent: bool
) -> None:
    """Decision 0025 V8: an effect sent, or possibly sent, is left to its receipt."""
    from autobots.application.approvals import receipt_may_have_sent

    assert receipt_may_have_sent(status) is may_have_sent


@pytest.mark.asyncio
async def test_the_approved_request_is_read_by_its_operation() -> None:
    from autobots.application.approvals import ApprovedRequest, approved_request

    ledger = Ledger()
    assert await approved_request(ledger, OPERATION) == ApprovedRequest(TARGET, APPROVED_DETAIL)
    query, params, _ = ledger.statements[0]
    assert "status = 'approved'" in query and params == (OPERATION,)
    assert await approved_request(Ledger(approved=False), OPERATION) is None


class MovedBase:
    """GitHub after the approval: main moved from base-1 to base-2. Only reads are answered."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = unquote(request.url.path).removeprefix(f"/repos/{REPOSITORY}")
        if request.method == "GET" and path == "/git/ref/heads/main":
            return httpx.Response(200, json={"object": {"sha": "base-2"}})
        if request.method == "GET" and path == "/contents/README.md":
            content = base64.b64encode(b"Hello, changed upstream\n").decode()
            return httpx.Response(200, json={"type": "file", "content": content})
        return httpx.Response(599)


def open_pull_request(ledger: Ledger, github: MovedBase) -> None:
    """The approved attempt, handed what the person approved, as the gateway hands it (XMOD-02)."""
    from autobots.adapters.github_pulls import github_pull_request_tool
    from autobots.application.approvals import ApprovedRequest

    tool = github_pull_request_tool(httpx.MockTransport(github), ENV)
    context = ToolContext(ledger, SCOPE, OPERATION, ApprovedRequest(TARGET, APPROVED_DETAIL))

    async def attempt() -> None:
        await tool.handler(PROPOSAL, context)

    asyncio.run(attempt())


def test_a_moved_base_returns_the_request_through_approvals() -> None:
    """D15: base_moved, nothing written to GitHub, and the request goes back with the diff against
    the new head in the one transaction that holds the lease."""
    ledger, github = Ledger(), MovedBase()
    with pytest.raises(ToolFailed, match=r"^base_moved$"):
        open_pull_request(ledger, github)
    assert all(request.method == "GET" for request in github.requests)
    fenced = [entry for entry in ledger.statements if entry[2] is not None]
    assert [kind(query) for query, _, _ in fenced] == [
        "hold lease",
        "lock request",
        "settle receipt",
        "reopen request",
        "next sequence",
        "append event",
    ]
    assert len({transaction for _, _, transaction in fenced}) == 1
    assert all(transaction is not None for _, _, transaction in ledger.writes())
    reopened = next(params for query, params, _ in fenced if kind(query) == "reopen request")
    detail = json.loads(reopened[2])
    readme = next(item for item in detail["files"] if item["path"] == "README.md")
    assert detail["base_sha"] == "base-2" and "-Hello, changed upstream" in readme["diff"]


def test_a_lease_lost_during_the_reads_changes_no_decision() -> None:
    """A worker that lost the run while reading GitHub is refused before any write."""
    ledger, github = Ledger(owned=False), MovedBase()
    with pytest.raises(LeaseLost):
        open_pull_request(ledger, github)
    assert ledger.writes() == []
    assert all(request.method == "GET" for request in github.requests)


def test_only_approvals_reads_an_approved_request() -> None:
    """XDUP-02: one reader of the approved request by operation, which V7 and V8 depend on."""
    owner = SOURCE / "application/approvals.py"
    found = [
        str(path.relative_to(SOURCE))
        for path in sorted(SOURCE.rglob("*.py"))
        if path != owner and "status = 'approved'" in path.read_text()
    ]
    assert found == []
