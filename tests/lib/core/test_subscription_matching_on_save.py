"""Tests for automatic subscription matching when events are saved."""

from datetime import date
from datetime import timedelta

from events_scraper.lib import mock_data
from events_scraper.lib.core.orm_models import EventSubscription
from events_scraper.lib.core.orm_models import Notification
from events_scraper.lib.core.orm_session import get_session
from events_scraper.lib.core.orm_session import upsert_event
from events_scraper.lib.subscriptions.scrape_integration import (
    create_notifications_for_matching_subscriptions,
)
from tests.lib.core.test_base import DatabaseTestCase


class UpsertSubscriptionMatchingTestCase(DatabaseTestCase):
    """Test that upsert_event triggers subscription matching."""

    def setUp(self):
        super().setUp()
        self.session = get_session()
        self.user = mock_data.get_orm_user(session=self.session, username="testuser")
        self.session.commit()
        self.future_date = date.today() + timedelta(days=30)

    def test_new_event_creates_notification_for_matching_subscription(self):
        """Saving a new event should create notifications for matching subscriptions."""
        sub = EventSubscription(
            user_id=self.user.id,
            group="paris",
            title_keyword="jazz",
        )
        self.session.add(sub)
        self.session.commit()

        event = mock_data.get_orm_event(
            title="Jazz Night",
            scraper="paris.venue",
            date=self.future_date,
        )
        upsert_event(event)

        notifications = (
            self.session.query(Notification).filter_by(user_id=self.user.id).all()
        )
        self.assertGreater(len(notifications), 0)

    def test_non_matching_event_creates_no_notification(self):
        """Saving an event that doesn't match should create no notifications."""
        sub = EventSubscription(
            user_id=self.user.id,
            group="paris",
            title_keyword="jazz",
        )
        self.session.add(sub)
        self.session.commit()

        event = mock_data.get_orm_event(
            title="Rock Concert",
            scraper="paris.venue",
            date=self.future_date,
        )
        upsert_event(event)

        notifications = (
            self.session.query(Notification).filter_by(user_id=self.user.id).all()
        )
        self.assertEqual(len(notifications), 0)

    def test_no_duplicate_notifications_on_rematch(self):
        """Matching the same event twice should not create duplicate notifications."""
        sub = EventSubscription(
            user_id=self.user.id,
            group="paris",
            title_keyword="jazz",
        )
        self.session.add(sub)

        event = mock_data.get_orm_event(
            session=self.session,
            title="Jazz Night",
            scraper="paris.venue",
            date=self.future_date,
        )
        self.session.commit()

        created_first = create_notifications_for_matching_subscriptions(
            event, self.session
        )
        created_second = create_notifications_for_matching_subscriptions(
            event, self.session
        )

        self.assertGreater(created_first, 0)
        self.assertEqual(created_second, 0)

    def test_different_group_subscription_not_matched(self):
        """Event from different group should not match subscription."""
        sub = EventSubscription(
            user_id=self.user.id,
            group="paris",
            title_keyword="jazz",
        )
        self.session.add(sub)
        self.session.commit()

        event = mock_data.get_orm_event(
            title="Jazz Night",
            scraper="london.venue",
            date=self.future_date,
        )
        upsert_event(event)

        notifications = (
            self.session.query(Notification).filter_by(user_id=self.user.id).all()
        )
        self.assertEqual(len(notifications), 0)
