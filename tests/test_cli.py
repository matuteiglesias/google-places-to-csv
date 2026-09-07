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
    def test_default_profile_is_core_pro_and_one_page(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            stderr = io.StringIO()
            stdout = io.StringIO()
            with patch("gmaps_scraper.cli.search_text", return_value=[SAMPLE_PLACE]) as search:
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
            self.assertIn("Highest triggered SKU: Text Search Pro", stderr.getvalue())
            self.assertIn("Maximum Text Search requests this run: 1", stderr.getvalue())

            csv_files = list(Path(tmpdir).glob("*.csv"))
            self.assertEqual(len(csv_files), 1)
            with csv_files[0].open(newline="", encoding="utf-8") as handle:
                header = next(csv.reader(handle))
            self.assertIn("display_name", header)
            self.assertNotIn("rating", header)
            self.assertNotIn("nextPageToken", header)

    def test_custom_fields_control_request_and_csv_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("gmaps_scraper.cli.search_text", return_value=[SAMPLE_PLACE]) as search:
                with redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
                    cli.main(
                        [
                            "--query",
                            "example cafe",
                            "--fields",
                            "places.displayName,places.formattedAddress",
                            "--max-pages",
                            "1",
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
        with patch("gmaps_scraper.cli.search_text") as search:
            with self.assertRaisesRegex(SystemExit, "between 1 and 3"):
                cli.main(["--query", "x", "--max-pages", "4"])
            search.assert_not_called()

    def test_core_profile_constant_contains_no_review_fields(self) -> None:
        self.assertNotIn("places.reviews", CORE_FIELDS)
        self.assertNotIn("places.reviewSummary", CORE_FIELDS)


if __name__ == "__main__":
    unittest.main()
