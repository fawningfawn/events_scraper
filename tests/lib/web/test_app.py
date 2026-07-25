"""Tests for Flask web application"""

import unittest
from datetime import date
from datetime import timedelta
from unittest.mock import MagicMock
from unittest.mock import patch

from flask import url_for

import events_scraper.lib.web.app as web_app
from events_scraper.lib import mock_data
from events_scraper.lib.core.orm_session import get_session
from events_scraper.lib.web.app import create_app
from tests.lib.core.test_base import DatabaseTestCase


class FlaskAppTestCase(DatabaseTestCase):
    """Test Flask app creation and basic routes"""

    def setUp(self):
        """Set up test environment with clean database"""
        super().setUp()

    def test_app_creation(self):
        """Test that Flask app can be created"""

        app = create_app(test_mode=True)
        self.assertIsNotNone(app)
        self.assertEqual(app.config["TESTING"], True)

    def test_index_route_exists(self):
        """Test that index route exists and redirects to /events/"""

        app = create_app(test_mode=True)
        with app.test_client() as client:
            response = client.get("/")
            self.assertEqual(response.status_code, 302)
            self.assertIn("/events/", response.location)

    def test_index_route_redirects_to_events(self):
        """Test that index route redirects to /events/"""

        app = create_app(test_mode=True)
        with app.test_client() as client:
            response = client.get("/", follow_redirects=False)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.location, "/events/")

    def test_app_has_correct_template_folder(self):
        """Test that Flask app is configured with correct template folder"""

        app = create_app(test_mode=True)
        self.assertTrue(app.template_folder.endswith("templates"))

    def test_app_has_correct_static_folder(self):
        """Test that Flask app is configured with correct static folder"""

        app = create_app(test_mode=True)
        self.assertTrue(app.static_folder.endswith("static"))

    def test_dead_event_loader_helpers_removed(self):
        """`events` page should not rely on legacy server-side DB loader helpers."""
        self.assertFalse(hasattr(web_app, "_load_events_for_view"))
        self.assertFalse(hasattr(web_app, "_load_scraper_view"))
        self.assertFalse(hasattr(web_app, "_load_date_view"))
        self.assertFalse(hasattr(web_app, "_load_conference_view"))


class StatusPageTestCase(DatabaseTestCase):
    """Test status page functionality"""

    def setUp(self):
        """Set up test environment with clean database"""
        super().setUp()

    def test_status_route_exists(self):
        """Test that status route exists and returns 200"""
        app = create_app(test_mode=True)
        with app.test_client() as client:
            response = client.get("/status")
            self.assertEqual(response.status_code, 200)

    def test_status_route_content_type(self):
        """Test that status route returns HTML content"""
        app = create_app(test_mode=True)
        with app.test_client() as client:
            response = client.get("/status")
            self.assertIn("text/html", response.content_type)

    @patch("events_scraper.lib.web.app.get_session")
    def test_status_route_renders_template(self, mock_get_session):
        """Test that status route renders template with correct data"""
        # Mock database session
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session

        # Mock query results
        mock_session.query.return_value.group_by.return_value.order_by.return_value.all.return_value = [
            ("scraper1", 10),
            ("scraper2", 5),
        ]
        mock_session.query.return_value.scalar.return_value = 15

        app = create_app(test_mode=True)
        with app.test_client() as client:
            response = client.get("/status")
            self.assertEqual(response.status_code, 200)

            # Verify session was used correctly
            mock_session.query.assert_called()
            mock_session.close.assert_called()

    @patch("events_scraper.lib.web.app.get_session")
    @patch("events_scraper.lib.web.app._get_available_scrapers")
    def test_status_route_handles_empty_database(
        self, mock_get_available, mock_get_session
    ):
        """Test that status route handles empty database gracefully"""
        mock_session = MagicMock()
        mock_get_session.return_value = mock_session
        mock_session.query.return_value.group_by.return_value.order_by.return_value.all.return_value = (
            []
        )
        mock_session.query.return_value.scalar.return_value = 0

        mock_get_available.return_value = set()

        app = create_app(test_mode=True)
        with app.test_client() as client:
            response = client.get("/status")
            self.assertEqual(response.status_code, 200)
            # Should not raise any errors with empty data

    def test_status_route_handles_scraper_loading_errors(self):
        """Test that status route handles database errors gracefully"""
        app = create_app(test_mode=True)
        with app.test_client() as client:
            response = client.get("/status")
            self.assertEqual(response.status_code, 200)
            # Should not crash with empty database


