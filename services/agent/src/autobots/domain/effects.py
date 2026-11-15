"""Tool-attempt receipt and approval request states, apart from run status (SP-010, PTOL-03).

Each command names the moves it makes, as (from, to), with None for a row not stored yet. The
writers build their SQL guards from these tables, so a move outside them matches no row:
`application/receipts.py` alone writes a receipt's status, and `application/approvals.py` alone
writes a request's. The Option B contract lists the same tables beside SP-010 (Decision 0029 F8).
The values are the ones the columns' checks admit, so stored rows read unchanged.
"""

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType

from autobots.domain.tools import EFFECTFUL, OperationClass


class ReceiptStatus(StrEnum):
    STARTED = "started"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    UNKNOWN = "unknown"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    WITHDRAWN = "withdrawn"


class ReceiptCommand(StrEnum):
    # Committed before the effect runs, so a crash leaves a record that it may have happened.
    START = "start"
    # A new attempt, where no earlier one succeeded.
    REOPEN = "reopen"
    # What the attempt learned about its effect.
    RECORD = "record"
    # A worker's death leaves its attempt's outcome unknown, never assumed (SP-012).
    MARK_UNKNOWN = "mark_unknown"
    # A person reports what the destination's own records show (SP-012).
    RULE = "rule"


class ApprovalCommand(StrEnum):
    REQUEST = "request"
    DECIDE = "decide"
    # Expiry is not consent (SP-010).
    EXPIRE = "expire"
    # A cancelled run's waiting requests.
    WITHDRAW = "withdraw"
    # Nothing was sent: stale, consumed, or its base moved (Decision 0022 D15).
    RETURN_TO_REVIEW = "return_to_review"


R, A = ReceiptStatus, ApprovalStatus
ReceiptMoves = frozenset[tuple[ReceiptStatus | None, ReceiptStatus]]
ApprovalMoves = frozenset[tuple[ApprovalStatus | None, ApprovalStatus]]

RECEIPT_MOVES: Mapping[ReceiptCommand, ReceiptMoves] = MappingProxyType(
    {
        ReceiptCommand.START: frozenset({(None, R.STARTED)}),
        ReceiptCommand.REOPEN: frozenset(
            {(R.STARTED, R.STARTED), (R.FAILED, R.STARTED), (R.UNKNOWN, R.STARTED)}
        ),
        # A success is recorded over any earlier outcome, as the effect happened and repeating it
        # would be the worse mistake. Anything else speaks only for the attempt still started.
        ReceiptCommand.RECORD: frozenset(
            {
                (R.STARTED, R.SUCCEEDED),
                (R.STARTED, R.FAILED),
                (R.STARTED, R.UNKNOWN),
                (R.FAILED, R.SUCCEEDED),
                (R.UNKNOWN, R.SUCCEEDED),
            }
        ),
        ReceiptCommand.MARK_UNKNOWN: frozenset({(R.STARTED, R.UNKNOWN)}),
        ReceiptCommand.RULE: frozenset({(R.UNKNOWN, R.SUCCEEDED), (R.UNKNOWN, R.FAILED)}),
    }
)
APPROVAL_MOVES: Mapping[ApprovalCommand, ApprovalMoves] = MappingProxyType(
    {
        ApprovalCommand.REQUEST: frozenset({(None, A.PENDING)}),
        ApprovalCommand.DECIDE: frozenset({(A.PENDING, A.APPROVED), (A.PENDING, A.REJECTED)}),
        ApprovalCommand.EXPIRE: frozenset({(A.PENDING, A.EXPIRED)}),
        ApprovalCommand.WITHDRAW: frozenset({(A.PENDING, A.WITHDRAWN)}),
        ApprovalCommand.RETURN_TO_REVIEW: frozenset({(A.APPROVED, A.PENDING)}),
    }
)


def receipt_move_permitted(current: ReceiptStatus | None, following: ReceiptStatus) -> bool:
    """Whether any command moves a receipt from `current` (None: no receipt yet) to `following`."""
    return any((current, following) in moves for moves in RECEIPT_MOVES.values())


def approval_move_permitted(current: ApprovalStatus | None, following: ApprovalStatus) -> bool:
    """Whether any command moves a request from `current` (None: no request yet) to `following`."""
    return any((current, following) in moves for moves in APPROVAL_MOVES.values())


def _sources[S: StrEnum](
    command: StrEnum, moves: frozenset[tuple[S | None, S]], following: S
) -> list[str]:
    found = sorted(
        source.value for source, target in moves if target == following and source is not None
    )
    if not found:
        # A writer asked for a move its command doesn't make: a defect, never a write.
        raise ValueError(f"{command.value} makes no move to {following.value} from a stored row")
    return found


def receipt_sources(command: ReceiptCommand, following: ReceiptStatus) -> list[str]:
    """The stored statuses `command` moves to `following` from, for its writer's guard."""
    return _sources(command, RECEIPT_MOVES[command], following)


def approval_sources(command: ApprovalCommand, following: ApprovalStatus) -> list[str]:
    """The stored statuses `command` moves to `following` from, for its writer's guard."""
    return _sources(command, APPROVAL_MOVES[command], following)


def leaves_receipt(operation_class: OperationClass) -> bool:
    """Only an effect leaves a receipt under its operation identity. The gateway dispatches by
    this, and the approval gate consumes an approval only for a call that leaves none (Decisions
    0018 B6 and 0020 L5)."""
    return operation_class in EFFECTFUL
