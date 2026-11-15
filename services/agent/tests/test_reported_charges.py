"""A reply's reported charge in micro-USD: exact, rounded up, and never invented.

DH-06 asks for exact monetary units, and a price never under-counts (PADP-12). The worker and the
paid trials settle the same reply to the same figure.
"""

from decimal import Decimal

import pytest
from langchain_core.messages import AIMessage

from autobots.adapters import loop_middleware
from autobots.adapters.models import catalog
from autobots.operations.paid import pricing


@pytest.mark.parametrize(
    ("reported", "expected"),
    [
        pytest.param(0.0000125, 13, id="half-a-micro-usd"),
        pytest.param(0.000001234, 2, id="a-fraction-above-one"),
        pytest.param("0.0000005", 1, id="text"),
        pytest.param(Decimal("0.0000015"), 2, id="decimal"),
        pytest.param(0.1, 100_000, id="exact-where-a-float-product-is-not"),
        pytest.param(0, 0, id="free"),
    ],
)
def test_a_reported_charge_is_rounded_up(reported: object, expected: int) -> None:
    assert catalog.micro_usd(reported) == expected


@pytest.mark.parametrize(
    "reported",
    [None, "abc", float("nan"), float("inf"), "Infinity", -0.001, True, [0.5]],
)
def test_an_unreadable_charge_stays_unreported(reported: object) -> None:
    """The estimate stays open for reconciliation instead (model-gateway: no invented charge)."""
    assert catalog.micro_usd(reported) is None


@pytest.mark.parametrize(("cost", "expected"), [(0.0000125, 13), (0.000001234, 2)])
def test_the_worker_settles_a_half_micro_usd_charge_upward(cost: float, expected: int) -> None:
    assert loop_middleware._charged(AIMessage("", response_metadata={"cost": cost})) == expected


@pytest.mark.parametrize("metadata", [{}, {"cost": "nan"}, {"cost": float("inf")}, {"cost": "x"}])
def test_the_worker_leaves_an_unreadable_charge_unreported(metadata: dict[str, object]) -> None:
    assert loop_middleware._charged(AIMessage("", response_metadata=metadata)) is None


def test_the_trials_and_the_worker_settle_one_reply_to_one_figure() -> None:
    message = AIMessage("", response_metadata={"cost": 0.0000125})
    assert pricing.reported_micro_usd(message) == loop_middleware._charged(message)
