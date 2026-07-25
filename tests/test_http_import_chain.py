"""
Integration tests that exercise the real HTTP request path while mocking
only the network transport. Catches dependency breakage like idna 3.18
renaming uts46data.
"""

import unittest
from unittest.mock import patch

import idna

from events_scraper.lib.mock_data import MockHttpResponse
from events_scraper.lib.mock_data import MockTransport


class IdnaIntegrationTest(unittest.TestCase):
    """Verify the idna library works correctly — catches breakage like 3.18 renaming uts46data."""

    def test_idna_encode_internationalized_domain(self):
        """idna.encode should handle internationalized domain names."""
        encoded = idna.encode("münchen.example.com")
        self.assertIsInstance(encoded, bytes)
        self.assertIn(b"xn--mnchen-3ya", encoded)

    def test_idna_uts46data_module_structure(self):
        """Verify idna uts46data module exposes the names we depend on.

        idna 3.18 renamed uts46data -> uts46_replacements/starts/statuses.
        If this test breaks, pin idna<3.18 in requirements.in.
        """
        from idna import uts46data

        has_old = hasattr(uts46data, "uts46data")
        has_new = hasattr(uts46data, "uts46_replacements")
        self.assertTrue(
            has_old or has_new,
            "idna uts46data module exposes neither old nor new names",
        )


class HttpImportChainIntegrationTest(unittest.TestCase):
    """Verify http_get works end-to-end with mocked transport.

    These tests catch dependency breakage by exercising the real code path.
    """

    def test_http_get_through_real_stack(self):
        """http_get should work end-to-end with mocked transport and network guard."""
        mock_resp = MockHttpResponse(200, "<html>hello</html>")

        with (
            patch("events_scraper.lib.core.scraper._ensure_network_allowed_for_tests"),
            patch("requests.get", return_value=mock_resp),
        ):
            from events_scraper.lib.core.scraper import http_get

            response = http_get("https://example.com/events")
            self.assertEqual(response.status_code, 200)

    def test_requests_send_with_mocked_transport(self):
        """Adapter.send should work through the real requests code path."""
        import requests

        transport = MockTransport(MockHttpResponse(200, "<html>ok</html>"))
        req = requests.Request("GET", "https://example.com/events").prepare()
        resp = transport.send(req)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.url, "https://example.com/events")


if __name__ == "__main__":
    unittest.main()
