from __future__ import annotations

import unittest

from gmaps_scraper.billing import TextSearchTier, assess_text_search_fields
from gmaps_scraper.profiles import (
    ATMOSPHERE_FIELDS,
    CORE_FIELDS,
    ENTERPRISE_FIELDS,
    IDS_FIELDS,
)


class BillingProfileTests(unittest.TestCase):
    def test_ids_profile_is_ids_only(self) -> None:
        assessment = assess_text_search_fields(IDS_FIELDS)
        self.assertTrue(assessment.fully_classified)
        self.assertEqual(assessment.highest_tier, TextSearchTier.ESSENTIALS_IDS_ONLY)

    def test_core_profile_is_pro(self) -> None:
        assessment = assess_text_search_fields(CORE_FIELDS)
        self.assertTrue(assessment.fully_classified)
        self.assertEqual(assessment.highest_tier, TextSearchTier.PRO)

    def test_enterprise_profile_is_enterprise(self) -> None:
        assessment = assess_text_search_fields(ENTERPRISE_FIELDS)
        self.assertTrue(assessment.fully_classified)
        self.assertEqual(assessment.highest_tier, TextSearchTier.ENTERPRISE)

    def test_atmosphere_profile_is_atmosphere(self) -> None:
        assessment = assess_text_search_fields(ATMOSPHERE_FIELDS)
        self.assertTrue(assessment.fully_classified)
        self.assertEqual(
            assessment.highest_tier,
            TextSearchTier.ENTERPRISE_ATMOSPHERE,
        )

    def test_rating_and_website_raise_to_enterprise(self) -> None:
        for field in ("places.rating", "places.websiteUri"):
            with self.subTest(field=field):
                assessment = assess_text_search_fields((*CORE_FIELDS, field))
                self.assertEqual(assessment.highest_tier, TextSearchTier.ENTERPRISE)

    def test_reviews_raise_to_atmosphere(self) -> None:
        for field in ("places.reviews", "places.reviewSummary"):
            with self.subTest(field=field):
                assessment = assess_text_search_fields((*CORE_FIELDS, field))
                self.assertEqual(
                    assessment.highest_tier,
                    TextSearchTier.ENTERPRISE_ATMOSPHERE,
                )

    def test_nested_fields_use_billable_parent(self) -> None:
        assessment = assess_text_search_fields(
            ("places.displayName.text", "places.rating")
        )
        self.assertTrue(assessment.fully_classified)
        self.assertEqual(assessment.highest_tier, TextSearchTier.ENTERPRISE)

    def test_unknown_field_is_not_classified_as_cheap(self) -> None:
        assessment = assess_text_search_fields(("places.displayName", "places.futureField"))
        self.assertFalse(assessment.fully_classified)
        self.assertEqual(assessment.unknown_fields, ("places.futureField",))
        self.assertEqual(assessment.label, "UNCLASSIFIED")

    def test_wildcard_is_not_classified_as_cheap(self) -> None:
        assessment = assess_text_search_fields("*")
        self.assertFalse(assessment.fully_classified)
        self.assertTrue(assessment.has_wildcard)
        self.assertEqual(assessment.label, "UNCLASSIFIED")


if __name__ == "__main__":
    unittest.main()
