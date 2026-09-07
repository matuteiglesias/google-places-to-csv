from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Iterable

# Verified against Google Text Search (New) documentation on 2026-09-07.
# Source: https://developers.google.com/maps/documentation/places/web-service/text-search
# Billing semantics: a request is billed at the highest SKU represented in the field mask.
VERIFIED_ON = "2026-09-07"
SOURCE_URL = "https://developers.google.com/maps/documentation/places/web-service/text-search"


class TextSearchTier(IntEnum):
    ESSENTIALS_IDS_ONLY = 10
    PRO = 20
    ENTERPRISE = 30
    ENTERPRISE_ATMOSPHERE = 40


TIER_LABELS = {
    TextSearchTier.ESSENTIALS_IDS_ONLY: "Text Search Essentials (IDs Only)",
    TextSearchTier.PRO: "Text Search Pro",
    TextSearchTier.ENTERPRISE: "Text Search Enterprise",
    TextSearchTier.ENTERPRISE_ATMOSPHERE: "Text Search Enterprise + Atmosphere",
}


ESSENTIALS_FIELDS = frozenset(
    {
        "nextPageToken",
        "places.attributions",
        "places.consumerAlert",
        "places.id",
        "places.movedPlace",
        "places.movedPlaceId",
        "places.name",
    }
)

PRO_FIELDS = frozenset(
    {
        "places.accessibilityOptions",
        "places.addressComponents",
        "places.addressDescriptor",
        "places.adrFormatAddress",
        "places.businessStatus",
        "places.containingPlaces",
        "places.displayName",
        "places.formattedAddress",
        "places.googleMapsLinks",
        "places.googleMapsTypeLabel",
        "places.googleMapsUri",
        "places.iconBackgroundColor",
        "places.iconMaskBaseUri",
        "places.location",
        "places.openingDate",
        "places.photos",
        "places.plusCode",
        "places.postalAddress",
        "places.primaryType",
        "places.primaryTypeDisplayName",
        "places.pureServiceAreaBusiness",
        "places.searchUri",
        "places.shortFormattedAddress",
        "places.subDestinations",
        "places.timeZone",
        "places.types",
        "places.utcOffsetMinutes",
        "places.viewport",
    }
)

ENTERPRISE_FIELDS = frozenset(
    {
        "places.currentOpeningHours",
        "places.currentSecondaryOpeningHours",
        "places.internationalPhoneNumber",
        "places.nationalPhoneNumber",
        "places.priceLevel",
        "places.priceRange",
        "places.rating",
        "places.regularOpeningHours",
        "places.regularSecondaryOpeningHours",
        "places.transitStation",
        "places.userRatingCount",
        "places.websiteUri",
    }
)

ATMOSPHERE_FIELDS = frozenset(
    {
        "places.allowsDogs",
        "places.curbsidePickup",
        "places.delivery",
        "places.dineIn",
        "places.editorialSummary",
        "places.evChargeAmenitySummary",
        "places.evChargeOptions",
        "places.fuelOptions",
        "places.generativeSummary",
        "places.goodForChildren",
        "places.goodForGroups",
        "places.goodForWatchingSports",
        "places.liveMusic",
        "places.menuForChildren",
        "places.neighborhoodSummary",
        "places.outdoorSeating",
        "places.parkingOptions",
        "places.paymentOptions",
        "places.reservable",
        "places.restroom",
        "places.reviews",
        "places.reviewSummary",
        "places.servesBeer",
        "places.servesBreakfast",
        "places.servesBrunch",
        "places.servesCocktails",
        "places.servesCoffee",
        "places.servesDessert",
        "places.servesDinner",
        "places.servesLunch",
        "places.servesVegetarianFood",
        "places.servesWine",
        "places.takeout",
        "routingSummaries",
    }
)

FIELD_TIERS = {
    **{field: TextSearchTier.ESSENTIALS_IDS_ONLY for field in ESSENTIALS_FIELDS},
    **{field: TextSearchTier.PRO for field in PRO_FIELDS},
    **{field: TextSearchTier.ENTERPRISE for field in ENTERPRISE_FIELDS},
    **{field: TextSearchTier.ENTERPRISE_ATMOSPHERE for field in ATMOSPHERE_FIELDS},
}


@dataclass(frozen=True)
class BillingAssessment:
    highest_tier: TextSearchTier | None
    unknown_fields: tuple[str, ...] = ()
    has_wildcard: bool = False

    @property
    def fully_classified(self) -> bool:
        return not self.unknown_fields and not self.has_wildcard and self.highest_tier is not None

    @property
    def label(self) -> str:
        if not self.fully_classified:
            return "UNCLASSIFIED"
        return TIER_LABELS[self.highest_tier]


def split_fields(fields: str | Iterable[str]) -> list[str]:
    if isinstance(fields, str):
        raw = fields.split(",")
    else:
        raw = list(fields)
    return [str(field).strip() for field in raw if str(field).strip()]


def canonical_billable_field(field: str) -> str:
    """Reduce nested Place field masks to the documented billable top-level field."""
    field = field.strip()
    if field in {"*", "places.*"}:
        return "*"
    if field.startswith("places."):
        parts = field.split(".")
        if len(parts) >= 2:
            return ".".join(parts[:2])
    return field


def assess_text_search_fields(fields: str | Iterable[str]) -> BillingAssessment:
    parsed = split_fields(fields)
    if not parsed:
        return BillingAssessment(highest_tier=None, unknown_fields=("<empty field mask>",))

    highest: TextSearchTier | None = None
    unknown: list[str] = []
    wildcard = False

    for raw in parsed:
        canonical = canonical_billable_field(raw)
        if canonical == "*":
            wildcard = True
            continue
        tier = FIELD_TIERS.get(canonical)
        if tier is None:
            unknown.append(raw)
            continue
        if highest is None or tier > highest:
            highest = tier

    return BillingAssessment(
        highest_tier=highest,
        unknown_fields=tuple(dict.fromkeys(unknown)),
        has_wildcard=wildcard,
    )
