"""What one paid call is reserved at, and what its reply says it cost, in micro-USD."""

from autobots.adapters.models.catalog import CatalogEntry, micro_usd
from autobots.application.model_admission import CostUnavailable, worst_case_cost
from autobots.operations.cli import Refused

# What each call is reserved for, in prompt and output tokens. Every trial's prompt is far shorter.
CONTEXT_TOKENS = 8_192
OUTPUT_TOKENS = 512


def trial_worst_case(entry: CatalogEntry) -> int:
    """The most one call can cost, in micro-USD, priced by admission's rules (MP-07, POPS-01).

    Cache writes, reasoning tokens, a per-request fee and every rate a prompt of CONTEXT_TOKENS
    could reach all count, since Decisions 0009 and 0019 S4 hold a call at its worst case. An
    unknown or unbounded price, or a higher rate that starts within that prompt, is refused.
    """
    unpriced = Refused("the catalog gives no usable price for this route")
    tier = entry.pricing.tier_from_tokens if entry.pricing else None
    if tier is not None and tier <= CONTEXT_TOKENS:
        raise unpriced
    try:
        return worst_case_cost(entry.pricing, CONTEXT_TOKENS, OUTPUT_TOKENS)
    except CostUnavailable:
        raise unpriced from None


def reported_micro_usd(message: object) -> int | None:
    """The reply's own charge, converted as the worker converts it (PADP-12)."""
    return micro_usd((getattr(message, "response_metadata", None) or {}).get("cost"))
