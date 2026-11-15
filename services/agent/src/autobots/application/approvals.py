"""Proposals bound to exact arguments, and decisions validated against them, PRD 9.2.

A worker stops at a proposal, with nothing done. Its checkpoint holds the pending tool call, so the
tool step runs again after the decision and finds the answer here. Only the approved operation's
own identity can pass, so a changed argument is a different operation that needs its own approval.

This module is the one writer of a request's status: request, decide, expire, withdraw and return
to review, each guarded by its moves in `domain/effects.py` (PTOL-03, Decision 0029 F8).
"""

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Protocol, assert_never
from uuid import UUID, uuid4

from autobots.application import receipts
from autobots.application.runs import (
    CommandKey,
    CommandRefused,
    Idempotent,
    append_event,
    apply_command,
    apply_worker_command,
    cascade_command,
    current_status,
)
from autobots.application.worker_leases import LeaseHolder, hold_lease
from autobots.contracts.approvals import ApprovalVerdict
from autobots.contracts.persisted import ApprovalDecisionReceipt
from autobots.contracts.runs import ApprovalDecided, ApprovalRequested
from autobots.domain.effects import (
    ApprovalCommand,
    ApprovalStatus,
    ReceiptStatus,
    approval_sources,
    leaves_receipt,
)
from autobots.domain.errors import Refusal, RefusalKind
from autobots.domain.runs import RunCommand, RunStatus
from autobots.domain.stops import GatewayCode
from autobots.domain.tools import OperationClass

DEFAULT_TTL_SECONDS = 86_400
# The failure code of an attempt the lease refused before it wrote anything.
LEASE_LOST = GatewayCode.LEASE_LOST


# What a reviewer can be shown whole. Anything longer can be rejected, not approved.
ARGUMENT_LIMIT = 64_000


def exceeds_review_limit(arguments: str) -> bool:
    return len(arguments) > ARGUMENT_LIMIT


class ApprovalRefused(Refusal):
    kinds = MappingProxyType({"approval_not_found": RefusalKind.NOT_FOUND})


@dataclass(frozen=True)
class DecisionResult:
    approval_id: UUID
    status: ApprovalStatus
    replayed: bool


@dataclass(frozen=True)
class ApprovedRequest:
    """What a person approved for one operation: the target the request recorded (Decision 0025
    V7) and the detail they were shown, such as a pull request's diffs (PRD-Studio GH-06)."""

    resource_target: str | None
    review_detail: dict[str, Any] | None


def receipt_may_have_sent(status: str | None) -> bool:
    """A receipt that exists and hasn't failed means the effect was sent, or may have been, so the
    receipt and its reconciliation answer for it (Decision 0025 V8). None is no receipt at all."""
    return status is not None and status != ReceiptStatus.FAILED


async def approved_request(connection: Any, operation_id: str) -> ApprovedRequest | None:
    """The operation's request while it is approved, and None otherwise."""
    cursor = await connection.execute(
        "select resource_target, review_detail from public.approval_requests "
        "where operation_id = %s and status = 'approved'",
        (operation_id,),
    )
    row = await cursor.fetchone()
    return None if row is None else ApprovedRequest(row[0], row[1])


def scope_snapshot(tools: Any, paths: Any) -> dict[str, Any]:
    """The grants a request was made under, stored whole with it, Decision 0015."""
    return {"tools": dict(tools), "paths": list(paths)}


