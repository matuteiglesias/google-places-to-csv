from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, Sequence

from .kernel import utc_observed_at
from .providers import DiscoveryRequest, GeoArea, GeoCircle, get_provider
from .utils import now_stamp, slugify, write_csv, write_json


OUTPUT_CONTRACTS = ("business", "refs")


def _load_plan(path: str | Path) -> dict[str, Any]:
    plan_path = Path(path)
    try:
        payload = json.loads(plan_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Plan not found: {plan_path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON plan {plan_path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit("Census plan must be a JSON object.")
    return payload


def _plan_hash(plan: dict[str, Any]) -> str:
    encoded = json.dumps(plan, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _area_from_cell(cell: dict[str, Any]) -> GeoArea | None:
    values = (cell.get("city"), cell.get("state"), cell.get("country"))
    if not any(value not in (None, "") for value in values):
        return None
    return GeoArea(city=cell.get("city"), state=cell.get("state"), country=cell.get("country"))


def _circle_from_cell(cell: dict[str, Any]) -> GeoCircle | None:
    values = (cell.get("latitude"), cell.get("longitude"), cell.get("radius_m"))
    if all(value is None for value in values):
        return None
    if any(value is None for value in values):
        raise SystemExit(
            "Each circle census cell must provide latitude, longitude, and radius_m together."
        )
    return GeoCircle(
        latitude=float(cell["latitude"]),
        longitude=float(cell["longitude"]),
        radius_m=float(cell["radius_m"]),
    )


def _validated_plan(plan: dict[str, Any]) -> tuple[str, str, list[dict[str, Any]], int, int | None, str | None]:
    name = str(plan.get("name") or "business-census")
    provider_name = str(plan.get("provider") or "")
    if not provider_name:
        raise SystemExit("Census plan requires provider.")
    get_provider(provider_name)

    output_contract = str(plan.get("output_contract") or "business")
    if output_contract not in OUTPUT_CONTRACTS:
        raise SystemExit("Census output_contract must be business or refs.")

    cells = plan.get("cells")
    if not isinstance(cells, list) or not cells:
        raise SystemExit("Census plan requires a non-empty cells list.")
    normalized_cells: list[dict[str, Any]] = []
    for index, raw_cell in enumerate(cells, start=1):
        if not isinstance(raw_cell, dict):
            raise SystemExit(f"Census cell {index} must be an object.")
        query = str(raw_cell.get("query") or "").strip()
        if not query:
            raise SystemExit(f"Census cell {index} requires query.")
        cell = dict(raw_cell)
        cell["query"] = query
        cell.setdefault("label", f"cell-{index:02d}")
        normalized_cells.append(cell)

    max_pages = int(plan.get("max_pages", 1))
    if max_pages < 1 or max_pages > 3:
        raise SystemExit("Census plan max_pages must be between 1 and 3.")
    page_size_raw = plan.get("page_size")
    page_size = int(page_size_raw) if page_size_raw is not None else None
    if page_size is not None and page_size < 1:
        raise SystemExit("Census plan page_size must be >= 1.")

    field_mask_raw = plan.get("field_mask")
    field_mask = str(field_mask_raw).strip() if field_mask_raw not in (None, "") else None
    return name, provider_name, normalized_cells, max_pages, page_size, field_mask


def _cell_budget(cell: dict[str, Any], default_pages: int, default_page_size: int | None) -> tuple[int, int | None]:
    pages = int(cell.get("max_pages", default_pages))
    if pages < 1 or pages > 3:
        raise SystemExit(f"Cell {cell['label']} max_pages must be between 1 and 3.")
    page_size_raw = cell.get("page_size", default_page_size)
    page_size = int(page_size_raw) if page_size_raw is not None else None
    if page_size is not None and page_size < 1:
        raise SystemExit(f"Cell {cell['label']} page_size must be >= 1.")
    return pages, page_size


def _preflight(
    plan: dict[str, Any],
    *,
    max_total_requests: int,
) -> dict[str, Any]:
    name, provider_name, cells, default_pages, default_page_size, field_mask = _validated_plan(plan)
    provider = get_provider(provider_name)

    requests = 0
    max_records: int | None = 0
    cell_summaries: list[dict[str, Any]] = []
    for cell in cells:
        pages, page_size = _cell_budget(cell, default_pages, default_page_size)
        area = _area_from_cell(cell)
        circle = _circle_from_cell(cell)
        if area is not None and circle is not None:
            raise SystemExit(f"Cell {cell['label']} cannot combine structured area and circle.")

        if provider_name == "google":
            if not (cell.get("field_mask") or field_mask):
                raise SystemExit("Google census plans require field_mask at plan or cell level.")
            if area is not None:
                raise SystemExit("Google census cells currently support circles, not structured areas.")
            if page_size is not None:
                raise SystemExit("Google census does not expose page_size.")
        elif provider_name == "openmart":
            if circle is not None:
                raise SystemExit("Openmart census cells currently support structured areas, not circles.")
            if page_size is not None and page_size > 100:
                raise SystemExit(f"Cell {cell['label']} Openmart page_size must be <= 100.")

        requests += pages
        if page_size is None:
            max_records = None
        elif max_records is not None:
            max_records += pages * page_size
        cell_summaries.append(
            {
                "label": cell["label"],
                "query": cell["query"],
                "city": cell.get("city"),
                "state": cell.get("state"),
                "country": cell.get("country"),
                "max_pages": pages,
                "page_size": page_size,
            }
        )

    if requests > max_total_requests:
        raise SystemExit(
            f"Census would make at most {requests} provider requests, exceeding "
            f"--max-total-requests={max_total_requests}. Increase the budget explicitly."
        )

    return {
        "name": name,
        "provider": provider_name,
        "provider_label": provider.spec.label,
        "provider_policy_verified_on": provider.spec.policy_verified_on,
        "persistence_mode": provider.spec.persistence_mode,
        "output_contract": str(plan.get("output_contract") or "business"),
        "cells": cell_summaries,
        "cell_count": len(cells),
        "max_requests": requests,
        "max_records": max_records,
        "plan_sha256": _plan_hash(plan),
    }


def _identity_key(provider: Any, raw: Dict[str, Any], *, fallback: str) -> tuple[str, Any]:
    ref = provider.to_ref(raw)
    if ref is None:
        return fallback, None
    return f"{ref.provider}:{ref.provider_id}", ref


def _atomic_write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    tmp = path.with_name(path.name + ".tmp")
    write_csv(rows, tmp)
    tmp.replace(path)


def _atomic_write_json(payload: Any, path: Path) -> None:
    tmp = path.with_name(path.name + ".tmp")
    write_json(payload, tmp)
    tmp.replace(path)


def _checkpoint_manifest(
    *,
    preflight: dict[str, Any],
    observed_at: str,
    unique_rows: dict[str, dict[str, Any]],
    membership: list[dict[str, Any]],
    cell_results: list[dict[str, Any]],
    data_name: str,
    status: str,
    failed_cell: dict[str, Any] | None = None,
    last_error: str | None = None,
) -> dict[str, Any]:
    manifest = {
        **preflight,
        "status": status,
        "observed_at": observed_at,
        "completed_cells": len(cell_results),
        "unique_records": len(unique_rows),
        "membership_rows": len(membership),
        "cell_results": cell_results,
        "artifacts": {
            "records": data_name,
            "membership": "membership.csv",
            "checkpoint": "checkpoint.json",
            "manifest": "manifest.json",
        },
    }
    if failed_cell is not None:
        manifest["failed_cell"] = failed_cell
    if last_error is not None:
        manifest["last_error"] = last_error
    return manifest


def _persist_checkpoint(
    *,
    run_root: Path,
    preflight: dict[str, Any],
    observed_at: str,
    unique_rows: dict[str, dict[str, Any]],
    membership: list[dict[str, Any]],
    cell_results: list[dict[str, Any]],
    data_name: str,
    status: str,
    failed_cell: dict[str, Any] | None = None,
    last_error: str | None = None,
) -> dict[str, Any]:
    rows = list(unique_rows.values())
    _atomic_write_csv(rows, run_root / data_name)
    _atomic_write_csv(membership, run_root / "membership.csv")
    checkpoint = {
        "plan_sha256": preflight["plan_sha256"],
        "observed_at": observed_at,
        "unique_rows": unique_rows,
        "membership": membership,
        "cell_results": cell_results,
    }
    _atomic_write_json(checkpoint, run_root / "checkpoint.json")
    manifest = _checkpoint_manifest(
        preflight=preflight,
        observed_at=observed_at,
        unique_rows=unique_rows,
        membership=membership,
        cell_results=cell_results,
        data_name=data_name,
        status=status,
        failed_cell=failed_cell,
        last_error=last_error,
    )
    _atomic_write_json(manifest, run_root / "manifest.json")
    return manifest


def _load_checkpoint(run_root: Path, expected_plan_hash: str) -> tuple[str, dict[str, dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    checkpoint_path = run_root / "checkpoint.json"
    try:
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Resume checkpoint not found: {checkpoint_path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid resume checkpoint {checkpoint_path}: {exc}") from exc
    if checkpoint.get("plan_sha256") != expected_plan_hash:
        raise SystemExit("Resume checkpoint plan hash does not match the supplied census plan.")
    observed_at = str(checkpoint.get("observed_at") or utc_observed_at())
    unique_rows = checkpoint.get("unique_rows") or {}
    membership = checkpoint.get("membership") or []
    cell_results = checkpoint.get("cell_results") or []
    if not isinstance(unique_rows, dict) or not isinstance(membership, list) or not isinstance(cell_results, list):
        raise SystemExit("Resume checkpoint has an invalid shape.")
    return observed_at, unique_rows, membership, cell_results


def run_plan(
    plan: dict[str, Any],
    *,
    out_dir: str | Path,
    max_total_requests: int = 25,
    dry_run: bool = False,
    resume_run: str | Path | None = None,
) -> dict[str, Any]:
    preflight = _preflight(plan, max_total_requests=max_total_requests)
    print(
        f"Census preflight: {preflight['cell_count']} cells; "
        f"max {preflight['max_requests']} provider requests; "
        f"max records {preflight['max_records'] if preflight['max_records'] is not None else 'provider-defined'}.",
        file=sys.stderr,
    )
    print(
        f"Provider persistence mode: {preflight['persistence_mode']} "
        f"(metadata verified {preflight['provider_policy_verified_on']}).",
        file=sys.stderr,
    )
    if dry_run:
        return preflight

    name, provider_name, cells, default_pages, default_page_size, default_field_mask = _validated_plan(plan)
    output_contract = str(plan.get("output_contract") or "business")
    provider = get_provider(provider_name)
    data_name = "businesses.csv" if output_contract == "business" else "refs.csv"

    if resume_run is not None:
        run_root = Path(resume_run)
        if not run_root.is_dir():
            raise SystemExit(f"Resume run directory not found: {run_root}")
        observed_at, unique_rows, membership, cell_results = _load_checkpoint(
            run_root, preflight["plan_sha256"]
        )
        print(
            f"Resuming {run_root}: {len(cell_results)} completed cells, "
            f"{len(unique_rows)} persisted unique records.",
            file=sys.stderr,
        )
    else:
        observed_at = utc_observed_at()
        unique_rows: dict[str, dict[str, Any]] = {}
        membership: list[dict[str, Any]] = []
        cell_results: list[dict[str, Any]] = []
        run_root = Path(out_dir) / f"{slugify(name)}_{now_stamp()}"
        run_root.mkdir(parents=True, exist_ok=False)
        _persist_checkpoint(
            run_root=run_root,
            preflight=preflight,
            observed_at=observed_at,
            unique_rows=unique_rows,
            membership=membership,
            cell_results=cell_results,
            data_name=data_name,
            status="in_progress",
        )
        print(f"Checkpoint run directory: {run_root}", file=sys.stderr)

    completed_indices = {
        int(result["cell_index"])
        for result in cell_results
        if isinstance(result, dict) and result.get("cell_index") is not None
    }

    for cell_index, cell in enumerate(cells, start=1):
        if cell_index in completed_indices:
            print(
                f"[{cell_index}/{len(cells)}] {cell['label']}: already checkpointed; skipping.",
                file=sys.stderr,
            )
            continue

        pages, page_size = _cell_budget(cell, default_pages, default_page_size)
        area = _area_from_cell(cell)
        circle = _circle_from_cell(cell)
        field_mask = cell.get("field_mask") or default_field_mask

        try:
            raw_results = provider.search(
                DiscoveryRequest(
                    query=cell["query"],
                    field_mask=field_mask,
                    max_pages=pages,
                    page_size=page_size,
                    circle=circle,
                    area=area,
                )
            )
        except Exception as exc:
            error_text = f"{type(exc).__name__}: {exc}"
            manifest = _persist_checkpoint(
                run_root=run_root,
                preflight=preflight,
                observed_at=observed_at,
                unique_rows=unique_rows,
                membership=membership,
                cell_results=cell_results,
                data_name=data_name,
                status="failed",
                failed_cell={
                    "cell_index": cell_index,
                    "label": cell["label"],
                    "query": cell["query"],
                },
                last_error=error_text,
            )
            print(
                f"Cell {cell_index} failed; preserved {manifest['unique_records']} unique records "
                f"from {manifest['completed_cells']} completed cells in {run_root}.",
                file=sys.stderr,
            )
            raise

        new_unique = 0
        for row_index, raw in enumerate(raw_results, start=1):
            fallback = f"unresolved:{cell_index}:{row_index}"
            identity_key, ref = _identity_key(provider, raw, fallback=fallback)
            if identity_key not in unique_rows:
                if output_contract == "refs":
                    if ref is None:
                        continue
                    unique_rows[identity_key] = provider.to_ref(
                        raw,
                        source_query=cell["query"],
                        observed_at=observed_at,
                    ).to_dict()
                else:
                    unique_rows[identity_key] = provider.to_record(
                        raw,
                        source_query=cell["query"],
                    ).to_dict()
                new_unique += 1

            membership.append(
                {
                    "identity_key": identity_key,
                    "provider": ref.provider if ref is not None else provider_name,
                    "provider_id": ref.provider_id if ref is not None else None,
                    "cell_label": cell["label"],
                    "query": cell["query"],
                    "city": cell.get("city"),
                    "state": cell.get("state"),
                    "country": cell.get("country"),
                }
            )

        cell_results.append(
            {
                "cell_index": cell_index,
                "label": cell["label"],
                "query": cell["query"],
                "observations": len(raw_results),
                "new_unique": new_unique,
            }
        )
        manifest = _persist_checkpoint(
            run_root=run_root,
            preflight=preflight,
            observed_at=observed_at,
            unique_rows=unique_rows,
            membership=membership,
            cell_results=cell_results,
            data_name=data_name,
            status="in_progress",
        )
        print(
            f"[{cell_index}/{len(cells)}] {cell['label']}: "
            f"{len(raw_results)} observations, {new_unique} new unique; checkpointed "
            f"{manifest['unique_records']} unique.",
            file=sys.stderr,
        )

    manifest = _persist_checkpoint(
        run_root=run_root,
        preflight=preflight,
        observed_at=observed_at,
        unique_rows=unique_rows,
        membership=membership,
        cell_results=cell_results,
        data_name=data_name,
        status="complete",
    )
    print(f"Wrote {manifest['unique_records']} unique records -> {run_root / data_name}")
    print(f"Wrote {manifest['membership_rows']} membership rows -> {run_root / 'membership.csv'}")
    print(f"Wrote run manifest -> {run_root / 'manifest.json'}")
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a bounded, deduplicated local-business census from a JSON plan."
    )
    parser.add_argument("plan", help="Path to census JSON plan.")
    parser.add_argument("--out-dir", default="out/census")
    parser.add_argument(
        "--max-total-requests",
        type=int,
        default=25,
        help="Hard safety budget for provider requests across all cells (default: 25).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print the request/record budget without network calls.",
    )
    parser.add_argument(
        "--resume-run",
        default=None,
        help="Resume a checkpointed run directory; completed cells are not requested again.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.max_total_requests < 1:
        raise SystemExit("--max-total-requests must be >= 1.")
    if args.dry_run and args.resume_run:
        raise SystemExit("--dry-run cannot be combined with --resume-run.")
    plan = _load_plan(args.plan)
    result = run_plan(
        plan,
        out_dir=args.out_dir,
        max_total_requests=args.max_total_requests,
        dry_run=args.dry_run,
        resume_run=args.resume_run,
    )
    if args.dry_run:
        print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())