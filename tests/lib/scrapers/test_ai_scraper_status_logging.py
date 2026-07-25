"""
Tests for AI scraper status logging
"""

from unittest.mock import Mock
from unittest.mock import patch

import requests

from events_scraper.lib.core.database import configure_database
from events_scraper.lib.core.orm_models import ScraperStatus
from events_scraper.lib.core.orm_session import get_session
from events_scraper.lib.scrapers.ai_scraper import AIScraper
from tests.lib.core.test_base import BaseTestCase


class TestAIScraperStatusLogging(BaseTestCase):
    """Test that AIScraper logs status to database"""

    def setUp(self):
        """Set up in-memory test database"""
        configure_database(":memory:")

    @patch("events_scraper.lib.scrapers.ai_scraper.http_get")
    @patch("events_scraper.lib.core.llm_mixin.LLMClient")
    def test_logs_success_status_on_200(self, mock_llm_client, mock_requests_get):
        """Test that successful scrape (200) logs status to database"""
        # Mock HTTP 200 response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<html>test</html>"
        mock_requests_get.return_value = mock_response

        # Mock LLM response
        mock_llm = Mock()
        mock_llm.complete.return_value = '{"events": []}'
        mock_llm_client.get_provider.return_value = mock_llm

        # Create scraper and fetch
        scraper = AIScraper("https://example.com", "test_scraper")
        scraper.fetch()

        # Verify status was logged
        session = get_session()
        try:
            result = (
                session.query(ScraperStatus)
                .filter_by(scraper_name="test_scraper")
                .first()
            )

            self.assertIsNotNone(result)
            self.assertEqual(result.status_code, 200)
            self.assertIsNone(result.error_message)
            self.assertEqual(result.url, "https://example.com")
        finally:
            session.close()

    @patch("events_scraper.lib.scrapers.ai_scraper.http_get")
    def test_logs_404_status(self, mock_requests_get):
        """Test that 404 error logs status to database"""
        # Mock HTTP 404 response with proper HTTPError
        mock_response = Mock()
        mock_response.status_code = 404

        http_error = requests.HTTPError("404 Not Found")
        http_error.response = mock_response
        mock_response.raise_for_status.side_effect = http_error

        mock_requests_get.return_value = mock_response

        # Create scraper and fetch
        scraper = AIScraper("https://example.com/404", "test_scraper")
        result = scraper.fetch()

        # Should return empty collection on error
        self.assertEqual(len(result.events), 0)

        # Verify status was logged
        session = get_session()
        try:
            status = (
                session.query(ScraperStatus)
                .filter_by(scraper_name="test_scraper")
                .first()
            )

            self.assertIsNotNone(status)
            self.assertEqual(status.status_code, 404)
            self.assertIsNotNone(status.error_message)
            self.assertEqual(status.url, "https://example.com/404")
        finally:
            session.close()

    @patch("events_scraper.lib.scrapers.ai_scraper.http_get")
    def test_logs_exception_status(self, mock_requests_get):
        """Test that Python exception logs status with -1 code"""
        # Mock connection error
        mock_requests_get.side_effect = ConnectionError("Network unreachable")

        # Create scraper and fetch
        scraper = AIScraper("https://example.com/broken", "test_scraper")
        result = scraper.fetch()

        # Should return empty collection on error
        self.assertEqual(len(result.events), 0)

        # Verify status was logged
        session = get_session()
        try:
            status = (
                session.query(ScraperStatus)
                .filter_by(scraper_name="test_scraper")
                .first()
            )

            self.assertIsNotNone(status)
            self.assertEqual(status.status_code, -1)
            self.assertIn("ConnectionError", status.error_message)
            self.assertEqual(status.url, "https://example.com/broken")
        finally:
            session.close()

    @patch("events_scraper.lib.scrapers.ai_scraper.http_get")
    @patch("events_scraper.lib.core.llm_mixin.LLMClient")
    def test_updates_status_on_subsequent_scrapes(
        self, mock_llm_client, mock_requests_get
    ):
        """Test that subsequent scrapes update status (not duplicate)"""
        # First scrape - success
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<html>test</html>"
        mock_requests_get.return_value = mock_response

        mock_llm = Mock()
        mock_llm.complete.return_value = '{"events": []}'
        mock_llm_client.get_provider.return_value = mock_llm

        scraper = AIScraper("https://example.com", "test_scraper")
        scraper.fetch()

        # Second scrape - also success (should create new status entry)
        scraper.fetch()

        # Verify we have 2 status entries
        session = get_session()
        try:
            statuses = (
                session.query(ScraperStatus).filter_by(scraper_name="test_scraper").all()
            )

            self.assertEqual(len(statuses), 2)
            # Both should be successful
            for status in statuses:
                self.assertEqual(status.status_code, 200)
        finally:
            session.close()
