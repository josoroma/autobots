"""Loop policy with plain values: what a request larger than the assumed size reserves, and where a
known higher rate refuses it (application/loop_policy.py). Found by US-11.12's independent review
(docs/engineering/evidence/US-11.12/), and filed in test_final_review.py until refactor plan R-66
filed tests by module (PTST-05).
"""

from autobots.adapters.models.catalog import RESERVED_PROMPT_TOKENS, parse_pricing
from autobots.application.loop_policy import past_known_price, reservation_for
from autobots.domain.models import ModelRoute

# Keyword fields, so the reservation and the rate can't be swapped unseen (PTST-19).
ROUTE = ModelRoute(
    role="executor",
    profile="openrouter_terra",
    wire_id="fixture/model",
    worst_case_micro_usd=34_560,
    input_per_million_micro_usd=1_000_000,
)


def test_a_request_under_the_assumed_size_keeps_the_routes_reservation() -> None:
    assert reservation_for(ROUTE, RESERVED_PROMPT_TOKENS) == 34_560
    assert reservation_for(ROUTE, 10) == 34_560


def test_a_larger_request_reserves_for_every_byte_past_it() -> None:
    assert reservation_for(ROUTE, RESERVED_PROMPT_TOKENS + 1000) == 34_560 + 1000


def test_with_no_known_rate_the_reservation_stays_the_routes() -> None:
    route = ModelRoute(
        role="executor",
        profile="openrouter_terra",
        wire_id="fixture/model",
        worst_case_micro_usd=34_560,
    )
    assert reservation_for(route, RESERVED_PROMPT_TOKENS * 2) == 34_560


def test_a_rate_above_the_assumed_size_is_kept_as_where_refusals_start() -> None:
    item = {
        "pricing": {
            "prompt": "0.000001",
            "completion": "0.000002",
            "overrides": [{"min_prompt_tokens": 272_000, "prompt": "0.01", "completion": "0.01"}],
        }
    }
    pricing = parse_pricing(item)
    assert pricing is not None
    assert pricing.tier_from_tokens == 272_000
    route = ModelRoute(
        role="executor",
        profile="p",
        wire_id="w",
        worst_case_micro_usd=1_000,
        input_per_million_micro_usd=1_000_000,
        tier_from_tokens=pricing.tier_from_tokens,
    )
    assert past_known_price(route, 272_000)
    assert not past_known_price(route, 271_999)
    assert not past_known_price(ROUTE, 10_000_000)
