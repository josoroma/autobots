"""A run's chosen budget, Decision 0022 D11. No framework imports."""

from dataclasses import dataclass

BUDGET_MIN_MICRO_USD = 250_000
BUDGET_MAX_MICRO_USD = 5_000_000
BUDGET_STEP_MICRO_USD = 250_000
BUDGET_DEFAULT_MICRO_USD = 1_000_000


class BudgetRefused(ValueError):
    """A typed reason, and no run starts."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class BudgetChoices:
    """What a person may choose now. `highest` is below `lowest` when nothing is left today."""

    lowest: int
    highest: int
    step: int
    default: int
    remaining_daily: int

    @property
    def available(self) -> bool:
        return self.highest >= self.lowest


def budget_choices(remaining_daily: int) -> BudgetChoices:
    """US$0.25 to US$5.00 in US$0.25 steps, never above what's left of the daily cap."""
    left = max(remaining_daily, 0)
    highest = min(BUDGET_MAX_MICRO_USD, left // BUDGET_STEP_MICRO_USD * BUDGET_STEP_MICRO_USD)
    default = min(BUDGET_DEFAULT_MICRO_USD, highest)
    return BudgetChoices(
        BUDGET_MIN_MICRO_USD, highest, BUDGET_STEP_MICRO_USD, max(default, 0), left
    )


def require_budget(chosen: int, remaining_daily: int) -> None:
    """Range and step first, as they don't depend on today's spend, then the daily cap."""
    if not BUDGET_MIN_MICRO_USD <= chosen <= BUDGET_MAX_MICRO_USD:
        raise BudgetRefused("budget_out_of_range")
    if chosen % BUDGET_STEP_MICRO_USD:
        raise BudgetRefused("budget_off_step")
    if chosen > max(remaining_daily, 0):
        raise BudgetRefused("budget_above_daily_cap")
