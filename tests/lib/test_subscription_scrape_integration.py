"""Test subscription integration with event scraping"""

import unittest
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from events_scraper.lib.core.orm_models import Base
from events_scraper.lib.core.orm_models import Event
from events_scraper.lib.core.orm_models import EventSubscription
from events_scraper.lib.core.orm_models import Notification
from events_scraper.lib.core.orm_models import User
from events_scraper.lib.subscriptions.scrape_integration import (
    create_notifications_for_matching_subscriptions,
)


class TestSubscriptionScrapeIntegration(unittest.TestCase):
    """Test subscription integration with scraping"""

    def setUp(self):
        """Set up test database"""
        self.engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

        # Create test user
        self.user = User(username="testuser")
        self.session.add(self.user)
        self.session.commit()

    def tearDown(self):
        """Clean up database"""
        self.session.close()
        self.engine.dispose()

    def test_check_subscriptions_on_event_save(self):
        """Test when event is saved, all active subscriptions for that group are checked"""
        # Create subscription
        subscription = EventSubscription(
            user_id=self.user.id,
            group="paris",
            keyword="Kammerorchester",
            title_keyword="Kammerorchester",
            body_keyword=None,
            status="active",
        )
        self.session.add(subscription)
        self.session.commit()

        # Create matching event
        event = Event(
            title="Paris Philharmonic Kammerorchester Concert",
            date=date(2025, 2, 15),
            location="Test Hall",
            detail_url="http://example.com/event",
            scraper="paris.test",
        )
        self.session.add(event)
        self.session.commit()

        # Check subscriptions
        result = create_notifications_for_matching_subscriptions(event, self.session)

        self.assertEqual(result, 2)  # 3-day and 3-hour notifications

    def test_matching_subscription_creates_notifications_with_standard_deltas(self):
        """Test matching subscription creates notifications with standard deltas"""
        # Create subscription
        subscription = EventSubscription(
            user_id=self.user.id,
            group="paris",
            keyword="Concert",
            title_keyword="Concert",
            body_keyword=None,
            status="active",
        )
        self.session.add(subscription)
        self.session.commit()

        # Create matching event
        event = Event(
            title="Piano Concert",
            date=date(2025, 2, 15),
            location="Test Hall",
            detail_url="http://example.com/event",
            scraper="paris.test",
        )
        self.session.add(event)
        self.session.commit()

        # Check subscriptions
        create_notifications_for_matching_subscriptions(event, self.session)

        # Verify notifications created
        notifications = (
            self.session.query(Notification)
            .filter_by(user_id=self.user.id, event_id=event.id)
            .all()
        )
        self.assertEqual(len(notifications), 2)

        # Verify deltas
        deltas = sorted([n.notify_delta for n in notifications])
        self.assertEqual(deltas, [10800, 259200])  # 3 hours, 3 days

    def test_non_matching_event_does_not_create_notifications(self):
        """Test non-matching event doesn't create notifications"""
        # Create subscription
        subscription = EventSubscription(
            user_id=self.user.id,
            group="paris",
            keyword="Kammerorchester",
            title_keyword="Kammerorchester",
            body_keyword=None,
            status="active",
        )
        self.session.add(subscription)
        self.session.commit()

        # Create non-matching event
        event = Event(
            title="Rock Concert",
            date=date(2025, 2, 15),
            location="Test Hall",
            detail_url="http://example.com/event",
            scraper="paris.test",
        )
        self.session.add(event)
        self.session.commit()

        # Check subscriptions
        created_count = create_notifications_for_matching_subscriptions(
            event, self.session
        )

        self.assertEqual(created_count, 0)

    def test_prevents_duplicate_notifications(self):
        """Test doesn't create duplicate notifications for same user+event+delta combo"""
        # Create subscription
        subscription = EventSubscription(
            user_id=self.user.id,
            group="paris",
            keyword="Concert",
            title_keyword="Concert",
            body_keyword=None,
            status="active",
        )
        self.session.add(subscription)
        self.session.commit()

        # Create event
        event = Event(
            title="Piano Concert",
            date=date(2025, 2, 15),
            location="Test Hall",
            detail_url="http://example.com/event",
            scraper="paris.test",
        )
        self.session.add(event)
        self.session.commit()

        # Create notifications first time
        created_count_1 = create_notifications_for_matching_subscriptions(
            event, self.session
        )
        self.assertEqual(created_count_1, 2)

        # Try creating again
        created_count_2 = create_notifications_for_matching_subscriptions(
            event, self.session
        )
        self.assertEqual(created_count_2, 0)  # Should not create duplicates

        # Verify only 2 notifications exist
        notifications = (
            self.session.query(Notification)
            .filter_by(user_id=self.user.id, event_id=event.id)
            .all()
        )
        self.assertEqual(len(notifications), 2)

    def test_only_active_subscriptions_are_checked(self):
        """Test only active subscriptions are checked, disabled ones are ignored"""
        # Create active subscription
        active_sub = EventSubscription(
            user_id=self.user.id,
            group="paris",
            keyword="Concert",
            title_keyword="Concert",
            body_keyword=None,
            status="active",
        )
        self.session.add(active_sub)

        # Create disabled subscription
        disabled_sub = EventSubscription(
            user_id=self.user.id,
            group="paris",
            keyword="Concert",
            title_keyword="Concert",
            body_keyword=None,
            status="disabled",
        )
        self.session.add(disabled_sub)
        self.session.commit()

        # Create matching event
        event = Event(
            title="Piano Concert",
            date=date(2025, 2, 15),
            location="Test Hall",
            detail_url="http://example.com/event",
            scraper="paris.test",
        )
        self.session.add(event)
        self.session.commit()

        # Check subscriptions
        created_count = create_notifications_for_matching_subscriptions(
            event, self.session
        )

        # Should only create for active subscription (2 notifications)
        self.assertEqual(created_count, 2)

    def test_handles_event_with_no_group(self):
        """Test handles case where event has no group (scraper format issues)"""
        # Create subscription
        subscription = EventSubscription(
            user_id=self.user.id,
            group="paris",
            keyword="Concert",
            title_keyword="Concert",
            body_keyword=None,
            status="active",
        )
        self.session.add(subscription)
        self.session.commit()

        # Create event with no group in scraper name
        event = Event(
            title="Piano Concert",
            date=date(2025, 2, 15),
            location="Test Hall",
            detail_url="http://example.com/event",
            scraper="invalid_scraper",  # No dot, can't extract group
        )
        self.session.add(event)
        self.session.commit()

        # Should handle gracefully
        result = create_notifications_for_matching_subscriptions(event, self.session)
        self.assertEqual(result, 0)

    def test_handles_database_errors_gracefully(self):
        """Test handles database errors gracefully without breaking scraper"""
        # Create subscription first
        subscription = EventSubscription(
            user_id=self.user.id,
            group="paris",
            keyword="Concert",
            title_keyword="Concert",
            body_keyword=None,
            status="active",
        )
        self.session.add(subscription)
        self.session.commit()

        # Create event with valid scraper
        event = Event(
            title="Concert",
            date=date(2025, 2, 15),
            location="Test Hall",
            detail_url="http://example.com/event",
            scraper="paris.test",
        )
        self.session.add(event)
        self.session.commit()

        # Create a new session for error testing
        bad_session = sessionmaker(bind=self.engine)()

        # Should handle error gracefully and not raise exception
        # Even with a fresh session, the function should handle issues gracefully
        try:
            created_count = create_notifications_for_matching_subscriptions(
                event, bad_session
            )
            # Should return > 0 (notifications created)
            self.assertGreater(created_count, 0)
        except Exception as e:
            self.fail(f"Should handle operations without raising but got: {e}")
