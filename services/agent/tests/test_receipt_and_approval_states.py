"""Receipt and approval request states and their permitted moves, apart from run status (refactor
plan R-50: PTOL-03; SP-010; Decision 0029 F8).

The tables below are written out by hand, as are the stored values the migrations' checks admit, so
a change to `domain/effects.py` fails here until this file and the Option B contract's subsection
say the same.
"""

import re
from itertools import product
from pathlib import Path

import pytest

from autobots.domain.effects import (
    APPROVAL_MOVES,
    RECEIPT_MOVES,
    ApprovalCommand,
    ApprovalStatus,
    ReceiptCommand,
    ReceiptStatus,
    approval_move_permitted,
    approval_sources,
    leaves_receipt,
    receipt_move_permitted,
    receipt_sources,
)
from autobots.domain.tools import EFFECTFUL, OperationClass

ROOT = Path(__file__).resolve().parents[3]
R, A = ReceiptStatus, ApprovalStatus
RECEIPT_TABLE: dict[ReceiptCommand, set[tuple[ReceiptStatus | None, ReceiptStatus]]] = {
    ReceiptCommand.START: {(None, R.STARTED)},
    ReceiptCommand.REOPEN: {(R.STARTED, R.STARTED), (R.FAILED, R.STARTED), (R.UNKNOWN, R.STARTED)},
    ReceiptCommand.RECORD: {
        (R.STARTED, R.SUCCEEDED),
        (R.STARTED, R.FAILED),
        (R.STARTED, R.UNKNOWN),
        (R.FAILED, R.SUCCEEDED),
        (R.UNKNOWN, R.SUCCEEDED),
    },
    ReceiptCommand.MARK_UNKNOWN: {(R.STARTED, R.UNKNOWN)},
    ReceiptCommand.RULE: {(R.UNKNOWN, R.SUCCEEDED), (R.UNKNOWN, R.FAILED)},
}
APPROVAL_TABLE: dict[ApprovalCommand, set[tuple[ApprovalStatus | None, ApprovalStatus]]] = {
    ApprovalCommand.REQUEST: {(None, A.PENDING)},
    ApprovalCommand.DECIDE: {(A.PENDING, A.APPROVED), (A.PENDING, A.REJECTED)},
    ApprovalCommand.EXPIRE: {(A.PENDING, A.EXPIRED)},
    ApprovalCommand.WITHDRAW: {(A.PENDING, A.WITHDRAWN)},
    ApprovalCommand.RETURN_TO_REVIEW: {(A.APPROVED, A.PENDING)},
}
RECEIPT_PERMITTED = set().union(*RECEIPT_TABLE.values())
APPROVAL_PERMITTED = set().union(*APPROVAL_TABLE.values())


def test_each_command_makes_exactly_its_moves() -> None:
    assert {command: set(moves) for command, moves in RECEIPT_MOVES.items()} == RECEIPT_TABLE
    assert {command: set(moves) for command, moves in APPROVAL_MOVES.items()} == APPROVAL_TABLE


@pytest.mark.parametrize(("current", "following"), list(product([None, *R], list(R))))
def test_every_permitted_receipt_move_is_accepted_and_every_other_refused(
    current: ReceiptStatus | None, following: ReceiptStatus
) -> None:
    assert receipt_move_permitted(current, following) is ((current, following) in RECEIPT_PERMITTED)


@pytest.mark.parametrize(("current", "following"), list(product([None, *A], list(A))))
def test_every_permitted_approval_move_is_accepted_and_every_other_refused(
    current: ApprovalStatus | None, following: ApprovalStatus
) -> None:
    assert approval_move_permitted(current, following) is (
        (current, following) in APPROVAL_PERMITTED
    )


def test_a_succeeded_receipt_and_a_settled_request_never_move() -> None:
    assert not any(receipt_move_permitted(R.SUCCEEDED, following) for following in R)
    for settled in (A.REJECTED, A.EXPIRED, A.WITHDRAWN):
        assert not any(approval_move_permitted(settled, following) for following in A)


