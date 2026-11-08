"""Proposals bound to exact arguments, and decisions validated against them, PRD 9.2.

A worker stops at a proposal, with nothing done. Its checkpoint holds the pending tool call, so the
tool step runs again after the decision and finds the answer here. Only the approved operation's
own identity can pass, so a changed argument is a different operation that needs its own approval.
"""

import hashlib
import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from autobots.application.runs import (
    Actor,
    CommandRefused,
    append_event,
    apply_command,
    existing_receipt,
    request_hash,
    store_receipt,
)
from autobots.domain.runs import RunCommand, RunStatus

DEFAULT_TTL_SECONDS = 86_400


# What a reviewer can be shown whole. Anything longer can be rejected, not approved.
ARGUMENT_LIMIT = 64_000


def exceeds_review_limit(arguments: str) -> bool:
    return len(arguments) > ARGUMENT_LIMIT


class ApprovalRefused(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class DecisionResult:
    approval_id: UUID
    status: str
    replayed: bool


def scope_snapshot(tools: Any, paths: Any) -> dict[str, Any]:
    """The grants a request was made under, stored whole with it, Decision 0015."""
    return {"tools": dict(tools), "paths": list(paths)}


def scope_hash(tools: Any, paths: Any) -> str:
    encoded = json.dumps(scope_snapshot(tools, paths), sort_keys=True)
    return hashlib.sha256(encoded.encode()).hexdigest()


def requesting_agent(expert_id: UUID | None, expert_version: int | None) -> dict[str, Any]:
    """The Expert the run belongs to, or the coordinator when it has none, Decision 0015."""
    if expert_id is None:
        return {"kind": "coordinator"}
    return {"kind": "expert", "id": str(expert_id), "version": expert_version}


async def _version(connection: Any, run_id: UUID) -> int:
    cursor = await connection.execute("select version from public.runs where id = %s", (run_id,))
    version: int = (await cursor.fetchone())[0]
    return version


async def _enter_wait(
    connection: Any, workspace_id: UUID, run_id: UUID, generation: int, detail: str
) -> None:
    await apply_command(
        connection,
        workspace_id=workspace_id,
        run_id=run_id,
        command=RunCommand.REQUEST_APPROVAL,
        actor=Actor.WORKER,
        expected_version=await _version(connection, run_id),
        generation=generation,
        detail=detail,
    )


async def approval_gate(
    connection: Any,
    *,
    workspace_id: UUID,
    run_id: UUID,
    generation: int,
    operation_id: str,
    tool_id: str,
    tool_version: int,
    operation_class: str,
    argument_hash: str,
    arguments: dict[str, Any],
    current_scope_hash: str,
    policy_reason: str,
    resource_target: str | None,
    scope: dict[str, Any] | None = None,
    policy_version: str | None = None,
    policy_rule: str | None = None,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> str | None:
    """None releases the operation. Any code means no effect, and says why."""
    async with connection.transaction():
        cursor = await connection.execute(
            "select id, status, scope_hash, expires_at <= clock_timestamp() "
            "from public.approval_requests where operation_id = %s for update",
            (operation_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            approval_id = uuid4()
            # Who asked is read from the run in this transaction, never from the call.
            cursor = await connection.execute(
                "select started_by, expert_id, expert_version from public.runs where id = %s",
                (run_id,),
            )
            started_by, expert_id, expert_version = await cursor.fetchone()
            await connection.execute(
                "insert into public.approval_requests (id, workspace_id, run_id, operation_id, "
                "tool_id, tool_version, operation_class, argument_hash, arguments, scope_hash, "
                "policy_reason, resource_target, requested_by, requested_by_agent, "
                "scope_snapshot, policy_version, policy_rule, expires_at) "
                "values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
                "clock_timestamp() + make_interval(secs => %s))",
                (
                    approval_id,
                    workspace_id,
                    run_id,
                    operation_id,
                    tool_id,
                    tool_version,
                    operation_class,
                    argument_hash,
                    json.dumps(arguments),
                    current_scope_hash,
                    policy_reason,
                    resource_target,
                    started_by,
                    json.dumps(requesting_agent(expert_id, expert_version)),
                    None if scope is None else json.dumps(scope),
                    policy_version,
                    policy_rule,
                    ttl_seconds,
                ),
            )
            await append_event(
                connection,
                run_id,
                {"type": "approval.requested", "approval_id": str(approval_id), "tool_id": tool_id},
            )
            await _enter_wait(connection, workspace_id, run_id, generation, str(approval_id))
            return "approval_pending"
        approval_id, status, stored_scope, expired = row
        if status == "pending":
            if expired:
                return "approval_expired"
            await _enter_wait(connection, workspace_id, run_id, generation, str(approval_id))
            return "approval_pending"
        if status == "approved":
            if stored_scope != current_scope_hash:
                return "approval_scope_changed"
            cursor = await connection.execute(
                "select status, reconciled_at from app_private.tool_receipts "
                "where operation_id = %s",
                (operation_id,),
            )
            receipt = await cursor.fetchone()
            if receipt is not None and receipt[0] != "failed":
                # It was already sent, or may have been. Its receipt answers that, whatever the
                # date, and refusing here would report an effect that happened as not happening.
                return None
            if receipt is not None and receipt[1] is None:
                # A failure nobody ruled on used this decision. A ruling grants one more try.
                return "approval_consumed"
            if expired:
                # Nothing was sent, so this is only stale. A person can look at it again.
                await connection.execute(
                    "update public.approval_requests set status = 'pending', decided_by = null, "
                    "decided_at = null, expires_at = clock_timestamp() + make_interval(secs => %s) "
                    "where id = %s",
                    (ttl_seconds, approval_id),
                )
                await append_event(
                    connection,
                    run_id,
                    {
                        "type": "approval.requested",
                        "approval_id": str(approval_id),
                        "tool_id": tool_id,
                    },
                )
                await _enter_wait(connection, workspace_id, run_id, generation, str(approval_id))
                return "approval_pending"
            return None
        return "approval_rejected" if status == "rejected" else "approval_expired"


async def _expire(connection: Any, approval_id: UUID, run_id: UUID, workspace_id: UUID) -> None:
    """Expiry is not consent. The wait ends, the run pauses, and the operation stays unapproved."""
    await connection.execute(
        "update public.approval_requests set status = 'expired' where id = %s", (approval_id,)
    )
    await connection.execute(
        "update app_private.run_obligations set status = 'met', response = 'expired', "
        "met_at = now() where run_id = %s and kind = 'approval' and status = 'open'",
        (run_id,),
    )
    await append_event(
        connection,
        run_id,
        {"type": "approval.decided", "approval_id": str(approval_id), "decision": "expired"},
    )
    cursor = await connection.execute("select status from public.runs where id = %s", (run_id,))
    if (await cursor.fetchone())[0] == RunStatus.WAITING_APPROVAL.value:
        await apply_command(
            connection,
            workspace_id=workspace_id,
            run_id=run_id,
            command=RunCommand.PAUSE,
            actor=Actor.USER,
            expected_version=await _version(connection, run_id),
        )


async def expire_due(connection: Any) -> int:
    cursor = await connection.execute(
        "select id, run_id, workspace_id from public.approval_requests "
        "where status = 'pending' and expires_at <= clock_timestamp()"
    )
    rows = await cursor.fetchall()
    for approval_id, run_id, workspace_id in rows:
        async with connection.transaction():
            await _expire(connection, approval_id, run_id, workspace_id)
    return len(rows)


async def decide(
    connection: Any,
    *,
    workspace_id: UUID,
    actor_id: UUID,
    approval_id: UUID,
    idempotency_key: str,
    decision: str,
    argument_hash: str,
) -> DecisionResult:
    """Valid only for this workspace, while pending and unexpired, for the arguments reviewed."""
    wanted = "approved" if decision == "approve" else "rejected"
    fingerprint = request_hash({"decision": decision, "argument_hash": argument_hash})
    scope = (workspace_id, actor_id, "decide_approval", str(approval_id), idempotency_key)
    expired_row = False
    async with connection.transaction():
        existing = await existing_receipt(connection, scope, fingerprint)
        if existing is not None:
            return DecisionResult(approval_id, existing["status"], True)
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
        if decision == "approve" and status == "pending" and exceeds_review_limit(arguments):
            # The hash proves what's stored, not what anyone read.
            raise ApprovalRefused("approval_too_large")
        if status != "pending":
            if status == wanted:
                return DecisionResult(approval_id, status, True)
            raise ApprovalRefused("approval_already_decided")
        if expired:
            await _expire(connection, approval_id, run_id, workspace_id)
            expired_row = True
        else:
            try:
                await apply_command(
                    connection,
                    workspace_id=workspace_id,
                    run_id=run_id,
                    command=RunCommand.DECIDE_APPROVAL,
                    actor=Actor.USER,
                    expected_version=await _version(connection, run_id),
                    response=wanted,
                )
            except CommandRefused:
                raise ApprovalRefused("approval_run_not_waiting") from None
            await connection.execute(
                "update public.approval_requests set status = %s, decided_by = %s, "
                "decided_at = now(), expires_at = clock_timestamp() + make_interval(secs => %s) "
                "where id = %s",
                (wanted, actor_id, DEFAULT_TTL_SECONDS, approval_id),
            )
            await append_event(
                connection,
                run_id,
                {"type": "approval.decided", "approval_id": str(approval_id), "decision": wanted},
            )
            await store_receipt(connection, scope, fingerprint, {"status": wanted})
    if expired_row:
        raise ApprovalRefused("approval_expired")
    return DecisionResult(approval_id, wanted, False)


DECIDED = ("approved", "rejected", "expired", "withdrawn")


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
        "octet_length(a.arguments::text) "
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
