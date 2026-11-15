"""The approval gate's decision table, with no database (PTOL-05, Decision 0015, Decision 0025 V8).

`gate_decision` reads the operation's request, the current scope hash and the operation's receipt,
and says whether the call runs, waits, goes back to a person or is refused. `approval_gate` then
writes what that decision needs, in the request's locked transaction.
"""

import contextlib
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from uuid import UUID

import pytest

from autobots.application.approvals import (
    ApprovalProposal,
    Gate,
    ReceiptState,
    RequestRow,
    approval_gate,
    gate_decision,
    scope_snapshot,
)
from autobots.domain.effects import ApprovalStatus, ReceiptStatus
from autobots.domain.stops import GatewayCode

APPROVAL = UUID("d0000000-0000-4000-8000-000000000004")
SNAPSHOT = scope_snapshot({"send_note": 1}, ())
PROPOSAL = ApprovalProposal(
    operation_id="op",
    tool_id="send_note",
    tool_version=1,
    operation_class="consequential_external_write",
    argument_hash="hash",
    arguments={},
    scope=SNAPSHOT,
    policy_version="approval-policy/2",
    policy_rule="consequential_external_write",
    policy_reason="Held.",
    resource_target=None,
    review_detail=None,
)
SCOPE = PROPOSAL.scope_hash
OTHER_SCOPE = "another scope"


def request(status: str, *, expired: bool = False, scope: str = SCOPE) -> RequestRow:
    return RequestRow(APPROVAL, ApprovalStatus(status), scope, expired)


def receipt(status: str, *, ruled: bool = False, code: str | None = None) -> ReceiptState:
    return ReceiptState(ReceiptStatus(status), ruled, code)


@pytest.mark.parametrize(
    ("row", "scope", "found", "decision"),
    [
        # No request yet: one is stored, and the call waits for a person.
        (None, SCOPE, None, Gate.REQUEST),
        (request("pending"), SCOPE, None, Gate.WAIT),
        (request("pending", expired=True), SCOPE, None, GatewayCode.APPROVAL_EXPIRED),
        (request("rejected"), SCOPE, None, GatewayCode.APPROVAL_REJECTED),
        (request("expired"), SCOPE, None, GatewayCode.APPROVAL_EXPIRED),
        (request("withdrawn"), SCOPE, None, GatewayCode.APPROVAL_EXPIRED),
        # Approved under other grants: the decision doesn't cover this scope, sent or not.
        (request("approved"), OTHER_SCOPE, None, GatewayCode.APPROVAL_SCOPE_CHANGED),
        (
            request("approved"),
            OTHER_SCOPE,
            receipt("succeeded"),
            GatewayCode.APPROVAL_SCOPE_CHANGED,
        ),
        (request("approved"), SCOPE, None, Gate.RELEASE),
        # Sent, or possibly sent: its receipt answers for it, however old the decision.
        (request("approved", expired=True), SCOPE, receipt("started"), Gate.RELEASE),
        (request("approved", expired=True), SCOPE, receipt("unknown"), Gate.RELEASE),
        (request("approved", expired=True), SCOPE, receipt("succeeded"), Gate.RELEASE),
        # A failure nobody ruled on used the decision.
        (request("approved"), SCOPE, receipt("failed"), GatewayCode.APPROVAL_CONSUMED),
        (
            request("approved", expired=True),
            SCOPE,
            receipt("failed", code="tool_failed"),
            GatewayCode.APPROVAL_CONSUMED,
        ),
        # A ruling grants one more try, and an attempt the lease refused wrote nothing.
        (request("approved"), SCOPE, receipt("failed", ruled=True), Gate.RELEASE),
        (request("approved"), SCOPE, receipt("failed", code="lease_lost"), Gate.RELEASE),
        # Stale with nothing sent: back to a person.
        (request("approved", expired=True), SCOPE, None, Gate.REOPEN),
        (request("approved", expired=True), SCOPE, receipt("failed", ruled=True), Gate.REOPEN),
        (
            request("approved", expired=True),
            SCOPE,
            receipt("failed", code="lease_lost"),
            Gate.REOPEN,
        ),
    ],
)
def test_the_gate_decides_from_the_request_the_scope_and_the_receipt(
    row: RequestRow | None, scope: str, found: ReceiptState | None, decision: Gate | GatewayCode
) -> None:
    assert gate_decision(row, scope, found) == decision


@dataclass
class Connection:
    """Answers the gate's two reads and records every statement."""

    row: tuple[object, ...] | None
    found: tuple[object, ...] | None = None
    statements: list[str] = field(default_factory=list)
    answer: tuple[object, ...] | None = None

    @contextlib.asynccontextmanager
    async def transaction(self) -> AsyncIterator[None]:
        yield

    async def execute(self, query: str, _: tuple[object, ...] = ()) -> "Connection":
        self.statements.append(query)
        self.answer = (
            self.row
            if "from public.approval_requests" in query
            else self.found
            if "from app_private.tool_receipts" in query
            else (1,)
        )
        return self

    async def fetchone(self) -> tuple[object, ...] | None:
        return self.answer


@dataclass(frozen=True)
class Run:
    """The requesting run, at the generation that holds it."""

    workspace_id: UUID
    run_id: UUID
    generation: int


RUN = Run(
    UUID("a0000000-0000-4000-8000-000000000001"), UUID("b0000000-0000-4000-8000-000000000002"), 3
)


@pytest.mark.parametrize(
    ("row", "found", "code", "writes"),
    [
        ((APPROVAL, "approved", SCOPE, False, False), None, None, []),
        ((APPROVAL, "rejected", SCOPE, False, False), None, "approval_rejected", []),
        ((APPROVAL, "pending", SCOPE, False, False), None, "approval_pending", ["wait"]),
        (
            (APPROVAL, "approved", SCOPE, True, False),
            None,
            "approval_pending",
            ["reopen", "wait"],
        ),
        ((APPROVAL, "approved", SCOPE, True, False), ("started", None, None), None, []),
    ],
    ids=["release", "refuse", "wait", "reopen", "sent"],
)
@pytest.mark.asyncio
async def test_the_gate_writes_only_what_its_decision_needs(
    monkeypatch: pytest.MonkeyPatch,
    row: tuple[object, ...],
    found: tuple[object, ...] | None,
    code: str | None,
    writes: list[str],
) -> None:
    waits: list[dict[str, object]] = []

    async def enter_wait(_: object, **fields: object) -> None:
        waits.append(fields)

    monkeypatch.setattr("autobots.application.approvals.apply_command", enter_wait)
    connection = Connection(row, found)
    assert await approval_gate(connection, RUN, PROPOSAL) == code
    reopened = any(
        query.startswith("update public.approval_requests") for query in connection.statements
    )
    assert ["reopen"] * reopened + ["wait"] * len(waits) == writes
    assert not any("insert into public.approval_requests" in q for q in connection.statements)
    for wait in waits:
        assert (wait["command"], wait["generation"], wait["detail"]) == (
            "request_approval",
            3,
            str(APPROVAL),
        )
