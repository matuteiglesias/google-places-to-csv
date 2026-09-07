from __future__ import annotations

IDS_FIELDS = (
    "nextPageToken",
    "places.id",
    "places.name",
)

CORE_FIELDS = (
    *IDS_FIELDS,
    "places.displayName",
    "places.formattedAddress",
    "places.location",
    "places.primaryType",
    "places.types",
    "places.businessStatus",
    "places.googleMapsUri",
)

ENTERPRISE_FIELDS = (
    *CORE_FIELDS,
    "places.rating",
    "places.userRatingCount",
    "places.internationalPhoneNumber",
    "places.websiteUri",
    "places.currentOpeningHours",
    "places.regularOpeningHours",
    "places.priceLevel",
    "places.priceRange",
)

ATMOSPHERE_FIELDS = (
    *ENTERPRISE_FIELDS,
    "places.reviews",
    "places.reviewSummary",
)

PROFILES = {
    "ids": IDS_FIELDS,
    "core": CORE_FIELDS,
    "enterprise": ENTERPRISE_FIELDS,
    "atmosphere": ATMOSPHERE_FIELDS,
}

DEFAULT_PROFILE = "core"


def profile_fields(name: str) -> tuple[str, ...]:
    try:
        return PROFILES[name]
    except KeyError as exc:
        raise ValueError(f"Unknown field profile: {name}") from exc
