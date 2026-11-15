"""Unknown effects, kept visible until evidence resolves them, SP-012 and PRD 10.1.

The gateway reads back from the destination when the tool can. When it can't, a person reports what
the destination's own records show. Nothing here treats an outcome as known without one of those.
"""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, assert_never
from uuid import UUID

from autobots.application import receipts
from autobots.application.runs import RUN_TREE, CommandKey, Idempotent, append_event
from autobots.contracts.persisted import EffectRulingReceipt
from autobots.contracts.run_commands import EffectOutcome
from autobots.contracts.runs import EffectReconciled
from autobots.domain.effects import ReceiptStatus
from autobots.domain.errors import Refusal, RefusalKind


class ReconciliationRefused(Refusal):
    kinds = MappingProxyType({"operation_not_found": RefusalKind.NOT_FOUND})


@dataclass(frozen=True)
class UnknownOperation:
    operation_id: str
    tool_id: str
    tool_version: int
    generation: int


async def unknown_operations(connection: Any, run_id: UUID) -> list[UnknownOperation]:
    cursor = await connection.execute(
        RUN_TREE
        + "select operation_id, tool_id, tool_version, generation from app_private.tool_receipts "
        "where run_id in (select id from tree) and status = 'unknown' order by created_at",
        (run_id,),
    )
    return [UnknownOperation(row[0], row[1], row[2], row[3]) for row in await cursor.fetchall()]


async def has_unresolvable_effect(connection: Any, run_id: UUID) -> bool:
    cursor = await connection.execute(
        RUN_TREE + "select exists (select 1 from app_private.tool_receipts "
        "where run_id in (select id from tree) and status = 'unknown' and not can_readback)",
        (run_id,),
    )
    return bool((await cursor.fetchone())[0])


def _ruled(outcome: EffectOutcome) -> ReceiptStatus:
    match outcome:
        case "delivered":
            return ReceiptStatus.SUCCEEDED
        case "not_delivered":
            return ReceiptStatus.FAILED
        case _:
            assert_never(outcome)


async def record_evidence(  # noqa: PLR0913 - baseline 2026-11-14, shrink only (STD-06)
    connection: Any,
    *,
    workspace_id: UUID,
    run_id: UUID,
    operation_id: str,
    actor_id: UUID,
    idempotency_key: str,
    outcome: EffectOutcome,
    evidence: str,
    generation: int | None = None,
) -> str:
    """Delivered closes the operation with no retry. Not delivered allows one fresh attempt."""
    command = Idempotent.of(
        CommandKey(workspace_id, actor_id, idempotency_key),
        "reconcile_effect",
        operation_id,
        {"outcome": outcome, "evidence": evidence},
    )
    status = _ruled(outcome)
    async with connection.transaction():
        existing = await command.replayed(connection, EffectRulingReceipt)
        if existing is not None:
            return existing.status.value
        # A parent's page lists its children's effects, so it can settle them too.
        cursor = await connection.execute(
            RUN_TREE + "select status, generation from app_private.tool_receipts "
            "where operation_id = %s and run_id in (select id from tree) and workspace_id = %s "
            "for update",
            (run_id, operation_id, workspace_id),
        )
        row = await cursor.fetchone()
        if row is None:
            raise ReconciliationRefused("operation_not_found")
        if row[0] != ReceiptStatus.UNKNOWN:
            raise ReconciliationRefused("operation_not_unknown")
        if generation is not None and row[1] != generation:
            raise ReconciliationRefused("operation_attempt_changed")
        await receipts.rule(connection, operation_id, receipts.Ruling(status, evidence, actor_id))
        await append_event(
            connection,
            run_id,
            EffectReconciled(type="effect.reconciled", operation_id=operation_id, outcome=outcome),
        )
        await command.store(connection, EffectRulingReceipt(status=status))
    return status.value
