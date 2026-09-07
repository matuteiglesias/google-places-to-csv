from __future__ import annotations

import unittest

from gmaps_scraper.kernel import google_place_to_business_record, google_place_to_ref
from gmaps_scraper.providers import GOOGLE_SPEC, OPENMART_SPEC, get_provider, provider_names


PLACE = {
    "id": "pid-1",
    "name": "places/pid-1",
    "displayName": {"text": "Cafe Uno"},
    "formattedAddress": "Calle 1",
    "location": {"latitude": -34.1, "longitude": -58.2},
    "primaryType": "cafe",
    "types": ["cafe", "food"],
    "businessStatus": "OPERATIONAL",
    "websiteUri": "https://example.com",
    "internationalPhoneNumber": "+54 11 5555 0000",
    "rating": 4.7,
    "userRatingCount": 42,
    "googleMapsUri": "https://maps.google.com/example",
}


class KernelContractTests(unittest.TestCase):
    def test_provider_registry_has_explicit_policy_metadata(self) -> None:
        self.assertEqual(provider_names(), ("google", "openmart"))
        google = get_provider("google")
        openmart = get_provider("openmart")
        self.assertEqual(google.spec, GOOGLE_SPEC)
        self.assertEqual(openmart.spec, OPENMART_SPEC)
        self.assertEqual(google.spec.persistence_mode, "provider-terms-controlled")
        self.assertIn("durable-id-handoff", google.spec.capabilities)
        self.assertEqual(openmart.spec.persistence_mode, "provider-documented-lead-generation")
        self.assertIn("lead-generation", openmart.spec.capabilities)
        self.assertTrue(google.spec.terms_url.startswith("https://cloud.google.com/"))
        self.assertTrue(openmart.spec.docs_url.startswith("https://www.openmart.com/"))

    def test_business_ref_contains_only_provider_identity_and_client_provenance(self) -> None:
        ref = google_place_to_ref(
            PLACE,
            source_query="cafes",
            observed_at="2026-09-07T19:00:00+00:00",
        )
        self.assertIsNotNone(ref)
        payload = ref.to_dict()
        self.assertEqual(
            set(payload),
            {"provider", "provider_id", "source_query", "observed_at"},
        )
        self.assertEqual(payload["provider_id"], "pid-1")
        self.assertNotIn("Cafe Uno", payload.values())
        self.assertNotIn("https://example.com", payload.values())

    def test_ref_can_recover_id_from_google_resource_name(self) -> None:
        ref = google_place_to_ref({"name": "places/fallback-id"})
        self.assertEqual(ref.provider_id, "fallback-id")

    def test_business_record_is_provider_neutral(self) -> None:
        record = google_place_to_business_record(PLACE, source_query="cafes")
        payload = record.to_dict()
        self.assertEqual(payload["provider"], "google")
        self.assertEqual(payload["provider_id"], "pid-1")
        self.assertEqual(payload["name"], "Cafe Uno")
        self.assertEqual(payload["website"], "https://example.com")
        self.assertEqual(payload["phone"], "+54 11 5555 0000")
        self.assertEqual(payload["review_count"], 42)
        self.assertEqual(payload["source_query"], "cafes")


if __name__ == "__main__":
    unittest.main()
