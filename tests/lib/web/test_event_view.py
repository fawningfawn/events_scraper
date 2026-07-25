"""Tests for web event presentation helpers."""

import unittest
from datetime import datetime

from events_scraper.lib import mock_data
from events_scraper.lib.web.event_view import build_event_view_dict


class TestEventView(unittest.TestCase):
    """Contract tests for ORM event -> web view payload mapping."""

    def test_build_event_view_dict_normalizes_fields_for_templates(self):
        event = mock_data.get_event(
            id=123,
            title="Event View Test",
            date="2026-03-22",
            time="09:30:00",
            location="Venue",
            detail_url="https://example.com/e",
            scraper="test.scraper",
        )
        event.categories = "Music, Culture"

        payload = build_event_view_dict(
            event=event,
            now=datetime(2026, 3, 22, 10, 0, 0),
            reference_date_str="2026-03-22",
        )

        self.assertEqual(payload["id"], 123)
        self.assertEqual(payload["api_url"], "/api/event/123")
        self.assertEqual(payload["date_str"], "2026-03-22")
        self.assertEqual(payload["formatted_time"], "09:30")
        self.assertEqual(payload["venue"], "Venue")
        self.assertEqual(payload["categories"], ["Music", "Culture"])
