from __future__ import annotations

import unittest
from unittest.mock import patch

from gmaps_scraper.openmart import (
    _extract_records,
    openmart_business_to_record,
    openmart_business_to_ref,
    search_businesses,
)


SAMPLE = {
    "id": "loc_123",
    "content": {
        "business_name": "Example Dental",
        "store_name": "Example Dental Greenwich",
        "business_type": "Cosmetic Dentist",
        "business_categories": ["HEALTHCARE"],
        "tags": ["dentist", "cosmetic dentist"],
        "street_address": "1 Main St",
        "city": "Greenwich",
        "state": "Connecticut",
        "zipcode": "06830",
        "country": "US",
        "latitude": 41.0,
        "longitude": -73.6,
        "store_phones": ["+1-203-555-0100"],
        "website_url": "https://example.test",
        "google_rating": 4.8,
        "google_reviews_count": 120,
        "from_sources": {
            "GOOGLE_MAP": {
                "id": "place_abc",
                "ref_url": "https://www.google.com/maps/place/?q=place_id:place_abc",
            }
        },
    },
    "match_score": 12.5,
    "cursor": [12.5, "loc_123"],
}


class OpenmartAdapterTests(unittest.TestCase):
    def test_extracts_documented_search_shapes_only(self) -> None:
        self.assertEqual(_extract_records([SAMPLE]), [SAMPLE])
        self.assertEqual(_extract_records({"data": [SAMPLE], "total_count": 1}), [SAMPLE])
        with self.assertRaisesRegex(RuntimeError, "unsupported search response shape"):
            _extract_records({"data": {"results": [SAMPLE]}})

    def test_record_normalization_from_documented_content_object(self) -> None:
        record = openmart_business_to_record(SAMPLE, source_query="cosmetic dentist")
        self.assertEqual(record.provider, "openmart")
        self.assertEqual(record.provider_id, "loc_123")
        self.assertEqual(record.name, "Example Dental")
        self.assertEqual(
            record.formatted_address,
            "1 Main St, Greenwich, Connecticut, 06830, US",
        )
        self.assertEqual(record.primary_type, "Cosmetic Dentist")
        self.assertEqual(record.types, "HEALTHCARE")
        self.assertEqual(record.website, "https://example.test")
        self.assertEqual(record.phone, "+1-203-555-0100")
        self.assertEqual(record.rating, 4.8)
        self.assertEqual(record.review_count, 120)
        self.assertEqual(
            record.provider_url,
            "https://www.google.com/maps/place/?q=place_id:place_abc",
        )

    def test_ref_uses_top_level_openmart_id(self) -> None:
        ref = openmart_business_to_ref(
            SAMPLE,
            source_query="cosmetic dentist",
            observed_at="2026-09-07T20:00:00+00:00",
        )
        self.assertIsNotNone(ref)
        self.assertEqual(ref.provider, "openmart")
        self.assertEqual(ref.provider_id, "loc_123")
        self.assertEqual(ref.source_query, "cosmetic dentist")

    def test_search_uses_documented_cursor_pagination_and_location_array(self) -> None:
        first_page = [
            {"id": "loc_1", "content": {"business_name": "One"}, "cursor": [9.0, "loc_1"]},
            {"id": "loc_2", "content": {"business_name": "Two"}, "cursor": [8.0, "loc_2"]},
        ]
        second_page = [
            {"id": "loc_3", "content": {"business_name": "Three"}, "cursor": [7.0, "loc_3"]}
        ]
        with patch("gmaps_scraper.openmart.getenv_openmart_api_key", return_value="test-key"):
            with patch(
                "gmaps_scraper.openmart._request_json",
                side_effect=[first_page, second_page],
            ) as request:
                rows = search_businesses(
                    query="medical spa",
                    max_pages=2,
                    page_size=2,
                    city="Scottsdale",
                    state="AZ",
                    country="USA",
                )

        self.assertEqual(len(rows), 3)
        first_payload = request.call_args_list[0].args[0]
        second_payload = request.call_args_list[1].args[0]
        self.assertEqual(first_payload["limit"], 2)
        self.assertNotIn("cursor", first_payload)
        self.assertEqual(second_payload["cursor"], [8.0, "loc_2"])
        self.assertEqual(
            first_payload["location"],
            [{"city": "Scottsdale", "state": "AZ", "country": "USA"}],
        )
        self.assertFalse(first_payload["estimate_total"])

    def test_full_page_without_cursor_fails_instead_of_guessing_offset(self) -> None:
        full_page = [{"id": "a"}, {"id": "b"}]
        with patch("gmaps_scraper.openmart.getenv_openmart_api_key", return_value="test-key"):
            with patch("gmaps_scraper.openmart._request_json", return_value=full_page):
                with self.assertRaisesRegex(RuntimeError, "without the documented pagination cursor"):
                    search_businesses(query="dentist", max_pages=2, page_size=2)

    def test_page_size_has_conservative_preview_compatible_local_cap(self) -> None:
        with self.assertRaisesRegex(ValueError, "between 1 and 100"):
            search_businesses(query="x", page_size=101)


if __name__ == "__main__":
    unittest.main()
