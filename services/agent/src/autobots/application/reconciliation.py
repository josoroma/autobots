"""Unknown effects, kept visible until evidence resolves them, SP-012 and PRD 10.1.

The gateway reads back from the destination when the tool can. When it can't, a person reports what
the destination's own records show. Nothing here treats an outcome as known without one of those.
"""

import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from autobots.application.runs import (
    append_event,
    existing_receipt,
    request_hash,
    store_receipt,
)


class ReconciliationRefused(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class UnknownOperation:
    operation_id: str
    tool_id: str
    tool_version: int


async def unknown_operations(connection: Any, run_id: UUID) -> list[UnknownOperation]:
    cursor = await connection.execute(
        "with recursive tree as (select id from public.runs where id = %s union all "
        "select r.id from public.runs r join tree t on r.parent_run_id = t.id) "
        "select operation_id, tool_id, tool_version from app_private.tool_receipts "
        "where run_id in (select id from tree) and status = 'unknown' order by created_at",
        (run_id,),
    )
    return [UnknownOperation(row[0], row[1], row[2]) for row in await cursor.fetchall()]


async def has_unresolvable_effect(connection: Any, run_id: UUID) -> bool:
    cursor = await connection.execute(
        "with recursive tree as (select id from public.runs where id = %s union all "
        "select r.id from public.runs r join tree t on r.parent_run_id = t.id) "
        "select exists (select 1 from app_private.tool_receipts "
        "where run_id in (select id from tree) and status = 'unknown' and not can_readback)",
        (run_id,),
    )
    return bool((await cursor.fetchone())[0])


async def record_evidence(
    connection: Any,
    *,
    workspace_id: UUID,
    run_id: UUID,
    operation_id: str,
    actor_id: UUID,
    idempotency_key: str,
    outcome: str,
    evidence: str,
) -> str:
    """Delivered closes the operation with no retry. Not delivered allows one fresh attempt."""
    scope = (workspace_id, actor_id, "reconcile_effect", operation_id, idempotency_key)
    fingerprint = request_hash({"outcome": outcome, "evidence": evidence})
    status = "succeeded" if outcome == "delivered" else "failed"
    async with connection.transaction():
        existing = await existing_receipt(connection, scope, fingerprint)
        if existing is not None:
            return str(existing["status"])
        # A parent's page lists its children's effects, so it can settle them too.
        cursor = await connection.execute(
            "with recursive tree as (select id from public.runs where id = %s union all "
            "select r.id from public.runs r join tree t on r.parent_run_id = t.id) "
            "select status from app_private.tool_receipts "
            "where operation_id = %s and run_id in (select id from tree) and workspace_id = %s "
            "for update",
            (run_id, operation_id, workspace_id),
        )
        row = await cursor.fetchone()
        if row is None:
            raise ReconciliationRefused("operation_not_found")
        if row[0] != "unknown":
            raise ReconciliationRefused("operation_not_unknown")
        result = {"reconciled": "operator"} if outcome == "delivered" else None
        await connection.execute(
            "update app_private.tool_receipts set status = %s, result = %s, evidence = %s, "
            "reconciled_by = %s, reconciled_at = now(), updated_at = now() "
            "where operation_id = %s",
            (status, json.dumps(result) if result else None, evidence, actor_id, operation_id),
        )
        await append_event(
            connection,
            run_id,
            {"type": "effect.reconciled", "operation_id": operation_id, "outcome": outcome},
        )
        await store_receipt(connection, scope, fingerprint, {"status": status})
    return status
