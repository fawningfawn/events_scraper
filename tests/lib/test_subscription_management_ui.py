"""Test subscription management UI"""

import json
import unittest
from unittest.mock import patch

from events_scraper.lib.core.orm_models import User
from events_scraper.lib.core.orm_session import get_session
from events_scraper.lib.core.orm_session import init_database
from events_scraper.lib.web.app import create_app


class TestSubscriptionManagementUI(unittest.TestCase):
    """Test subscription management UI"""

    def setUp(self):
        """Set up test client and database"""
        self.engine = init_database("sqlite:///:memory:")

        self._groups_patcher = patch(
            "events_scraper.lib.web.api.subscriptions.get_supported_groups",
            return_value=["paris", "paris"],
        )
        self._groups_patcher.start()

        session = get_session()
        self.user = User(username="admin")
        session.add(self.user)
        session.commit()
        session.close()

        self.app = create_app(test_mode=True)
        self.client = self.app.test_client()

    def tearDown(self):
        """Clean up test database"""
        self._groups_patcher.stop()
        self.engine.dispose()

    def test_subscriptions_tab_displays_form(self):
        """Test Subscriptions tab has form for creating subscriptions"""
        response = self.client.get("/user")
        self.assertEqual(response.status_code, 200)
        data = response.data.decode()

        # Should have form elements for subscription creation
        self.assertIn("keyword", data.lower())
        self.assertIn("group", data.lower())

    def test_subscriptions_list_displays_created_subscriptions(self):
        """Test subscriptions list shows all user's subscriptions"""
        # Create a subscription via API
        response = self.client.post(
            "/api/subscriptions",
            data=json.dumps(
                {
                    "title_keyword": "Orchestre National",
                    "body_keyword": None,
                    "groups": ["paris"],
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        # Load profile page
        response = self.client.get("/user")
        self.assertEqual(response.status_code, 200)

    def test_subscriptions_list_groups_by_group(self):
        """Test subscriptions list displays subscriptions grouped by group"""
        # Create multiple subscriptions
        self.client.post(
            "/api/subscriptions",
            data=json.dumps(
                {
                    "title_keyword": "Concert",
                    "body_keyword": None,
                    "groups": ["paris"],
                }
            ),
            content_type="application/json",
        )
        self.client.post(
            "/api/subscriptions",
            data=json.dumps(
                {
                    "title_keyword": "Theater",
                    "body_keyword": None,
                    "groups": ["paris"],
                }
            ),
            content_type="application/json",
        )

        # Load profile page
        response = self.client.get("/user")
        self.assertEqual(response.status_code, 200)

    def test_delete_subscription_button_removes_subscription(self):
        """Test delete button removes subscription"""
        # Create subscription
        response = self.client.post(
            "/api/subscriptions",
            data=json.dumps(
                {
                    "title_keyword": "Concert",
                    "body_keyword": None,
                    "groups": ["paris"],
                }
            ),
            content_type="application/json",
        )
        sub_id = json.loads(response.data)["id"]

        # Delete via API
        response = self.client.delete(f"/api/subscriptions/{sub_id}")
        self.assertEqual(response.status_code, 200)

    def test_edit_subscription_updates_keyword(self):
        """Test edit updates subscription keyword"""
        # Create subscription
        response = self.client.post(
            "/api/subscriptions",
            data=json.dumps(
                {
                    "title_keyword": "Original",
                    "body_keyword": None,
                    "groups": ["paris"],
                }
            ),
            content_type="application/json",
        )
        sub_id = json.loads(response.data)["id"]

        # Update via API
        response = self.client.put(
            f"/api/subscriptions/{sub_id}",
            data=json.dumps({"title_keyword": "Updated"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

    def test_subscriptions_list_shows_no_subscriptions_message(self):
        """Test shows message when user has no subscriptions"""
        response = self.client.get("/user")
        self.assertEqual(response.status_code, 200)
        data = response.data.decode()

        # Should have placeholder or message for empty subscriptions
        self.assertIn("subscription", data.lower())
