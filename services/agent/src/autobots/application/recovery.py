"""What an interruption left behind, classified before anything is dispatched, SP-012 and MP-08, and
whether a saved run can continue under this release at all (domain/execution.py)."""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from autobots.application import receipts
from autobots.application.model_admission import InvocationStatus, ModelAdmission, SettlementReason
from autobots.application.runs import RUN_TREE
from autobots.domain.execution import incompatibility


@dataclass(frozen=True)
class Outstanding:
    """Known unknowns. Each stays visible until someone reconciles it from evidence."""

    uncertain_calls: int
    unknown_effects: int
    # The call worked and the provider named no charge, so only the amount is open.
    unreported_charges: int = 0


async def classify_interrupted(connection: Any, run_id: UUID, generation: int) -> None:
    """A dead owner's work: never sent is nothing, and sent may have happened. The ledger and the
    receipts each keep their one writer (PRUN-09, Decision 0029 F8)."""
    await ModelAdmission(connection).close_interrupted(run_id)
    await receipts.mark_unknown(connection, run_id, generation)


async def outstanding(connection: Any, run_id: UUID) -> Outstanding:
    cursor = await connection.execute(
        "select count(*) filter (where failure_class is distinct from %(unreported)s), "
        "count(*) filter (where failure_class = %(unreported)s) "
        "from app_private.model_invocations where (run_id = %(run)s or root_run_id = %(run)s) "
        "and status = %(uncertain)s and reconciled_at is null",
        {
            "unreported": SettlementReason.CHARGE_NOT_REPORTED.value,
            "run": run_id,
            "uncertain": InvocationStatus.UNCERTAIN.value,
        },
    )
    calls, unreported = await cursor.fetchone()
    cursor = await connection.execute(
        RUN_TREE + "select count(*) from app_private.tool_receipts "
        "where run_id in (select id from tree) and status = 'unknown'",
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


async def execution_block(connection: Any, run_id: UUID) -> str | None:
    """Why a saved run can't continue under this release, or None. It stays as it was saved. The
    worker checks it before a pass, and a resume before it is accepted."""
    cursor = await connection.execute(
        "select execution_contract from public.runs where id = %s", (run_id,)
    )
    row = await cursor.fetchone()
    return incompatibility(None if row is None else row[0])