def _digest(snapshot: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()


def scope_hash(tools: Any, paths: Any) -> str:
    return _digest(scope_snapshot(tools, paths))


class Requester(LeaseHolder, Protocol):
    """The run a proposal comes from, at the generation that holds it, such as a call's scope."""

    @property
    def workspace_id(self) -> UUID: ...


@dataclass(frozen=True)
class ApprovalProposal:
    """What a held call asks a person to approve, built once per dispatch by the gateway.

    SP-013 binds the operation's identity, its tool version, the argument hash and the scope.
    Decision 0015 adds the scope snapshot, the policy version and the rule that held the call.
    Every field is required, so no request is stored without them. `resource_target` is None when
    the tool names no target, and `review_detail` when it has no review (PRD-Studio GH-06)."""

    operation_id: str
    tool_id: str
    tool_version: int
    operation_class: str
    argument_hash: str
    arguments: dict[str, Any]
    scope: dict[str, Any]
    policy_version: str
    policy_rule: str
    policy_reason: str
    resource_target: str | None
    review_detail: dict[str, Any] | None

    @property
    def scope_hash(self) -> str:
        """Computed from the snapshot, so the two always agree (Decision 0015)."""
        return _digest(self.scope)


def requesting_agent(expert_id: UUID | None, expert_version: int | None) -> dict[str, Any]:
    """The Expert the run belongs to, or the coordinator when it has none, Decision 0015."""
    if expert_id is None:
        return {"kind": "coordinator"}
    return {"kind": "expert", "id": str(expert_id), "version": expert_version}


async def _version(connection: Any, run_id: UUID) -> int:
    cursor = await connection.execute("select version from public.runs where id = %s", (run_id,))
    version: int = (await cursor.fetchone())[0]
    return version


def _requested(approval_id: UUID, tool_id: str) -> ApprovalRequested:
    return ApprovalRequested(type="approval.requested", approval_id=approval_id, tool_id=tool_id)


async def _reopen(
    connection: Any,
    run_id: UUID,
    approval_id: UUID,
    tool_id: str,
    ttl_seconds: int,
    review_detail: dict[str, Any] | None = None,
) -> None:
    """Approved back to pending, with nobody's decision on it, not consumed, a fresh expiry, and
    announced. A new review detail replaces the stored one, and None keeps it. Its callers hold the
    request's row lock, having read it approved."""
    await connection.execute(
        "update public.approval_requests set status = %s, decided_by = null, "
        "decided_at = null, consumed_at = null, "
        "expires_at = clock_timestamp() + make_interval(secs => %s), "
        "review_detail = coalesce(%s::jsonb, review_detail) where id = %s and status = any(%s)",
        (
            ApprovalStatus.PENDING.value,
            ttl_seconds,
            None if review_detail is None else json.dumps(review_detail),
            approval_id,
            approval_sources(ApprovalCommand.RETURN_TO_REVIEW, ApprovalStatus.PENDING),
        ),
    )
    await append_event(connection, run_id, _requested(approval_id, tool_id))


async def _consume(connection: Any, approval_id: UUID) -> None:
    """The approval released a call that leaves no receipt, so it can't release another: the same
    call again goes back to a person (Decisions 0018 B6 and 0020 L5, SP-013). The request stays
    approved, as consuming is no move of its status. The gate holds the request's row lock."""
    await connection.execute(
        "update public.approval_requests set consumed_at = clock_timestamp() "
        "where id = %s and status = %s and consumed_at is null",
        (approval_id, ApprovalStatus.APPROVED.value),
    )


async def _enter_wait(connection: Any, run: Requester, approval_id: UUID) -> None:
    await apply_worker_command(
        connection, run, RunCommand.REQUEST_APPROVAL, detail=str(approval_id)
    )


async def _request_review(
    connection: Any, run: Requester, proposal: ApprovalProposal, ttl_seconds: int
) -> UUID:
    """Stores the request with every Decision 0015 field and announces it. Who asked is read from
    the run in this transaction, never from the call. Its status takes the column's default,
    pending, the one move a request starts with (ApprovalCommand.REQUEST)."""
    approval_id = uuid4()
    cursor = await connection.execute(
        "select started_by, expert_id, expert_version from public.runs where id = %s",
        (run.run_id,),
    )
    started_by, expert_id, expert_version = await cursor.fetchone()
    await connection.execute(
        "insert into public.approval_requests (id, workspace_id, run_id, operation_id, "
        "tool_id, tool_version, operation_class, argument_hash, arguments, scope_hash, "
        "policy_reason, resource_target, requested_by, requested_by_agent, "
        "scope_snapshot, policy_version, policy_rule, review_detail, expires_at) "
        "values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
        "clock_timestamp() + make_interval(secs => %s))",
        (
            approval_id,
            run.workspace_id,
            run.run_id,
            proposal.operation_id,
            proposal.tool_id,
            proposal.tool_version,
            proposal.operation_class,
            proposal.argument_hash,
            json.dumps(proposal.arguments),
            proposal.scope_hash,
            proposal.policy_reason,
            proposal.resource_target,
            started_by,
            json.dumps(requesting_agent(expert_id, expert_version)),
            json.dumps(proposal.scope),
            proposal.policy_version,
            proposal.policy_rule,
            None if proposal.review_detail is None else json.dumps(proposal.review_detail),
            ttl_seconds,
        ),
    )
    await append_event(connection, run.run_id, _requested(approval_id, proposal.tool_id))
    return approval_id


@dataclass(frozen=True)
class RequestRow:
    """The operation's approval request, as the gate reads it under the request's row lock."""

    approval_id: UUID
    status: ApprovalStatus
    scope_hash: str
    expired: bool
    # It released a call that left no receipt, so it can't release another (PTOL-06).
    consumed: bool = False


@dataclass(frozen=True)
class ReceiptState:
    """The operation's receipt, as the gate reads it: whether a person ruled on its last attempt,
    and the code that attempt failed with."""

    status: ReceiptStatus
    ruled: bool
    failure_code: str | None


class Gate(Enum):
    """What the gate does with a call that no refusal stopped."""

    RELEASE = "release"  # the effect may run
    REQUEST = "request"  # no request yet: store one, then wait for a person
    WAIT = "wait"  # a person hasn't decided yet
    REOPEN = "reopen"  # approved, but stale or consumed, nothing sent: back to a person, then wait


def gate_decision(
    row: RequestRow | None, scope_hash: str, receipt: ReceiptState | None
) -> Gate | GatewayCode:
    """The decision table. `scope_hash` is the call's current scope. `receipt` is the operation's
    receipt, or None when it has none, and is consulted only for an approved request."""
    if row is None:
        return Gate.REQUEST
    if row.status is ApprovalStatus.PENDING:
        return GatewayCode.APPROVAL_EXPIRED if row.expired else Gate.WAIT
    if row.status is not ApprovalStatus.APPROVED:
        rejected = row.status is ApprovalStatus.REJECTED
        return GatewayCode.APPROVAL_REJECTED if rejected else GatewayCode.APPROVAL_EXPIRED
    if row.scope_hash != scope_hash:
        return GatewayCode.APPROVAL_SCOPE_CHANGED
    if receipt_may_have_sent(None if receipt is None else receipt.status):
        # It was already sent, or may have been. Its receipt answers that, whatever the date, and
        # refusing here would report an effect that happened as not happening (Decision 0025 V8).
        return Gate.RELEASE
    if receipt is not None and not receipt.ruled and receipt.failure_code != LEASE_LOST:
        # A failure nobody ruled on used this decision. A ruling grants one more try. An attempt
        # whose lease was lost wrote nothing and wasn't the run's current owner's, so the decision
        # still stands for that owner.
        return GatewayCode.APPROVAL_CONSUMED
    # A consumed approval released a call that left no receipt, so this one needs a person again.
    return Gate.REOPEN if row.expired or row.consumed else Gate.RELEASE


async def _request_row(connection: Any, operation_id: str) -> RequestRow | None:
    """Locked until the gate's transaction ends, so concurrent attempts decide one at a time."""
    cursor = await connection.execute(
        "select id, status, scope_hash, expires_at <= clock_timestamp(), "
        "consumed_at is not null from public.approval_requests where operation_id = %s for update",
        (operation_id,),
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    return RequestRow(row[0], ApprovalStatus(row[1]), row[2], bool(row[3]), bool(row[4]))


async def _receipt_state(connection: Any, operation_id: str) -> ReceiptState | None:
    cursor = await connection.execute(
        "select status, reconciled_at, failure_code from app_private.tool_receipts "
        "where operation_id = %s",
        (operation_id,),
    )
    row = await cursor.fetchone()
    return None if row is None else ReceiptState(ReceiptStatus(row[0]), row[1] is not None, row[2])


async def approval_gate(
    connection: Any,
    run: Requester,
    proposal: ApprovalProposal,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> GatewayCode | None:
    """None releases the operation. Any code means no effect, and says why. Releasing a call that
    leaves no receipt consumes its approval in this transaction (PTOL-06)."""
    async with connection.transaction():
        row = await _request_row(connection, proposal.operation_id)
        receipt = (
            await _receipt_state(connection, proposal.operation_id)
            if row is not None and row.status is ApprovalStatus.APPROVED
            else None
        )
        decision = gate_decision(row, proposal.scope_hash, receipt)
        if isinstance(decision, GatewayCode):
            return decision
        if decision is Gate.RELEASE:
            if row is not None and not leaves_receipt(OperationClass(proposal.operation_class)):
                # Fenced like the wait: a worker that lost the run consumes nothing, and its
                # LeaseLost rolls this transaction back (SP-012).
                await hold_lease(connection, run)
                await _consume(connection, row.approval_id)
            return None
        if row is None:
            approval_id = await _request_review(connection, run, proposal, ttl_seconds)
        else:
            approval_id = row.approval_id
            if decision is Gate.REOPEN:
                # Nothing was sent, so this is only stale. A person can look at it again.
                await _reopen(connection, run.run_id, approval_id, proposal.tool_id, ttl_seconds)
        await _enter_wait(connection, run, approval_id)
        return GatewayCode.APPROVAL_PENDING


async def return_to_review(
    connection: Any,
    holder: LeaseHolder,
    *,
    operation_id: str,
    tool_id: str,
    detail: dict[str, Any],
) -> UUID | None:
    """Nothing was sent, so the approved request goes back to a person with `detail`, and this
    attempt's receipt is settled, so its next approval can send (Decision 0022 D15). Returns the
    request, or None when the operation has no approved request and nothing changed.

    One transaction under the lease: a worker that lost the run leaves the decision as it was, and
    the receipt, the request and its event commit together (SP-010, SP-012). The run makes no
    transition here and keeps running; it enters the decision wait when the call is tried again
    (Decision 0028 E1).
    """
    async with connection.transaction():
        await hold_lease(connection, holder)
        cursor = await connection.execute(
            "select id from public.approval_requests "
            "where operation_id = %s and run_id = %s and status = 'approved' for update",
            (operation_id, holder.run_id),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        approval_id: UUID = row[0]
        await receipts.settle_for_review(connection, operation_id, holder.run_id)
        await _reopen(connection, holder.run_id, approval_id, tool_id, DEFAULT_TTL_SECONDS, detail)
    return approval_id


async def _lock_job(connection: Any, run_id: UUID) -> None:
    """The run's job row, in the caller's transaction: every path that moves a run or its requests
    takes it first, as a transition does (SP-012)."""
    await connection.execute(
        "select 1 from app_private.run_jobs where run_id = %s for update", (run_id,)
    )


async def expire(connection: Any, approval_id: UUID, run_id: UUID, workspace_id: UUID) -> bool:
    """Expiry is not consent. The wait ends, the run pauses, and the operation stays unapproved.

    Only a pending request expires. A pass that read it pending before a person decided it or the
    run was cancelled matches no row and writes nothing else, so an expiry never overwrites a
    decision or a withdrawal. Returns whether it expired the request.

    The run's job row is locked first, in the caller's transaction, as every transition locks it
    before the run's row, so an expiry and a person's cancel can't deadlock (SP-012)."""
    await _lock_job(connection, run_id)
    cursor = await connection.execute(
        "update public.approval_requests set status = %s where id = %s and status = any(%s) "
        "returning id",
        (
            ApprovalStatus.EXPIRED.value,
            approval_id,
            approval_sources(ApprovalCommand.EXPIRE, ApprovalStatus.EXPIRED),
        ),
    )
    if await cursor.fetchone() is None:
        return False
    await connection.execute(
        "update app_private.run_obligations set status = 'met', response = 'expired', "
        "met_at = now() where run_id = %s and kind = 'approval' and status = 'open'",
        (run_id,),
    )
    await append_event(
        connection,
        run_id,
        ApprovalDecided(type="approval.decided", approval_id=approval_id, decision="expired"),
    )
    if await current_status(connection, run_id) is RunStatus.WAITING_APPROVAL:
        # The system's pause, not a person's: it leaves a live owner its job, as theirs would
        # (Decision 0029 F5).
        await cascade_command(
            connection, workspace_id=workspace_id, run_id=run_id, command=RunCommand.PAUSE
        )
    return True


async def expire_due(connection: Any) -> int:
    """Expires every pending request past its expiry, each in its own transaction, and returns how
    many it expired."""
    cursor = await connection.execute(
        "select id, run_id, workspace_id from public.approval_requests "
        "where status = 'pending' and expires_at <= clock_timestamp()"
    )
    rows = await cursor.fetchall()
    expired = 0
    for approval_id, run_id, workspace_id in rows:
        async with connection.transaction():
            expired += await expire(connection, approval_id, run_id, workspace_id)
    return expired


async def withdraw_pending(connection: Any, run_id: UUID) -> None:
    """A cancelled run's waiting requests, in the cancel's transaction (SP-010)."""
    await connection.execute(
        "update public.approval_requests set status = %s where run_id = %s and status = any(%s)",
        (
            ApprovalStatus.WITHDRAWN.value,
            run_id,
            approval_sources(ApprovalCommand.WITHDRAW, ApprovalStatus.WITHDRAWN),
        ),
    )


def _decided(decision: ApprovalVerdict) -> ApprovalStatus:
    match decision:
        case "approve":
            return ApprovalStatus.APPROVED
        case "reject":
            return ApprovalStatus.REJECTED
        case _:
            assert_never(decision)


async def decide(
    connection: Any,
    *,
    workspace_id: UUID,
    actor_id: UUID,
    approval_id: UUID,
    idempotency_key: str,
    decision: ApprovalVerdict,
    argument_hash: str,
) -> DecisionResult:
    """Valid only for this workspace, while pending and unexpired, for the arguments reviewed."""
    wanted = _decided(decision)
    command = Idempotent.of(
        CommandKey(workspace_id, actor_id, idempotency_key),
        "decide_approval",
        str(approval_id),
        {"decision": decision, "argument_hash": argument_hash},
    )
    expired_row = False
    async with connection.transaction():
        existing = await command.replayed(connection, ApprovalDecisionReceipt)
        if existing is not None:
            return DecisionResult(approval_id, existing.status, True)
        # A request's run never changes, so it is read before any lock. Then the job's row, the
        # run's and the request's, in the order a person's cancel takes them as it withdraws
        # pending requests, so a decision and a cancel can't deadlock (SP-012).
        cursor = await connection.execute(
            "select run_id from public.approval_requests where id = %s and workspace_id = %s",
            (approval_id, workspace_id),
        )
        found = await cursor.fetchone()
        if found is None:
            raise ApprovalRefused("approval_not_found")
        await _lock_job(connection, found[0])
        await connection.execute("select 1 from public.runs where id = %s for update", (found[0],))
        cursor = await connection.execute(
            "select run_id, status, argument_hash, expires_at <= clock_timestamp(), "
            "arguments::text from public.approval_requests "
            "where id = %s and workspace_id = %s for update",
            (approval_id, workspace_id),
        )
        row = await cursor.fetchone()
        if row is None:
            raise ApprovalRefused("approval_not_found")
        run_id, status, stored_hash, expired, arguments = row
        if stored_hash != argument_hash:
            raise ApprovalRefused("approval_mismatch")
        pending = status == ApprovalStatus.PENDING
        if wanted is ApprovalStatus.APPROVED and pending and exceeds_review_limit(arguments):
            # The hash proves what's stored, not what anyone read.
            raise ApprovalRefused("approval_too_large")
        if not pending:
            if status == wanted:
                return DecisionResult(approval_id, wanted, True)
            raise ApprovalRefused("approval_already_decided")
        if expired:
            # Read pending under this row's lock, so the expiry always moves it.
            await expire(connection, approval_id, run_id, workspace_id)
            expired_row = True
        else:
            try:
                await apply_command(
                    connection,
                    workspace_id=workspace_id,
                    run_id=run_id,
                    command=RunCommand.DECIDE_APPROVAL,
                    expected_version=await _version(connection, run_id),
                    response=wanted.value,
                )
            except CommandRefused:
                raise ApprovalRefused("approval_run_not_waiting") from None
            await connection.execute(
                "update public.approval_requests set status = %s, decided_by = %s, "
                "decided_at = now(), expires_at = clock_timestamp() + make_interval(secs => %s) "
                "where id = %s and status = any(%s)",
                (
                    wanted.value,
                    actor_id,
                    DEFAULT_TTL_SECONDS,
                    approval_id,
                    approval_sources(ApprovalCommand.DECIDE, wanted),
                ),
            )
            await append_event(
                connection,
                run_id,
                ApprovalDecided(
                    type="approval.decided",
                    approval_id=approval_id,
                    decision="approved" if wanted is ApprovalStatus.APPROVED else "rejected",
                ),
            )
            await command.store(connection, ApprovalDecisionReceipt(status=wanted))
    if expired_row:
        raise ApprovalRefused("approval_expired")
    return DecisionResult(approval_id, wanted, False)


# The settled statuses the decided list shows (PRD-Studio AP-02), as stored strings.
DECIDED = tuple(
    status.value
    for status in (
        ApprovalStatus.APPROVED,
        ApprovalStatus.REJECTED,
        ApprovalStatus.EXPIRED,
        ApprovalStatus.WITHDRAWN,
    )
)


async def list_approvals(
    connection: Any, workspace_id: UUID, statuses: str | tuple[str, ...]
) -> list[dict[str, Any]]:
    """PRD-Studio AP-01 and AP-02: requests in these statuses, with the run's goal, the plan task
    the call served (through its tool use's operation ID), who decided it and when, and the size of
    the stored arguments."""
    cursor = await connection.execute(
        "select a.id, a.run_id, a.tool_id, a.tool_version, a.operation_class, a.argument_hash, "
        "a.arguments::text, a.status, a.expires_at, a.policy_reason, a.resource_target, "
        "a.requested_by, a.requested_by_agent, a.scope_snapshot, a.policy_version, "
        "a.policy_rule, e.name, r.goal_summary, "
        "(select t ->> 'title' from app_private.tool_uses u "
        "join app_private.plan_versions p on p.run_id = u.run_id, "
        "jsonb_array_elements(p.tasks) t "
        "where u.operation_id = a.operation_id and t ->> 'id' = u.task_id "
        "order by p.version desc limit 1), "
        "a.decided_at, a.decided_by, d.display_name, "
        "octet_length(a.arguments::text), a.review_detail "
        "from public.approval_requests a left join public.experts e "
        "on e.id = (a.requested_by_agent ->> 'id')::uuid and e.workspace_id = a.workspace_id "
        "left join public.runs r on r.id = a.run_id and r.workspace_id = a.workspace_id "
        "left join public.user_profiles d on d.user_id = a.decided_by "
        "where a.workspace_id = %s and a.status = any(%s) "
        "order by coalesce(a.decided_at, a.created_at) desc limit 200",
        (workspace_id, [statuses] if isinstance(statuses, str) else list(statuses)),
    )
    names = (
        "id",
        "run_id",
        "tool_id",
        "tool_version",
        "operation_class",
        "argument_hash",
        "arguments",
        "status",
        "expires_at",
        "policy_reason",
        "resource_target",
        "requested_by",
        "requested_by_agent",
        "scope_snapshot",
        "policy_version",
        "policy_rule",
        "expert_name",
        "run_goal",
        "task_title",
        "decided_at",
        "decided_by",
        "decided_by_name",
        "arguments_bytes",
        "review_detail",
    )
    return [dict(zip(names, row, strict=True)) for row in await cursor.fetchall()]


async def approval_counts(connection: Any, workspace_id: UUID) -> tuple[int, int]:
    """Waiting and decided counts, so a tab or badge never counts a listed page."""
    cursor = await connection.execute(
        "select count(*) filter (where status = 'pending'), "
        "count(*) filter (where status = any(%s)) "
        "from public.approval_requests where workspace_id = %s",
        (list(DECIDED), workspace_id),
    )
    row = await cursor.fetchone()
    return int(row[0]), int(row[1])
