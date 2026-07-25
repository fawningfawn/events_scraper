"""Tests for database management script"""

import unittest
from datetime import date
from unittest.mock import patch

from events_scraper.lib.core.ai_cache import AICache
from events_scraper.lib.core.database_maintenance import clear_ai_cache
from events_scraper.lib.core.database_maintenance import delete_group_events
from events_scraper.lib.core.database_maintenance import delete_group_status
from events_scraper.lib.core.database_maintenance import show_group_stats
from events_scraper.lib.core.orm_models import Event
from events_scraper.lib.core.orm_models import ScraperStatus
from events_scraper.lib.core.orm_session import get_session
from tests.lib.core.test_base import DatabaseTestCase


class DBMaintTestCase(DatabaseTestCase):
    """Test database management functions"""

    def setUp(self):
        """Set up test environment with clean database"""
        super().setUp()
        self.session = get_session()

    def tearDown(self):
        """Clean up after tests"""
        self.session.close()
        super().tearDown()

    def _create_test_events(self):
        """Create test events: 2 festival, 2 city"""
        # Festival events (prefixed scraper name)
        fest1 = Event(
            title="Test Festival 2025",
            date=date(2025, 6, 1),
            scraper="festivals.testfest1",
            detail_url="https://example.com/fest1",
        )
        fest2 = Event(
            title="Lightning Summit",
            date=date(2025, 7, 15),
            scraper="festivals.testfest2",
            detail_url="https://example.com/fest2",
        )

        # City events (have dot in scraper name)
        city1 = Event(
            title="City Event 1",
            date=date(2025, 5, 1),
            scraper="paris.staatstheater",
            detail_url="https://example.com/city1",
        )
        city2 = Event(
            title="City Event 2",
            date=date(2025, 5, 2),
            scraper="paris.garage_sb",
            detail_url="https://example.com/city2",
        )

        self.session.add_all([fest1, fest2, city1, city2])
        self.session.commit()

        return {"festival": [fest1, fest2], "city": [city1, city2]}

    def _create_test_status(self):
        """Create test scraper status entries"""
        status1 = ScraperStatus(
            scraper_name="festivals.testfest1",
            url="https://example.com/fest1",
            status_code=200,
            error_message=None,
        )
        status2 = ScraperStatus(
            scraper_name="festivals.testfest2",
            url="https://example.com/fest2",
            status_code=404,
            error_message="Not found",
        )

        # City status (have dot in scraper name)
        city_status = ScraperStatus(
            scraper_name="paris.garage_sb",
            url="https://garage-sb.de/events",
            status_code=200,
            error_message=None,
        )

        self.session.add_all([status1, status2, city_status])
        self.session.commit()

        return {
            "festival": [status1, status2],
            "city": [city_status],
        }

    def _create_test_ai_cache(self):
        """Create test AI cache entries"""
        # AICache uses its own database connection, so we need to pass our test db path
        cache = AICache(db_path=self.temp_db.name)
        # AICache.set(url, html, response) signature
        cache.set("https://test1.com", "<html>test1</html>", {"result": "test1"})
        cache.set("https://test2.com", "<html>test2</html>", {"result": "test2"})
        cache.set("https://test3.com", "<html>test3</html>", {"result": "test3"})
        cache.close()  # Close the connection
        return 3

    @patch("events_scraper.lib.core.database_maintenance.get_scraper_names_for_group")
    def test_delete_group_events_filters_correctly(self, mock_names):
        """Test that delete_group_events only deletes festival events"""
        mock_names.return_value = ["festivals.testfest1", "festivals.testfest2"]
        self._create_test_events()

        # Verify initial state
        all_events = self.session.query(Event).count()
        self.assertEqual(all_events, 4)

        # Delete festival events
        deleted_count = delete_group_events("festivals")

        # Should have deleted 2 festival events
        self.assertEqual(deleted_count, 2)

        # Verify only city events remain
        remaining = self.session.query(Event).all()
        self.assertEqual(len(remaining), 2)
        for event in remaining:
            self.assertIn(".", event.scraper)  # City events have dots

    @patch("events_scraper.lib.core.database_maintenance.get_scraper_names_for_group")
    def test_delete_group_events_empty_database(self, mock_names):
        """Test delete_group_events with empty database"""
        mock_names.return_value = ["festivals.testfest1"]
        deleted_count = delete_group_events("festivals")
        self.assertEqual(deleted_count, 0)

    @patch("events_scraper.lib.core.database_maintenance.get_scraper_names_for_group")
    def test_delete_group_status_filters_correctly(self, mock_names):
        """Test that delete_group_status only deletes festival status"""
        mock_names.return_value = ["festivals.testfest1", "festivals.testfest2"]
        self._create_test_status()

        # Verify initial state
        all_status = self.session.query(ScraperStatus).count()
        self.assertEqual(all_status, 3)

        # Delete festival status
        deleted_count = delete_group_status("festivals")

        # Should have deleted 2 festival status entries
        self.assertEqual(deleted_count, 2)

        # Verify only city status remains
        remaining = self.session.query(ScraperStatus).all()
        self.assertEqual(len(remaining), 1)
        self.assertIn(".", remaining[0].scraper_name)  # City status has dot

    @patch("events_scraper.lib.core.database_maintenance.get_scraper_names_for_group")
    def test_delete_group_status_empty_database(self, mock_names):
        """Test delete_group_status with empty database"""
        mock_names.return_value = ["festivals.testfest1"]
        deleted_count = delete_group_status("festivals")
        self.assertEqual(deleted_count, 0)

    def test_clear_ai_cache_with_data(self):
        """Test clear_ai_cache removes all cache entries"""
        # Create cache entries
        created = self._create_test_ai_cache()
        self.assertEqual(created, 3)

        # Verify cache has data using direct SQL
        cache = AICache(db_path=self.temp_db.name)
        cursor = cache.conn.execute("SELECT COUNT(*) FROM ai_cache")
        count = cursor.fetchone()[0]
        cache.close()
        self.assertEqual(count, 3)

        # Clear cache using test database
        cleared_count = clear_ai_cache(db_path=self.temp_db.name)
        self.assertEqual(cleared_count, 3)

        # Verify cache is empty using direct SQL
        cache = AICache(db_path=self.temp_db.name)
        cursor = cache.conn.execute("SELECT COUNT(*) FROM ai_cache")
        count = cursor.fetchone()[0]
        cache.close()
        self.assertEqual(count, 0)

    def test_clear_ai_cache_empty_table(self):
        """Test clear_ai_cache with empty ai_cache table"""
        # Initialize cache (creates table) using test database
        cache = AICache(db_path=self.temp_db.name)
        cache.close()

        # Clear should work and return 0
        cleared_count = clear_ai_cache(db_path=self.temp_db.name)
        self.assertEqual(cleared_count, 0)

    @patch("events_scraper.lib.core.database_maintenance.get_scraper_names_for_group")
    def test_show_group_stats_with_data(self, mock_names):
        """Test show_group_stats returns correct counts"""
        mock_names.return_value = ["festivals.testfest1", "festivals.testfest2"]
        self._create_test_events()
        self._create_test_status()
        self._create_test_ai_cache()

        stats = show_group_stats("festivals", db_path=self.temp_db.name)

        # Verify stats
        self.assertEqual(stats["events"], 2)  # 2 festival events
        self.assertEqual(stats["status"], 2)  # 2 festival status entries
        self.assertEqual(stats["cache"], 3)  # 3 AI cache entries

    @patch("events_scraper.lib.core.database_maintenance.get_scraper_names_for_group")
    def test_show_group_stats_empty_database(self, mock_names):
        """Test show_group_stats with empty database"""
        mock_names.return_value = ["festivals.testfest1"]
        stats = show_group_stats("festivals", db_path=self.temp_db.name)

        self.assertEqual(stats["events"], 0)
        self.assertEqual(stats["status"], 0)
        self.assertEqual(stats["cache"], 0)

    @patch("events_scraper.lib.core.database_maintenance.get_scraper_names_for_group")
    def test_show_group_stats_mixed_data(self, mock_names):
        """Test stats only counts festival data, not city data"""
        mock_names.return_value = ["festivals.testfest1", "festivals.testfest2"]
        self._create_test_events()  # Creates 2 festival + 2 city events
        self._create_test_status()  # Creates 2 festival + 1 city status

        stats = show_group_stats("festivals")

        # Should only count festival data
        self.assertEqual(stats["events"], 2)
        self.assertEqual(stats["status"], 2)

        # Verify city data still exists but not counted
        all_events = self.session.query(Event).count()
        self.assertEqual(all_events, 4)  # 2 festival + 2 city

    @patch("events_scraper.lib.core.database_maintenance.get_scraper_names_for_group")
    def test_operations_are_independent(self, mock_names):
        """Test that operations don't affect each other's data"""
        mock_names.return_value = ["festivals.testfest1", "festivals.testfest2"]
        self._create_test_events()
        self._create_test_status()

        # Delete events only
        deleted_events = delete_group_events("festivals")
        self.assertEqual(deleted_events, 2)

        # Status should still exist
        status_count = self.session.query(ScraperStatus).count()
        self.assertEqual(status_count, 3)  # All status still there

        # Now delete status
        deleted_status = delete_group_status("festivals")
        self.assertEqual(deleted_status, 2)

        # City events should still exist
        remaining_events = self.session.query(Event).count()
        self.assertEqual(remaining_events, 2)  # 2 city events remain


if __name__ == "__main__":
    unittest.main()
