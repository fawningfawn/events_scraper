"""Test SQLAlchemy session management that replaces DatabaseManager"""

import shutil
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import patch

from sqlalchemy import inspect

from events_scraper.lib import mock_data
from events_scraper.lib.core.orm_models import Event
from events_scraper.lib.core.orm_session import _build_scraper_query
from events_scraper.lib.core.orm_session import count_events_by_scraper
from events_scraper.lib.core.orm_session import get_session
from events_scraper.lib.core.orm_session import init_database
from events_scraper.lib.core.orm_session import load_events_by_date
from events_scraper.lib.core.orm_session import load_events_by_scraper_paginated
from events_scraper.lib.core.orm_session import upsert_event
from tests.lib.core.test_base import BaseTestCase


class TestOrmSession(BaseTestCase):
    """Test SQLAlchemy session management replacing DatabaseManager"""

    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"

    def tearDown(self):
        """Clean up test environment"""
        super().tearDown()
        shutil.rmtree(self.temp_dir)

    def test_init_database_creates_tables(self):
        """Test that init_database creates all required tables"""
        # This test will fail until we implement init_database
        db_url = f"sqlite:////{self.db_path}"
        engine = init_database(db_url)

        # Check that tables exist
        inspector = inspect(engine)
        table_names = inspector.get_table_names()

        self.assertIn("events", table_names)
        self.assertIn("event_details", table_names)

    def test_init_database_in_memory(self):
        """Test that init_database works with in-memory database"""
        # This test will fail until we implement init_database
        engine = init_database("sqlite:///:memory:")

        inspector = inspect(engine)
        table_names = inspector.get_table_names()

        self.assertIn("events", table_names)
        self.assertIn("event_details", table_names)

    def test_get_session_returns_working_session(self):
        """Test that get_session returns a working SQLAlchemy session"""
        # This test will fail until we implement get_session
        init_database("sqlite:///:memory:")
        session = get_session()

        # Test that we can use the session
        event = mock_data.get_orm_event()

        session.add(event)
        session.commit()

        # Verify event was saved
        saved_event = session.query(Event).filter(Event.title == event.title).first()
        self.assertIsNotNone(saved_event)
        self.assertEqual(saved_event.title, event.title)
        self.assertEqual(saved_event.date, event.date)

        session.close()

    def test_multiple_sessions_work_independently(self):
        """Test that multiple sessions can be created and work independently"""
        # This test will fail until we implement session management
        init_database("sqlite:///:memory:")

        session1 = get_session()
        session2 = get_session()

        # Sessions should be different objects
        self.assertIsNot(session1, session2)

        # Both should work independently
        event1 = mock_data.get_orm_event()
        event2 = mock_data.get_orm_event()

        session1.add(event1)
        session2.add(event2)

        session1.commit()
        session2.commit()

        # Both events should exist
        self.assertEqual(session1.query(Event).count(), 2)
        self.assertEqual(session2.query(Event).count(), 2)

        session1.close()
        session2.close()

    def test_session_handles_database_url_configuration(self):
        """Test that session management respects database URL configuration"""
        # This test will fail until we implement URL configuration
        file_db_url = f"sqlite:////{self.db_path}"
        init_database(file_db_url)

        session = get_session()

        event = mock_data.get_orm_event()

        # Capture title before session operations
        event_title = event.title

        session.add(event)
        session.commit()
        session.close()

        # Database file should exist
        self.assertTrue(self.db_path.exists())

        # Should be able to reconnect and find the event
        session2 = get_session()
        saved_event = session2.query(Event).filter(Event.title == event_title).first()
        self.assertIsNotNone(saved_event)
        session2.close()

    def test_load_events_using_orm_session(self):
        """Test loading events using ORM session (replacing load_events_from_database)"""
        # This test will fail until we implement ORM-based event loading
        init_database("sqlite:///:memory:")
        session = get_session()

        # Create test events with consistent date and scraper for city filtering
        test_date = mock_data.get_date()
        test_date_str = test_date.strftime("%Y-%m-%d")
        different_date = test_date + timedelta(days=1)
        different_date_str = different_date.strftime("%Y-%m-%d")

        event1 = mock_data.get_orm_event(
            date=test_date_str, scraper="paris.test", id=None
        )
        event2 = mock_data.get_orm_event(
            date=different_date_str, scraper="paris.test", id=None
        )  # Different date
        event3 = mock_data.get_orm_event(
            date=test_date_str, scraper="paris.test", id=None
        )

        # Capture titles before session operations
        event1_title = event1.title
        event2_title = event2.title
        event3_title = event3.title

        session.add_all([event1, event2, event3])
        session.commit()
        session.close()

        # Load events for specific date
        events = load_events_by_date(test_date, group="paris")

        self.assertEqual(len(events), 2)
        event_titles = [e.title for e in events]
        self.assertIn(event1_title, event_titles)
        self.assertIn(event3_title, event_titles)
        self.assertNotIn(event2_title, event_titles)

    def test_save_event_using_orm_session(self):
        """Test saving events using ORM session (replacing Event.save)"""
        init_database("sqlite:///:memory:")

        event = mock_data.get_orm_event()

        event_title = event.title
        event_date = event.date

        upsert_event(event)

        session = get_session()
        saved_event = session.query(Event).filter(Event.title == event_title).first()
        self.assertIsNotNone(saved_event)
        self.assertEqual(saved_event.date, event_date)
        session.close()

    def test_build_scraper_query_uses_injected_session(self):
        """`_build_scraper_query` must use caller-provided session."""
        init_database("sqlite:///:memory:")
        session = get_session()
        try:
            query = _build_scraper_query(session, "paris.test", include_past=True)
            self.assertIsNotNone(query)
        finally:
            session.close()

    @patch("events_scraper.lib.core.orm_session._build_scraper_query")
    @patch("events_scraper.lib.core.orm_session.get_session")
    def test_load_events_by_scraper_paginated_passes_own_session(
        self, mock_get_session, mock_build_query
    ):
        """Pagination loader should build query with its own session."""
        session = MagicMock()
        mock_get_session.return_value = session

        query = MagicMock()
        query.offset.return_value = query
        query.limit.return_value = query
        query.all.return_value = []
        mock_build_query.return_value = query

        result = load_events_by_scraper_paginated("paris.test", page=2, per_page=10)

        self.assertEqual(result, [])
        mock_build_query.assert_called_once_with(session, "paris.test", False)
        session.close.assert_called_once()

    def test_load_events_by_date_none_target_returns_all(self):
        init_database("sqlite:///:memory:")
        mock_data.get_orm_event(
            session=get_session(),
            title="Today Event",
            date="2026-06-01",
        )
        mock_data.get_orm_event(
            session=get_session(),
            title="Future Event",
            date="2027-12-15",
        )

        events = load_events_by_date(target_date=None)
        titles = [e.title for e in events]
        self.assertIn("Today Event", titles)
        self.assertIn("Future Event", titles)

    def test_load_events_by_date_excludes_cancelled_by_default(self):
        init_database("sqlite:///:memory:")
        target = mock_data.get_date()

        mock_data.get_orm_event(
            session=get_session(),
            title="Active Event",
            date=target.strftime("%Y-%m-%d"),
            cancelled=False,
        )
        mock_data.get_orm_event(
            session=get_session(),
            title="Cancelled Event",
            date=target.strftime("%Y-%m-%d"),
            cancelled=True,
        )

        events = load_events_by_date(target)
        titles = [e.title for e in events]

        self.assertIn("Active Event", titles)
        self.assertNotIn("Cancelled Event", titles)

    def test_load_events_by_date_includes_cancelled_when_requested(self):
        init_database("sqlite:///:memory:")
        target = mock_data.get_date()

        mock_data.get_orm_event(
            session=get_session(),
            title="Active Event",
            date=target.strftime("%Y-%m-%d"),
            cancelled=False,
        )
        mock_data.get_orm_event(
            session=get_session(),
            title="Cancelled Event",
            date=target.strftime("%Y-%m-%d"),
            cancelled=True,
        )

        events = load_events_by_date(target, include_cancelled=True)
        titles = [e.title for e in events]

        self.assertIn("Active Event", titles)
        self.assertIn("Cancelled Event", titles)

    def test_upsert_event_preserves_cancelled_on_update(self):
        init_database("sqlite:///:memory:")
        target = mock_data.get_date()

        first = mock_data.get_orm_event(
            title="Same Event",
            location="Same Venue",
            time="19:00",
            date=target.strftime("%Y-%m-%d"),
            cancelled=False,
        )
        upsert_event(first)

        second = mock_data.get_orm_event(
            title="Same Event",
            location="Same Venue",
            time="19:00",
            date=target.strftime("%Y-%m-%d"),
            cancelled=False,
        )

        session = get_session()
        try:
            existing = session.query(Event).filter(Event.date == target).first()
            if existing:
                existing.cancelled = True
                session.commit()
        finally:
            session.close()

        upsert_event(second)

        session = get_session()
        try:
            events = session.query(Event).filter(Event.date == target).all()
            self.assertEqual(len(events), 1)
            self.assertTrue(events[0].cancelled)
        finally:
            session.close()

    @patch("events_scraper.lib.core.orm_session._build_scraper_query")
    @patch("events_scraper.lib.core.orm_session.get_session")
    def test_count_events_by_scraper_passes_own_session(
        self, mock_get_session, mock_build_query
    ):
        """Count loader should build query with its own session."""
        session = MagicMock()
        mock_get_session.return_value = session

        query = MagicMock()
        query.count.return_value = 7
        mock_build_query.return_value = query

        result = count_events_by_scraper("paris.test")

        self.assertEqual(result, 7)
        mock_build_query.assert_called_once_with(session, "paris.test", False)
        session.close.assert_called_once()
