from __future__ import annotations
import argparse
from pathlib import Path
from typing import Any, Dict, List
from .api import search_text
from .normalize import flatten_place
from .utils import slugify, now_stamp, write_csv, write_json

DEFAULT_FIELDS = ",".join([
    # lean Text Search mask; enrich with Place Details later if needed
    "nextPageToken",
    "places.id","places.name","places.displayName","places.formattedAddress",
    "places.location","places.primaryType","places.types",
    "places.rating","places.userRatingCount",
    "places.internationalPhoneNumber","places.websiteUri",
    "places.currentOpeningHours","places.priceLevel",
    "places.googleMapsUri",
    # include these only if you truly need them:
    "places.addressComponents","places.plusCode","places.viewport",
    "places.regularOpeningHours","places.priceRange",
    # "places.reviews","places.reviewSummary",  # heavy: optional
])

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", "-q", required=True, help="Text query (e.g. 'restaurants in Buenos Aires')")
    ap.add_argument("--fields", default=DEFAULT_FIELDS, help="Comma-separated Places v1 fields (use 'places.*').")
    ap.add_argument("--max-pages", type=int, default=3, help="1..3 (Google caps text search around ~60 results).")
    ap.add_argument("--language-code", default=None)
    ap.add_argument("--region-code", default=None)
    ap.add_argument("--out-dir", default="out")
    ap.add_argument("--format", choices=["csv","json","both"], default="csv")
    return ap.parse_args()

def main():
    args = parse_args()
    if args.max_pages < 1 or args.max_pages > 3:
        raise SystemExit("--max-pages must be between 1 and 3 for Text Search.")

    places: List[Dict[str, Any]] = search_text(
        query=args.query,
        field_mask=args.fields,
        max_pages=args.max_pages,
        language_code=args.language_code,
        region_code=args.region_code,
    )

    # de-dupe by id or name
    seen, uniq = set(), []
    for p in places:
        pid = p.get("id") or p.get("name")
        if pid and pid not in seen:
            seen.add(pid); uniq.append(p)
    places = uniq

    fields = [f.strip() for f in args.fields.split(",") if f.strip()]
    rows = [flatten_place(p, fields) for p in places]

    out_dir = Path(args.out_dir)
    base = f"{slugify(args.query)}_{args.max_pages}p_{now_stamp()}"
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.format in ("csv","both"):
        write_csv(rows, out_dir / f"{base}.csv")
    if args.format in ("json","both"):
        write_json(places, out_dir / f"{base}.raw.json")

if __name__ == "__main__":
    main()
