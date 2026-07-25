"""Tests for upsert_event() using content hash deduplication"""

import unittest
from datetime import date as date_type

from events_scraper.lib.core.orm_models import Event
from events_scraper.lib.core.orm_session import dispose_engine
from events_scraper.lib.core.orm_session import get_session
from events_scraper.lib.core.orm_session import init_database
from events_scraper.lib.core.orm_session import load_events_by_date
from events_scraper.lib.core.orm_session import upsert_event


class TestUpsertByContentHash(unittest.TestCase):
    """Test upsert_event() with content hash deduplication"""

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

    def test_upsert_new_event(self):
        """Inserting new event should create row"""
        event = Event(
            title="Concert",
            date=date_type(2026, 3, 15),
            time="19:00",
            location="Hall",
            scraper="scraper1",
            detail_url="https://example.com/1",
        )

        upsert_event(event)

        # Verify event was inserted
        events = load_events_by_date(date_type(2026, 3, 15))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].title, "Concert")

    def test_upsert_duplicate_same_date_updates(self):
        """Upserting same event on same date should update, not create duplicate"""
        event1 = Event(
            title="Concert",
            date=date_type(2026, 3, 15),
            time="19:00",
            location="Hall",
            scraper="scraper1",
            detail_url="https://example.com/1",
        )
        event2 = Event(
            title="Concert",
            date=date_type(2026, 3, 15),
            time="19:00",
            location="Hall",
            scraper="scraper2",
            detail_url="https://example.com/2",  # Different URL, same event
        )

        upsert_event(event1)
        upsert_event(event2)

        # Should only have 1 event (updated, not duplicated)
        events = load_events_by_date(date_type(2026, 3, 15))
        self.assertEqual(len(events), 1)
        # Should keep the most recent scraper/URL
        self.assertEqual(events[0].scraper, "scraper2")
        self.assertEqual(events[0].detail_url, "https://example.com/2")

    def test_upsert_same_event_different_date_creates_new_row(self):
        """Upserting same event on different date should create new row (recurring)"""
        event1 = Event(
            title="Weekly Yoga",
            date=date_type(2026, 3, 15),
            time="10:00",
            location="Studio",
            scraper="scraper1",
            detail_url="https://example.com/yoga/1",
        )
        event2 = Event(
            title="Weekly Yoga",
            date=date_type(2026, 3, 22),  # Different date
            time="10:00",
            location="Studio",
            scraper="scraper1",
            detail_url="https://example.com/yoga/1",
        )

        upsert_event(event1)
        upsert_event(event2)

        # Should have 2 events (different dates)
        events1 = load_events_by_date(date_type(2026, 3, 15))
        events2 = load_events_by_date(date_type(2026, 3, 22))
        self.assertEqual(len(events1), 1)
        self.assertEqual(len(events2), 1)

    def test_upsert_different_time_creates_new_row(self):
        """Same event, same date, different time should create new row"""
        event1 = Event(
            title="Yoga Class",
            date=date_type(2026, 3, 15),
            time="09:00",
            location="Studio",
            scraper="scraper1",
            detail_url="https://example.com/1",
        )
        event2 = Event(
            title="Yoga Class",
            date=date_type(2026, 3, 15),
            time="10:00",  # Different time = different event
            location="Studio",
            scraper="scraper1",
            detail_url="https://example.com/2",
        )

        upsert_event(event1)
        upsert_event(event2)

        # Should have 2 events (different times)
        events = load_events_by_date(date_type(2026, 3, 15))
        self.assertEqual(len(events), 2)

    def test_upsert_different_location_creates_new_row(self):
        """Same event, same date/time, different location should create new row"""
        event1 = Event(
            title="Concert",
            date=date_type(2026, 3, 15),
            time="19:00",
            location="Hall A",
            scraper="scraper1",
            detail_url="https://example.com/1",
        )
        event2 = Event(
            title="Concert",
            date=date_type(2026, 3, 15),
            time="19:00",
            location="Hall B",  # Different location = different event
            scraper="scraper1",
            detail_url="https://example.com/2",
        )

        upsert_event(event1)
        upsert_event(event2)

        # Should have 2 events (different locations)
        events = load_events_by_date(date_type(2026, 3, 15))
        self.assertEqual(len(events), 2)

    def test_upsert_multiple_duplicates_keeps_latest(self):
        """Multiple upserts of same event should keep latest version"""
        event1 = Event(
            title="Event",
            date=date_type(2026, 3, 15),
            time="10:00",
            location="Location",
            scraper="scraper1",
            detail_url="https://example.com/1",
        )
        event2 = Event(
            title="Event",
            date=date_type(2026, 3, 15),
            time="10:00",
            location="Location",
            scraper="scraper2",
            detail_url="https://example.com/2",
        )
        event3 = Event(
            title="Event",
            date=date_type(2026, 3, 15),
            time="10:00",
            location="Location",
            scraper="scraper3",
            detail_url="https://example.com/3",
        )

        upsert_event(event1)
        upsert_event(event2)
        upsert_event(event3)

        # Should only have 1 event, latest version
        events = load_events_by_date(date_type(2026, 3, 15))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].scraper, "scraper3")
        self.assertEqual(events[0].detail_url, "https://example.com/3")

    def test_upsert_whitespace_variation_considered_duplicate(self):
        """Whitespace variations in title/location should be considered same event"""
        event1 = Event(
            title="Museum After Work",
            date=date_type(2026, 3, 15),
            time="18:00",
            location="Musée du Louvre",
            scraper="scraper1",
            detail_url="https://example.com/1",
        )
        event2 = Event(
            title="  Museum  After  Work  ",
            date=date_type(2026, 3, 15),
            time="18:00",
            location="  Musée du Louvre  ",
            scraper="scraper2",
            detail_url="https://example.com/2",
        )

        upsert_event(event1)
        upsert_event(event2)

        # Should only have 1 event (whitespace normalized)
        events = load_events_by_date(date_type(2026, 3, 15))
        self.assertEqual(len(events), 1)

    def test_upsert_case_variation_considered_duplicate(self):
        """Case variations should be considered same event"""
        event1 = Event(
            title="Concert",
            date=date_type(2026, 3, 15),
            time="19:00",
            location="Hall",
            scraper="scraper1",
            detail_url="https://example.com/1",
        )
        event2 = Event(
            title="CONCERT",
            date=date_type(2026, 3, 15),
            time="19:00",
            location="HALL",
            scraper="scraper2",
            detail_url="https://example.com/2",
        )

        upsert_event(event1)
        upsert_event(event2)

        # Should only have 1 event (case normalized)
        events = load_events_by_date(date_type(2026, 3, 15))
        self.assertEqual(len(events), 1)

    def test_cross_scraper_same_content_same_date_deduplicates(self):
        """Same event from different scrapers should deduplicate at DB upsert boundary."""
        event_one = Event(
            title="Shared Event",
            date=date_type(2026, 3, 15),
            time="20:00",
            location="Venue",
            scraper="scraper.alpha",
            detail_url="https://example.com/a",
        )
        event_two = Event(
            title="Shared Event",
            date=date_type(2026, 3, 15),
            time="20:00",
            location="Venue",
            scraper="scraper.beta",
            detail_url="https://example.com/b",
        )

        upsert_event(event_one)
        upsert_event(event_two)

        events = load_events_by_date(date_type(2026, 3, 15))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].scraper, "scraper.beta")
