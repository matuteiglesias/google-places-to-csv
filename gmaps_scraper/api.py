from __future__ import annotations
import os, time, requests
from typing import Any, Dict, List, Optional

__all__ = ["getenv_api_key", "search_text"]

API_URL = "https://places.googleapis.com/v1/places:searchText"

def getenv_api_key() -> str:
    for k in ("GOOGLE_PLACES_API_KEY", "GOOGLE_API_KEY", "API_KEY"):
        v = os.getenv(k)
        if v:
            return v
    raise RuntimeError("Missing API key (set GOOGLE_PLACES_API_KEY or GOOGLE_API_KEY).")

PLACES_BASE = "https://places.googleapis.com/v1"

def _request_json(
    path: str,
    payload: Dict,
    field_mask: str,
    api_key: str,
    max_retries: int = 5,
    timeout: int = 30,
) -> Dict:
    # normalize fields list
    raw = [x.strip() for x in field_mask.split(",") if x.strip()]
    norm = []
    have_next = False
    for f in raw:
        if f == "places.nextPageToken":
            f = "nextPageToken"
        if f == "nextPageToken":
            have_next = True
        norm.append(f)
    if not have_next:
        norm.insert(0, "nextPageToken")

    # dedupe, preserve order
    seen = set(); fields = []
    for f in norm:
        if f not in seen:
            seen.add(f); fields.append(f)

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": ",".join(fields),
    }

    url = f"https://places.googleapis.com/v1/{path}"
    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    if resp.status_code >= 400:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:1000]}")
    return resp.json()



def _paginate(
    path: str,
    payload: Dict,
    field_mask: str,
    api_key: str,
    max_pages: int = 10,
) -> List[Dict]:
    """Iterate through paginated results using nextPageToken."""
    all_places: List[Dict] = []
    page = 0
    token = None

    while page < max_pages:
        body = dict(payload)
        if token:
            body["pageToken"] = token

        data = _request_json(path, body, field_mask, api_key)

        # In v1, results are in "places"
        places = data.get("places", [])
        all_places.extend(places)

        # Pagination token: appears if there are more results
        token = data.get("nextPageToken")
        if not token:
            break

        # wait for token to become valid
        time.sleep(2.1)
        page += 1

    return all_places


def search_text(
    query: str,
    field_mask: str,
    max_pages: int,
    location_bias: Optional[Dict] = None,
    language_code: Optional[str] = None,
    region_code: Optional[str] = None,
) -> List[Dict]:
    payload = {"textQuery": query}
    if location_bias:
        payload["locationBias"] = location_bias
    if language_code:
        payload["languageCode"] = language_code
    if region_code:
        payload["regionCode"] = region_code

    api_key = getenv_api_key()
    return _paginate("places:searchText", payload, field_mask, api_key, max_pages=max_pages)
