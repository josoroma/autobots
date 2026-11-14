"""Catalog prices in micro-USD per million tokens: the worst reachable rate, and where a higher one
starts (MP-02, MP-07). Split from test_worker_inference.py by module (PTST-04)."""

import json
from pathlib import Path

import pytest

from autobots.adapters.models.catalog import RESERVED_PROMPT_TOKENS, parse_pricing
from autobots.application.model_admission import Pricing, worst_case_cost
from autobots.domain.models import MAX_OUTPUT_TOKENS
from fake_openrouter import DEEPSEEK_WIRE_ID, PRICE, TERRA_WIRE_ID


def test_a_catalog_price_is_scaled_to_micro_usd_per_million_tokens() -> None:
    assert parse_pricing({"pricing": PRICE}) == Pricing(1_000_000, 2_000_000)


def test_the_highest_listed_rate_counts_including_overrides_and_cache_writes() -> None:
    pricing = {
        "prompt": "0.00001",
        "completion": "0.00005",
        "input_cache_write": "0.0000125",
        "internal_reasoning": "0.00006",
        "request": "0.001",
        "overrides": [{"prompt": "0.00002", "completion": "0.0001", "min_prompt_tokens": 5}],
    }
    assert parse_pricing({"pricing": pricing}) == Pricing(20_000_000, 100_000_000, 1000)


@pytest.mark.parametrize(
    "pricing",
    [None, {}, {"prompt": "0.1"}, {"prompt": "free", "completion": "0.1"}, {"prompt": "NaN"}],
)
def test_a_missing_or_unreadable_price_is_no_price(pricing: object) -> None:
    assert parse_pricing({"pricing": pricing}) is None


def test_the_real_catalog_prices_both_profiles_within_a_runs_default_cap() -> None:
    """Terra's cache-write rate is its highest input rate. Its long-prompt override starts far above
    what's reserved for, so it doesn't count, and a request that could reach it isn't sent."""
    path = Path(__file__).parents[3] / "research/openrouter-model-catalog-2026-11-05.json"
    matches = {item["id"]: item for item in json.loads(path.read_text())["matches"]}
    prices = {wire: parse_pricing(matches[wire]) for wire in (DEEPSEEK_WIRE_ID, TERRA_WIRE_ID)}
    assert prices[DEEPSEEK_WIRE_ID] == Pricing(300_000, 1_200_000)
    assert prices[TERRA_WIRE_ID] == Pricing(1_250_000, 5_000_000, tier_from_tokens=272_000)
    worst = {
        wire: worst_case_cost(price, RESERVED_PROMPT_TOKENS, MAX_OUTPUT_TOKENS)
        for wire, price in prices.items()
    }
    assert worst == {DEEPSEEK_WIRE_ID: 10_215, TERRA_WIRE_ID: 42_560}


def test_an_override_this_app_can_reach_still_counts() -> None:
    near = {"min_prompt_tokens": RESERVED_PROMPT_TOKENS, "prompt": "0.5", "completion": "0.5"}
    far = {"min_prompt_tokens": RESERVED_PROMPT_TOKENS + 1, "prompt": "9", "completion": "9"}
    pricing = {"prompt": "0.1", "completion": "0.1", "overrides": [near, far]}
    assert parse_pricing({"pricing": pricing}) == Pricing(
        500_000_000_000, 500_000_000_000, tier_from_tokens=RESERVED_PROMPT_TOKENS + 1
    )


def test_a_per_request_price_counts_wherever_it_is_listed() -> None:
    pricing = {"prompt": "0", "completion": "0", "overrides": [{"request": "0.002"}]}
    assert parse_pricing({"pricing": pricing}) == Pricing(0, 0, 2000)
