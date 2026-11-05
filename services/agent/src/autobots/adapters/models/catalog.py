"""Public catalog metadata, MP-02. A paid attempt needs a fresh, exact association."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from autobots.domain.models import ModelProfile

MAX_CATALOG_AGE = timedelta(minutes=5)


class ModelUnavailable(Exception):
    """Blocks dispatch. The reason is safe to show, and no substitute is ever chosen."""

    code = "model_unavailable"


@dataclass(frozen=True)
class CatalogEntry:
    wire_id: str
    canonical_slug: str
    supported_parameters: frozenset[str]


@dataclass(frozen=True)
class CatalogSnapshot:
    revision: str
    retrieved_at: datetime
    entries: tuple[CatalogEntry, ...]


def parse_catalog(
    payload: Mapping[str, Any], *, retrieved_at: datetime, revision: str
) -> CatalogSnapshot:
    """From the public `/models` shape. An entry missing a field is dropped, so it cannot match."""
    entries = []
    for item in payload.get("data", ()):
        wire_id, slug = item.get("id"), item.get("canonical_slug")
        if isinstance(wire_id, str) and isinstance(slug, str):
            supported = frozenset(str(name) for name in item.get("supported_parameters") or ())
            entries.append(CatalogEntry(wire_id, slug, supported))
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
