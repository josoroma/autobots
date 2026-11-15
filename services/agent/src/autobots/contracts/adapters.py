"""Explicit conversion between rows, the domain and public DTOs."""

from autobots.contracts.runs import BudgetCounters, RunSummary
from autobots.domain.runs import Run, RunStatus
from autobots.persistence.rows import RunRow


def run_from_row(row: RunRow) -> Run:
    """An unknown stored status raises, instead of reaching a client. The ledger's charged figure
    is what the run has spent (Decision 0029 F10)."""
    return Run(
        id=row.id,
        workspace_id=row.workspace_id,
        parent_run_id=row.parent_run_id,
        status=RunStatus(row.status),
        created_at=row.created_at,
        updated_at=row.updated_at,
        spent_micro_usd=row.charged_micro_usd,
        reserved_micro_usd=row.reserved_micro_usd,
        limit_micro_usd=row.limit_micro_usd,
        lease_generation=row.lease_generation,
        checkpoint_thread_id=row.checkpoint_thread_id,
        version=row.version,
    )


def run_summary_from_domain(run: Run) -> RunSummary:
    """Names each public field, so a new domain field stays private by default."""
    return RunSummary(
        schema_version=1,
        version=run.version,
        id=run.id,
        workspace_id=run.workspace_id,
        parent_run_id=run.parent_run_id,
        status=run.status,
        created_at=run.created_at,
        updated_at=run.updated_at,
        budget=BudgetCounters(
            spent_micro_usd=run.spent_micro_usd,
            reserved_micro_usd=run.reserved_micro_usd,
            limit_micro_usd=run.limit_micro_usd,
        ),
    )
