"""Tests for web rescrape runtime execution."""

import unittest
from unittest.mock import patch

from events_scraper.lib import mock_data
from events_scraper.lib.core.database import EventCollection
from events_scraper.lib.core.orm_models import ScraperStatus
from events_scraper.lib.core.orm_session import get_session
from events_scraper.lib.web import rescrape
from tests.lib.core.test_base import DatabaseTestCase


class FakePythonScraper:
    """Minimal BaseEventScraper-like object exposing base_url (not url)."""

    scraper_name = "paris.alteoper"
    base_url = "https://example.com/events"
    events_url = None
    url = None

    def fetch(self):
        return EventCollection([])


class FakeAIScraper(FakePythonScraper):
    """Minimal AIScraper-like object exposing url instead of base_url."""

    url = "https://example.com/events"
    base_url = None


class RunScraperTestCase(DatabaseTestCase):
    """run_scraper should work for both Python and AI scraper variants."""

    def _make_package(self, scraper):
        pkg = mock_data.get_package("paris")
        pkg._scrapers = [scraper]
        return pkg

    def _record_status(self, scraper_name, url, status_code=200):
        session = get_session()
        try:
            session.add(
                ScraperStatus(
                    scraper_name=scraper_name,
                    url=url,
                    status_code=status_code,
                )
            )
            session.commit()
        finally:
            session.close()

    def test_run_scraper_python_scraper_with_base_url(self):
        """Python scrapers exposing base_url (not url) must not AttributeError."""
        self._record_status("paris.alteoper", "https://example.com/events")
        pkg = self._make_package(FakePythonScraper())

        with patch.object(rescrape, "load_packages", return_value=[pkg]):
            result = rescrape.run_scraper("paris.alteoper", save=False)

        self.assertEqual(result.scraper_name, "paris.alteoper")
        self.assertEqual(result.url, "https://example.com/events")
        self.assertEqual(result.http_status, 200)

    def test_run_scraper_ai_scraper_with_url(self):
        """AI scrapers exposing url still work."""
        self._record_status("paris.alteoper", "https://example.com/events")
        pkg = self._make_package(FakeAIScraper())

        with patch.object(rescrape, "load_packages", return_value=[pkg]):
            result = rescrape.run_scraper("paris.alteoper", save=False)

        self.assertEqual(result.url, "https://example.com/events")
        self.assertEqual(result.http_status, 200)

    def test_resolve_scraper_matches_target_url(self):
        """resolve_scraper should match a target URL against base_url."""
        pkg = self._make_package(FakePythonScraper())

        with patch.object(rescrape, "load_packages", return_value=[pkg]):
            found = rescrape.resolve_scraper(
                "paris.alteoper", target_url="https://example.com/events"
            )
            not_found = rescrape.resolve_scraper(
                "paris.alteoper", target_url="https://other.example.com"
            )

        self.assertIsNotNone(found)
        self.assertIsNone(not_found)


if __name__ == "__main__":
    unittest.main()
