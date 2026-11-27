"""Which local profiles the Local source offers, from their stored route qualifications (Decision
0041 A7, US-23.2).

A local profile is offered once its own route's stored qualification, for its own canonical ID, is
`qualified_with_limits`. The qualification runner records that status only when plain text,
automatic and required tool calls, flat structured output and streamed text passed in all three
trials (operations/route_qualification.py GATING). OpenRouter's offering (`OFFERED_FOR_NEW_RUNS`)
is unchanged, so on OpenRouter a local profile stays refused `model_not_offered`. US-23.3's Model
source setting reads these when the source is Local.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from autobots.contracts.settings import RouteQualification
from autobots.domain.models import PROFILES, ModelProfileId

# The name each reason uses, as the web's profile table names it (apps/web/lib/model-profile.ts).
LOCAL_NAMES = {
    ModelProfileId.LOCAL_BONSAI_2_5: "Bonsai 2.5",
    ModelProfileId.LOCAL_INKLING_2_MINI: "Inkling 2 Mini",
}


@dataclass(frozen=True)
class LocalOffer:
    """One local profile on the Local source: offered with what its qualification found, or not,
    with a reason that is safe to show."""

    profile: ModelProfileId
    offered: bool
    qualified_on: date | None = None
    configuration: str | None = None
    limits: str | None = None
    reason: str | None = None


def local_offers(qualifications: Iterable[RouteQualification]) -> list[LocalOffer]:
    """Every local profile, in the registry's order. `qualifications` are the stored records,
    matched to each profile's own canonical ID by provider_settings.qualification_from_record, so
    a record for another model reads as none, with no date."""
    by_profile = {item.profile: item for item in qualifications}
    offers = []
    for profile in PROFILES.values():
        if profile.local is None:
            continue
        name = LOCAL_NAMES.get(profile.id, profile.wire_id)
        record = by_profile.get(profile.id)
        if record is not None and record.status == "qualified_with_limits":
            offers.append(
                LocalOffer(
                    profile.id,
                    True,
                    qualified_on=record.qualified_on,
                    configuration=record.configuration,
                    limits=record.limits,
                )
            )
        elif record is None or record.qualified_on is None:
            offers.append(
                LocalOffer(
                    profile.id,
                    False,
                    reason=f"{name} isn't offered: its local route hasn't passed US-3.4's suite, "
                    "and no qualification is stored.",
                )
            )
        else:
            offers.append(
                LocalOffer(
                    profile.id,
                    False,
                    qualified_on=record.qualified_on,
                    limits=record.limits,
                    reason=f"{name} isn't offered: its local route's qualification didn't pass. "
                    f"{record.limits or ''}".strip(),
                )
            )
    return offers


def offered_locally(qualifications: Iterable[RouteQualification]) -> frozenset[ModelProfileId]:
    """The local profiles the Local source offers for new work."""
    return frozenset(offer.profile for offer in local_offers(qualifications) if offer.offered)
