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


def scope_hash(tools: Any, paths: Any) -> str:
    encoded = json.dumps({"tools": dict(tools), "paths": list(paths)}, sort_keys=True)
    return hashlib.sha256(encoded.encode()).hexdigest()


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
            await connection.execute(
                "insert into public.approval_requests (id, workspace_id, run_id, operation_id, "
                "tool_id, tool_version, operation_class, argument_hash, arguments, scope_hash, "
                "expires_at) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
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
            return None if stored_scope == current_scope_hash else "approval_scope_changed"
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
                "decided_at = now() where id = %s",
                (wanted, actor_id, approval_id),
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


async def list_approvals(connection: Any, workspace_id: UUID, status: str) -> list[dict[str, Any]]:
    cursor = await connection.execute(
        "select id, run_id, tool_id, tool_version, operation_class, argument_hash, "
        "arguments::text, status, expires_at from public.approval_requests "
        "where workspace_id = %s and status = %s order by created_at desc limit 200",
        (workspace_id, status),
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
    )
    return [dict(zip(names, row, strict=True)) for row in await cursor.fetchall()]
