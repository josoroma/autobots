"""What an interruption left behind, classified before anything is dispatched, SP-012 and MP-08."""

from dataclasses import dataclass
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class Outstanding:
    """Known unknowns. Each stays visible until someone reconciles it from evidence."""

    uncertain_calls: int
    unknown_effects: int
    # The call worked and the provider named no charge, so only the amount is open.
    unreported_charges: int = 0


async def classify_interrupted(connection: Any, run_id: UUID, generation: int) -> None:
    """A dead owner's work: never sent is nothing, and sent may have happened. A closed stream or a
    lost process doesn't prove a provider stopped."""
    await connection.execute(
        "update app_private.model_invocations set status = 'cancelled', charged_micro_usd = 0, "
        "failure_class = 'worker_lost', finished_at = now() "
        "where run_id = %s and status = 'reserved'",
        (run_id,),
    )
    await connection.execute(
        "update app_private.model_invocations set status = 'uncertain', "
        "failure_class = 'worker_lost', finished_at = now() "
        "where run_id = %s and status = 'dispatched'",
        (run_id,),
    )
    await connection.execute(
        "update app_private.tool_receipts set status = 'unknown', updated_at = now() "
        "where run_id = %s and status = 'started' and generation < %s",
        (run_id, generation),
    )


async def outstanding(connection: Any, run_id: UUID) -> Outstanding:
    cursor = await connection.execute(
        "select count(*) filter (where failure_class is distinct from 'charge_not_reported'), "
        "count(*) filter (where failure_class = 'charge_not_reported') "
        "from app_private.model_invocations where (run_id = %s or root_run_id = %s) "
        "and status = 'uncertain' and reconciled_at is null",
        (run_id, run_id),
    )
    calls, unreported = await cursor.fetchone()
    cursor = await connection.execute(
        "select count(*) from app_private.tool_receipts where run_id = %s and status = 'unknown'",
        (run_id,),
    )
    return Outstanding(calls, (await cursor.fetchone())[0], unreported)


async def open_obligation(connection: Any, run_id: UUID) -> tuple[str, str] | None:
    """An outstanding wait that a pause and resume must not skip."""
    cursor = await connection.execute(
        "select kind, detail from app_private.run_obligations "
        "where run_id = %s and status = 'open' order by created_at limit 1",
        (run_id,),
    )
    row = await cursor.fetchone()
    return (row[0], row[1]) if row else None
