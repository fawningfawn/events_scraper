"""Test SQLAlchemy ORM models"""

import unittest
from datetime import date
from datetime import timedelta

from sqlalchemy import create_engine
from sqlalchemy import inspect
from sqlalchemy.orm import sessionmaker

from events_scraper.lib import mock_data
from events_scraper.lib.core.orm_models import Base
from events_scraper.lib.core.orm_models import Event
from events_scraper.lib.core.orm_models import EventDetail


class TestOrmModels(unittest.TestCase):
    """Test SQLAlchemy ORM Event and EventDetail models"""

    def setUp(self):
        """Set up in-memory SQLite database for testing"""
        self.engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

    def tearDown(self):
        """Clean up database session"""
        self.session.close()
        self.engine.dispose()

    def test_event_creation_with_required_fields(self):
        """Test creating an Event with only required fields"""
        event = mock_data.get_orm_event()

        self.session.add(event)
        self.session.commit()

        # Verify event was saved and has auto-generated ID
        self.assertIsNotNone(event.id)
        self.assertIsNotNone(event.title)
        self.assertIsNotNone(event.date)
        self.assertIsNotNone(event.ctime)  # Should have default timestamp
        # Verify required fields are populated
        self.assertIsNotNone(event.scraper)
        self.assertIsNotNone(event.detail_url)

    def test_event_creation_with_all_fields(self):
        """Test creating an Event with all fields populated"""
        event = Event(
            title="Full Event",
            date=date(2025, 7, 29),
            time="19:30",
            location="Test Venue",
            categories="music,concert",
            detail_url="http://example.com/event",
            scraper="test_scraper",
            latitude=49.2301,
            longitude=6.9967,
            end_date=date(2025, 7, 31),
        )

        self.session.add(event)
        self.session.commit()

        # Verify all fields
        self.assertEqual(event.title, "Full Event")
        self.assertEqual(event.date, date(2025, 7, 29))
        self.assertEqual(event.time, "19:30")
        self.assertEqual(event.location, "Test Venue")
        self.assertEqual(event.categories, "music,concert")
        self.assertEqual(event.detail_url, "http://example.com/event")
        self.assertEqual(event.scraper, "test_scraper")
        self.assertEqual(event.latitude, 49.2301)
        self.assertEqual(event.longitude, 6.9967)
        self.assertEqual(event.end_date, date(2025, 7, 31))

    def test_event_categories_list_property(self):
        """Test categories_list property conversion"""
        event = mock_data.get_orm_event()

        # Test setting categories as list
        event.categories_list = ["music", "concert", "jazz"]
        self.assertEqual(event.categories, "music,concert,jazz")

        # Test getting categories as list
        self.assertEqual(event.categories_list, ["music", "concert", "jazz"])

        # Test empty categories
        event.categories_list = []
        self.assertIsNone(event.categories)
        self.assertEqual(event.categories_list, [])

    def test_event_contains_date_single_day(self):
        """Test contains_date for single-day events"""
        event = mock_data.get_orm_event()

        # Should match exact date
        self.assertTrue(event.contains_date(event.date))

        # Should not match other dates

        day_before = event.date - timedelta(days=1)
        day_after = event.date + timedelta(days=1)
        self.assertFalse(event.contains_date(day_before))
        self.assertFalse(event.contains_date(day_after))

    def test_event_contains_date_multi_day(self):
        """Test contains_date for multi-day events"""
        # Create multi-day event with consistent date range
        start_date = mock_data.get_date()

        end_date = start_date + timedelta(days=2)

        event = mock_data.get_orm_event(
            date=start_date.strftime("%Y-%m-%d"), end_date=end_date.strftime("%Y-%m-%d")
        )

        # Should match all dates in range
        self.assertTrue(event.contains_date(event.date))  # Start date
        middle_date = event.date + timedelta(days=1)
        self.assertTrue(event.contains_date(middle_date))  # Middle date
        self.assertTrue(event.contains_date(event.end_date))  # End date

        # Should not match dates outside range
        before_start = event.date - timedelta(days=1)
        after_end = event.end_date + timedelta(days=1)
        self.assertFalse(event.contains_date(before_start))
        self.assertFalse(event.contains_date(after_end))

    def test_event_detail_creation(self):
        """Test creating EventDetail"""
        detail = EventDetail(
            url="http://example.com/event/123",
            content="<html>Event details here</html>",
            fetched_at=1234567890.0,
            scraper="test_scraper",
        )

        self.session.add(detail)
        self.session.commit()

        # Verify detail was saved
        self.assertEqual(detail.url, "http://example.com/event/123")
        self.assertEqual(detail.content, "<html>Event details here</html>")
        self.assertEqual(detail.fetched_at, 1234567890.0)
        self.assertEqual(detail.scraper, "test_scraper")

    def test_event_detail_relationship(self):
        """Test relationship between Event and EventDetail"""
        # Create event with specific detail URL for relationship testing
        detail_url = "http://example.com/event/123"
        event = mock_data.get_orm_event(detail_url=detail_url)
        self.session.add(event)
        self.session.commit()

        # Create related detail
        detail = EventDetail(
            url=detail_url,
            content="<html>Detailed content</html>",
            fetched_at=1234567890.0,
            event_id=event.id,
        )
        self.session.add(detail)
        self.session.commit()

        # Test relationship works both ways
        self.assertEqual(event.detail, detail)
        self.assertEqual(detail.event, event)

    def test_event_query_by_date(self):
        """Test querying events by date"""
        # Create events on different dates
        test_date = mock_data.get_date()
        different_date = test_date + timedelta(days=1)

        event1 = mock_data.get_orm_event(date=test_date.strftime("%Y-%m-%d"), id=None)
        event2 = mock_data.get_orm_event(
            date=different_date.strftime("%Y-%m-%d"), id=None
        )
        event3 = mock_data.get_orm_event(date=test_date.strftime("%Y-%m-%d"), id=None)

        self.session.add_all([event1, event2, event3])
        self.session.commit()

        # Query events for specific date
        events_on_test_date = (
            self.session.query(Event).filter(Event.date == test_date).all()
        )

        self.assertEqual(len(events_on_test_date), 2)
        event_titles = [e.title for e in events_on_test_date]
        self.assertIn(event1.title, event_titles)
        self.assertIn(event3.title, event_titles)

    def test_date_field_is_proper_date_object(self):
        """Test that date field stores and returns proper date objects"""
        event = mock_data.get_orm_event()

        self.session.add(event)
        self.session.commit()

        # Reload from database
        reloaded_event = (
            self.session.query(Event).filter(Event.title == event.title).first()
        )

        # Verify it's still a date object, not a string
        self.assertIsInstance(reloaded_event.date, date)
        self.assertEqual(reloaded_event.date, event.date)

        # This should work without AttributeError
        formatted_date = reloaded_event.date.strftime("%Y-%m-%d")
        expected_formatted = event.date.strftime("%Y-%m-%d")
        self.assertEqual(formatted_date, expected_formatted)

    def test_events_unique_constraint_matches_content_hash_plus_date(self):
        """Schema guard: events must be unique on (`content_hash`, `date`)."""
        inspector = inspect(self.engine)
        constraints = inspector.get_unique_constraints("events")

        constrained_column_sets = {
            frozenset(constraint.get("column_names", [])) for constraint in constraints
        }

        self.assertIn(
            frozenset(["content_hash", "date"]),
            constrained_column_sets,
            "Missing unique constraint on (`content_hash`, `date`)",
        )
        self.assertNotIn(
            frozenset(["detail_url", "year"]),
            constrained_column_sets,
            "Unexpected legacy unique constraint on (`detail_url`, `year`)",
        )

    def test_same_detail_url_is_allowed_on_different_dates(self):
        """Regression: identical `detail_url` should not block recurring events."""
        shared_url = "https://example.test/event/shared-url"
        event1 = mock_data.get_orm_event(
            title="Recurring Event",
            location="Same Venue",
            time="19:30",
            date="2026-03-22",
            detail_url=shared_url,
        )
        event2 = mock_data.get_orm_event(
            title="Recurring Event",
            location="Same Venue",
            time="19:30",
            date="2026-03-23",
            detail_url=shared_url,
        )

        self.session.add_all([event1, event2])
        self.session.commit()

        saved = (
            self.session.query(Event)
            .filter(Event.detail_url == shared_url)
            .order_by(Event.date)
            .all()
        )
        self.assertEqual(len(saved), 2)
        self.assertNotEqual(saved[0].date, saved[1].date)


