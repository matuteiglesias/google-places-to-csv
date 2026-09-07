from __future__ import annotations

import os
import time
from typing import Any, Callable, Dict, List, Optional

import requests

__all__ = [
    "getenv_api_key",
    "normalize_field_mask",
    "search_text",
]

PLACES_BASE = "https://places.googleapis.com/v1"
RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


def getenv_api_key() -> str:
    for key_name in ("GOOGLE_PLACES_API_KEY", "GOOGLE_API_KEY"):
        value = os.getenv(key_name)
        if value:
            return value
    raise RuntimeError(
        "Missing API key (set GOOGLE_PLACES_API_KEY or GOOGLE_API_KEY)."
    )


def normalize_field_mask(field_mask: str) -> str:
    """Normalize, de-duplicate and ensure pagination metadata is requested once."""
    raw = [part.strip() for part in field_mask.split(",") if part.strip()]
    if not raw:
        raise ValueError("field_mask must contain at least one field")

    normalized: list[str] = []
    for field in raw:
        if field == "places.nextPageToken":
            field = "nextPageToken"
        normalized.append(field)

    if "nextPageToken" not in normalized:
        normalized.insert(0, "nextPageToken")

    seen: set[str] = set()
    unique: list[str] = []
    for field in normalized:
        if field not in seen:
            seen.add(field)
            unique.append(field)
    return ",".join(unique)


def _request_json(
    path: str,
    payload: Dict[str, Any],
    field_mask: str,
    api_key: str,
    *,
    max_retries: int = 2,
    timeout: float = 30.0,
    request_func: Callable[..., Any] = requests.post,
    sleep_func: Callable[[float], None] = time.sleep,
) -> Dict[str, Any]:
    """POST one Places request with bounded, conservative retry behavior.

    Only explicit HTTP responses known to be retryable are retried. Network exceptions
    are not retried automatically because the server may have successfully received a
    billable request even when the client cannot observe the response.
    """
    if max_retries < 0:
        raise ValueError("max_retries must be >= 0")
    if timeout <= 0:
        raise ValueError("timeout must be > 0")

    normalized_mask = normalize_field_mask(field_mask)
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": normalized_mask,
    }
    url = f"{PLACES_BASE}/{path}"

    for attempt in range(max_retries + 1):
        try:
            response = request_func(
                url,
                headers=headers,
                json=payload,
                timeout=timeout,
            )
        except requests.RequestException as exc:
            raise RuntimeError(
                "Places request failed with an ambiguous network outcome; "
                "it was not retried automatically to avoid accidental duplicate billing."
            ) from exc

        if 200 <= response.status_code < 300:
            try:
                return response.json()
            except Exception as exc:
                raise RuntimeError(
                    f"Places returned a non-JSON success response: {response.text[:500]}"
                ) from exc

        if (
            response.status_code in RETRYABLE_STATUS_CODES
            and attempt < max_retries
        ):
            sleep_func(min(2.0**attempt, 8.0))
            continue

        raise RuntimeError(
            f"HTTP {response.status_code}: {response.text[:1000]}"
        )

    raise AssertionError("unreachable")


def _paginate(
    path: str,
    payload: Dict[str, Any],
    field_mask: str,
    api_key: str,
    *,
    max_pages: int = 3,
) -> List[Dict[str, Any]]:
    """Collect at most three Text Search pages using nextPageToken/pageToken."""
    if max_pages < 1 or max_pages > 3:
        raise ValueError("max_pages must be between 1 and 3 for Text Search")

    all_places: List[Dict[str, Any]] = []
    token: str | None = None

    for _page_number in range(max_pages):
        body = dict(payload)
        if token:
            body["pageToken"] = token

        data = _request_json(path, body, field_mask, api_key)
        all_places.extend(data.get("places", []))

        token = data.get("nextPageToken")
        if not token:
            break

    return all_places


def search_text(
    query: str,
    field_mask: str,
    max_pages: int,
    location_bias: Optional[Dict[str, Any]] = None,
    language_code: Optional[str] = None,
    region_code: Optional[str] = None,
) -> List[Dict[str, Any]]:
    if max_pages < 1 or max_pages > 3:
        raise ValueError("max_pages must be between 1 and 3 for Text Search")

    payload: Dict[str, Any] = {"textQuery": query}
    if location_bias:
        payload["locationBias"] = location_bias
    if language_code:
        payload["languageCode"] = language_code
    if region_code:
        payload["regionCode"] = region_code

    api_key = getenv_api_key()
    return _paginate(
        "places:searchText",
        payload,
        field_mask,
        api_key,
        max_pages=max_pages,
    )
