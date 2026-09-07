from __future__ import annotations

import unittest
from unittest.mock import patch

import requests

from gmaps_scraper import api


class FakeResponse:
    def __init__(self, status_code: int, payload=None, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class ApiContractTests(unittest.TestCase):
    def test_normalize_field_mask_adds_next_token_once_and_dedupes(self) -> None:
        mask = api.normalize_field_mask(
            "places.id, places.displayName,places.id,places.nextPageToken"
        )
        self.assertEqual(
            mask,
            "places.id,places.displayName,nextPageToken",
        )

    def test_normalize_field_mask_rejects_empty(self) -> None:
        with self.assertRaises(ValueError):
            api.normalize_field_mask(" , ")

    def test_retryable_http_response_is_bounded_and_uses_timeout(self) -> None:
        responses = iter(
            [
                FakeResponse(429, text="quota/rate"),
                FakeResponse(200, payload={"places": []}),
            ]
        )
        calls = []
        sleeps = []

        def request_func(url, **kwargs):
            calls.append((url, kwargs))
            return next(responses)

        payload = api._request_json(
            "places:searchText",
            {"textQuery": "x"},
            "places.id",
            "fake-key",
            max_retries=2,
            timeout=7.5,
            request_func=request_func,
            sleep_func=sleeps.append,
        )
        self.assertEqual(payload, {"places": []})
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][1]["timeout"], 7.5)
        self.assertEqual(sleeps, [1.0])
        self.assertEqual(
            calls[0][1]["headers"]["X-Goog-FieldMask"],
            "nextPageToken,places.id",
        )

    def test_network_exception_is_not_retried(self) -> None:
        call_count = 0

        def request_func(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise requests.Timeout("ambiguous")

        with self.assertRaisesRegex(RuntimeError, "not retried automatically"):
            api._request_json(
                "places:searchText",
                {"textQuery": "x"},
                "places.id",
                "fake-key",
                request_func=request_func,
                sleep_func=lambda _seconds: None,
            )
        self.assertEqual(call_count, 1)

    def test_pagination_uses_page_token_and_respects_max_pages(self) -> None:
        responses = [
            {"places": [{"id": "1"}], "nextPageToken": "a"},
            {"places": [{"id": "2"}], "nextPageToken": "b"},
            {"places": [{"id": "3"}], "nextPageToken": "c"},
        ]
        seen_payloads = []

        def fake_request(path, payload, field_mask, api_key):
            seen_payloads.append(dict(payload))
            return responses[len(seen_payloads) - 1]

        with patch("gmaps_scraper.api._request_json", side_effect=fake_request):
            places = api._paginate(
                "places:searchText",
                {"textQuery": "x"},
                "places.id",
                "fake-key",
                max_pages=3,
            )

        self.assertEqual([place["id"] for place in places], ["1", "2", "3"])
        self.assertNotIn("pageToken", seen_payloads[0])
        self.assertEqual(seen_payloads[1]["pageToken"], "a")
        self.assertEqual(seen_payloads[2]["pageToken"], "b")

    def test_search_rejects_more_than_three_pages_before_key_lookup(self) -> None:
        with self.assertRaises(ValueError):
            api.search_text("x", "places.id", max_pages=4)


if __name__ == "__main__":
    unittest.main()
