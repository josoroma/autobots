"""Approval rows map field by field (refactor plan R-54, XTYP-04, PAPI-14).

The gate's request and receipt rows become the states it decides on, and the inbox's row becomes
the view a reviewer sees, with truncation worked out once. Every value differs, so a swap fails,
and an unknown stored status raises instead of reaching a client or a decision.
"""

from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID

import pytest

from autobots.api.approval_routes import approval_view
from autobots.application.approvals import (
    ARGUMENT_LIMIT,
    ReceiptState,
    RequestRow,
    receipt_state_of,
    request_row_of,
)
from autobots.application.sql import UnknownStoredValue
from autobots.domain.effects import ApprovalStatus, ReceiptStatus
from autobots.persistence.rows import ApprovalGateRow, ApprovalListRow, ReceiptStateRow

APPROVAL = UUID(int=1)
RUN = UUID(int=2)
VIEWER = UUID(int=3)
OTHER = UUID(int=4)
EXPERT = UUID(int=5)
LOCAL = timezone(timedelta(hours=-6))
EXPIRES = datetime(2026, 11, 16, 3, tzinfo=LOCAL)
DECIDED = datetime(2026, 11, 15, 9, tzinfo=UTC)


def test_the_gate_reads_its_request_and_receipt_rows() -> None:
    row = ApprovalGateRow(
        id=APPROVAL, status="approved", scope_hash="h", expired=True, consumed=False
    )
    assert request_row_of(row) == RequestRow(APPROVAL, ApprovalStatus.APPROVED, "h", True, False)
    with pytest.raises(ValueError, match="granted"):
        request_row_of(replace(row, status="granted"))
    ruled = ReceiptStateRow(status="failed", reconciled_at=DECIDED, failure_code="timeout")
    assert receipt_state_of(ruled) == ReceiptState(ReceiptStatus.FAILED, True, "timeout")
    assert receipt_state_of(replace(ruled, reconciled_at=None)).ruled is False


LISTED = ApprovalListRow(
    id=APPROVAL,
    run_id=RUN,
    tool_id="send_note",
    tool_version=2,
    operation_class="consequential_external_write",
    argument_hash="a" * 64,
    arguments='{"text": "hello"}',
    status="approved",
    expires_at=EXPIRES,
    policy_reason="Sends outside this Mac.",
    resource_target="the sink",
    requested_by=VIEWER,
    requested_by_agent={"kind": "expert", "id": str(EXPERT), "version": 3},
    scope_snapshot={"tools": {"send_note": 2}, "paths": ["outputs"]},
    policy_version="approval-policy/1",
    policy_rule="tool_marked",
    expert_name="Writer",
    run_goal="Send the note",
    task_title="Write it",
    decided_at=DECIDED,
    decided_by=OTHER,
    decided_by_name="Ana",
    arguments_bytes=17,
    review_detail=None,
)


def test_a_listed_request_takes_each_field_from_its_own_column() -> None:
    view = approval_view(LISTED, VIEWER)
    assert (view.id, view.run_id, view.tool_id, view.tool_version) == (
        APPROVAL,
        RUN,
        "send_note",
        2,
    )
    assert (view.operation_class, view.argument_hash) == ("consequential_external_write", "a" * 64)
    assert (view.arguments, view.arguments_truncated, view.arguments_bytes) == (
        '{"text": "hello"}',
        False,
        17,
    )
    assert (view.status, view.expires_at) == (ApprovalStatus.APPROVED, EXPIRES.astimezone(UTC))
    assert (view.policy_reason, view.resource_target, view.policy_version, view.policy_rule) == (
        "Sends outside this Mac.",
        "the sink",
        "approval-policy/1",
        "tool_marked",
    )
    assert (view.run_goal, view.task_title) == ("Send the note", "Write it")
    assert (view.decided_at, view.decided_by, view.decided_by_name) == (DECIDED, "member", "Ana")
    assert view.scope_snapshot is not None
    assert (view.scope_snapshot.tools, view.scope_snapshot.paths) == ({"send_note": 2}, ["outputs"])
    requester = view.requester
    assert requester is not None
    assert (requester.person_id, requester.person_is_viewer, requester.agent) == (
        VIEWER,
        True,
        "expert",
    )
    assert (requester.expert_id, requester.expert_version, requester.expert_name) == (
        EXPERT,
        3,
        "Writer",
    )


def test_arguments_past_the_review_limit_are_cut_and_marked_once() -> None:
    long = "x" * (ARGUMENT_LIMIT + 10)
    view = approval_view(replace(LISTED, arguments=long), VIEWER)
    assert (len(view.arguments), view.arguments_truncated) == (ARGUMENT_LIMIT, True)


def test_a_request_the_viewer_decided_with_no_agent_or_scope_on_record() -> None:
    view = approval_view(
        replace(LISTED, decided_by=VIEWER, requested_by_agent=None, scope_snapshot=None), VIEWER
    )
    assert (view.decided_by, view.requester, view.scope_snapshot) == ("you", None, None)


def test_a_listed_request_with_an_unknown_stored_value_raises() -> None:
    with pytest.raises(ValueError, match="granted"):
        approval_view(replace(LISTED, status="granted"), VIEWER)
    with pytest.raises(UnknownStoredValue, match="retired_rule"):
        approval_view(replace(LISTED, policy_rule="retired_rule"), VIEWER)


def test_a_request_a_tool_marked_reads_its_rule() -> None:
    """Decision 0026 C3: migration 53's CHECK allows `action_marked`, and the view shows it."""
    marked = approval_view(replace(LISTED, policy_rule="action_marked"), VIEWER)
    assert marked.policy_rule == "action_marked"
