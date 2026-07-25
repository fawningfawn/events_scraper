"""Tests for database-first event loading functionality"""

from unittest.mock import patch

from events_scraper.lib import mock_data
from events_scraper.lib.core import EventCollection
from events_scraper.lib.core import load_events_from_database
from events_scraper.lib.core.orm_models import Event as ORMEvent
from tests.lib.core.test_base import DatabaseTestCase
from tests.lib.core.test_base import PostgreSQLTestCase


class DatabaseLoadingTestMixin:
    """Test database loading functionality"""

    def _event_categories(self, event):
        categories = getattr(event, "categories", None)
        if isinstance(categories, list):
            return categories
        if isinstance(categories, str):
            return [cat.strip() for cat in categories.split(",") if cat.strip()]
        if hasattr(event, "categories_list"):
            return event.categories_list or []
        return []

    def test_load_events_from_empty_database(self):
        """Test loading from empty database returns empty list"""
        test_date = mock_data.get_date()
        events = load_events_from_database(test_date)
        self.assertEqual(len(events), 0)

    def test_event_save_and_load(self):
        """Test saving event to database and loading it back"""
        # Generate random test date and reuse it
        test_date = mock_data.get_date()
        test_event = mock_data.get_event(
            title="Test Event",
            date=test_date.strftime("%Y-%m-%d"),
            time="10:00",
            location="Test Location",
            categories=["Test Category"],
        )

        # Save to database
        test_event.save()

        # Load from database
        events = load_events_from_database(test_date)

        self.assertEqual(len(events), 1)
        loaded_event = events[0]
        self.assertEqual(loaded_event.title, "Test Event")
        self.assertEqual(loaded_event.date, test_date)
        self.assertEqual(loaded_event.location, "Test Location")
        self.assertEqual(self._event_categories(loaded_event), ["Test Category"])

    def test_event_save_duplicate_prevention(self):
        """Test that duplicate events are not saved (based on content_hash + date)"""
        # Generate random test date and reuse it
        test_date = mock_data.get_date()
        common_params = {
            "title": "Duplicate Event",
            "date": test_date.strftime("%Y-%m-%d"),
            "location": "Same Location",
            "time": "10:00",  # Include time for consistent hash
            "scraper": "test.de",
            "detail_url": "https://example.com/event",
        }
        event1 = mock_data.get_event(**common_params)
        event2 = mock_data.get_event(**common_params)

        # Save both
        event1.save()
        event2.save()

        # Should only have one event (deduplicated by content_hash + date)
        events = load_events_from_database(test_date)
        self.assertEqual(len(events), 1)

    def test_eventcollection_from_database_empty(self):
        """Test EventCollection.from_database with empty database"""
        test_date = mock_data.get_date()
        collection = EventCollection.from_database(test_date)
        self.assertEqual(len(collection.events), 0)

    def test_eventcollection_from_database_with_existing_data(self):
        """Test EventCollection.from_database with existing data (no fallback)"""
        # Generate random test date and reuse it
        test_date = mock_data.get_date()
        test_event = mock_data.get_event(
            title="Existing Event",
            date=test_date.strftime("%Y-%m-%d"),
            scraper="testcity.de",  # Match the city filter with dot pattern
        )
        test_event.save()

        # Load from database - should not trigger fallback
        with patch(
            "events_scraper.lib.scraper_loader.fetch_all_events"
        ) as mock_fetch_all:
            collection = EventCollection.from_database(test_date, group="testcity")

            # Should not have called scraping fallback
            mock_fetch_all.assert_not_called()
            self.assertEqual(len(collection.events), 1)
            self.assertEqual(collection.events[0].title, "Existing Event")

    def test_load_events_with_city_filter(self):
        """Test loading events with city filter"""
        # Generate random test date and reuse it
        test_date = mock_data.get_date()

        # Save events with different scrapers using distinct city names
        event1 = mock_data.get_event(
            title="Event 1",
            date=test_date.strftime("%Y-%m-%d"),
            location="Paris Venue",
            scraper="paris.de",
        )
        event2 = mock_data.get_event(
            title="Event 2",
            date=test_date.strftime("%Y-%m-%d"),
            location="Munich Venue",
            scraper="munich.de",
        )
        event1.save()
        event2.save()

        # Load with city filter
        events = load_events_from_database(test_date, group="paris")

        # Should only get events matching city filter
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].title, "Event 1")

    def test_categories_handling(self):
        """Test that categories are properly stored and loaded"""
        # Generate random test date and reuse it
        test_date = mock_data.get_date()

        # Event with multiple categories
        event = mock_data.get_event(
            title="Multi Category Event",
            date=test_date.strftime("%Y-%m-%d"),
            categories=["Music", "Culture", "Entertainment"],
        )
        event.save()

        # Load and check categories
        events = load_events_from_database(test_date)
        self.assertEqual(len(events), 1)
        self.assertEqual(
            self._event_categories(events[0]),
            ["Music", "Culture", "Entertainment"],
        )

    def test_empty_categories_handling(self):
        """Test that empty categories are handled correctly"""
        # Generate random test date and reuse it
        test_date = mock_data.get_date()

        event = mock_data.get_event(
            title="No Categories Event",
            date=test_date.strftime("%Y-%m-%d"),
            categories=[],
            scraper="test-scraper",
        )
        event.save()

        events = load_events_from_database(test_date)
        self.assertEqual(len(events), 1)
        self.assertEqual(self._event_categories(events[0]), [])

    def test_upstream_id_roundtrip_preserved(self):
        """`upstream_id` set at event creation must persist unchanged."""
        test_date = mock_data.get_date()
        event = mock_data.get_event(
            title="Upstream ID Event",
            date=test_date.strftime("%Y-%m-%d"),
            detail_url="https://example.com/event-abc123",
            scraper="test.scraper",
        )
        event.upstream_id = "abc123"
        event.save()

        events = load_events_from_database(test_date)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].upstream_id, "abc123")

    def test_load_events_returns_orm_event_instances(self):
        """Runtime callers should receive ORM events as the canonical shape."""
        test_date = mock_data.get_date()
        mock_data.get_event(
            title="ORM Event",
            date=test_date.strftime("%Y-%m-%d"),
        ).save()

        events = load_events_from_database(test_date)

        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], ORMEvent)

    def test_eventcollection_from_database_uses_orm_events(self):
        """`EventCollection.from_database` should expose ORM events directly."""
        test_date = mock_data.get_date()
        mock_data.get_event(
            title="Collection ORM Event",
            date=test_date.strftime("%Y-%m-%d"),
        ).save()

        collection = EventCollection.from_database(test_date)

        self.assertEqual(len(collection.events), 1)
        self.assertIsInstance(collection.events[0], ORMEvent)


# Database-specific test implementations
class TestDatabaseLoadingSQLite(DatabaseTestCase, DatabaseLoadingTestMixin):
    """Run database loading tests on SQLite"""


class TestDatabaseLoadingPostgreSQL(PostgreSQLTestCase, DatabaseLoadingTestMixin):
    """Run database loading tests on PostgreSQL"""
