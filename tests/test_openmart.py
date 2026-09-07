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
    "company_name": "Example Dental",
    "company_type": "dentist",
    "company_categories": ["Dentist", "Cosmetic Dentist"],
    "street_address": "1 Main St",
    "city": "Greenwich",
    "state": "CT",
    "zipcode": "06830",
    "latitude": 41.0,
    "longitude": -73.6,
    "company_phones": ["+1-203-555-0100"],
    "website_url": "https://example.test",
    "google_rating": 4.8,
    "google_reviews_count": 120,
}


class OpenmartAdapterTests(unittest.TestCase):
    def test_extracts_known_response_envelopes(self) -> None:
        self.assertEqual(_extract_records([SAMPLE]), [SAMPLE])
        self.assertEqual(_extract_records({"data": [SAMPLE]}), [SAMPLE])
        self.assertEqual(_extract_records({"data": {"results": [SAMPLE]}}), [SAMPLE])

    def test_record_normalization(self) -> None:
        record = openmart_business_to_record(SAMPLE, source_query="cosmetic dentist")
        self.assertEqual(record.provider, "openmart")
        self.assertEqual(record.provider_id, "loc_123")
        self.assertEqual(record.name, "Example Dental")
        self.assertEqual(record.formatted_address, "1 Main St, Greenwich, CT, 06830")
        self.assertEqual(record.primary_type, "dentist")
        self.assertEqual(record.types, "Dentist,Cosmetic Dentist")
        self.assertEqual(record.website, "https://example.test")
        self.assertEqual(record.phone, "+1-203-555-0100")
        self.assertEqual(record.rating, 4.8)
        self.assertEqual(record.review_count, 120)

    def test_ref_uses_openmart_id(self) -> None:
        ref = openmart_business_to_ref(SAMPLE, source_query="cosmetic dentist", observed_at="2026-09-07T20:00:00+00:00")
        self.assertIsNotNone(ref)
        self.assertEqual(ref.provider, "openmart")
        self.assertEqual(ref.provider_id, "loc_123")
        self.assertEqual(ref.source_query, "cosmetic dentist")

    def test_search_uses_bounded_offset_pagination_and_location(self) -> None:
        first_page = [{"id": f"loc_{i}"} for i in range(2)]
        second_page = [{"id": "loc_2"}]
        with patch("gmaps_scraper.openmart.getenv_openmart_api_key", return_value="test-key"):
            with patch("gmaps_scraper.openmart._request_json", side_effect=[{"data": first_page}, {"data": second_page}]) as request:
                rows = search_businesses(
                    query="medical spa",
                    max_pages=2,
                    page_size=2,
                    city="Scottsdale",
                    state="AZ",
                    country="US",
                )

        self.assertEqual(len(rows), 3)
        first_payload = request.call_args_list[0].args[0]
        second_payload = request.call_args_list[1].args[0]
        self.assertEqual(first_payload["pagination"]["start"], 0)
        self.assertEqual(second_payload["pagination"]["start"], 2)
        self.assertEqual(first_payload["pagination"]["limit"], 2)
        self.assertEqual(
            first_payload["location"],
            {"city": "Scottsdale", "state": "AZ", "country": "US"},
        )

    def test_page_size_is_bounded(self) -> None:
        with self.assertRaisesRegex(ValueError, "between 1 and 100"):
            search_businesses(query="x", page_size=101)


if __name__ == "__main__":
    unittest.main()
