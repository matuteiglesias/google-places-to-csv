from __future__ import annotations

import csv
import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from gmaps_scraper import cli
from gmaps_scraper.profiles import CORE_FIELDS


SAMPLE_PLACE = {
    "id": "abc",
    "name": "places/abc",
    "displayName": {"text": "Example Cafe"},
    "formattedAddress": "1 Example St",
    "location": {"latitude": -34.6, "longitude": -58.4},
    "primaryType": "cafe",
    "types": ["cafe", "food"],
    "businessStatus": "OPERATIONAL",
    "googleMapsUri": "https://maps.google.com/example",
    "rating": 4.8,
}


class CliContractTests(unittest.TestCase):
    def test_default_is_google_core_business_one_page(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            stderr = io.StringIO()
            stdout = io.StringIO()
            with patch("gmaps_scraper.providers.search_text", return_value=[SAMPLE_PLACE]) as search:
                with redirect_stderr(stderr), redirect_stdout(stdout):
                    rc = cli.main(
                        [
                            "--query",
                            "example cafe",
                            "--out-dir",
                            tmpdir,
                        ]
                    )

            self.assertEqual(rc, 0)
            self.assertEqual(search.call_args.kwargs["max_pages"], 1)
            field_mask = search.call_args.kwargs["field_mask"]
            self.assertIn("places.displayName", field_mask)
            self.assertNotIn("places.rating", field_mask)
            self.assertNotIn("places.websiteUri", field_mask)
            self.assertNotIn("places.reviews", field_mask)

            preflight = stderr.getvalue()
            self.assertIn("Provider: google", preflight)
            self.assertIn("Output contract: business", preflight)
            self.assertIn("Highest triggered SKU: Text Search Pro", preflight)
            self.assertIn("Maximum Text Search requests this run: 1", preflight)

            csv_path = next(Path(tmpdir).glob("*.csv"))
            with csv_path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["provider"], "google")
            self.assertEqual(rows[0]["provider_id"], "abc")
            self.assertEqual(rows[0]["name"], "Example Cafe")
            self.assertEqual(rows[0]["source_query"], "example cafe")

    def test_geographic_circle_maps_to_google_location_bias(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            stderr = io.StringIO()
            with patch("gmaps_scraper.providers.search_text", return_value=[]) as search:
                with redirect_stderr(stderr), redirect_stdout(io.StringIO()):
                    cli.main(
                        [
                            "--query",
                            "cafes",
                            "--center",
                            "-34.60,-58.38",
                            "--radius-m",
                            "2500",
                            "--out-dir",
                            tmpdir,
                        ]
                    )

            self.assertEqual(
                search.call_args.kwargs["location_bias"],
                {
                    "circle": {
                        "center": {"latitude": -34.6, "longitude": -58.38},
                        "radius": 2500.0,
                    }
                },
            )
            self.assertIn("Geographic bias: circle(-34.6,-58.38, radius_m=2500)", stderr.getvalue())

    def test_geographic_circle_requires_center_and_radius_together(self) -> None:
        with self.assertRaisesRegex(SystemExit, "must be provided together"):
            cli.main(["--query", "cafes", "--center", "-34.6,-58.4"])

    def test_google_radius_is_bounded_before_network_access(self) -> None:
        with patch("gmaps_scraper.providers.search_text") as search:
            with self.assertRaisesRegex(SystemExit, "between 0 and 50000"):
                cli.main(
                    [
                        "--query",
                        "cafes",
                        "--center",
                        "-34.6,-58.4",
                        "--radius-m",
                        "50001",
                    ]
                )
            search.assert_not_called()

    def test_provider_output_preserves_custom_field_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("gmaps_scraper.providers.search_text", return_value=[SAMPLE_PLACE]) as search:
                with redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
                    cli.main(
                        [
                            "--query",
                            "example cafe",
                            "--fields",
                            "places.displayName,places.formattedAddress",
                            "--output-contract",
                            "provider",
                            "--out-dir",
                            tmpdir,
                        ]
                    )

            field_mask = search.call_args.kwargs["field_mask"]
            self.assertEqual(
                field_mask,
                "nextPageToken,places.displayName,places.formattedAddress",
            )

            csv_path = next(Path(tmpdir).glob("*.csv"))
            with csv_path.open(newline="", encoding="utf-8") as handle:
                header = next(csv.reader(handle))
            self.assertIn("display_name", header)
            self.assertIn("formatted_address", header)
            self.assertNotIn("rating", header)
            self.assertNotIn("website", header)
            self.assertNotIn("nextPageToken", header)

    def test_refs_contract_forces_ids_only_and_is_durable_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            stderr = io.StringIO()
            with patch("gmaps_scraper.providers.search_text", return_value=[SAMPLE_PLACE]) as search:
                with redirect_stderr(stderr), redirect_stdout(io.StringIO()):
                    cli.main(
                        [
                            "--query",
                            "example cafe",
                            "--output-contract",
                            "refs",
                            "--out-dir",
                            tmpdir,
                        ]
                    )

            self.assertEqual(
                search.call_args.kwargs["field_mask"],
                "nextPageToken,places.id,places.name",
            )
            self.assertIn("Essentials (IDs Only)", stderr.getvalue())
            self.assertIn("durable place_id handoff only", stderr.getvalue())

            csv_path = next(Path(tmpdir).glob("*.csv"))
            with csv_path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(
                set(rows[0]),
                {"provider", "provider_id", "source_query", "observed_at"},
            )
            self.assertEqual(rows[0]["provider"], "google")
            self.assertEqual(rows[0]["provider_id"], "abc")
            self.assertNotIn("Example Cafe", rows[0].values())

    def test_refs_rejects_non_ids_profile(self) -> None:
        with self.assertRaisesRegex(SystemExit, "only accepts --profile ids"):
            cli.main(
                [
                    "--query",
                    "x",
                    "--output-contract",
                    "refs",
                    "--profile",
                    "enterprise",
                ]
            )

    def test_profile_and_custom_fields_are_mutually_exclusive(self) -> None:
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                cli.parse_args(
                    [
                        "--query",
                        "x",
                        "--profile",
                        "core",
                        "--fields",
                        "places.id",
                    ]
                )

    def test_invalid_page_count_fails_before_network_access(self) -> None:
        with patch("gmaps_scraper.providers.search_text") as search:
            with self.assertRaisesRegex(SystemExit, "between 1 and 3"):
                cli.main(["--query", "x", "--max-pages", "4"])
            search.assert_not_called()

    def test_core_profile_constant_contains_no_review_fields(self) -> None:
        self.assertNotIn("places.reviews", CORE_FIELDS)
        self.assertNotIn("places.reviewSummary", CORE_FIELDS)


if __name__ == "__main__":
    unittest.main()
