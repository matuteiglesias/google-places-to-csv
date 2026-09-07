from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Protocol

from .api import search_text
from .kernel import BusinessRecord, BusinessRef, google_place_to_business_record, google_place_to_ref
from .openmart import (
    DEFAULT_PAGE_SIZE as OPENMART_DEFAULT_PAGE_SIZE,
    openmart_business_to_record,
    openmart_business_to_ref,
    search_businesses as openmart_search_businesses,
)


@dataclass(frozen=True)
class ProviderSpec:
    key: str
    label: str
    docs_url: str
    terms_url: str
    policy_verified_on: str
    persistence_mode: str
    persistence_summary: str
    durable_identifier: str
    capabilities: tuple[str, ...]


@dataclass(frozen=True)
class GeoCircle:
    latitude: float
    longitude: float
    radius_m: float

    def __post_init__(self) -> None:
        if not -90 <= self.latitude <= 90:
            raise ValueError("latitude must be between -90 and 90")
        if not -180 <= self.longitude <= 180:
            raise ValueError("longitude must be between -180 and 180")
        if self.radius_m < 0:
            raise ValueError("radius_m must be >= 0")


@dataclass(frozen=True)
class GeoArea:
    city: str | None = None
    state: str | None = None
    country: str | None = None

    def __post_init__(self) -> None:
        if not any(value and value.strip() for value in (self.city, self.state, self.country)):
            raise ValueError("GeoArea requires at least one of city/state/country")


@dataclass(frozen=True)
class DiscoveryRequest:
    query: str
    field_mask: str | None = None
    max_pages: int = 1
    page_size: int | None = None
    language_code: str | None = None
    region_code: str | None = None
    circle: GeoCircle | None = None
    area: GeoArea | None = None


class LocalBusinessProvider(Protocol):
    spec: ProviderSpec

    def search(self, request: DiscoveryRequest) -> list[Dict[str, Any]]: ...

    def to_ref(
        self,
        raw: Dict[str, Any],
        *,
        source_query: str | None = None,
        observed_at: str | None = None,
    ) -> BusinessRef | None: ...

    def to_record(
        self,
        raw: Dict[str, Any],
        *,
        source_query: str | None = None,
    ) -> BusinessRecord: ...


GOOGLE_SPEC = ProviderSpec(
    key="google",
    label="Google Places Text Search (New)",
    docs_url="https://developers.google.com/maps/documentation/places/web-service/text-search",
    terms_url="https://cloud.google.com/maps-platform/terms/maps-service-terms",
    policy_verified_on="2026-09-07",
    persistence_mode="provider-terms-controlled",
    persistence_summary=(
        "Google IDs may be cached where current documentation allows; other Places content "
        "remains governed by Google Maps Platform restrictions on caching/export."
    ),
    durable_identifier="place_id",
    capabilities=(
        "text-search",
        "circle-bias",
        "field-mask",
        "cost-preflight",
        "durable-id-handoff",
        "normalized-business-record",
    ),
)


OPENMART_SPEC = ProviderSpec(
    key="openmart",
    label="Openmart Local Business API",
    docs_url="https://www.openmart.com/product-tutorials/using-the-openmart-api-to-fetch-data",
    terms_url="https://www.openmart.com/products/local-business-data-api",
    policy_verified_on="2026-09-07",
    persistence_mode="provider-documented-lead-generation",
    persistence_summary=(
        "Openmart's current product documentation explicitly markets the API for B2B lead "
        "generation and states that returned structured JSON may be stored and used. Verify "
        "the terms attached to your account before production use."
    ),
    durable_identifier="openmart_id",
    capabilities=(
        "text-search",
        "structured-area",
        "persistent-business-record",
        "lead-generation",
        "normalized-business-record",
    ),
)


class GooglePlacesProvider:
    spec = GOOGLE_SPEC

    def search(self, request: DiscoveryRequest) -> list[Dict[str, Any]]:
        if not request.field_mask:
            raise ValueError("Google Places requires a field_mask")
        if request.area is not None:
            raise ValueError(
                "Google adapter does not translate GeoArea; use a circle or include the place in the query."
            )
        location_bias = None
        if request.circle is not None:
            location_bias = {
                "circle": {
                    "center": {
                        "latitude": request.circle.latitude,
                        "longitude": request.circle.longitude,
                    },
                    "radius": request.circle.radius_m,
                }
            }
        return search_text(
            query=request.query,
            field_mask=request.field_mask,
            max_pages=request.max_pages,
            location_bias=location_bias,
            language_code=request.language_code,
            region_code=request.region_code,
        )

    def to_ref(
        self,
        raw: Dict[str, Any],
        *,
        source_query: str | None = None,
        observed_at: str | None = None,
    ) -> BusinessRef | None:
        return google_place_to_ref(
            raw,
            source_query=source_query,
            observed_at=observed_at,
        )

    def to_record(
        self,
        raw: Dict[str, Any],
        *,
        source_query: str | None = None,
    ) -> BusinessRecord:
        return google_place_to_business_record(raw, source_query=source_query)


class OpenmartProvider:
    spec = OPENMART_SPEC

    def search(self, request: DiscoveryRequest) -> list[Dict[str, Any]]:
        if request.circle is not None:
            raise ValueError(
                "Openmart adapter currently supports structured city/state/country areas, not circles."
            )
        area = request.area
        return openmart_search_businesses(
            query=request.query,
            max_pages=request.max_pages,
            page_size=request.page_size or OPENMART_DEFAULT_PAGE_SIZE,
            city=area.city if area else None,
            state=area.state if area else None,
            country=area.country if area else None,
        )

    def to_ref(
        self,
        raw: Dict[str, Any],
        *,
        source_query: str | None = None,
        observed_at: str | None = None,
    ) -> BusinessRef | None:
        return openmart_business_to_ref(
            raw,
            source_query=source_query,
            observed_at=observed_at,
        )

    def to_record(
        self,
        raw: Dict[str, Any],
        *,
        source_query: str | None = None,
    ) -> BusinessRecord:
        return openmart_business_to_record(raw, source_query=source_query)


_PROVIDERS: dict[str, LocalBusinessProvider] = {
    "google": GooglePlacesProvider(),
    "openmart": OpenmartProvider(),
}


def provider_names() -> tuple[str, ...]:
    return tuple(sorted(_PROVIDERS))


def get_provider(name: str) -> LocalBusinessProvider:
    try:
        return _PROVIDERS[name]
    except KeyError as exc:
        raise ValueError(f"Unknown provider: {name}") from exc
