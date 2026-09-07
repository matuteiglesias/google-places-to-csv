from __future__ import annotations

import argparse
import json
from typing import Sequence

from .billing import SOURCE_URL, VERIFIED_ON, assess_text_search_fields
from .profiles import DEFAULT_PROFILE, PROFILES, profile_fields


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Classify a Google Places Text Search field mask before making API calls."
    )
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--fields", help="Comma-separated Text Search response fields.")
    selector.add_argument("--profile", choices=sorted(PROFILES))
    parser.add_argument(
        "--max-requests",
        type=int,
        default=1,
        help="Upper bound on planned Text Search requests (default: 1).",
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def assess_selection(fields: str, *, selection: str, max_requests: int) -> dict[str, object]:
    if max_requests < 1:
        raise ValueError("max_requests must be >= 1")

    parsed_fields = [item.strip() for item in fields.split(",") if item.strip()]
    assessment = assess_text_search_fields(parsed_fields)
    return {
        "selection": selection,
        "field_count": len(parsed_fields),
        "fields": parsed_fields,
        "highest_sku": assessment.label,
        "fully_classified": assessment.fully_classified,
        "unknown_fields": list(assessment.unknown_fields),
        "has_wildcard": assessment.has_wildcard,
        "max_requests": max_requests,
        "verified_on": VERIFIED_ON,
        "source_url": SOURCE_URL,
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.max_requests < 1:
        raise SystemExit("--max-requests must be >= 1")

    if args.fields:
        selection = "custom"
        fields = args.fields
    else:
        selection = args.profile or DEFAULT_PROFILE
        fields = ",".join(profile_fields(selection))

    report = assess_selection(fields, selection=selection, max_requests=args.max_requests)

    if args.as_json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["fully_classified"] else 2

    print(f"Field selection: {report['selection']}")
    print(f"Field count: {report['field_count']}")
    print(f"Maximum planned Text Search requests: {report['max_requests']}")
    print(f"Highest triggered SKU: {report['highest_sku']}")
    print(f"Billing map verified: {report['verified_on']}")
    print(f"Source: {report['source_url']}")

    if not report["fully_classified"]:
        if report["has_wildcard"]:
            print("WARNING: wildcard mask prevents a bounded cost classification.")
        if report["unknown_fields"]:
            print("WARNING: unclassified fields: " + ", ".join(report["unknown_fields"]))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
