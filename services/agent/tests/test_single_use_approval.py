"""An approval that releases a call leaving no receipt is used up in the releasing transaction, so
repeating the call waits for a person again (refactor plan R-50: PTOL-06; Decisions 0018 B6 and
0020 L5; SP-013).

An effect's receipt already makes its approval single-use: a repeat finds the receipt and replays
it. browse_goal leaves none, so its approval is consumed instead, and a consumed approval goes back
to a person. tests/db/approval_check.py repeats an approved browse_goal call against Postgres.
"""

import contextlib
from collections.abc import AsyncIterator
from dataclasses import dataclass, field, replace
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
from autobots.application.runs import LeaseLost
from autobots.domain.effects import ApprovalStatus, ReceiptStatus

APPROVAL = UUID("d0000000-0000-4000-8000-000000000004")
BROWSE = ApprovalProposal(
    operation_id="op",
    tool_id="browse_goal",
    tool_version=1,
    operation_class="arbitrary_execution",
    argument_hash="hash",
    arguments={},
    scope=scope_snapshot({"browse_goal": 1}, ()),
    policy_version="approval-policy/2",
    policy_rule="tool_marked",
    policy_reason="Held.",
    resource_target=None,
    review_detail=None,
)
EFFECT = replace(
    BROWSE,
    tool_id="send_note",
    operation_class="consequential_external_write",
    policy_rule="consequential_external_write",
)
SCOPE = BROWSE.scope_hash


def approved(*, expired: bool = False, consumed: bool = False) -> RequestRow:
    return RequestRow(APPROVAL, ApprovalStatus.APPROVED, SCOPE, expired, consumed)


@pytest.mark.parametrize(
    ("row", "found", "decision"),
    [
        (approved(), None, Gate.RELEASE),
        (approved(consumed=True), None, Gate.REOPEN),
        (approved(expired=True, consumed=True), None, Gate.REOPEN),
        # An effect's receipt answers for it, whatever the request says.
        (
            approved(consumed=True),
            ReceiptState(ReceiptStatus.STARTED, False, None),
            Gate.RELEASE,
        ),
    ],
    ids=["approved", "consumed", "consumed and stale", "sent"],
)
def test_a_consumed_approval_goes_back_to_a_person(
    row: RequestRow, found: ReceiptState | None, decision: Gate
) -> None:
    assert gate_decision(row, SCOPE, found) == decision


@dataclass
class Connection:
    """Answers the request's locked read with `row`, and the lease with whether this worker still
    `owned` the run, and records each statement with the transaction it ran in. A transaction that
    raises is recorded as rolled back."""

    row: tuple[object, ...] | None
    owned: bool = True
    statements: list[tuple[str, tuple[object, ...], int | None]] = field(default_factory=list)
    rolled_back: set[int] = field(default_factory=set)
    answer: tuple[object, ...] | None = None
    opened: int = 0
    current: int | None = None

    @contextlib.asynccontextmanager
    async def transaction(self) -> AsyncIterator[None]:
        if self.current is not None:
            yield
            return
        self.opened += 1
        self.current = self.opened
        try:
            yield
        except BaseException:
            self.rolled_back.add(self.opened)
            raise
        finally:
            self.current = None

    async def execute(self, query: str, params: tuple[object, ...] = ()) -> "Connection":
        self.statements.append((query, params, self.current))
        if "from public.approval_requests" in query:
            self.answer = self.row
        elif "from app_private.run_jobs" in query:
            self.answer = (1,) if self.owned else None
        else:
            # No receipt: the call never reached an effect.
            self.answer = None if "from app_private.tool_receipts" in query else (1,)
        return self

    async def fetchone(self) -> tuple[object, ...] | None:
        return self.answer

    def with_text(self, part: str) -> list[tuple[str, tuple[object, ...], int | None]]:
        return [statement for statement in self.statements if part in statement[0]]


@dataclass(frozen=True)
class Run:
    workspace_id: UUID
    run_id: UUID
    generation: int


RUN = Run(
    UUID("a0000000-0000-4000-8000-000000000001"), UUID("b0000000-0000-4000-8000-000000000002"), 3
)


def request_row(*, consumed: bool) -> tuple[object, ...]:
    return (APPROVAL, ApprovalStatus.APPROVED.value, SCOPE, False, consumed)


@pytest.mark.asyncio
async def test_a_release_that_leaves_no_receipt_consumes_its_approval_in_the_same_transaction() -> (
    None
):
    connection = Connection(request_row(consumed=False))
    assert await approval_gate(connection, RUN, BROWSE) is None
    [locked] = connection.with_text("from public.approval_requests where operation_id")
    [lease] = connection.with_text("from app_private.run_jobs")
    [consumed] = connection.with_text("set consumed_at = clock_timestamp()")
    assert consumed[1] == (APPROVAL, ApprovalStatus.APPROVED.value)
    assert "consumed_at is null" in consumed[0]
    # The lease is held, in the same transaction, before the approval is used up.
    assert lease[1] == (RUN.run_id, RUN.generation) and "for share" in lease[0]
    assert connection.statements.index(lease) < connection.statements.index(consumed)
    assert locked[2] is not None and locked[2] == lease[2] == consumed[2]


@pytest.mark.asyncio
async def test_a_worker_that_lost_the_run_consumes_nothing() -> None:
    """Its lease expired after admission: the gate refuses it before the consume, and the
    transaction rolls back, so the approval still releases the run's current owner (SP-012)."""
    connection = Connection(request_row(consumed=False), owned=False)
    with pytest.raises(LeaseLost):
        await approval_gate(connection, RUN, BROWSE)
    assert connection.with_text("set consumed_at") == []
    assert connection.rolled_back == {1}


@pytest.mark.asyncio
async def test_an_effects_release_consumes_nothing_as_its_receipt_answers() -> None:
    connection = Connection(request_row(consumed=False))
    assert await approval_gate(connection, RUN, EFFECT) is None
    assert connection.with_text("set consumed_at") == []


@pytest.mark.asyncio
async def test_repeating_a_consumed_call_waits_for_a_person_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    waits: list[dict[str, object]] = []

    async def enter_wait(_: object, **fields: object) -> None:
        waits.append(fields)

    monkeypatch.setattr("autobots.application.approvals.apply_command", enter_wait)
    connection = Connection(request_row(consumed=True))
    assert await approval_gate(connection, RUN, BROWSE) == "approval_pending"
    [reopened] = connection.with_text("update public.approval_requests set status = %s")
    assert "consumed_at = null" in reopened[0] and "decided_by = null" in reopened[0]
    assert reopened[1][0] == ApprovalStatus.PENDING.value
    assert reopened[1][-1] == [ApprovalStatus.APPROVED.value]
    assert [wait["detail"] for wait in waits] == [str(APPROVAL)]
    assert connection.with_text("set consumed_at = clock_timestamp()") == []
