from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout

from gmaps_scraper import costcheck


class CostcheckTests(unittest.TestCase):
    def test_enterprise_field_is_classified_without_network_access(self) -> None:
        report = costcheck.assess_selection(
            "places.displayName,places.websiteUri",
            selection="custom",
            max_requests=2,
        )
        self.assertEqual(report["highest_sku"], "Text Search Enterprise")
        self.assertTrue(report["fully_classified"])
        self.assertEqual(report["max_requests"], 2)

    def test_unknown_field_returns_nonzero_and_json_evidence(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            rc = costcheck.main(
                [
                    "--fields",
                    "places.displayName,places.futureField",
                    "--json",
                ]
            )
        self.assertEqual(rc, 2)
        payload = json.loads(stdout.getvalue())
        self.assertFalse(payload["fully_classified"])
        self.assertEqual(payload["highest_sku"], "UNCLASSIFIED")
        self.assertEqual(payload["unknown_fields"], ["places.futureField"])

    def test_profile_surface_exposes_core_as_pro(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            rc = costcheck.main(["--profile", "core"])
        self.assertEqual(rc, 0)
        self.assertIn("Highest triggered SKU: Text Search Pro", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
