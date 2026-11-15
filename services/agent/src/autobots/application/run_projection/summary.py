"""A run's summary: the row each of its views starts from (SP-011)."""

from uuid import UUID

from autobots.application.model_admission import LEDGER_PARAMS, spend_columns
from autobots.application.runs import RunNotFound
from autobots.application.sql import SqlConnection, optional_row
from autobots.contracts.adapters import run_from_row, run_summary_from_domain
from autobots.contracts.runs import RunSummary
from autobots.persistence.rows import RunRow

# Spent and reserved are the ledger's, as admission counts them (Decision 0029 F10).
SELECT_RUN = (
    "select r.id, r.workspace_id, r.parent_run_id, r.status, r.created_at, r.updated_at, "
    f"{spend_columns('r')}, "
    "r.limit_micro_usd, r.lease_generation, r.checkpoint_thread_id, r.version, r.event_sequence "
    "from public.runs r where r.id = %(run)s and r.workspace_id = %(workspace)s"
)


def _run_params(workspace_id: UUID, run_id: UUID) -> dict[str, object]:
    return {"run": run_id, "workspace": workspace_id, **LEDGER_PARAMS}


async def run_row(connection: SqlConnection, workspace_id: UUID, run_id: UUID) -> RunRow | None:
    return await optional_row(connection, RunRow, SELECT_RUN, _run_params(workspace_id, run_id))


async def require_run(connection: SqlConnection, workspace_id: UUID, run_id: UUID) -> RunRow:
    row = await run_row(connection, workspace_id, run_id)
    if row is None:
        raise RunNotFound("that run is not available")
    return row


def summary_of(row: RunRow) -> RunSummary:
    return run_summary_from_domain(run_from_row(row))


async def read_summary(
    connection: SqlConnection, workspace_id: UUID, run_id: UUID
) -> RunSummary | None:
    """One statement, so it reads one snapshot without opening a transaction of its own."""
    row = await run_row(connection, workspace_id, run_id)
    return None if row is None else summary_of(row)
