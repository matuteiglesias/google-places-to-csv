from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Protocol

from .api import search_text
from .kernel import BusinessRecord, BusinessRef, google_place_to_business_record, google_place_to_ref


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
class DiscoveryRequest:
    query: str
    field_mask: str
    max_pages: int = 1
    language_code: str | None = None
    region_code: str | None = None


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
    terms_url="https://developers.google.com/maps/documentation/places/web-service/policies",
    policy_verified_on="2026-09-07",
    persistence_mode="provider-terms-controlled",
    persistence_summary=(
        "Google Place IDs are explicitly exempt from Places caching restrictions; "
        "other Places content remains governed by current Google Maps Platform terms."
    ),
    durable_identifier="place_id",
    capabilities=(
        "text-search",
        "field-mask",
        "cost-preflight",
        "durable-id-handoff",
        "normalized-business-record",
    ),
)


class GooglePlacesProvider:
    spec = GOOGLE_SPEC

    def search(self, request: DiscoveryRequest) -> list[Dict[str, Any]]:
        return search_text(
            query=request.query,
            field_mask=request.field_mask,
            max_pages=request.max_pages,
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


_PROVIDERS: dict[str, LocalBusinessProvider] = {
    "google": GooglePlacesProvider(),
}


def provider_names() -> tuple[str, ...]:
    return tuple(sorted(_PROVIDERS))


def get_provider(name: str) -> LocalBusinessProvider:
    try:
        return _PROVIDERS[name]
    except KeyError as exc:
        raise ValueError(f"Unknown provider: {name}") from exc
