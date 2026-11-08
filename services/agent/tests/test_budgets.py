"""Decision 0022 D11: chosen budgets, their range, step and the remaining daily cap."""

import pytest

from autobots.contracts.settings import budget_range
from autobots.domain.budgets import BudgetRefused, budget_choices, require_budget


def test_choices_stop_at_the_remaining_daily_cap() -> None:
    choices = budget_choices(2_100_000)
    assert (choices.lowest, choices.highest, choices.step, choices.default) == (
        250_000,
        2_000_000,
        250_000,
        1_000_000,
    )
    assert choices.available


def test_choices_never_exceed_five_dollars() -> None:
    assert budget_choices(50_000_000).highest == 5_000_000


def test_the_default_is_lowered_to_what_is_left() -> None:
    choices = budget_choices(600_000)
    assert (choices.highest, choices.default) == (500_000, 500_000)


def test_nothing_left_offers_nothing() -> None:
    for remaining in (0, 249_999, -10):
        choices = budget_choices(remaining)
        assert not choices.available
        assert choices.remaining_daily == max(remaining, 0)
    assert budget_range(100_000).max_micro_usd < budget_range(100_000).min_micro_usd


@pytest.mark.parametrize(
    ("chosen", "code"),
    [
        (5_250_000, "budget_out_of_range"),
        (100_000, "budget_out_of_range"),
        (0, "budget_out_of_range"),
        (1_100_000, "budget_off_step"),
        (2_250_000, "budget_above_daily_cap"),
    ],
)
def test_a_budget_outside_the_rules_is_refused(chosen: int, code: str) -> None:
    with pytest.raises(BudgetRefused) as refused:
        require_budget(chosen, 2_100_000)
    assert refused.value.code == code


@pytest.mark.parametrize("chosen", [250_000, 1_500_000, 2_000_000])
def test_a_budget_within_the_rules_is_accepted(chosen: int) -> None:
    require_budget(chosen, 2_100_000)


def test_five_dollars_needs_five_dollars_left() -> None:
    require_budget(5_000_000, 5_000_000)
    with pytest.raises(BudgetRefused):
        require_budget(5_000_000, 4_999_999)