class ScraperDetailRouteTestCase(DatabaseTestCase):
    """Test /status/scraper/<scraper_name> route with mock packages (Phase 1)"""

    def setUp(self):
        super().setUp()
        self.pkg = mock_data.get_package("testgroup", ["testgroup.s1"])

    def _mock_load_packages(self, fn):
        def wrapper(*args, **kwargs):
            return [self.pkg]

        return wrapper

    @patch("events_scraper.lib.scraper_meta.load_packages")
    @patch("events_scraper.lib.packages.load_packages")
    def test_scraper_detail_route_returns_200(self, mock_pkg_lp, mock_meta_lp):
        """GET /status/scraper/<name> returns 200 for existing scraper"""
        mock_pkg_lp.return_value = [self.pkg]
        mock_meta_lp.return_value = [self.pkg]
        app = create_app(test_mode=True)
        with app.test_client() as client:
            response = client.get("/status/scraper/testgroup.s1")
            self.assertEqual(response.status_code, 200)

    @patch("events_scraper.lib.scraper_meta.load_packages")
    @patch("events_scraper.lib.packages.load_packages")
    def test_scraper_detail_renders_scraper_detail_template(
        self, mock_pkg_lp, mock_meta_lp
    ):
        """scraper_detail.html is rendered with scraper name"""
        mock_pkg_lp.return_value = [self.pkg]
        mock_meta_lp.return_value = [self.pkg]
        app = create_app(test_mode=True)
        with app.test_client() as client:
            response = client.get("/status/scraper/testgroup.s1")
            html_content = response.data.decode("utf-8")
            self.assertIn("testgroup.s1", html_content.lower())

    @patch("events_scraper.lib.scraper_meta.load_packages")
    @patch("events_scraper.lib.packages.load_packages")
    def test_scraper_detail_contains_status_table_years(self, mock_pkg_lp, mock_meta_lp):
        """Status table contains year columns"""
        mock_pkg_lp.return_value = [self.pkg]
        mock_meta_lp.return_value = [self.pkg]
        current_year = date.today().year
        next_year = current_year + 1
        app = create_app(test_mode=True)
        with app.test_client() as client:
            response = client.get("/status/scraper/testgroup.s1")
            html_content = response.data.decode("utf-8")
            self.assertIn(str(current_year), html_content)
            self.assertIn(str(next_year), html_content)

    @patch("events_scraper.lib.scraper_meta.load_packages")
    @patch("events_scraper.lib.packages.load_packages")
    def test_scraper_detail_does_not_contain_filter_toggles(
        self, mock_pkg_lp, mock_meta_lp
    ):
        """Scraper detail page should show all rows without list-page filter toggles."""
        mock_pkg_lp.return_value = [self.pkg]
        mock_meta_lp.return_value = [self.pkg]
        app = create_app(test_mode=True)
        with app.test_client() as client:
            response = client.get("/status/scraper/testgroup.s1")
            html_content = response.data.decode("utf-8")
            self.assertNotIn("Only errors", html_content)
            self.assertNotIn("Only 0 events", html_content)


