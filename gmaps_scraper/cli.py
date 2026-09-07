from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

from .api import normalize_field_mask, search_text
from .billing import VERIFIED_ON, assess_text_search_fields
from .normalize import flatten_place
from .profiles import DEFAULT_PROFILE, PROFILES, profile_fields
from .utils import now_stamp, slugify, write_csv, write_json


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Google Places Text Search (New) -> CSV/JSON with explicit cost-aware field masks."
    )
    parser.add_argument(
        "--query",
        "-q",
        required=True,
        help="Text query (e.g. 'restaurants in Buenos Aires').",
    )

    selector = parser.add_mutually_exclusive_group()
    selector.add_argument(
        "--profile",
        choices=sorted(PROFILES),
        help=f"Named field profile (default: {DEFAULT_PROFILE}).",
    )
    selector.add_argument(
        "--fields",
        help="Expert override: comma-separated Places v1 response fields.",
    )

    parser.add_argument(
        "--max-pages",
        type=int,
        default=1,
        help="Maximum Text Search pages, 1..3 (default: 1).",
    )
    parser.add_argument("--language-code", default=None)
    parser.add_argument("--region-code", default=None)
    parser.add_argument("--out-dir", default="out")
    parser.add_argument(
        "--format",
        choices=["csv", "json", "both"],
        default="csv",
    )
    return parser


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def resolve_fields(args: argparse.Namespace) -> tuple[str, list[str]]:
    if args.fields:
        selection_name = "custom"
        mask = args.fields
    else:
        selection_name = args.profile or DEFAULT_PROFILE
        mask = ",".join(profile_fields(selection_name))

    normalized_mask = normalize_field_mask(mask)
    fields = [part for part in normalized_mask.split(",") if part]
    return selection_name, fields


def describe_billing(selection_name: str, fields: Iterable[str], max_pages: int) -> None:
    fields = list(fields)
    assessment = assess_text_search_fields(fields)

    print(f"Field selection: {selection_name}", file=sys.stderr)
    print(f"Field count: {len(fields)}", file=sys.stderr)
    print(f"Maximum Text Search requests this run: {max_pages}", file=sys.stderr)
    print(f"Text Search billing map verified: {VERIFIED_ON}", file=sys.stderr)

    if assessment.fully_classified:
        print(f"Highest triggered SKU: {assessment.label}", file=sys.stderr)
        return

    print("WARNING: highest triggered SKU is UNCLASSIFIED.", file=sys.stderr)
    if assessment.has_wildcard:
        print(
            "  Wildcard masks may request high-cost fields and should not be used in production.",
            file=sys.stderr,
        )
    if assessment.unknown_fields:
        print(
            "  Unclassified fields: " + ", ".join(assessment.unknown_fields),
            file=sys.stderr,
        )
    print(
        "  Verify the current Google Places Text Search field/SKU documentation before running.",
        file=sys.stderr,
    )


def _dedupe_places(places: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: set[str] = set()
    unique: List[Dict[str, Any]] = []
    for place in places:
        place_id = place.get("id") or place.get("name")
        if place_id is None:
            unique.append(place)
            continue
        if place_id in seen:
            continue
        seen.add(place_id)
        unique.append(place)
    return unique


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.max_pages < 1 or args.max_pages > 3:
        raise SystemExit("--max-pages must be between 1 and 3 for Text Search.")

    selection_name, fields = resolve_fields(args)
    describe_billing(selection_name, fields, args.max_pages)
    field_mask = ",".join(fields)

    places = search_text(
        query=args.query,
        field_mask=field_mask,
        max_pages=args.max_pages,
        language_code=args.language_code,
        region_code=args.region_code,
    )
    places = _dedupe_places(places)

    rows = [flatten_place(place, fields) for place in places]
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    base = f"{slugify(args.query)}_{selection_name}_{args.max_pages}p_{now_stamp()}"

    if args.format in ("csv", "both"):
        csv_path = out_dir / f"{base}.csv"
        write_csv(rows, csv_path)
        print(f"Wrote {len(rows)} rows -> {csv_path}")

    if args.format in ("json", "both"):
        json_path = out_dir / f"{base}.raw.json"
        write_json(places, json_path)
        print(f"Wrote {len(places)} places -> {json_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
