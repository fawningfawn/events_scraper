"""Test Event Subscriptions API endpoints"""

import json
import unittest
from datetime import date
from datetime import timedelta
from unittest.mock import patch

from events_scraper.lib.core.orm_models import Event
from events_scraper.lib.core.orm_models import EventSubscription
from events_scraper.lib.core.orm_models import Notification
from events_scraper.lib.core.orm_models import User
from events_scraper.lib.core.orm_session import get_session
from events_scraper.lib.core.orm_session import init_database
from events_scraper.lib.web.app import create_app


class TestSubscriptionsAPI(unittest.TestCase):
    """Test subscriptions API endpoints"""

    def setUp(self):
        """Set up test client and database"""
        self.engine = init_database("sqlite:///:memory:")

        self._groups_patcher = patch(
            "events_scraper.lib.web.api.subscriptions.get_supported_groups",
            return_value=["paris", "paris"],
        )
        self._groups_patcher.start()

        # Create test user
        session = get_session()
        user = User(username="admin")
        session.add(user)
        session.commit()
        session.close()

        # Create app and client
        self.app = create_app(test_mode=True)
        self.client = self.app.test_client()

    def tearDown(self):
        """Clean up test database"""
        self._groups_patcher.stop()
        self.engine.dispose()

    def test_get_subscriptions_returns_empty_list_for_new_user(self):
        """Test GET /api/subscriptions returns empty list when user has no subscriptions"""
        response = self.client.get("/api/subscriptions")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data["subscriptions"], [])

    def test_post_subscription_creates_subscription(self):
        """Test POST /api/subscriptions creates subscription and returns id"""
        payload = {
            "title_keyword": "Orchestre National",
            "body_keyword": None,
            "groups": ["paris"],
        }
        response = self.client.post(
            "/api/subscriptions",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn("id", data)
        self.assertIsNotNone(data["id"])

    def test_post_subscription_rejects_empty_keyword(self):
        """Test POST /api/subscriptions rejects empty keyword with error message"""
        payload = {
            "title_keyword": None,
            "body_keyword": None,
            "groups": ["paris"],
        }
        response = self.client.post(
            "/api/subscriptions",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn("error", data)

    def test_post_subscription_rejects_invalid_group(self):
        """Test POST /api/subscriptions rejects invalid group"""
        payload = {
            "title_keyword": "Orchestre National",
            "body_keyword": None,
            "groups": ["nonexistent_group"],
        }
        response = self.client.post(
            "/api/subscriptions",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn("error", data)

    def test_get_subscriptions_returns_created_subscriptions(self):
        """Test GET /api/subscriptions returns user's subscriptions"""
        # Create a subscription
        create_payload = {
            "title_keyword": "Orchestre National",
            "body_keyword": None,
            "groups": ["paris"],
        }
        create_response = self.client.post(
            "/api/subscriptions",
            data=json.dumps(create_payload),
            content_type="application/json",
        )
        self.assertEqual(create_response.status_code, 200)

        # Get subscriptions
        get_response = self.client.get("/api/subscriptions")
        self.assertEqual(get_response.status_code, 200)
        data = json.loads(get_response.data)
        self.assertGreater(len(data["subscriptions"]), 0)

    def test_put_subscription_updates_subscription(self):
        """Test PUT /api/subscriptions/{id} updates subscription"""
        # Create subscription
        create_payload = {
            "title_keyword": "Original",
            "body_keyword": None,
            "groups": ["paris"],
        }
        create_response = self.client.post(
            "/api/subscriptions",
            data=json.dumps(create_payload),
            content_type="application/json",
        )
        sub_id = json.loads(create_response.data)["id"]

        # Update subscription
        update_payload = {
            "title_keyword": "Updated",
        }
        update_response = self.client.put(
            f"/api/subscriptions/{sub_id}",
            data=json.dumps(update_payload),
            content_type="application/json",
        )
        self.assertEqual(update_response.status_code, 200)

        # Verify updated
        get_response = self.client.get("/api/subscriptions")
        data = json.loads(get_response.data)
        subscription = next(
            (s for s in data["subscriptions"] if s["id"] == sub_id), None
        )
        self.assertIsNotNone(subscription)

    def test_put_subscription_returns_404_for_nonexistent(self):
        """Test PUT /api/subscriptions/{id} returns 404 if subscription doesn't exist"""
        update_payload = {"title_keyword": "Updated"}
        response = self.client.put(
            "/api/subscriptions/99999",
            data=json.dumps(update_payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)

    def test_put_subscription_rejects_empty_keyword(self):
        """Test PUT /api/subscriptions/{id} rejects empty keyword"""
        # Create subscription
        create_payload = {
            "title_keyword": "Original",
            "body_keyword": None,
            "groups": ["paris"],
        }
        create_response = self.client.post(
            "/api/subscriptions",
            data=json.dumps(create_payload),
            content_type="application/json",
        )
        sub_id = json.loads(create_response.data)["id"]

        # Try to update with empty keywords
        update_payload = {"title_keyword": None, "body_keyword": None}
        update_response = self.client.put(
            f"/api/subscriptions/{sub_id}",
            data=json.dumps(update_payload),
            content_type="application/json",
        )
        self.assertEqual(update_response.status_code, 400)

    def test_delete_subscription_deletes_subscription(self):
        """Test DELETE /api/subscriptions/{id} deletes subscription"""
        # Create subscription
        create_payload = {
            "title_keyword": "ToDelete",
            "body_keyword": None,
            "groups": ["paris"],
        }
        create_response = self.client.post(
            "/api/subscriptions",
            data=json.dumps(create_payload),
            content_type="application/json",
        )
        sub_id = json.loads(create_response.data)["id"]

        # Delete subscription
        delete_response = self.client.delete(f"/api/subscriptions/{sub_id}")
        self.assertEqual(delete_response.status_code, 200)

        # Verify deleted
        get_response = self.client.get("/api/subscriptions")
        data = json.loads(get_response.data)
        subscription = next(
            (s for s in data["subscriptions"] if s["id"] == sub_id), None
        )
        self.assertIsNone(subscription)

    def test_delete_subscription_returns_404_for_nonexistent(self):
        """Test DELETE /api/subscriptions/{id} returns 404 if subscription doesn't exist"""
        response = self.client.delete("/api/subscriptions/99999")
        self.assertEqual(response.status_code, 404)

    def test_subscription_list_includes_pending_notifications_count(self):
        """Test subscription list API returns pending_notifications count for each subscription"""

        session = get_session()

        # Get the test user
        user = session.query(User).filter_by(username="admin").first()

        # Create a subscription
        subscription = EventSubscription(
            user_id=user.id,
            group="paris",
            status="active",
        )
        session.add(subscription)
        session.commit()

        # Create future event
        today = date.today()
        event = Event(
            title="Kammerorchester Concert",
            date=today + timedelta(days=5),
            detail_url="http://example.com/event1",
            scraper="paris.test_scraper",
        )
        session.add(event)
        session.commit()

        # Create notifications for this subscription
        notification = Notification(
            user_id=user.id,
            event_id=event.id,
            subscription_id=subscription.id,
            notify_delta=259200,  # 3 days
            status="pending",
            plugin="signal",
        )
        notification.send_at = notification.calculate_send_at(event)
        session.add(notification)
        session.commit()

        # Get subscriptions list
        response = self.client.get("/api/subscriptions")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)

        # Verify subscription has pending_notifications count
        self.assertEqual(len(data["subscriptions"]), 1)
        self.assertEqual(data["subscriptions"][0]["id"], subscription.id)
        self.assertEqual(data["subscriptions"][0]["pending_notifications"], 1)

        session.close()