class ScrapersIndexTestCase(DatabaseTestCase):
    """Test /status/scrapers index page (Phase 2)"""

    def test_scrapers_index_route_returns_200(self):
        """GET /status/scrapers returns 200"""
        app = create_app(test_mode=True)
        with (
            patch("events_scraper.lib.scraper_meta.load_packages") as mock_meta,
            patch("events_scraper.lib.packages.load_packages") as mock_pkg,
        ):
            pkg = mock_data.get_package("test", ["test.s1"])
            mock_meta.return_value = [pkg]
            mock_pkg.return_value = [pkg]
            with app.test_client() as client:
                response = client.get("/status/scrapers")
                self.assertEqual(response.status_code, 200)

    def test_scrapers_index_contains_scraper_links(self):
        """/status/scrapers contains links to scrapers"""
        app = create_app(test_mode=True)
        with (
            patch("events_scraper.lib.scraper_meta.load_packages") as mock_meta,
            patch("events_scraper.lib.packages.load_packages") as mock_pkg,
        ):
            pkg = mock_data.get_package("test", ["test.s1"])
            mock_meta.return_value = [pkg]
            mock_pkg.return_value = [pkg]
            with app.test_client() as client:
                response = client.get("/status/scrapers")
                html_content = response.data.decode("utf-8")
                self.assertIn("/status/scraper/", html_content)

    def test_old_conferences_route_returns_404(self):
        """Old /status/conferences route returns 404"""
        app = create_app(test_mode=True)
        with app.test_client() as client:
            response = client.get("/status/conferences")
            self.assertEqual(response.status_code, 404)


class EventDetailAPIContractTestCase(DatabaseTestCase):
    """Test /api/event/<id> returns stable JSON contract."""

    def test_event_detail_api_contract_fields(self):
        """`/api/event/<id>` should return stable JSON fields."""
        session = get_session()
        try:
            orm_event = mock_data.get_orm_event(
                session=session,
                title="API Contract Event",
                date=mock_data.get_date().strftime("%Y-%m-%d"),
                time="20:00",
                location="Contract Venue",
                detail_url="https://example.com/contract-event",
                scraper="contract.scraper",
            )
            session.commit()
            event_id = orm_event.id
        finally:
            session.close()

        app = create_app(test_mode=True)
        with app.test_client() as client:
            with app.test_request_context():
                url = url_for("event_detail_route", event_id=event_id)
            response = client.get(url)

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["id"], event_id)
        self.assertEqual(payload["title"], "API Contract Event")
        self.assertIn("date", payload)
        self.assertIn("time", payload)
        self.assertIn("location", payload)
        self.assertIn("detail_url", payload)


class ScraperViewWithDateFilterTestCase(DatabaseTestCase):
    """Test scraper view with date filtering"""

    def setUp(self):
        """Set up test environment with multi-date test data"""
        super().setUp()

        session = get_session()
        try:
            # Create events on different dates for same scraper
            date1 = mock_data.get_date(min_age=0, max_age=0, future=False)  # today
            date2 = date1 + timedelta(days=5)  # 5 days in future
            date3 = date1 + timedelta(days=10)  # 10 days in future

            scraper_name = "paris.operadeparis"

            # Event on date1
            mock_data.get_orm_event(
                session=session,
                scraper=scraper_name,
                date=date1.strftime("%Y-%m-%d"),
                title="Event on date1",
            )
            # Event on date2
            mock_data.get_orm_event(
                session=session,
                scraper=scraper_name,
                date=date2.strftime("%Y-%m-%d"),
                title="Event on date2",
            )
            # Event on date3
            mock_data.get_orm_event(
                session=session,
                scraper=scraper_name,
                date=date3.strftime("%Y-%m-%d"),
                title="Event on date3",
            )
            session.commit()
            self.scraper_name = scraper_name
            self.date1 = date1
            self.date2 = date2
            self.date3 = date3
        finally:
            session.close()

    def test_scraper_view_with_specific_date_returns_only_that_date(self):
        """Test that /events?scraper=X&date=Y returns only events on that date, not all events for scraper"""
        app = create_app(test_mode=True)
        with app.test_client() as client:
            with app.test_request_context():
                # Request events for scraper on date2 specifically
                url = url_for(
                    "list_all_events",
                    group="paris",
                    scraper=self.scraper_name,
                    date=self.date2.strftime("%Y-%m-%d"),
                    hide_past="off",
                )
            response = client.get(url)
            self.assertEqual(response.status_code, 200)
            data = response.get_json()

            # Should only return 1 event (date2), not all 3
            self.assertEqual(
                len(data["events"]),
                1,
                f"Expected 1 event on {self.date2}, got {len(data['events'])} events",
            )
            # Verify it's the correct event (check title in HTML)
            html_content = data["events"][0]
            self.assertIn("Event on date2", html_content)


