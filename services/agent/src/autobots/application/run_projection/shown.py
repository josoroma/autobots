"""What a run's pages show of stored values: redacted model text and the routes a run froze."""

from collections.abc import Mapping

from autobots.contracts.persisted import FrozenRoute, PolicySnapshot, read_policy_snapshot
from autobots.domain.models import PROFILES, UnknownModelProfile, approved_profile
from autobots.domain.secret_patterns import redact_shown

MAX_TEXT = 500


def public_text(text: str, *, limit: int = MAX_TEXT) -> str:
    """Plans and summaries are written by a model, so a key it was shown must not be displayed."""
    return redact_shown(text)[:limit]


def shown_snapshot(stored: object) -> PolicySnapshot:
    """A stored snapshot as the run's pages show it. One this release can't read, such as a newer
    record version after a rollback, shows nothing bound; routing refuses it (frozen_policy)."""
    try:
        return read_policy_snapshot(stored)
    except UnknownModelProfile:
        return PolicySnapshot()


def canonical_id(profile: str, routes: Mapping[str, FrozenRoute]) -> str:
    """What this run froze, then what the profile means now. A retired one keeps only its name."""
    frozen = routes.get(profile)
    if frozen is not None and frozen.canonical_id:
        return frozen.canonical_id
    try:
        return PROFILES[approved_profile(profile)].canonical_id
    except UnknownModelProfile:
        return "unknown"
