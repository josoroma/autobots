"""The most one call can cost, at the stated prompt and output limits, which admission reserves
(MP-07). Split from test_worker_inference.py by module (PTST-04)."""

from datetime import UTC, datetime
from typing import Any

import pytest

from autobots.adapters.models.catalog import (
    RESERVED_PROMPT_TOKENS,
    CatalogSnapshot,
    parse_catalog,
    parse_pricing,
)
from autobots.application.model_admission import worst_case_cost
from autobots.domain.models import MAX_OUTPUT_TOKENS
from fake_openrouter import catalog_payload

NOW = datetime(2026, 11, 5, 12, tzinfo=UTC)


def fresh_catalog() -> CatalogSnapshot:
    return parse_catalog(catalog_payload(), retrieved_at=NOW, revision="fixture")


def test_a_variable_price_has_no_bound_so_a_reservation_refuses_it() -> None:
    pricing = parse_pricing({"pricing": {"prompt": "-1", "completion": "-1"}})
    with pytest.raises(Exception, match="price is not known"):
        worst_case_cost(pricing, 1, 1)


def test_the_worst_case_is_an_upper_bound_at_the_stated_limits() -> None:
    entry = fresh_catalog().entries[0]
    assert entry.pricing is not None
    worst = worst_case_cost(entry.pricing, RESERVED_PROMPT_TOKENS, MAX_OUTPUT_TOKENS)
    assert worst == RESERVED_PROMPT_TOKENS * 1 + MAX_OUTPUT_TOKENS * 2


@pytest.mark.parametrize(
    "pricing",
    [
        {"prompt": "0.1", "completion": "0.1", "overrides": [{"prompt": "-1"}]},
        {"prompt": "0.1", "completion": "0.1", "request": "-1"},
    ],
)
def test_a_variable_rate_is_not_hidden_by_a_fixed_one(pricing: dict[str, Any]) -> None:
    with pytest.raises(Exception, match="price is not known"):
        worst_case_cost(parse_pricing({"pricing": pricing}), 1, 1)