class ScraperRescrapeAPITestCase(DatabaseTestCase):
    """Test /api/scraper/<scraper_name>/rescrape endpoint (Phase 4)"""

    def test_rescrape_api_invalid_scraper_returns_404(self):
        """POST /api/scraper/nonexistent/rescrape returns 404"""
        app = create_app(test_mode=True)
        with app.test_client() as client:
            response = client.post(
                "/api/scraper/nonexistent/rescrape?year=2025", json={}
            )
            self.assertEqual(response.status_code, 404)

    def test_rescrape_api_dotted_scraper_name_is_accepted(self):
        """POST /api/scraper/group.scraper/rescrape no longer rejects dotted names."""
        app = create_app(test_mode=True)
        with app.test_client() as client:
            response = client.post("/api/scraper/paris.alteoper/rescrape", json={})
            self.assertNotEqual(response.status_code, 400)


class EventCancelledAPITestCase(DatabaseTestCase):
    def test_cancel_toggle_endpoint(self):
        session = get_session()
        try:
            event = mock_data.get_orm_event(
                session=session,
                title="Toggle Test Event",
                date=mock_data.get_date().strftime("%Y-%m-%d"),
                cancelled=False,
            )
            session.commit()
            event_id = event.id
        finally:
            session.close()

        app = create_app(test_mode=True)
        with app.test_client() as client:
            with app.test_request_context():
                url = url_for("event_cancel_route", event_id=event_id)
            response = client.post(url)
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertEqual(data["status"], "success")
            self.assertTrue(data["cancelled"])

            response = client.post(url)
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertEqual(data["status"], "success")
            self.assertFalse(data["cancelled"])

    def test_cancel_toggle_404_for_nonexistent(self):
        app = create_app(test_mode=True)
        with app.test_client() as client:
            with app.test_request_context():
                url = url_for("event_cancel_route", event_id=99999)
            response = client.post(url)
            self.assertEqual(response.status_code, 404)

    def test_event_detail_includes_cancelled_field(self):
        session = get_session()
        try:
            event = mock_data.get_orm_event(
                session=session,
                title="Detail Cancelled Test",
                date=mock_data.get_date().strftime("%Y-%m-%d"),
                cancelled=True,
            )
            session.commit()
            event_id = event.id
        finally:
            session.close()

        app = create_app(test_mode=True)
        with app.test_client() as client:
            with app.test_request_context():
                url = url_for("event_detail_route", event_id=event_id)
            response = client.get(url)
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertIn("cancelled", data)
            self.assertTrue(data["cancelled"])

    @patch("events_scraper.lib.web.api.feeds.load_group_meta")
    def test_ics_city_feed_excludes_cancelled(self, mock_load_group_meta):
        from events_scraper.lib.packages import GroupMeta

        mock_load_group_meta.return_value = [
            GroupMeta(group="paris", display_name="Paris", source="python", weight=10),
        ]

        session = get_session()
        try:
            city = "paris"
            mock_data.get_orm_event(
                session=session,
                scraper=f"{city}.testscraper",
                title="Active ICS Event",
                date=date.today().strftime("%Y-%m-%d"),
                cancelled=False,
            )
            mock_data.get_orm_event(
                session=session,
                scraper=f"{city}.testscraper",
                title="Cancelled ICS Event",
                date=date.today().strftime("%Y-%m-%d"),
                cancelled=True,
            )
            session.commit()
        finally:
            session.close()

        app = create_app(test_mode=True)
        with app.test_client() as client:
            with app.test_request_context():
                url = url_for("feeds_group_ics", group=city)
            response = client.get(url)
            self.assertEqual(response.status_code, 200)
            ics_text = response.data.decode("utf-8")
            self.assertIn("Active ICS Event", ics_text)
            self.assertNotIn("Cancelled ICS Event", ics_text)


if __name__ == "__main__":
    unittest.main()
