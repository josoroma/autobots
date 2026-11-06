"""Public catalog metadata, MP-02. A paid attempt needs a fresh, exact association."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_CEILING, Decimal, InvalidOperation
from typing import Any

from autobots.application.model_admission import Pricing
from autobots.domain.models import ModelProfile

MAX_CATALOG_AGE = timedelta(minutes=5)
# What one call reserves for its prompt, an estimate since no tokenizer is pinned. Compaction keeps
# messages near 24K characters, and the system prompt and tool schemas add some. Mostly Latin text
# stays under this, but text with more than a token per character can pass it, and nothing refuses
# that. The reported cost settles each call either way.
RESERVED_PROMPT_TOKENS = 32_000


class ModelUnavailable(Exception):
    """Blocks dispatch. The reason is safe to show, and no substitute is ever chosen."""

    code = "model_unavailable"


@dataclass(frozen=True)
class CatalogEntry:
    wire_id: str
    canonical_slug: str
    supported_parameters: frozenset[str]
    pricing: Pricing | None = None


@dataclass(frozen=True)
class CatalogSnapshot:
    revision: str
    retrieved_at: datetime
    entries: tuple[CatalogEntry, ...]


def _scaled(value: object, factor: int) -> int | None:
    """Rounded up, so a price never under-counts. Anything unreadable has no price at all."""
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        return None
    if not number.is_finite():
        return None
    return int((number * factor).to_integral_value(rounding=ROUND_CEILING))


def _highest(rates: Sequence[Mapping[str, Any]], names: tuple[str, ...], factor: int) -> int | None:
    """The most any listed rate could charge. A negative one has no bound, so it stays negative."""
    found = [_scaled(rate[name], factor) for rate in rates for name in names if name in rate]
    if not found or any(price is None for price in found):
        return None
    prices = [price for price in found if price is not None]
    return min(prices) if min(prices) < 0 else max(prices)


def _reachable(rate: object) -> bool:
    """A rate that starts above the assumed prompt isn't in the worst case.

    `Pricing.tier_from_tokens` keeps where the first such rate starts, and a request that could
    reach it is refused before sending, as nothing was reserved at that rate.
    """
    if not isinstance(rate, Mapping):
        return False
    start = rate.get("min_prompt_tokens")
    return not isinstance(start, int) or start <= RESERVED_PROMPT_TOKENS


def parse_pricing(item: Mapping[str, Any]) -> Pricing | None:
    """USD per token in the catalog. An override, such as a weekend rate, counts if it can apply."""
    pricing = item.get("pricing")
    if not isinstance(pricing, Mapping):
        return None
    overrides = pricing.get("overrides")
    rates = [pricing, *filter(_reachable, overrides if isinstance(overrides, list) else ())]
    per_token = 1_000_000 * 1_000_000
    prompt = _highest(rates, ("prompt", "input_cache_write"), per_token)
    completion = _highest(rates, ("completion", "internal_reasoning"), per_token)
    if prompt is None or completion is None:
        return None
    charged_per_request = any("request" in rate for rate in rates)
    request = _highest(rates, ("request",), 1_000_000) if charged_per_request else 0
    if request is None:
        return None
    tiers = [
        rate["min_prompt_tokens"]
        for rate in (overrides if isinstance(overrides, list) else ())
        if isinstance(rate, Mapping) and isinstance(rate.get("min_prompt_tokens"), int)
    ]
    above = [start for start in tiers if start > RESERVED_PROMPT_TOKENS]
    return Pricing(prompt, completion, request, min(above) if above else None)


def parse_catalog(
    payload: Mapping[str, Any], *, retrieved_at: datetime, revision: str
) -> CatalogSnapshot:
    """From the public `/models` shape. An entry missing a field is dropped, so it cannot match."""
    entries = []
    for item in payload.get("data", ()):
        wire_id, slug = item.get("id"), item.get("canonical_slug")
        if isinstance(wire_id, str) and isinstance(slug, str):
            supported = frozenset(str(name) for name in item.get("supported_parameters") or ())
            entries.append(CatalogEntry(wire_id, slug, supported, parse_pricing(item)))
    return CatalogSnapshot(revision, retrieved_at, tuple(entries))


def validated_entry(profile: ModelProfile, catalog: CatalogSnapshot, now: datetime) -> CatalogEntry:
    """The entry for this profile's request ID, with exactly the requested canonical slug."""
    if (
        catalog.retrieved_at.tzinfo is None
        or now - catalog.retrieved_at.astimezone(UTC) > MAX_CATALOG_AGE
    ):
        raise ModelUnavailable("the model catalog is stale")
    if now < catalog.retrieved_at.astimezone(UTC) - timedelta(minutes=1):
        raise ModelUnavailable("the model catalog is dated in the future")
    matches: Sequence[CatalogEntry] = [e for e in catalog.entries if e.wire_id == profile.wire_id]
    if not matches:
        raise ModelUnavailable("the model is missing from the catalog")
    if len(matches) > 1:
        raise ModelUnavailable("the catalog mapping is ambiguous")
    if matches[0].canonical_slug != profile.canonical_id:
        raise ModelUnavailable("the model's canonical identity has drifted")
    return matches[0]
