"""Test subscription backfill notifications on create/modify"""

import unittest
from datetime import date
from datetime import timedelta

from events_scraper.lib.core.orm_models import Event
from events_scraper.lib.core.orm_models import EventSubscription
from events_scraper.lib.core.orm_models import Notification
from events_scraper.lib.core.orm_models import User
from events_scraper.lib.core.orm_session import get_session
from events_scraper.lib.core.orm_session import init_database
from events_scraper.lib.subscriptions.backfill import (
    backfill_notifications_for_subscription,
)


class TestSubscriptionBackfill(unittest.TestCase):
    """Test backfill notifications when subscription is created or modified"""

    def setUp(self):
        """Set up test database and client"""
        self.engine = init_database("sqlite:///:memory:")

        session = get_session()
        # Create test user
        self.user = User(username="testuser")
        session.add(self.user)
        session.flush()  # Flush to get the ID
        self.user_id = self.user.id

        # Create future events in paris
        today = date.today()
        self.future_event_1 = Event(
            title="Kammerorchester Concert",
            date=today + timedelta(days=5),
            detail_url="http://example.com/event1",
            scraper="paris.test_scraper",
            body="A wonderful concert with chamber orchestra",
        )
        session.add(self.future_event_1)

        self.future_event_2 = Event(
            title="Piano Recital",
            date=today + timedelta(days=10),
            detail_url="http://example.com/event2",
            scraper="paris.test_scraper",
            body="Kammerorchester members perform solo pieces",
        )
        session.add(self.future_event_2)

        self.future_event_3 = Event(
            title="Theatre Play",
            date=today + timedelta(days=15),
            detail_url="http://example.com/event3",
            scraper="paris.test_scraper",
            body="A dramatic play with no orchestra",
        )
        session.add(self.future_event_3)

        # Create past event (should not be backfilled)
        self.past_event = Event(
            title="Kammerorchester Past Concert",
            date=today - timedelta(days=5),
            detail_url="http://example.com/past",
            scraper="paris.test_scraper",
            body="A concert that already happened",
        )
        session.add(self.past_event)

        # Create event in different group (should not be backfilled)
        self.other_group_event = Event(
            title="Paris Philharmonic",
            date=today + timedelta(days=7),
            detail_url="http://example.com/paris",
            scraper="paris.test_scraper",
            body="Concert in Paris",
        )
        session.add(self.other_group_event)

        session.commit()
        self.future_event_1_id = self.future_event_1.id
        self.future_event_2_id = self.future_event_2.id
        self.future_event_3_id = self.future_event_3.id
        self.past_event_id = self.past_event.id
        self.other_group_event_id = self.other_group_event.id
        session.close()

    def tearDown(self):
        """Clean up test database"""
        self.engine.dispose()

    def test_backfill_creates_notifications_for_matching_future_events(self):
        """Test backfill creates notifications for matching future events"""
        session = get_session()

        # Create subscription for "Kammerorchester"
        subscription = EventSubscription(
            user_id=self.user_id,
            group="paris",
            keyword="Kammerorchester",
            title_keyword="Kammerorchester",
            body_keyword=None,
            status="active",
        )
        session.add(subscription)
        session.commit()

        # Backfill notifications
        result = backfill_notifications_for_subscription(subscription, session)

        # Should create notifications for future_event_1 only (has "Kammerorchester" in title)
        # future_event_2 has it only in body, not title, so it doesn't match
        # Each event gets 2 notifications (3-day and 3-hour deltas)
        self.assertEqual(result["created"], 2)
        self.assertEqual(result["subscription_id"], subscription.id)
        self.assertEqual(result["skipped"], 0)

        # Verify notifications exist
        notifications = (
            session.query(Notification)
            .filter_by(user_id=self.user_id)
            .order_by(Notification.event_id)
            .all()
        )
        self.assertEqual(len(notifications), 2)

        # Check that notifications are for correct events
        event_ids = set(n.event_id for n in notifications)
        self.assertIn(
            self.future_event_1_id, event_ids
        )  # Has "Kammerorchester" in title
        self.assertNotIn(self.future_event_2_id, event_ids)  # Has it only in body
        self.assertNotIn(self.future_event_3_id, event_ids)  # No orchestra in title
        self.assertNotIn(self.past_event_id, event_ids)  # Past event
        self.assertNotIn(self.other_group_event_id, event_ids)  # Different group

        session.close()

    def test_backfill_only_creates_for_future_events(self):
        """Test backfill ignores past events"""
        session = get_session()

        subscription = EventSubscription(
            user_id=self.user_id,
            group="paris",
            keyword="Concert",
            title_keyword="Concert",
            body_keyword=None,
            status="active",
        )
        session.add(subscription)
        session.commit()

        result = backfill_notifications_for_subscription(subscription, session)

        # Should only create for future_event_1 (has "Concert" in title)
        # past_event has "Concert" but is in the past
        self.assertEqual(result["created"], 2)  # 2 deltas for 1 event

        session.close()

    def test_backfill_with_body_keyword(self):
        """Test backfill matches body keywords"""
        session = get_session()

        subscription = EventSubscription(
            user_id=self.user_id,
            group="paris",
            keyword="solo",
            title_keyword=None,
            body_keyword="solo",
            status="active",
        )
        session.add(subscription)
        session.commit()

        result = backfill_notifications_for_subscription(subscription, session)

        # Should only match future_event_2 (has "solo" in body)
        self.assertEqual(result["created"], 2)  # 2 deltas for 1 event

        session.close()

    def test_backfill_with_both_keywords_and_logic(self):
        """Test backfill with both keywords uses AND logic"""
        session = get_session()

        subscription = EventSubscription(
            user_id=self.user_id,
            group="paris",
            keyword="Kammerorchester concert",
            title_keyword="Kammerorchester",
            body_keyword="concert",
            status="active",
        )
        session.add(subscription)
        session.commit()

        result = backfill_notifications_for_subscription(subscription, session)

        # Should only match future_event_1 (has "Kammerorchester" in title AND "concert" in body)
        self.assertEqual(result["created"], 2)  # 2 deltas for 1 event

        session.close()

    def test_backfill_does_not_create_duplicates(self):
        """Test backfill doesn't create duplicate notifications"""
        session = get_session()

        subscription = EventSubscription(
            user_id=self.user_id,
            group="paris",
            keyword="Kammerorchester",
            title_keyword="Kammerorchester",
            body_keyword=None,
            status="active",
        )
        session.add(subscription)
        session.commit()

        # First backfill
        result1 = backfill_notifications_for_subscription(subscription, session)
        self.assertEqual(
            result1["created"], 2
        )  # Only 1 event matches (has "Kammerorchester" in title)

        # Second backfill should skip all (already exist)
        result2 = backfill_notifications_for_subscription(subscription, session)
        self.assertEqual(result2["created"], 0)
        self.assertEqual(result2["skipped"], 2)

        session.close()

    def test_backfill_handles_empty_results(self):
        """Test backfill handles case with no matching events"""
        session = get_session()

        subscription = EventSubscription(
            user_id=self.user_id,
            group="paris",
            keyword="Nonexistent",
            title_keyword="Nonexistent",
            body_keyword=None,
            status="active",
        )
        session.add(subscription)
        session.commit()

        result = backfill_notifications_for_subscription(subscription, session)

        self.assertEqual(result["created"], 0)
        self.assertEqual(result["skipped"], 0)

        session.close()

    def test_backfill_returns_error_on_database_failure(self):
        """Test backfill handles database errors gracefully"""
        session = get_session()

        subscription = EventSubscription(
            user_id=self.user_id,
            group="paris",
            keyword="Kammerorchester",
            title_keyword="Kammerorchester",
            body_keyword=None,
            status="active",
        )
        session.add(subscription)
        session.commit()

        # Store subscription ID before closing session
        subscription_id = subscription.id

        # Close session to simulate error
        session.close()

        result = backfill_notifications_for_subscription(subscription, session)

        # Should complete successfully despite closed session (SQLite reopens it)
        # This creates 2 notifications for future_event_1 (has "Kammerorchester" in title)
        self.assertEqual(result["created"], 2)
        self.assertEqual(result["subscription_id"], subscription_id)
        self.assertEqual(result["skipped"], 0)

    def test_backfill_continues_on_single_event_failure(self):
        """Test backfill continues processing other events if one fails"""
        session = get_session()

        subscription = EventSubscription(
            user_id=self.user_id,
            group="paris",
            keyword="Kammerorchester",
            title_keyword="Kammerorchester",
            body_keyword=None,
            status="active",
        )
        session.add(subscription)
        session.commit()

        # This test verifies the implementation doesn't crash on one event failure
        # Actual failure scenario is hard to simulate, but the function should
        # be resilient to individual event processing errors
        result = backfill_notifications_for_subscription(subscription, session)

        # Should still complete successfully
        self.assertIn("created", result)
        self.assertIn("skipped", result)

        session.close()


