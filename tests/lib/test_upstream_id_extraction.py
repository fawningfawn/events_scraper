"""Tests for upstream ID extraction from scrapers"""

import unittest
from datetime import date as date_type

from events_scraper.lib.core import BaseEventScraper
from events_scraper.lib.core.orm_models import Event
from events_scraper.lib.core.orm_session import dispose_engine
from events_scraper.lib.core.orm_session import get_session
from events_scraper.lib.core.orm_session import init_database
from events_scraper.lib.core.orm_session import load_events_by_date
from events_scraper.lib.core.orm_session import upsert_event


class TestUpstreamIDExtraction(unittest.TestCase):
    """Test upstream ID extraction and storage"""

    @classmethod
    def setUpClass(cls):
        """Initialize in-memory database for tests"""
        init_database("sqlite:///:memory:")

    @classmethod
    def tearDownClass(cls):
        """Dispose database"""
        dispose_engine()

    def setUp(self):
        """Clear database before each test"""
        session = get_session()
        session.query(Event).delete()
        session.commit()
        session.close()

    def test_base_scraper_has_optional_get_upstream_id_method(self):
        """Base scraper should have optional get_upstream_id method"""
        scraper = BaseEventScraper("http://example.com", "Test City")
        self.assertTrue(hasattr(scraper, "get_upstream_id"))
        self.assertTrue(callable(scraper.get_upstream_id))

    def test_base_scraper_get_upstream_id_returns_none_by_default(self):
        """Base scraper get_upstream_id should return None by default"""
        scraper = BaseEventScraper("http://example.com", "Test City")
        result = scraper.get_upstream_id("https://example.com/event/123")
        self.assertIsNone(result)

    def test_custom_scraper_can_implement_get_upstream_id(self):
        """Custom scraper can override get_upstream_id method"""

        class CustomScraper(BaseEventScraper):
            def get_upstream_id(self, url: str) -> str:
                # Extract event ID from URL like event-695f8b6e9cbd9
                if "event-" in url:
                    return url.split("event-")[1].split("/")[0]
                return None

        scraper = CustomScraper("http://example.com", "Test City")
        result = scraper.get_upstream_id(
            "https://example.com/event-695f8b6e9cbd9/date-123456"
        )
        self.assertEqual(result, "695f8b6e9cbd9")

    def test_upstream_id_stored_when_saving_event(self):
        """upstream_id should be stored when event is saved"""
        event = Event(
            title="Test Event",
            date=date_type(2026, 3, 15),
            time="10:00",
            location="Location",
            scraper="test_scraper",
            detail_url="https://example.com/event-abc123/date-789",
        )
        event.upstream_id = "abc123"

        upsert_event(event)

        # Verify upstream_id was stored
        events = load_events_by_date(date_type(2026, 3, 15))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].upstream_id, "abc123")

    def test_upstream_id_null_when_not_set(self):
        """upstream_id should be NULL when not set"""
        event = Event(
            title="Test Event",
            date=date_type(2026, 3, 15),
            time="10:00",
            location="Location",
            scraper="test_scraper",
            detail_url="https://example.com/event/1",
        )

        upsert_event(event)

        # Verify upstream_id is NULL
        events = load_events_by_date(date_type(2026, 3, 15))
        self.assertEqual(len(events), 1)
        self.assertIsNone(events[0].upstream_id)

    def test_upstream_id_preserved_on_upsert(self):
        """upstream_id should be preserved when event is updated"""
        event1 = Event(
            title="Event",
            date=date_type(2026, 3, 15),
            time="10:00",
            location="Location",
            scraper="scraper1",
            detail_url="https://example.com/1",
        )
        event1.upstream_id = "id_from_scraper1"

        event2 = Event(
            title="Event",
            date=date_type(2026, 3, 15),
            time="10:00",
            location="Location",
            scraper="scraper2",
            detail_url="https://example.com/2",
        )
        event2.upstream_id = "id_from_scraper2"

        upsert_event(event1)
        upsert_event(event2)

        # Verify both upstream_ids are stored (latest should win)
        events = load_events_by_date(date_type(2026, 3, 15))
        self.assertEqual(len(events), 1)
        # Latest update should have scraper2's upstream_id
        self.assertEqual(events[0].upstream_id, "id_from_scraper2")

    def test_different_upstream_ids_same_event_creates_duplicate(self):
        """Events with different upstream IDs but same content should deduplicate"""
        # This verifies that content_hash is the dedup key, not upstream_id
        event1 = Event(
            title="Event",
            date=date_type(2026, 3, 15),
            time="10:00",
            location="Location",
            scraper="scraper1",
            detail_url="https://example.com/event-123",
        )
        event1.upstream_id = "upstream_id_1"

        event2 = Event(
            title="Event",
            date=date_type(2026, 3, 15),
            time="10:00",
            location="Location",
            scraper="scraper2",
            detail_url="https://example.com/event-456",
        )
        event2.upstream_id = "upstream_id_2"

        upsert_event(event1)
        upsert_event(event2)

        # Should only have 1 event (deduplicated by content_hash, not upstream_id)
        events = load_events_by_date(date_type(2026, 3, 15))
        self.assertEqual(len(events), 1)
        # Should have the latest upstream_id
        self.assertEqual(events[0].upstream_id, "upstream_id_2")
