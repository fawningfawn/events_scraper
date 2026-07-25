"""Tests for ICS feed endpoints"""

from datetime import date
from datetime import timedelta

from flask import url_for
from icalendar import Calendar

from events_scraper.lib import mock_data
from events_scraper.lib.core.orm_session import get_session
from events_scraper.lib.web.app import create_app
from tests.lib.core.test_base import DatabaseTestCase


def _feed_url(app, user_id, group=None):
    with app.test_request_context():
        return url_for("user_events_feed", user_id=user_id, group=group)


class IcsFeedRoutesTestCase(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.session = get_session()
        self.user = mock_data.get_orm_user(session=self.session, username="feeduser")
        self.session.commit()

    def test_events_feed_returns_ics_content_type(self):
        app = create_app(test_mode=True)
        url = _feed_url(app, self.user.id)
        with app.test_client() as client:
            resp = client.get(url)
            self.assertEqual(resp.status_code, 200)
            self.assertIn("text/calendar", resp.content_type)

    def test_unknown_user_returns_404(self):
        app = create_app(test_mode=True)
        url = _feed_url(app, 99999)
        with app.test_client() as client:
            resp = client.get(url)
            self.assertEqual(resp.status_code, 404)

    def test_events_feed_returns_valid_vcalendar(self):
        app = create_app(test_mode=True)
        url = _feed_url(app, self.user.id)
        with app.test_client() as client:
            resp = client.get(url)
            cal = Calendar.from_ical(resp.data)
            self.assertEqual(cal["VERSION"], "2.0")

    def test_empty_feed_when_no_notifications(self):
        app = create_app(test_mode=True)
        url = _feed_url(app, self.user.id)
        with app.test_client() as client:
            resp = client.get(url)
            cal = Calendar.from_ical(resp.data)
            vevents = [c for c in cal.walk() if c.name == "VEVENT"]
            self.assertEqual(len(vevents), 0)


class IcsFeedMatchingTestCase(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.session = get_session()
        self.user = mock_data.get_orm_user(session=self.session, username="matchuser")
        self.session.commit()
        self.future_date = date.today() + timedelta(days=30)
        self.past_date = date.today() - timedelta(days=30)

    def _subscribe_to_event(self, event):
        return mock_data.get_orm_notification(
            session=self.session, user=self.user, event=event
        )

    def test_events_feed_includes_subscribed_future_events(self):
        event = mock_data.get_orm_event(
            session=self.session,
            title="Jazz Night",
            scraper="paris.venue",
            date=self.future_date,
        )
        self._subscribe_to_event(event)
        self.session.commit()

        app = create_app(test_mode=True)
        url = _feed_url(app, self.user.id)
        with app.test_client() as client:
            resp = client.get(url)
            cal = Calendar.from_ical(resp.data)
            vevents = [c for c in cal.walk() if c.name == "VEVENT"]
            self.assertEqual(len(vevents), 1)
            self.assertEqual(str(vevents[0]["SUMMARY"]), "Jazz Night")

    def test_events_feed_excludes_past_events(self):
        event = mock_data.get_orm_event(
            session=self.session,
            title="Jazz Night",
            scraper="paris.venue",
            date=self.past_date,
        )
        self._subscribe_to_event(event)
        self.session.commit()

        app = create_app(test_mode=True)
        url = _feed_url(app, self.user.id)
        with app.test_client() as client:
            resp = client.get(url)
            cal = Calendar.from_ical(resp.data)
            vevents = [c for c in cal.walk() if c.name == "VEVENT"]
            self.assertEqual(len(vevents), 0)

    def test_events_feed_excludes_unsubscribed_events(self):
        mock_data.get_orm_event(
            session=self.session,
            title="Rock Concert",
            scraper="paris.venue",
            date=self.future_date,
        )
        self.session.commit()

        app = create_app(test_mode=True)
        url = _feed_url(app, self.user.id)
        with app.test_client() as client:
            resp = client.get(url)
            cal = Calendar.from_ical(resp.data)
            vevents = [c for c in cal.walk() if c.name == "VEVENT"]
            self.assertEqual(len(vevents), 0)

    def test_feed_has_etag_header(self):
        app = create_app(test_mode=True)
        url = _feed_url(app, self.user.id)
        with app.test_client() as client:
            resp = client.get(url)
            self.assertIn("ETag", resp.headers)
