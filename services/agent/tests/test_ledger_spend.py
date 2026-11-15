"""Spend is defined once, as admission counts it, and the views share it (Decision 0029 F10,
PRUN-09, XDUP-05).

Admission's statement keeps its bytes, so what stops spend is unchanged. The run projection, the
run list and the workflow overview build their figures from the same fragments: a root's figures
are exactly admission's rows, and a child, which no budget is scoped by, adds the calls it made
itself (US-11.12 N-9). The database checks show the two agree on a seeded ledger and a depth-2
tree; this pins the statements that make it so.
"""

from autobots.application import model_admission, run_projection, workflow_overview
from autobots.application.model_admission import (
    ACTIVE,
    LEDGER_PARAMS,
    OUTSTANDING,
    InvocationStatus,
    SettlementReason,
    shown_for,
    spend,
    spend_columns,
    under_root,
    unreported_column,
)
from autobots.application.model_attempts import FailureClass

# Admission's count, byte for byte: admission is unchanged (Decision 0029 F10).
ADMISSION = (
    "select "
    "count(*) filter (where status = any(%(active)s)), "
    "coalesce(sum(case when status = any(%(outstanding)s) then reserved_micro_usd "
    "else coalesce(charged_micro_usd, 0) end) "
    "filter (where spend_day = %(day)s), 0), "
    "coalesce(sum(case when status = any(%(outstanding)s) then reserved_micro_usd "
    "else coalesce(charged_micro_usd, 0) end) "
    "filter (where root_run_id = %(root)s), 0) "
    "from app_private.model_invocations where workspace_id = %(workspace)s"
)


def test_admissions_count_keeps_its_bytes() -> None:
    assert model_admission._USAGE == ADMISSION
    assert spend() in ADMISSION and f"filter (where {under_root('%(root)s')})" in ADMISSION


def test_the_ledger_states_and_sets_are_the_constraints() -> None:
    """The six states 20261105000006_model_invocations.sql allows, and the sets admission uses."""
    assert {status.value for status in InvocationStatus} == {
        "reserved",
        "dispatched",
        "succeeded",
        "failed_before_acceptance",
        "uncertain",
        "cancelled",
    }
    assert set(ACTIVE) == {InvocationStatus.RESERVED, InvocationStatus.DISPATCHED}
    assert set(OUTSTANDING) == {*ACTIVE, InvocationStatus.UNCERTAIN}
    assert LEDGER_PARAMS == {"outstanding": ["reserved", "dispatched", "uncertain"]}


def test_a_settlement_reason_is_no_provider_failure() -> None:
    assert not {reason.value for reason in SettlementReason} & {item.value for item in FailureClass}


def test_a_runs_figures_are_its_roots_rows_and_a_childs_own_calls() -> None:
    rows = shown_for("r")
    assert rows.startswith(f"({under_root('r.id', 'i')} or ")
    assert "(r.parent_run_id is not null and i.run_id = r.id)" in rows


def test_each_view_builds_its_figures_from_the_shared_fragments() -> None:
    columns = spend_columns("r")
    assert columns in run_projection._SELECT_RUN
    assert f"{columns}, {unreported_column('r')}" in run_projection._LIST_SELECT
    assert f"{columns}, {unreported_column('r')}" in workflow_overview._EXECUTIONS
    for statement in (
        run_projection._SELECT_RUN,
        run_projection._LIST_SELECT,
        workflow_overview._EXECUTIONS,
    ):
        assert "reconciled_at is null), 0)" not in statement
        assert "'reserved', 'dispatched', 'uncertain'" not in statement


def test_spent_and_reserved_split_admissions_case_between_them() -> None:
    """Charged where the cost is settled and reserved where it is open, so the two add up to
    admission's sum over the same rows."""
    columns = spend_columns("r")
    assert "sum(coalesce(i.charged_micro_usd, 0)) filter (where not (i.status = any(" in columns
    assert "sum(i.reserved_micro_usd) filter (where i.status = any(%(outstanding)s))" in columns
    assert spend("i") == (
        "case when i.status = any(%(outstanding)s) then i.reserved_micro_usd "
        "else coalesce(i.charged_micro_usd, 0) end"
    )
