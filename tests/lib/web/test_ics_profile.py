"""Tests for ICS feed URLs on user profile page"""

from flask import url_for

from events_scraper.lib import mock_data
from events_scraper.lib.core.orm_session import get_session
from events_scraper.lib.web.app import create_app
from tests.lib.core.test_base import DatabaseTestCase


class IcsProfilePageTestCase(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        session = get_session()
        try:
            user = mock_data.get_orm_user(session=session, username="admin")
            session.commit()
            self.user_id = user.id
        finally:
            session.close()

    def test_profile_shows_feed_url(self):
        app = create_app(test_mode=True)
        with app.test_request_context():
            feed_url = url_for("user_events_feed", user_id=self.user_id)
            profile_url = url_for("user_profile_route")
        with app.test_client() as client:
            resp = client.get(profile_url)
            self.assertEqual(resp.status_code, 200)
            self.assertIn(feed_url.encode(), resp.data)
