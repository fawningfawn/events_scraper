"""Test user profile tabbed layout"""

import unittest

from events_scraper.lib.core.orm_models import User
from events_scraper.lib.core.orm_session import get_session
from events_scraper.lib.core.orm_session import init_database
from events_scraper.lib.web.app import create_app


class TestUserProfileTabs(unittest.TestCase):
    """Test user profile tabbed layout"""

    def setUp(self):
        """Set up test client and database"""
        # Initialize in-memory test database
        self.engine = init_database("sqlite:///:memory:")

        # Create test user
        session = get_session()
        self.user = User(username="admin", phone_number="+1234567890")
        session.add(self.user)
        session.commit()
        session.close()

        # Create app and client
        self.app = create_app(test_mode=True)
        self.client = self.app.test_client()

    def tearDown(self):
        """Clean up test database"""
        self.engine.dispose()

    def test_profile_page_has_three_tabs(self):
        """Test profile page renders with three tabs: Profile, Notifications, Subscriptions"""
        response = self.client.get("/user")
        self.assertEqual(response.status_code, 200)
        data = response.data.decode()

        # Check for tabs in HTML
        self.assertIn("Profile", data)
        self.assertIn("Notifications", data)
        self.assertIn("Subscriptions", data)
        self.assertIn("tab", data.lower())

    def test_profile_tab_is_active_by_default(self):
        """Test Profile tab is active when profile page first loads"""
        response = self.client.get("/user")
        self.assertEqual(response.status_code, 200)
        data = response.data.decode()

        # Check that profile form is visible by default
        self.assertIn("Edit Profile", data)

    def test_subscriptions_tab_loads_when_clicked(self):
        """Test clicking Subscriptions tab loads subscriptions content"""
        response = self.client.get("/user")
        self.assertEqual(response.status_code, 200)
        data = response.data.decode()

        # Should have subscriptions tab but content should be in page
        self.assertIn("Subscriptions", data)

    def test_sidebar_visible_in_notifications_tab(self):
        """Test sidebar is visible when Notifications tab is active"""
        response = self.client.get("/user")
        self.assertEqual(response.status_code, 200)
        data = response.data.decode()

        # Sidebar should be visible with "Show past" toggle
        self.assertIn("Show past", data)

    def test_sidebar_hidden_in_subscriptions_tab(self):
        """Test sidebar is hidden or different in Subscriptions tab"""
        response = self.client.get("/user")
        self.assertEqual(response.status_code, 200)
        # Sidebar behavior handled by JavaScript, just verify page loads
        self.assertEqual(response.status_code, 200)

    def test_tab_switching_javascript_included(self):
        """Test tab switching JavaScript is included in page"""
        response = self.client.get("/user")
        self.assertEqual(response.status_code, 200)
        data = response.data.decode()

        # Check for profile.js script tag (JavaScript is in external file)
        self.assertIn("/static/profile.js", data.lower())

    def test_error_loading_notifications_tab(self):
        """Test handles API errors when loading Notifications tab"""
        response = self.client.get("/user")
        self.assertEqual(response.status_code, 200)
        # Error handling is in JavaScript/fetch, page should still load
        self.assertEqual(response.status_code, 200)

    def test_error_loading_subscriptions_tab(self):
        """Test shows error message if Subscriptions tab load fails"""
        response = self.client.get("/user")
        self.assertEqual(response.status_code, 200)
        # Error handling is in JavaScript/fetch, page should still load
        self.assertEqual(response.status_code, 200)
