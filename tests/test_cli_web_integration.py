"""Integration test for CLI detail scraping → web interface pipeline"""

import json
import unittest

from flask import url_for

from events_scraper.lib.core.orm_models import Event as OrmEvent
from events_scraper.lib.core.orm_session import get_session
from events_scraper.lib.mock_data import get_event
from events_scraper.lib.mock_data import get_event_detail
from events_scraper.lib.web.app import create_app
from tests.lib.core.test_base import DatabaseTestCase


class CLIWebIntegrationTest(DatabaseTestCase):
    """Test the full pipeline: CLI scraping → database → web interface"""

    def test_cli_scraped_details_available_in_web_interface(self):
        """Test that details scraped by CLI are accessible via web interface"""

        # Create test event and detail
        test_event = get_event(
            title="Test Event", detail_url="https://example.com/test-event"
        )

        # Save event to database (simulating CLI behavior)
        test_event.save()

        test_detail = get_event_detail(
            url="https://example.com/test-event",
            content="This is detailed content from CLI scraping",
        )
        test_detail.save()

        session = get_session()
        saved_event = (
            session.query(OrmEvent).filter(OrmEvent.title == "Test Event").first()
        )
        event_id = saved_event.id
        session.close()

        # Create web app
        app = create_app(test_mode=True)

        with app.test_client() as client:
            with app.test_request_context():
                detail_url = url_for("event_detail_route", event_id=event_id)
            # Request event details via web API using event ID
            response = client.get(detail_url)

            # Should return 200 OK
            self.assertEqual(response.status_code, 200)

            # Parse response
            data = json.loads(response.data)

            # Should include the description from CLI-scraped details
            self.assertIn("description", data)
            self.assertEqual(
                data["description"], "This is detailed content from CLI scraping"
            )
            self.assertEqual(data["title"], "Test Event")

    def test_web_interface_handles_missing_details_gracefully(self):
        """Test that web interface handles events without scraped details"""

        # Create test event without details
        test_event = get_event(
            title="Event Without Details", detail_url="https://example.com/no-details"
        )

        # Save only the event (no details)
        test_event.save()

        session = get_session()
        saved_event = (
            session.query(OrmEvent)
            .filter(OrmEvent.title == "Event Without Details")
            .first()
        )
        event_id = saved_event.id
        session.close()

        # Create web app
        app = create_app(test_mode=True)

        with app.test_client() as client:
            with app.test_request_context():
                detail_url = url_for("event_detail_route", event_id=event_id)
            # Request event details via web API using event ID
            response = client.get(detail_url)

            # Should return 200 OK
            self.assertEqual(response.status_code, 200)

            # Parse response
            data = json.loads(response.data)

            # Should include description field but null (not 404)
            self.assertIn("description", data)
            self.assertIsNone(data["description"])
            self.assertEqual(data["title"], "Event Without Details")


if __name__ == "__main__":
    unittest.main()
