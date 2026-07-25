"""
Unit tests for hide_from_status filtering using mock packages.
"""

from unittest.mock import patch

from events_scraper.lib import mock_data
from events_scraper.lib.web.app import create_app
from tests.lib.core.test_base import DatabaseTestCase


class TestHideFromStatusFiltering(DatabaseTestCase):
    """Test that hide_from_status groups are excluded from status pages."""

    def setUp(self):
        super().setUp()
        self.hidden = mock_data.get_package(
            "hidden", ["hidden.s1"], hide_from_status=True
        )
        self.visible = mock_data.get_package("visible", ["visible.s1"])

    @patch("events_scraper.lib.scraper_meta.load_packages")
    @patch("events_scraper.lib.packages.load_packages")
    def test_status_scrapers_page_shows_all_scrapers(self, mock_pkg, mock_meta):
        """All scrapers appear on /status/scrapers regardless of hide_from_status."""
        mock_pkg.return_value = [self.visible, self.hidden]
        mock_meta.return_value = [self.visible, self.hidden]
        app = create_app(test_mode=True)
        with app.test_client() as client:
            response = client.get("/status/scrapers")
            html = response.data.decode("utf-8").lower()
            self.assertIn("visible.s1", html)
            self.assertIn("hidden.s1", html)

    @patch("events_scraper.lib.scraper_meta.load_packages")
    @patch("events_scraper.lib.packages.load_packages")
    def test_status_page_excludes_hidden(self, mock_pkg, mock_meta):
        """Hidden scraper names don't appear on /status page."""
        mock_pkg.return_value = [self.visible, self.hidden]
        mock_meta.return_value = [self.visible, self.hidden]
        app = create_app(test_mode=True)
        with app.test_client() as client:
            response = client.get("/status")
            html = response.data.decode("utf-8").lower()
            self.assertNotIn("hidden.s1", html)