def test_a_writer_admits_only_the_starting_states_of_its_commands_moves() -> None:
    """What each writer's guard admits, as `status = any(...)`."""
    assert receipt_sources(ReceiptCommand.RECORD, R.SUCCEEDED) == ["failed", "started", "unknown"]
    assert receipt_sources(ReceiptCommand.RECORD, R.FAILED) == ["started"]
    assert receipt_sources(ReceiptCommand.RECORD, R.UNKNOWN) == ["started"]
    assert receipt_sources(ReceiptCommand.REOPEN, R.STARTED) == ["failed", "started", "unknown"]
    assert receipt_sources(ReceiptCommand.MARK_UNKNOWN, R.UNKNOWN) == ["started"]
    assert receipt_sources(ReceiptCommand.RULE, R.FAILED) == ["unknown"]
    assert approval_sources(ApprovalCommand.DECIDE, A.APPROVED) == ["pending"]
    assert approval_sources(ApprovalCommand.EXPIRE, A.EXPIRED) == ["pending"]
    assert approval_sources(ApprovalCommand.WITHDRAW, A.WITHDRAWN) == ["pending"]
    assert approval_sources(ApprovalCommand.RETURN_TO_REVIEW, A.PENDING) == ["approved"]


@pytest.mark.parametrize(
    "asked",
    [
        lambda: receipt_sources(ReceiptCommand.RULE, R.STARTED),
        lambda: receipt_sources(ReceiptCommand.START, R.STARTED),
        lambda: approval_sources(ApprovalCommand.DECIDE, A.EXPIRED),
        lambda: approval_sources(ApprovalCommand.REQUEST, A.PENDING),
    ],
    ids=["rule to started", "start from a row", "decide to expired", "request from a row"],
)
def test_a_writer_asking_for_a_move_its_command_lacks_is_a_defect(asked: object) -> None:
    assert callable(asked)
    with pytest.raises(ValueError, match="makes no move"):
        asked()


def _checked_values(migration: str, column: str) -> list[str]:
    text = (ROOT / "supabase/migrations" / migration).read_text()
    found = re.search(rf"{column} text not null[^\n]*\n?\s*check \({column} in \(([^)]*)\)\)", text)
    assert found is not None, migration
    return [value.strip().strip("'") for value in found.group(1).split(",")]


def test_the_stored_values_are_the_ones_the_columns_admit() -> None:
    """No data migration: the enums name exactly the values already stored."""
    assert [status.value for status in R] == _checked_values(
        "20261105000009_tool_gateway.sql", "status"
    )
    assert [status.value for status in A] == _checked_values(
        "20261105000016_approvals.sql", "status"
    )


def test_only_an_effect_leaves_a_receipt() -> None:
    """The gateway sends an effect to its receipt, and the approval gate consumes an approval only
    for a call that leaves none, by the same rule (Decisions 0018 B6 and 0020 L5)."""
    for operation_class in OperationClass:
        assert leaves_receipt(operation_class) is (operation_class in EFFECTFUL)


def _contract_moves(header: str) -> set[tuple[str, str | None, str]]:
    """The moves a table in the Option B contract's subsection lists, as (command, from, to)."""
    lines = (ROOT / "docs/engineering/option-b-contract.md").read_text().splitlines()
    start = next(at for at, line in enumerate(lines) if line.startswith(f"| {header} |"))
    moves: set[tuple[str, str | None, str]] = set()
    for line in lines[start + 2 :]:
        if not line.startswith("|"):
            break
        command, sources, targets = (cell.strip() for cell in line.strip("|").split("|"))
        for source in sources.split(", "):
            for target in targets.split(", "):
                moves.add(
                    (
                        command.strip("`"),
                        None if source == "none" else source.strip("`"),
                        target.strip("`"),
                    )
                )
    return moves


def _table_moves(
    table: dict[ReceiptCommand, set[tuple[ReceiptStatus | None, ReceiptStatus]]]
    | dict[ApprovalCommand, set[tuple[ApprovalStatus | None, ApprovalStatus]]],
) -> set[tuple[str, str | None, str]]:
    return {
        (command.value, None if source is None else source.value, target.value)
        for command, moves in table.items()
        for source, target in moves
    }


def test_the_contract_lists_the_same_moves() -> None:
    """The Option B contract's subsection beside SP-010 (Decision 0029 F8)."""
    assert _contract_moves("Receipt command") == _table_moves(RECEIPT_TABLE)
    assert _contract_moves("Approval command") == _table_moves(APPROVAL_TABLE)
