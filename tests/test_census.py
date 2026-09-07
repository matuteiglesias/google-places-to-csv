from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gmaps_scraper.census import _preflight, run_plan
from gmaps_scraper.kernel import BusinessRecord, BusinessRef
from gmaps_scraper.providers import ProviderSpec


PLAN = {
    "name": "demo",
    "provider": "openmart",
    "output_contract": "business",
    "page_size": 50,
    "max_pages": 1,
    "cells": [
        {"label": "a", "query": "dentist", "city": "Greenwich", "state": "CT", "country": "US"},
        {"label": "b", "query": "medical spa", "city": "Greenwich", "state": "CT", "country": "US"},
    ],
}


class FakeProvider:
    spec = ProviderSpec(
        key="openmart",
        label="Fake Openmart",
        docs_url="https://example.test/docs",
        terms_url="https://example.test/terms",
        policy_verified_on="2026-09-07",
        persistence_mode="provider-documented-lead-generation",
        persistence_summary="test",
        durable_identifier="openmart_id",
        capabilities=("text-search",),
    )

    def __init__(self, *, fail_query: str | None = None) -> None:
        self.fail_query = fail_query
        self.calls: list[str] = []

    def search(self, request):
        self.calls.append(request.query)
        if request.query == self.fail_query:
            raise RuntimeError("synthetic provider failure")
        if request.query == "dentist":
            return [
                {"id": "loc_1", "company_name": "One"},
                {"id": "loc_shared", "company_name": "Shared"},
            ]
        return [
            {"id": "loc_shared", "company_name": "Shared"},
            {"id": "loc_2", "company_name": "Two"},
        ]

    def to_ref(self, raw, *, source_query=None, observed_at=None):
        return BusinessRef(
            provider="openmart",
            provider_id=raw["id"],
            source_query=source_query,
            observed_at=observed_at,
        )

    def to_record(self, raw, *, source_query=None):
        return BusinessRecord(
            provider="openmart",
            provider_id=raw["id"],
            name=raw["company_name"],
            source_query=source_query,
        )


class CensusTests(unittest.TestCase):
    def test_preflight_counts_request_and_record_budget(self) -> None:
        result = _preflight(PLAN, max_total_requests=5)
        self.assertEqual(result["cell_count"], 2)
        self.assertEqual(result["max_requests"], 2)
        self.assertEqual(result["max_records"], 100)

    def test_preflight_enforces_total_request_budget(self) -> None:
        with self.assertRaisesRegex(SystemExit, "exceeding --max-total-requests=1"):
            _preflight(PLAN, max_total_requests=1)

    def test_run_deduplicates_across_cells_and_preserves_membership(self) -> None:
        fake = FakeProvider()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("gmaps_scraper.census.get_provider", return_value=fake):
                manifest = run_plan(PLAN, out_dir=tmpdir, max_total_requests=5)

            self.assertEqual(manifest["status"], "complete")
            self.assertEqual(manifest["unique_records"], 3)
            self.assertEqual(manifest["membership_rows"], 4)
            run_dirs = list(Path(tmpdir).iterdir())
            self.assertEqual(len(run_dirs), 1)
            run_dir = run_dirs[0]
            self.assertTrue((run_dir / "businesses.csv").exists())
            self.assertTrue((run_dir / "membership.csv").exists())
            self.assertTrue((run_dir / "manifest.json").exists())
            self.assertTrue((run_dir / "checkpoint.json").exists())

    def test_completed_cell_is_checkpointed_before_later_failure(self) -> None:
        fake = FakeProvider(fail_query="medical spa")
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("gmaps_scraper.census.get_provider", return_value=fake):
                with self.assertRaisesRegex(RuntimeError, "synthetic provider failure"):
                    run_plan(PLAN, out_dir=tmpdir, max_total_requests=5)

            run_dir = next(Path(tmpdir).iterdir())
            manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
            checkpoint = json.loads((run_dir / "checkpoint.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "failed")
            self.assertEqual(manifest["completed_cells"], 1)
            self.assertEqual(manifest["unique_records"], 2)
            self.assertEqual(manifest["failed_cell"]["label"], "b")
            self.assertIn("synthetic provider failure", manifest["last_error"])
            self.assertEqual(len(checkpoint["unique_rows"]), 2)
            self.assertEqual(len(checkpoint["cell_results"]), 1)
            self.assertTrue((run_dir / "businesses.csv").exists())
            self.assertTrue((run_dir / "membership.csv").exists())

    def test_resume_skips_checkpointed_cells_and_finishes_run(self) -> None:
        failing = FakeProvider(fail_query="medical spa")
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("gmaps_scraper.census.get_provider", return_value=failing):
                with self.assertRaises(RuntimeError):
                    run_plan(PLAN, out_dir=tmpdir, max_total_requests=5)

            run_dir = next(Path(tmpdir).iterdir())
            resumed = FakeProvider()
            with patch("gmaps_scraper.census.get_provider", return_value=resumed):
                manifest = run_plan(
                    PLAN,
                    out_dir=tmpdir,
                    max_total_requests=5,
                    resume_run=run_dir,
                )

            self.assertEqual(resumed.calls, ["medical spa"])
            self.assertEqual(manifest["status"], "complete")
            self.assertEqual(manifest["completed_cells"], 2)
            self.assertEqual(manifest["unique_records"], 3)
            self.assertEqual(manifest["membership_rows"], 4)

    def test_resume_rejects_changed_plan(self) -> None:
        failing = FakeProvider(fail_query="medical spa")
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("gmaps_scraper.census.get_provider", return_value=failing):
                with self.assertRaises(RuntimeError):
                    run_plan(PLAN, out_dir=tmpdir, max_total_requests=5)
            run_dir = next(Path(tmpdir).iterdir())
            changed = dict(PLAN)
            changed["name"] = "different"
            with patch("gmaps_scraper.census.get_provider", return_value=FakeProvider()):
                with self.assertRaisesRegex(SystemExit, "plan hash does not match"):
                    run_plan(
                        changed,
                        out_dir=tmpdir,
                        max_total_requests=5,
                        resume_run=run_dir,
                    )

    def test_dry_run_does_not_create_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = run_plan(PLAN, out_dir=tmpdir, max_total_requests=5, dry_run=True)
            self.assertEqual(result["max_requests"], 2)
            self.assertEqual(list(Path(tmpdir).iterdir()), [])


if __name__ == "__main__":
    unittest.main()