#!/usr/bin/env python3
"""
text_runner.py
A focused pipeline for Google Places API v1 Text Search.

- Accepts one or more --query terms
- Uses API key auth via env GOOGLE_PLACES_API_KEY
- Requests a sensible default field mask (override with --fields)
- Saves outputs under ./data/ with standardized filenames:
    data/places_text_<slug(query)>_<YYYYMMDD_HHMMSS>.(csv|json)
- Prints a per-query summary

Usage:
  export GOOGLE_PLACES_API_KEY="YOUR_KEY"
  python text_runner.py --query "restaurants in Buenos Aires" --format csv
  python text_runner.py --query "nightclubs in Palermo" --format json --max-pages 3
"""

import os
import sys
import json
import csv
import argparse
from datetime import datetime
from typing import List, Dict
import time
import requests

# Import places_scraper.py from the same directory
from pathlib import Path
_here = Path(__file__).resolve().parent
sys.path.insert(0, str(_here))
# import data.text_runner as ps  # type: ignore

DEFAULT_FIELDS = (
    "places.id,"
    "places.name,"
    "places.displayName,"
    "places.formattedAddress,"
    "places.location,"
    "places.types,"
    "places.primaryType,"
    "places.businessStatus,"
    "places.googleMapsUri,"
    "places.primaryTypeDisplayName,"
    "places.plusCode,"
    "places.addressComponents,"
    "places.shortFormattedAddress,"
    "places.viewport,"
    "places.pureServiceAreaBusiness,"
    "places.containingPlaces,"
    "places.internationalPhoneNumber,"
    "places.websiteUri,"
    "places.rating,"
    "places.userRatingCount,"
    "places.currentOpeningHours,"
    "places.regularOpeningHours,"
    "places.priceLevel,"
    "places.priceRange,"
    "places.reviews,"
    "places.reviewSummary"
)

# places.id,places.name,places.displayName,places.formattedAddress,places.location,places.types,places.primaryType

def slugify(s: str) -> str:
    out = []
    for ch in s.lower():
        if ch.isalnum():
            out.append(ch)
        elif ch in [' ', '-', '_', '/', ',', '.', ':']:
            out.append('-')
    slug = ''.join(out)
    while '--' in slug:
        slug = slug.replace('--', '-')
    slug = slug.strip('-')
    return slug or 'query'

def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def write_csv(rows: List[Dict], path: str) -> None:
    if not rows:
        with open(path, "w", newline="", encoding="utf-8") as f:
            f.write("")
        return
    keys = sorted({k for r in rows for k in r.keys()})
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow(r)

def write_json(obj, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def parse_args():
    ap = argparse.ArgumentParser(description="Places Text Search pipeline -> CSV/JSON in ./data")
    ap.add_argument("--query", action="append", required=True, help="Repeat for multiple queries")
    ap.add_argument("--fields", default=DEFAULT_FIELDS, help="X-Goog-FieldMask")
    ap.add_argument("--max-pages", type=int, default=5)
    ap.add_argument("--language-code")
    ap.add_argument("--region-code")
    ap.add_argument("--format", choices=["csv", "json"], default="csv")
    return ap.parse_args()

from typing import Dict, List, Optional


PLACES_BASE = "https://places.googleapis.com/v1"

def getenv_api_key() -> str:
    key = os.getenv("GOOGLE_PLACES_API_KEY") or os.getenv("GOOGLE_API_KEY") or os.getenv("API_KEY")
    if not key:
        sys.stderr.write("ERROR: Set GOOGLE_PLACES_API_KEY (or GOOGLE_API_KEY / API_KEY) in environment.\n")
        sys.exit(2)
    return key

def _request_json(
    path: str,
    payload: Dict,
    field_mask: str,
    api_key: str,
    max_retries: int = 5,
    timeout: int = 30,
) -> Dict:
    """POST to Places API v1 with field mask and API key header. Retries with backoff on 429/5xx."""

    # make sure token is requested
    if "nextPageToken" not in field_mask.split(","):
        field_mask = "nextPageToken," + field_mask

    url = f"{PLACES_BASE}/{path}"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": field_mask,
    }
    backoff = 1.0
    for attempt in range(1, max_retries + 1):
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout)   ####
        if resp.status_code == 200:
            try:
                return resp.json()
            except Exception:
                raise RuntimeError(f"Non-JSON response: {resp.text[:500]}")
        # Handle retryable
        if resp.status_code in (429, 500, 502, 503, 504):
            time.sleep(backoff)
            backoff = min(backoff * 2, 16)
            continue
        # Non-retryable
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:1000]}")
    raise RuntimeError(f"Exhausted retries on {url}")

# ---------- Utilities ----------

def flatten_place(p: dict, fields: list[str]) -> dict:
    """
    Flatten a Google Places API response dict according to requested fields.
    - Nested dicts: pick nested keys (dot notation).
    - Lists: join into comma-separated strings.
    - Missing: return None.
    """
    out = {}

    def get_nested(d, path):
        """Safely get nested value from dict using dot-separated path."""
        parts = path.split(".")
        for part in parts:
            if isinstance(d, dict):
                d = d.get(part)
            else:
                return None
        return d

    for f in fields:
        # Normalize the column name (strip "places." prefix if present)
        col = f.replace("places.", "")
        val = get_nested(p, col)

        # If list, flatten
        if isinstance(val, list):
            # If list of dicts, collapse into string repr
            if all(isinstance(x, dict) for x in val):
                val = ";".join([str(x) for x in val])
            else:
                val = ",".join(map(str, val))
        elif isinstance(val, dict):
            # Collapse dicts (unless you want to expand further)
            val = str(val)

        out[col] = val

    return out


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



def main():
    # Ensure API key present
    if not (os.getenv("GOOGLE_PLACES_API_KEY") or os.getenv("GOOGLE_API_KEY") or os.getenv("API_KEY")):
        sys.stderr.write("ERROR: Set GOOGLE_PLACES_API_KEY (or GOOGLE_API_KEY / API_KEY) in environment.\n")
        sys.exit(2)

    args = parse_args()
    data_dir = (_here / "data")
    data_dir.mkdir(exist_ok=True)

    total = 0
    for q in args.query:
        # places = ps.search_text(
        places = search_text(
            query=q,
            field_mask=args.fields,
            max_pages=args.max_pages,
            language_code=args.language_code,
            region_code=args.region_code,
        )
        total += len(places)

        fn = f"places_text_{slugify(q)}_{now_stamp()}"
        if args.format == "csv":
            # rows = [ps.flatten_place(p) for p in places]

            fields = DEFAULT_FIELDS.split(",")
            rows = [flatten_place(p, fields) for p in places]
            
            out_path = data_dir / f"{fn}.csv"
            write_csv(rows, str(out_path))
        else:
            out_path = data_dir / f"{fn}.json"
            write_json({"query": q, "count": len(places), "places": places}, str(out_path))

        print(f"[OK] {q!r}: {len(places)} places -> {out_path}")

    print(f"\nDone. Total places across {len(args.query)} query(ies): {total}")

if __name__ == "__main__":
    main()