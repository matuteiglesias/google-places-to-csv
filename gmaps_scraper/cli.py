from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

from .api import normalize_field_mask
from .billing import VERIFIED_ON, assess_text_search_fields
from .kernel import utc_observed_at
from .normalize import flatten_place
from .profiles import DEFAULT_PROFILE, PROFILES, profile_fields
from .providers import DiscoveryRequest, ProviderSpec, get_provider, provider_names
from .utils import now_stamp, slugify, write_csv, write_json


OUTPUT_CONTRACTS = ("business", "refs", "provider")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Governed local-business discovery with Google Places Text Search today "
            "and a provider-ready output contract."
        )
    )
    parser.add_argument(
        "--query",
        "-q",
        required=True,
        help="Local-business discovery query (e.g. 'restaurants in Buenos Aires').",
    )
    parser.add_argument(
        "--provider",
        choices=provider_names(),
        default="google",
        help="Discovery provider (currently: google).",
    )

    selector = parser.add_mutually_exclusive_group()
    selector.add_argument(
        "--profile",
        choices=sorted(PROFILES),
        help=f"Named Google field profile (default: {DEFAULT_PROFILE}).",
    )
    selector.add_argument(
        "--fields",
        help="Expert override: comma-separated Google Places response fields.",
    )

    parser.add_argument(
        "--output-contract",
        choices=OUTPUT_CONTRACTS,
        default="business",
        help=(
            "business=provider-neutral record (default); refs=durable provider IDs only; "
            "provider=legacy Google-shaped output."
        ),
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=1,
        help="Maximum Google Text Search pages, 1..3 (default: 1).",
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
    if args.output_contract == "refs":
        if args.fields:
            raise SystemExit(
                "--output-contract refs intentionally uses the ids profile; custom --fields "
                "would add provider content without changing the durable handoff."
            )
        if args.profile not in (None, "ids"):
            raise SystemExit("--output-contract refs only accepts --profile ids.")
        selection_name = "ids"
        mask = ",".join(profile_fields("ids"))
    elif args.fields:
        selection_name = "custom"
        mask = args.fields
    else:
        selection_name = args.profile or DEFAULT_PROFILE
        mask = ",".join(profile_fields(selection_name))

    normalized_mask = normalize_field_mask(mask)
    fields = [part for part in normalized_mask.split(",") if part]
    return selection_name, fields


def describe_provider(spec: ProviderSpec, output_contract: str) -> None:
    print(f"Provider: {spec.key} ({spec.label})", file=sys.stderr)
    print(f"Output contract: {output_contract}", file=sys.stderr)
    print(f"Provider policy metadata verified: {spec.policy_verified_on}", file=sys.stderr)
    if output_contract == "refs":
        print(
            f"Persistence guidance: durable {spec.durable_identifier} handoff only.",
            file=sys.stderr,
        )
    else:
        print(
            f"Persistence guidance: {spec.persistence_mode}; see COMPLIANCE.md.",
            file=sys.stderr,
        )


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


def _dedupe_provider_results(provider: Any, raw_results: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: set[str] = set()
    unique: List[Dict[str, Any]] = []
    for raw in raw_results:
        ref = provider.to_ref(raw)
        if ref is None:
            unique.append(raw)
            continue
        key = f"{ref.provider}:{ref.provider_id}"
        if key in seen:
            continue
        seen.add(key)
        unique.append(raw)
    return unique


def _materialize_output(
    provider: Any,
    raw_results: List[Dict[str, Any]],
    *,
    output_contract: str,
    fields: list[str],
    query: str,
) -> list[dict[str, Any]]:
    if output_contract == "refs":
        observed_at = utc_observed_at()
        refs = [
            provider.to_ref(raw, source_query=query, observed_at=observed_at)
            for raw in raw_results
        ]
        return [ref.to_dict() for ref in refs if ref is not None]

    if output_contract == "business":
        return [provider.to_record(raw, source_query=query).to_dict() for raw in raw_results]

    if provider.spec.key != "google":
        raise SystemExit(
            "--output-contract provider is a legacy Google-specific surface; "
            "use business or refs for provider-neutral integrations."
        )
    return [flatten_place(raw, fields) for raw in raw_results]


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.max_pages < 1 or args.max_pages > 3:
        raise SystemExit("--max-pages must be between 1 and 3 for Google Text Search.")

    provider = get_provider(args.provider)
    selection_name, fields = resolve_fields(args)
    describe_provider(provider.spec, args.output_contract)
    describe_billing(selection_name, fields, args.max_pages)
    field_mask = ",".join(fields)

    raw_results = provider.search(
        DiscoveryRequest(
            query=args.query,
            field_mask=field_mask,
            max_pages=args.max_pages,
            language_code=args.language_code,
            region_code=args.region_code,
        )
    )
    raw_results = _dedupe_provider_results(provider, raw_results)
    rows = _materialize_output(
        provider,
        raw_results,
        output_contract=args.output_contract,
        fields=fields,
        query=args.query,
    )

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    base = (
        f"{slugify(args.query)}_{provider.spec.key}_{selection_name}_"
        f"{args.output_contract}_{args.max_pages}p_{now_stamp()}"
    )

    if args.format in ("csv", "both"):
        csv_path = out_dir / f"{base}.csv"
        write_csv(rows, csv_path)
        print(f"Wrote {len(rows)} rows -> {csv_path}")

    if args.format in ("json", "both"):
        json_path = out_dir / f"{base}.json"
        json_payload: Any = raw_results if args.output_contract == "provider" else rows
        write_json(json_payload, json_path)
        print(f"Wrote {len(rows)} records -> {json_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
