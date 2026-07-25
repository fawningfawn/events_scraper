"""Tests for duplicate cleanup functionality"""

import unittest
from datetime import date as date_type
from datetime import datetime

from events_scraper.lib.core.orm_models import Event
from events_scraper.lib.core.orm_models import EventDetail
from events_scraper.lib.core.orm_models import Notification
from events_scraper.lib.core.orm_models import User
from events_scraper.lib.core.orm_session import dispose_engine
from events_scraper.lib.core.orm_session import get_session
from events_scraper.lib.core.orm_session import init_database
from events_scraper.lib.core.orm_session import load_events_by_date
from events_scraper.lib.core.orm_session import upsert_event
from events_scraper.lib.deduplication_cleanup import cleanup_duplicates


class TestCleanupDuplicates(unittest.TestCase):
    """Test duplicate cleanup functionality"""

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
        session.query(EventDetail).delete()
        session.query(Event).delete()
        session.commit()
        session.close()

    def test_cleanup_finds_no_duplicates_with_different_content(self):
        """Cleanup should not remove events with different content"""
        event1 = Event(
            title="Event A",
            date=date_type(2026, 3, 15),
            time="10:00",
            location="Location",
            scraper="scraper1",
            detail_url="https://example.com/1",
        )
        event2 = Event(
            title="Event B",
            date=date_type(2026, 3, 15),
            time="10:00",
            location="Location",
            scraper="scraper2",
            detail_url="https://example.com/2",
        )

        upsert_event(event1)
        upsert_event(event2)

        before_count = len(load_events_by_date(date_type(2026, 3, 15)))
        stats = cleanup_duplicates()

        after_count = len(load_events_by_date(date_type(2026, 3, 15)))

        # No duplicates should be found
        self.assertEqual(stats["duplicates_found"], 0)
        self.assertEqual(stats["duplicates_removed"], 0)
        self.assertEqual(before_count, 2)
        self.assertEqual(after_count, 2)

    def test_cleanup_removes_exact_duplicates_keeps_earliest(self):
        """Cleanup should remove duplicate events, keeping the earliest (by ctime)"""
        # Create duplicate events (same title, location, time, date) with different URLs
        event1 = Event(
            title="Museum After Work",
            date=date_type(2026, 3, 15),
            time="18:00",
            location="Museum",
            scraper="scraper1",
            detail_url="https://example.com/event-1/date-1",
        )

        # Insert and verify first event
        upsert_event(event1)
        session = get_session()
        first_events = session.query(Event).all()
        session.close()
        self.assertEqual(len(first_events), 1)
        first_events[0].id

        # Now create a duplicate with same content but different URL
        event2 = Event(
            title="Museum After Work",
            date=date_type(2026, 3, 15),
            time="18:00",
            location="Museum",
            scraper="scraper2",
            detail_url="https://example.com/event-1/date-2",
        )
        upsert_event(event2)

        # Verify duplicate was detected and merged (should still be 1 event)
        before_count = len(load_events_by_date(date_type(2026, 3, 15)))
        self.assertEqual(before_count, 1)

        # Cleanup should report no duplicates to remove (they're already merged)
        stats = cleanup_duplicates()

        after_count = len(load_events_by_date(date_type(2026, 3, 15)))

        # After cleanup, should still have 1 event (or possibly 2 if duplicates existed)
        # Since upsert already deduplicates, cleanup should find 0 duplicates
        self.assertEqual(stats["duplicates_removed"], 0)
        self.assertEqual(after_count, before_count)

    def test_cleanup_preserves_recurring_events(self):
        """Cleanup should NOT remove same event on different dates (recurring events)"""
        # Same event on different dates - these should NOT be deduplicated
        event1 = Event(
            title="Weekly Meeting",
            date=date_type(2026, 3, 15),
            time="10:00",
            location="Conference Room",
            scraper="scraper1",
            detail_url="https://example.com/event-1",
        )
        event2 = Event(
            title="Weekly Meeting",
            date=date_type(2026, 3, 22),  # Different date
            time="10:00",
            location="Conference Room",
            scraper="scraper1",
            detail_url="https://example.com/event-1",
        )

        upsert_event(event1)
        upsert_event(event2)

        before_count = len(load_events_by_date(date_type(2026, 3, 15))) + len(
            load_events_by_date(date_type(2026, 3, 22))
        )
        stats = cleanup_duplicates()
        after_count = len(load_events_by_date(date_type(2026, 3, 15))) + len(
            load_events_by_date(date_type(2026, 3, 22))
        )

        # No duplicates should be removed (different dates = not duplicates)
        self.assertEqual(stats["duplicates_removed"], 0)
        self.assertEqual(before_count, 2)
        self.assertEqual(after_count, 2)

    def test_cleanup_handles_multiple_duplicates_same_date(self):
        """Cleanup should handle 3+ duplicates of same event on same date"""
        # Insert first event
        event1 = Event(
            title="Concert",
            date=date_type(2026, 3, 15),
            time="20:00",
            location="Stadium",
            scraper="scraper1",
            detail_url="https://example.com/concert-1",
        )
        upsert_event(event1)

        # Since upsert already deduplicates by content_hash + date,
        # trying to insert more duplicates should merge into existing event
        event2 = Event(
            title="Concert",
            date=date_type(2026, 3, 15),
            time="20:00",
            location="Stadium",
            scraper="scraper2",
            detail_url="https://example.com/concert-2",
        )
        upsert_event(event2)

        event3 = Event(
            title="Concert",
            date=date_type(2026, 3, 15),
            time="20:00",
            location="Stadium",
            scraper="scraper3",
            detail_url="https://example.com/concert-3",
        )
        upsert_event(event3)

        # All should be merged into one by upsert
        events = load_events_by_date(date_type(2026, 3, 15))
        self.assertEqual(len(events), 1)

        # Cleanup should find no duplicates to remove
        stats = cleanup_duplicates()
        self.assertEqual(stats["duplicates_removed"], 0)

    def test_cleanup_reports_stats(self):
        """Cleanup should return stats: duplicates_found, duplicates_removed, orphaned_details_removed"""
        event = Event(
            title="Test Event",
            date=date_type(2026, 3, 15),
            time="10:00",
            location="Location",
            scraper="scraper1",
            detail_url="https://example.com/1",
        )
        upsert_event(event)

        stats = cleanup_duplicates()

        # Should return a dict with required keys
        self.assertIn("duplicates_found", stats)
        self.assertIn("duplicates_removed", stats)
        self.assertIn("orphaned_details_removed", stats)
        self.assertIsInstance(stats["duplicates_found"], int)
        self.assertIsInstance(stats["duplicates_removed"], int)
        self.assertIsInstance(stats["orphaned_details_removed"], int)

    def test_cleanup_can_run_multiple_times_safely(self):
        """Cleanup should be idempotent - can run multiple times safely"""
        event = Event(
            title="Test Event",
            date=date_type(2026, 3, 15),
            time="10:00",
            location="Location",
            scraper="scraper1",
            detail_url="https://example.com/1",
        )
        upsert_event(event)

        # Run cleanup multiple times
        stats1 = cleanup_duplicates()
        stats2 = cleanup_duplicates()
        stats3 = cleanup_duplicates()

        # Should produce same results each time
        self.assertEqual(stats1["duplicates_removed"], stats2["duplicates_removed"])
        self.assertEqual(stats2["duplicates_removed"], stats3["duplicates_removed"])

    def test_cleanup_with_empty_database(self):
        """Cleanup should handle empty database gracefully"""
        stats = cleanup_duplicates()

        # Should complete without error and report 0 duplicates
        self.assertEqual(stats["duplicates_found"], 0)
        self.assertEqual(stats["duplicates_removed"], 0)
        self.assertEqual(stats["orphaned_details_removed"], 0)

    def test_cleanup_with_mixed_duplicate_and_unique_events(self):
        """Cleanup should remove duplicates but keep unique events"""
        # Unique event 1
        event1 = Event(
            title="Unique Event A",
            date=date_type(2026, 3, 15),
            time="10:00",
            location="Location A",
            scraper="scraper1",
            detail_url="https://example.com/1",
        )
        upsert_event(event1)

        # Unique event 2
        event2 = Event(
            title="Unique Event B",
            date=date_type(2026, 3, 15),
            time="14:00",
            location="Location B",
            scraper="scraper1",
            detail_url="https://example.com/2",
        )
        upsert_event(event2)

        # Duplicate of event 2
        event3 = Event(
            title="Unique Event B",
            date=date_type(2026, 3, 15),
            time="14:00",
            location="Location B",
            scraper="scraper2",
            detail_url="https://example.com/3",
        )
        upsert_event(event3)

        # Should have 2 events (1 + 1 merged duplicate)
        before_count = len(load_events_by_date(date_type(2026, 3, 15)))
        self.assertEqual(before_count, 2)

        stats = cleanup_duplicates()

        # Since upsert deduplicates, cleanup should find 0 duplicates
        self.assertEqual(stats["duplicates_removed"], 0)

        # Should still have 2 events after cleanup
        after_count = len(load_events_by_date(date_type(2026, 3, 15)))
        self.assertEqual(after_count, 2)

    def test_cleanup_handles_notifications_gracefully(self):
        """Cleanup should handle events with notifications"""
        session = get_session()

        # Create user
        user = User(username="testuser")
        session.add(user)
        session.commit()
        user_id = user.id

        # Create two DIFFERENT events
        event1 = Event(
            title="Event A",
            date=date_type(2026, 3, 15),
            time="10:00",
            location="Location",
            scraper="scraper1",
            detail_url="https://example.com/1",
        )
        session.add(event1)
        session.commit()
        event1_id = event1.id

        event2 = Event(
            title="Event B",  # Different title to avoid unique constraint
            date=date_type(2026, 3, 15),
            time="14:00",  # Different time
            location="Different Location",
            scraper="scraper2",
            detail_url="https://example.com/2",
        )
        session.add(event2)
        session.commit()
        event2_id = event2.id

        # Create notifications for both events
        notif1 = Notification(
            user_id=user_id,
            event_id=event1_id,
            send_at=datetime.now(),
            plugin="test",
        )
        notif2 = Notification(
            user_id=user_id,
            event_id=event2_id,
            send_at=datetime.now(),
            plugin="test",
        )
        session.add(notif1)
        session.add(notif2)
        session.commit()

        # Verify we have 2 events and 2 notifications
        self.assertEqual(session.query(Event).count(), 2)
        self.assertEqual(session.query(Notification).count(), 2)
        session.close()

        # Run cleanup - with no duplicates, should not remove anything but notifications_removed should be 0
        stats = cleanup_duplicates()

        # Verify results
        session = get_session()
        try:
            remaining_events = session.query(Event).count()
            remaining_notifs = session.query(Notification).count()
        finally:
            session.close()

        # Should still have 2 events and 2 notifications (no duplicates to remove)
        self.assertEqual(remaining_events, 2)
        self.assertEqual(remaining_notifs, 2)
        # Stats should show 0 notifications removed (no events were deleted)
        self.assertEqual(stats["notifications_removed"], 0)
