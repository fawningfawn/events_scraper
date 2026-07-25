"""Test notification API endpoints"""

import json
import unittest

from events_scraper.lib import mock_data
from events_scraper.lib.core.orm_models import Notification
from events_scraper.lib.core.orm_models import User
from events_scraper.lib.core.orm_session import dispose_engine
from events_scraper.lib.core.orm_session import get_session
from events_scraper.lib.core.orm_session import init_database
from events_scraper.lib.web.app import create_app


class TestNotificationAPI(unittest.TestCase):
    """Test notification API endpoints"""

    def setUp(self):
        """Set up test client and database"""
        # Initialize in-memory SQLite database
        init_database("sqlite:///:memory:")
        self.session = get_session()

        # Create Flask app in test mode
        self.app = create_app(test_mode=True)
        self.client = self.app.test_client()

        # Create admin user (used by endpoints) and event
        admin_user = User(username="admin")
        self.session.add(admin_user)
        self.session.flush()  # Get the ID
        self.user = admin_user

        self.event = mock_data.get_orm_event(session=self.session)
        self.session.commit()

    def tearDown(self):
        """Clean up database"""
        self.session.close()
        dispose_engine()

    def test_subscribe_creates_notification(self):
        """Test POST /api/events/<id>/notifications/subscribe creates notification"""
        # Verify no notification exists yet
        self.assertEqual(
            self.session.query(Notification)
            .filter_by(user_id=self.user.id, event_id=self.event.id)
            .count(),
            0,
        )

        # Subscribe to event notifications
        response = self.client.post(
            f"/api/events/{self.event.id}/notifications/subscribe"
        )

        # Check response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["status"], "subscribed")

        # Verify notification was created
        notification = (
            self.session.query(Notification)
            .filter_by(user_id=self.user.id, event_id=self.event.id)
            .first()
        )
        self.assertIsNotNone(notification)
        self.assertEqual(notification.status, "pending")
        self.assertEqual(notification.plugin, "signal")

    def test_unsubscribe_removes_notification(self):
        """Test DELETE /api/events/<id>/notifications removes notification"""
        # Create a notification first
        mock_data.get_orm_notification(
            session=self.session, user=self.user, event=self.event
        )
        self.session.commit()

        # Verify notification exists
        self.assertEqual(
            self.session.query(Notification)
            .filter_by(user_id=self.user.id, event_id=self.event.id)
            .count(),
            1,
        )

        # Unsubscribe from event notifications
        response = self.client.delete(f"/api/events/{self.event.id}/notifications")

        # Check response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["status"], "unsubscribed")

        # Verify notification was deleted
        self.assertEqual(
            self.session.query(Notification)
            .filter_by(user_id=self.user.id, event_id=self.event.id)
            .count(),
            0,
        )

    def test_get_status_subscribed(self):
        """Test GET /api/events/<id>/notifications/status returns subscribed=true"""
        # Create a notification
        mock_data.get_orm_notification(
            session=self.session, user=self.user, event=self.event
        )
        self.session.commit()

        # Check subscription status
        response = self.client.get(f"/api/events/{self.event.id}/notifications/status")

        # Check response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data["subscribed"])

    def test_get_status_not_subscribed(self):
        """Test GET /api/events/<id>/notifications/status returns subscribed=false"""
        # Verify no notification exists
        self.assertEqual(
            self.session.query(Notification)
            .filter_by(user_id=self.user.id, event_id=self.event.id)
            .count(),
            0,
        )

        # Check subscription status
        response = self.client.get(f"/api/events/{self.event.id}/notifications/status")

        # Check response
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertFalse(data["subscribed"])

    def test_subscribe_returns_400_for_invalid_event(self):
        """Test subscribe returns 400 for non-existent event"""
        response = self.client.post("/api/events/99999/notifications/subscribe")

        self.assertEqual(response.status_code, 400)

    def test_unsubscribe_returns_400_for_invalid_event(self):
        """Test unsubscribe returns 400 for non-existent event"""
        response = self.client.delete("/api/events/99999/notifications")

        self.assertEqual(response.status_code, 400)
