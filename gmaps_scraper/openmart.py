from __future__ import annotations

import os
import time
from typing import Any, Callable, Dict, List, Mapping

import requests

from .kernel import BusinessRecord, BusinessRef, utc_observed_at

OPENMART_SEARCH_URL = "https://api.openmart.ai/api/v1/search"
RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
DEFAULT_PAGE_SIZE = 50
# Deliberate local safety cap. Current Openmart docs allow larger pages for some keys,
# but preview API keys are limited to <=100 and 100 is the documented recommendation.
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

    # Current external API docs recommend Authorization: Bearer. They also state that
    # X-API-Key remains accepted for existing integrations; use the recommended form.
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
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
    """Extract records from the documented Openmart search response.

    With estimate_total=false (our default), current docs specify a top-level array.
    With estimate_total=true, current docs specify a {data, total_count} wrapper. We
    accept exactly those two public shapes so provider drift fails loudly.
    """
    if isinstance(payload, list):
        if not all(isinstance(item, dict) for item in payload):
            raise RuntimeError("Openmart search returned non-object records.")
        return list(payload)

    if isinstance(payload, Mapping) and isinstance(payload.get("data"), list):
        records = payload["data"]
        if not all(isinstance(item, dict) for item in records):
            raise RuntimeError("Openmart wrapped search returned non-object records.")
        return list(records)

    raise RuntimeError(
        "Openmart returned an unsupported search response shape; verify current API docs."
    )


def _last_cursor(records: List[Dict[str, Any]]) -> list[Any] | None:
    if not records:
        return None
    cursor = records[-1].get("cursor")
    if not isinstance(cursor, list) or len(cursor) != 2:
        return None
    return cursor


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

    cursor: list[Any] | None = None
    for page_number in range(max_pages):
        payload: Dict[str, Any] = {
            "query": query,
            "limit": page_size,
            "estimate_total": False,
        }
        if location:
            # Current docs type location as array[object].
            payload["location"] = [location]
        if cursor is not None:
            payload["cursor"] = cursor

        page = _extract_records(_request_json(payload, api_key))
        rows.extend(page)
        if len(page) < page_size or page_number + 1 >= max_pages:
            break

        cursor = _last_cursor(page)
        if cursor is None:
            raise RuntimeError(
                "Openmart returned a full page without the documented pagination cursor."
            )

    return rows


def _content(record: Mapping[str, Any]) -> Mapping[str, Any]:
    value = record.get("content")
    return value if isinstance(value, Mapping) else record


def _first_scalar(value: Any) -> Any:
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _openmart_id(record: Mapping[str, Any]) -> str | None:
    value = record.get("id") or record.get("openmart_id")
    if value in (None, ""):
        value = _content(record).get("store_id")
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


def _formatted_address(content: Mapping[str, Any]) -> str | None:
    explicit = content.get("formatted_address") or content.get("formattedAddress")
    if explicit:
        return str(explicit)
    parts = [
        content.get("street_address"),
        content.get("city"),
        content.get("state"),
        content.get("zipcode") or content.get("postal_code"),
        content.get("country"),
    ]
    values = [str(part).strip() for part in parts if part not in (None, "")]
    return ", ".join(values) if values else None


def _types_text(value: Any) -> str | None:
    if isinstance(value, list):
        return ",".join(str(item) for item in value)
    return str(value) if value not in (None, "") else None


def _source_ref_url(content: Mapping[str, Any]) -> str | None:
    from_sources = content.get("from_sources")
    if not isinstance(from_sources, Mapping):
        return None
    google = from_sources.get("GOOGLE_MAP")
    if not isinstance(google, Mapping):
        return None
    value = google.get("ref_url")
    return str(value) if value not in (None, "") else None


def openmart_business_to_record(
    record: Mapping[str, Any],
    *,
    source_query: str | None = None,
) -> BusinessRecord:
    content = _content(record)
    return BusinessRecord(
        provider="openmart",
        provider_id=_openmart_id(record),
        name=(
            content.get("business_name")
            or content.get("store_name")
            or content.get("company_name")
            or content.get("name")
        ),
        formatted_address=_formatted_address(content),
        latitude=content.get("latitude"),
        longitude=content.get("longitude"),
        primary_type=(
            content.get("business_type")
            or content.get("company_type")
            or content.get("primary_type")
        ),
        types=_types_text(
            content.get("business_categories")
            or content.get("tags")
            or content.get("company_categories")
        ),
        business_status=content.get("business_status") or content.get("status"),
        website=content.get("website_url") or content.get("website"),
        phone=_first_scalar(
            content.get("store_phones")
            or content.get("business_phones")
            or content.get("company_phones")
            or content.get("phones")
            or content.get("phone")
        ),
        rating=content.get("google_rating") or content.get("rating"),
        review_count=content.get("google_reviews_count") or content.get("review_count"),
        # Openmart's documented search response does not currently expose an Openmart
        # profile URL. Preserve a source reference URL only when the provider returns it.
        provider_url=(
            content.get("profile_url")
            or content.get("openmart_url")
            or _source_ref_url(content)
        ),
        source_query=source_query,
    )
