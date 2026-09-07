from __future__ import annotations

import os
import time
from typing import Any, Callable, Dict, Iterable, List, Mapping

import requests

from .kernel import BusinessRecord, BusinessRef, utc_observed_at

OPENMART_SEARCH_URL = "https://api.openmart.ai/api/v1/search"
RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100


def getenv_openmart_api_key() -> str:
    value = os.getenv("OPENMART_API_KEY")
    if value:
        return value
    raise RuntimeError("Missing API key (set OPENMART_API_KEY).")


def _request_json(
    payload: Dict[str, Any],
    api_key: str,
    *,
    max_retries: int = 2,
    timeout: float = 30.0,
    request_func: Callable[..., Any] = requests.post,
    sleep_func: Callable[[float], None] = time.sleep,
) -> Any:
    if max_retries < 0:
        raise ValueError("max_retries must be >= 0")
    if timeout <= 0:
        raise ValueError("timeout must be > 0")

    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
    }

    for attempt in range(max_retries + 1):
        try:
            response = request_func(
                OPENMART_SEARCH_URL,
                headers=headers,
                json=payload,
                timeout=timeout,
            )
        except requests.RequestException as exc:
            raise RuntimeError(
                "Openmart request failed with an ambiguous network outcome; "
                "it was not retried automatically to avoid accidental duplicate usage."
            ) from exc

        if 200 <= response.status_code < 300:
            try:
                return response.json()
            except Exception as exc:
                raise RuntimeError(
                    f"Openmart returned a non-JSON success response: {response.text[:500]}"
                ) from exc

        if response.status_code in RETRYABLE_STATUS_CODES and attempt < max_retries:
            sleep_func(min(2.0**attempt, 8.0))
            continue

        raise RuntimeError(f"Openmart HTTP {response.status_code}: {response.text[:1000]}")

    raise AssertionError("unreachable")


def _extract_records(payload: Any) -> List[Dict[str, Any]]:
    """Extract record arrays from documented/common Openmart response envelopes.

    Openmart's public examples have changed envelope shape over time. Keep the adapter
    strict about records being dictionaries, while tolerating a small set of known
    list containers so an envelope-only change does not silently corrupt output.
    """
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, Mapping):
        raise RuntimeError("Openmart returned an unsupported response shape.")

    for key in ("data", "results", "businesses", "companies"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, Mapping):
            for nested_key in ("results", "data", "businesses", "companies"):
                nested = value.get(nested_key)
                if isinstance(nested, list):
                    return [item for item in nested if isinstance(item, dict)]

    # Some examples show a single business object. Accept it only when it looks like
    # a record rather than a metadata envelope.
    if any(key in payload for key in ("id", "openmart_id", "company_name", "name")):
        return [dict(payload)]

    raise RuntimeError("Openmart response did not contain a recognized business record list.")


def search_businesses(
    *,
    query: str,
    max_pages: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    city: str | None = None,
    state: str | None = None,
    country: str | None = None,
) -> List[Dict[str, Any]]:
    if not query.strip():
        raise ValueError("query must not be empty")
    if max_pages < 1 or max_pages > 3:
        raise ValueError("max_pages must be between 1 and 3")
    if page_size < 1 or page_size > MAX_PAGE_SIZE:
        raise ValueError(f"page_size must be between 1 and {MAX_PAGE_SIZE}")

    api_key = getenv_openmart_api_key()
    rows: List[Dict[str, Any]] = []

    location: Dict[str, str] = {}
    if city:
        location["city"] = city
    if state:
        location["state"] = state
    if country:
        location["country"] = country

    for page_number in range(max_pages):
        payload: Dict[str, Any] = {
            "estimate_total": False,
            "query": query,
            "pagination": {
                "limit": page_size,
                "start": page_number * page_size,
                "total_count": {
                    "max_num": page_size * max_pages,
                    "to_estimate": False,
                },
            },
        }
        if location:
            payload["location"] = location

        page = _extract_records(_request_json(payload, api_key))
        rows.extend(page)
        if len(page) < page_size:
            break

    return rows


def _first_scalar(value: Any) -> Any:
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _openmart_id(record: Mapping[str, Any]) -> str | None:
    value = record.get("id") or record.get("openmart_id")
    return str(value) if value not in (None, "") else None


def openmart_business_to_ref(
    record: Mapping[str, Any],
    *,
    source_query: str | None = None,
    observed_at: str | None = None,
) -> BusinessRef | None:
    provider_id = _openmart_id(record)
    if not provider_id:
        return None
    return BusinessRef(
        provider="openmart",
        provider_id=provider_id,
        source_query=source_query,
        observed_at=observed_at or utc_observed_at(),
    )


def _formatted_address(record: Mapping[str, Any]) -> str | None:
    explicit = record.get("formatted_address") or record.get("formattedAddress")
    if explicit:
        return str(explicit)
    parts = [
        record.get("street_address"),
        record.get("city"),
        record.get("state"),
        record.get("zipcode") or record.get("postal_code"),
        record.get("country"),
    ]
    values = [str(part).strip() for part in parts if part not in (None, "")]
    return ", ".join(values) if values else None


def _types_text(value: Any) -> str | None:
    if isinstance(value, list):
        return ",".join(str(item) for item in value)
    return str(value) if value not in (None, "") else None


def openmart_business_to_record(
    record: Mapping[str, Any],
    *,
    source_query: str | None = None,
) -> BusinessRecord:
    return BusinessRecord(
        provider="openmart",
        provider_id=_openmart_id(record),
        name=record.get("company_name") or record.get("name"),
        formatted_address=_formatted_address(record),
        latitude=record.get("latitude"),
        longitude=record.get("longitude"),
        primary_type=record.get("company_type") or record.get("primary_type"),
        types=_types_text(record.get("company_categories") or record.get("tags")),
        business_status=record.get("business_status") or record.get("status"),
        website=record.get("website_url") or record.get("website"),
        phone=_first_scalar(record.get("company_phones") or record.get("phones") or record.get("phone")),
        rating=record.get("google_rating") or record.get("rating"),
        review_count=record.get("google_reviews_count") or record.get("review_count"),
        provider_url=record.get("profile_url") or record.get("openmart_url"),
        source_query=source_query,
    )
