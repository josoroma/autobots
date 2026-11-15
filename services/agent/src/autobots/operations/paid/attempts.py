"""A paid call outside a run gets the checks a real attempt gets: this exact identity, and only the
options the catalog lists for it (MP-04)."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, cast

from autobots.adapters.models.catalog import CatalogEntry, parse_catalog, validated_entry
from autobots.adapters.models.factory import PreparedAttempt, checked_options
from autobots.domain.models import ModelProfile, ModelRole
from autobots.operations.paid.pricing import OUTPUT_TOKENS

# How long one paid call may take before it is given up, still charged at its worst case.
CALL_SECONDS = 90.0


@dataclass(frozen=True)
class Route:
    """What a paid call sends. Separate from `PROFILES`, which is all the application may use."""

    wire_id: str
    canonical_id: str
    options: Mapping[str, Any] = field(default_factory=dict)


def prepare(
    route: Route, payload: Mapping[str, Any], max_tokens: int = OUTPUT_TOKENS
) -> tuple[PreparedAttempt, CatalogEntry]:
    """The validated entry comes back with the attempt, so a call is priced from it."""
    now = datetime.now(UTC)
    catalog = parse_catalog(payload, retrieved_at=now, revision="qualification")
    # Only wire_id and canonical_id are read from it (POPS-16).
    profile = cast(ModelProfile, route)
    entry = validated_entry(profile, catalog, now)
    options = checked_options(
        {"max_tokens": max_tokens, **route.options}, entry.supported_parameters
    )
    return PreparedAttempt(profile, ModelRole.EXECUTOR, catalog.revision, options), entry