class TestNotificationModel(unittest.TestCase):
    """Test SQLAlchemy ORM Notification model"""

    def setUp(self):
        """Set up in-memory SQLite database for testing"""
        self.engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

    def tearDown(self):
        """Clean up database session"""
        self.session.close()
        self.engine.dispose()

    def test_notification_creation_with_required_fields(self):
        """Test creating a Notification with required fields"""
        user = mock_data.get_orm_user(session=self.session)
        event = mock_data.get_orm_event(session=self.session)
        notification = mock_data.get_orm_notification(
            session=self.session, user=user, event=event
        )

        self.session.commit()

        # Verify notification was saved
        self.assertIsNotNone(notification.id)
        self.assertEqual(notification.user_id, user.id)
        self.assertEqual(notification.event_id, event.id)
        self.assertIsNotNone(notification.notify_delta)
        self.assertIsNotNone(notification.send_at)
        self.assertIsNone(notification.sent_at)
        self.assertEqual(notification.status, "pending")

    def test_notification_default_values(self):
        """Test Notification model default values"""
        user = mock_data.get_orm_user(session=self.session)
        event = mock_data.get_orm_event(session=self.session)
        notification = mock_data.get_orm_notification(
            session=self.session, user=user, event=event
        )

        # Check defaults
        self.assertEqual(notification.notify_delta, 259200)  # 3 days in seconds
        self.assertEqual(notification.status, "pending")
        self.assertIsNone(notification.sent_at)

    def test_notification_relationships(self):
        """Test Notification relationships to User and Event"""
        user = mock_data.get_orm_user(session=self.session)
        event = mock_data.get_orm_event(session=self.session)
        notification = mock_data.get_orm_notification(
            session=self.session, user=user, event=event
        )

        self.session.commit()

        # Reload from database
        reloaded = (
            self.session.query(notification.__class__)
            .filter_by(id=notification.id)
            .first()
        )

        # Verify relationships work
        self.assertEqual(reloaded.user_id, user.id)
        self.assertEqual(reloaded.event_id, event.id)

    def test_event_cancelled_default_false(self):
        event = mock_data.get_orm_event()

        self.session.add(event)
        self.session.commit()

        self.assertFalse(event.cancelled)

    def test_event_cancelled_can_be_true(self):
        event = mock_data.get_orm_event(cancelled=True)

        self.session.add(event)
        self.session.commit()

        self.assertTrue(event.cancelled)

    def test_event_cancelled_query_filters(self):
        active = mock_data.get_orm_event(title="Active Event", cancelled=False)
        cancelled = mock_data.get_orm_event(title="Cancelled Event", cancelled=True)

        self.session.add_all([active, cancelled])
        self.session.commit()

        active_events = self.session.query(Event).filter(~Event.cancelled).all()
        self.assertEqual(len(active_events), 1)
        self.assertEqual(active_events[0].title, "Active Event")

        cancelled_events = self.session.query(Event).filter(Event.cancelled).all()
        self.assertEqual(len(cancelled_events), 1)
        self.assertEqual(cancelled_events[0].title, "Cancelled Event")

    def test_event_to_dict_includes_cancelled(self):
        event = mock_data.get_orm_event(cancelled=True)
        self.session.add(event)
        self.session.commit()

        d = event.to_dict()
        self.assertIn("cancelled", d)
        self.assertTrue(d["cancelled"])

    def test_event_cancelled_toggle(self):
        event = mock_data.get_orm_event()
        self.session.add(event)
        self.session.commit()

        self.assertFalse(event.cancelled)

        event.cancelled = True
        self.session.commit()

        reloaded = self.session.query(Event).filter_by(id=event.id).first()
        self.assertTrue(reloaded.cancelled)

        event.cancelled = False
        self.session.commit()

        reloaded = self.session.query(Event).filter_by(id=event.id).first()
        self.assertFalse(reloaded.cancelled)

    def test_notification_status_values(self):
        """Test valid status values for Notification"""
        user = mock_data.get_orm_user(session=self.session)
        event = mock_data.get_orm_event(session=self.session)

        for status in ["pending", "sent", "failed"]:
            notification = mock_data.get_orm_notification(
                session=self.session, user=user, event=event, status=status
            )
            self.session.commit()
            self.assertEqual(notification.status, status)
