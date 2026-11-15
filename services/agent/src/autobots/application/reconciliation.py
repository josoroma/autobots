"""Unknown effects, kept visible until evidence resolves them, SP-012 and PRD 10.1.

The gateway reads back from the destination when the tool can. When it can't, a person reports what
the destination's own records show. Nothing here treats an outcome as known without one of those.
"""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, assert_never
from uuid import UUID

from autobots.application import receipts
from autobots.application.model_admission import ModelAdmission
from autobots.application.recovery import execution_block, outstanding
from autobots.application.runs import RUN_TREE, CommandKey, Idempotent, append_event, require_run
from autobots.contracts.persisted import EffectRulingReceipt, ModelCallReconciliationReceipt
from autobots.contracts.run_commands import EffectOutcome
from autobots.contracts.runs import EffectReconciled
from autobots.domain.effects import ReceiptStatus
from autobots.domain.errors import Refusal, RefusalKind


class ReconciliationRefused(Refusal):
    kinds = MappingProxyType({"operation_not_found": RefusalKind.NOT_FOUND})


class ResumeBlocked(Refusal):
    """What must be settled before a paused run may resume: `incompatible_version`, a saved run
    this release can't continue; `uncertain_model_call`; or `unknown_effect`, one with no readback.
    Nothing changes."""


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


async def require_resumable(connection: Any, workspace_id: UUID, run_id: UUID) -> None:
    """A resume's preconditions, read in one place and refused in this order: the run is this
    workspace's, this release can continue it, no model call's outcome is open, and no effect
    waits on a person. A tool with a readback resolves itself on replay, so only an effect without
    one blocks. Raises RunNotFound or ResumeBlocked."""
    await require_run(connection, workspace_id, run_id)
    left = await outstanding(connection, run_id)
    blocked = await has_unresolvable_effect(connection, run_id)
    blocked_contract = await execution_block(connection, run_id)
    if blocked_contract is not None:
        raise ResumeBlocked("incompatible_version", detail=blocked_contract)
    if left.uncertain_calls:
        raise ResumeBlocked("uncertain_model_call")
    if blocked:
        raise ResumeBlocked("unknown_effect")


async def reconcile_oldest_uncertain_call(
    connection: Any,
    *,
    workspace_id: UUID,
    actor_id: UUID,
    run_id: UUID,
    idempotency_key: str,
    charged_micro_usd: int,
) -> int:
    """An owner's charge, seen in the provider's own account, settles the run tree's oldest open
    model call, under the command's idempotency key (US-4.8). Returns how many calls it settled, 0
    or 1, and a repeat returns the first answer. The caller has checked the run is the workspace's.
    Raises IdempotencyConflict."""
    command = Idempotent.of(
        CommandKey(workspace_id, actor_id, idempotency_key),
        "reconcile_model_call",
        str(run_id),
        {"charged": charged_micro_usd},
    )
    async with connection.transaction():
        existing = await command.replayed(connection, ModelCallReconciliationReceipt)
        if existing is not None:
            return existing.reconciled_calls
        cursor = await connection.execute(
            "select id from app_private.model_invocations "
            "where (run_id = %s or root_run_id = %s) "
            "and status = 'uncertain' and reconciled_at is null "
            "order by created_at limit 1 for update",
            (run_id, run_id),
        )
        row = await cursor.fetchone()
        if row is not None:
            await ModelAdmission(connection).reconcile(row[0], charged_micro_usd)
        reconciled = 0 if row is None else 1
        await command.store(connection, ModelCallReconciliationReceipt(reconciled_calls=reconciled))
    return reconciled
