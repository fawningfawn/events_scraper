"""Test notification UI functionality"""

import unittest

from events_scraper.lib import mock_data
from events_scraper.lib.core.orm_models import Notification
from events_scraper.lib.core.orm_models import User
from events_scraper.lib.core.orm_session import dispose_engine
from events_scraper.lib.core.orm_session import get_session
from events_scraper.lib.core.orm_session import init_database
from events_scraper.lib.web.app import create_app


class TestNotificationUI(unittest.TestCase):
    """Test notification UI components"""

    def setUp(self):
        """Set up test client and database"""
        # Initialize in-memory SQLite database
        init_database("sqlite:///:memory:")
        self.session = get_session()

        # Create Flask app in test mode
        self.app = create_app(test_mode=True)
        self.client = self.app.test_client()

        # Create admin user and events
        admin_user = User(username="admin")
        self.session.add(admin_user)
        self.session.flush()
        self.user = admin_user

        # Create test events
        self.event1 = mock_data.get_orm_event(session=self.session)
        self.event2 = mock_data.get_orm_event(session=self.session)
        self.session.commit()

    def tearDown(self):
        """Clean up database"""
        self.session.close()
        dispose_engine()

    def test_notification_checkbox_api_subscribe(self):
        """Test that checkbox can subscribe to notifications via API"""
        # Verify no notification exists
        self.assertEqual(
            self.session.query(Notification)
            .filter_by(user_id=self.user.id, event_id=self.event1.id)
            .count(),
            0,
        )

        # Subscribe via API
        response = self.client.post(
            f"/api/events/{self.event1.id}/notifications/subscribe"
        )

        self.assertEqual(response.status_code, 200)

        # Verify notification was created
        notification = (
            self.session.query(Notification)
            .filter_by(user_id=self.user.id, event_id=self.event1.id)
            .first()
        )
        self.assertIsNotNone(notification)

    def test_notification_checkbox_api_unsubscribe(self):
        """Test that checkbox can unsubscribe from notifications via API"""
        # Create a notification
        mock_data.get_orm_notification(
            session=self.session, user=self.user, event=self.event1
        )
        self.session.commit()

        # Unsubscribe via API
        response = self.client.delete(f"/api/events/{self.event1.id}/notifications")

        self.assertEqual(response.status_code, 200)

        # Verify notification was deleted
        self.assertEqual(
            self.session.query(Notification)
            .filter_by(user_id=self.user.id, event_id=self.event1.id)
            .count(),
            0,
        )
