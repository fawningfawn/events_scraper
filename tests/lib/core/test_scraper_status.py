"""
Unit tests for scraper status tracking
"""

import time

from events_scraper.lib.core.database import configure_database
from events_scraper.lib.core.orm_session import get_session
from events_scraper.lib.mock_data import get_scraper_status
from tests.lib.core.test_base import BaseTestCase


class TestScraperStatusTable(BaseTestCase):
    """Test scraper_status table and ORM model"""

    def setUp(self):
        """Set up in-memory test database"""
        configure_database(":memory:")

    def test_scraper_status_table_exists(self):
        """Test scraper_status table is created"""
        session = get_session()
        try:
            # Create a test status using mock_data
            status = get_scraper_status()
            # Try to query the table - should not raise
            result = session.query(type(status)).all()
            self.assertIsInstance(result, list)
        finally:
            session.close()

    def test_scraper_status_has_required_columns(self):
        """Test ScraperStatus model has all required columns"""
        status = get_scraper_status()
        self.assertTrue(hasattr(status, "scraper_name"))
        self.assertTrue(hasattr(status, "url"))
        self.assertTrue(hasattr(status, "timestamp"))
        self.assertTrue(hasattr(status, "status_code"))
        self.assertTrue(hasattr(status, "error_message"))

    def test_store_successful_scrape_status(self):
        """Test storing successful scrape status (200 with events)"""
        session = get_session()
        try:
            # Use mock_data to generate realistic status
            status = get_scraper_status()
            session.add(status)
            session.commit()

            # Verify it was stored
            result = (
                session.query(type(status))
                .filter_by(scraper_name=status.scraper_name)
                .first()
            )
            self.assertIsNotNone(result)
            self.assertEqual(result.status_code, 200)
            self.assertIsNone(result.error_message)
        finally:
            session.close()

    def test_store_http_error_status(self):
        """Test storing HTTP error status (404, 500, etc)"""
        session = get_session()
        try:
            status = get_scraper_status(status_code=404, error_message="Not Found")
            session.add(status)
            session.commit()

            # Verify it was stored
            result = session.query(type(status)).filter_by(url=status.url).first()
            self.assertIsNotNone(result)
            self.assertEqual(result.status_code, 404)
            self.assertEqual(result.error_message, "Not Found")
        finally:
            session.close()

    def test_store_python_exception_status(self):
        """Test storing Python exception status"""
        session = get_session()
        try:
            status = get_scraper_status(
                status_code=-1, error_message="ConnectionError: Network unreachable"
            )
            session.add(status)
            session.commit()

            # Verify it was stored
            result = session.query(type(status)).filter_by(url=status.url).first()
            self.assertIsNotNone(result)
            self.assertEqual(result.status_code, -1)
            self.assertIn("ConnectionError", result.error_message)
        finally:
            session.close()

    def test_query_latest_status_for_scraper(self):
        """Test querying the latest status for a scraper"""
        session = get_session()
        try:
            # Add multiple statuses for same scraper
            base_time = time.time()
            scraper = get_scraper_status()

            old_status = get_scraper_status(
                scraper_name=scraper.scraper_name,
                url=scraper.url,
                timestamp=base_time - 86400,  # 1 day ago
            )
            new_status = get_scraper_status(
                scraper_name=scraper.scraper_name,
                url=scraper.url,
                timestamp=base_time,
                status_code=404,
                error_message="Not Found",
            )
            session.add_all([old_status, new_status])
            session.commit()

            # Query latest status
            result = (
                session.query(type(old_status))
                .filter_by(scraper_name=scraper.scraper_name)
                .order_by(type(old_status).timestamp.desc())
                .first()
            )

            self.assertIsNotNone(result)
            self.assertEqual(result.status_code, 404)
            self.assertEqual(result.error_message, "Not Found")
        finally:
            session.close()

    def test_query_status_by_url(self):
        """Test querying status by URL (for multiple year expansions)"""
        session = get_session()
        try:
            # Add statuses for different URLs
            status_1 = get_scraper_status()
            status_2 = get_scraper_status(status_code=404, error_message="Not Found")
            session.add_all([status_1, status_2])
            session.commit()

            # Query by specific URL
            result_1 = session.query(type(status_1)).filter_by(url=status_1.url).first()
            result_2 = session.query(type(status_2)).filter_by(url=status_2.url).first()

            self.assertEqual(result_1.status_code, 200)
            self.assertEqual(result_2.status_code, 404)
        finally:
            session.close()