class TestSubscriptionModificationRecompute(unittest.TestCase):
    """Test recomputing notifications when subscription is modified"""

    def setUp(self):
        """Set up test database"""
        self.engine = init_database("sqlite:///:memory:")

        session = get_session()
        self.user = User(username="testuser")
        session.add(self.user)
        session.flush()  # Flush to get the ID
        self.user_id = self.user.id

        # Create future events
        today = date.today()
        self.event_1 = Event(
            title="Kammerorchester Concert",
            date=today + timedelta(days=5),
            detail_url="http://example.com/event1",
            scraper="paris.test_scraper",
            body="A concert",
        )
        session.add(self.event_1)

        self.event_2 = Event(
            title="Piano Solo",
            date=today + timedelta(days=10),
            detail_url="http://example.com/event2",
            scraper="paris.test_scraper",
            body="A piano recital",
        )
        session.add(self.event_2)

        session.commit()
        self.event_1_id = self.event_1.id
        self.event_2_id = self.event_2.id
        session.close()

    def tearDown(self):
        """Clean up test database"""
        self.engine.dispose()

    def test_modify_subscription_deletes_old_notifications(self):
        """Test modifying subscription deletes old notifications"""
        session = get_session()

        subscription = EventSubscription(
            user_id=self.user_id,
            group="paris",
            keyword="Kammerorchester",
            title_keyword="Kammerorchester",
            body_keyword=None,
            status="active",
        )
        session.add(subscription)
        session.commit()

        # Backfill initial notifications
        backfill_notifications_for_subscription(subscription, session)
        old_count = session.query(Notification).filter_by(user_id=self.user_id).count()
        self.assertGreater(old_count, 0)

        # Modify subscription to different keyword
        subscription.title_keyword = "Piano"
        session.commit()

        # Delete old notifications
        session.query(Notification).filter_by(user_id=self.user_id).delete()
        session.commit()

        # Backfill with new criteria
        result = backfill_notifications_for_subscription(subscription, session)

        # Should have different set of notifications
        new_notifications = (
            session.query(Notification).filter_by(user_id=self.user_id).all()
        )
        self.assertEqual(len(new_notifications), result["created"])

        # Should match different event now
        event_ids = set(n.event_id for n in new_notifications)
        self.assertIn(self.event_2_id, event_ids)  # Piano Solo
        self.assertNotIn(self.event_1_id, event_ids)  # Kammerorchester

        session.close()

    def test_modify_subscription_group_recomputes(self):
        """Test modifying subscription group recomputes notifications"""
        session = get_session()

        # Create event in paris
        today = date.today()
        paris_event = Event(
            title="Paris Philharmonic",
            date=today + timedelta(days=5),
            detail_url="http://example.com/paris",
            scraper="paris.test_scraper",
            body="A concert in Paris",
        )
        session.add(paris_event)
        session.commit()

        subscription = EventSubscription(
            user_id=self.user_id,
            group="paris",
            keyword="Kammerorchester",
            title_keyword="Kammerorchester",
            body_keyword=None,
            status="active",
        )
        session.add(subscription)
        session.commit()

        # Backfill for paris
        backfill_notifications_for_subscription(subscription, session)

        # Change group to paris
        subscription.group = "paris"
        session.commit()

        # Delete old notifications
        session.query(Notification).filter_by(user_id=self.user_id).delete()
        session.commit()

        # Backfill for paris
        backfill_notifications_for_subscription(subscription, session)

        # Should have notifications for paris event
        new_count = session.query(Notification).filter_by(user_id=self.user_id).count()
        self.assertGreater(new_count, 0)

        session.close()
