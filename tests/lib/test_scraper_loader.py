"""
Tests for scraper loader functionality (updated for multi-scraper architecture)
"""

import unittest
from datetime import date
from unittest.mock import Mock
from unittest.mock import patch

from events_scraper.lib.core.database import EventCollection
from events_scraper.lib.core.models import Event
from events_scraper.lib.packages import GroupMeta
from events_scraper.lib.scraper_loader import _fetch_from_single_scraper
from events_scraper.lib.scraper_loader import _populate_upstream_ids
from events_scraper.lib.scraper_loader import _save_events_to_database
from events_scraper.lib.scraper_loader import fetch_all_events
from events_scraper.lib.scraper_loader import get_supported_groups


class TestScraperLoader(unittest.TestCase):
    """Test cases for scraper loader functionality"""

    @patch("events_scraper.lib.scraper_loader.load_group_meta")
    def test_get_supported_groups(self, mock_load_group_meta):
        """Test getting list of supported groups"""
        mock_load_group_meta.return_value = [
            GroupMeta(group="paris", display_name="Paris", weight=10),
        ]
        groups = get_supported_groups()
        self.assertGreaterEqual(len(groups), 1)
        # All groups should be strings
        for group in groups:
            self.assertIsInstance(group, str)


class TestFetchAllEvents(unittest.TestCase):
    """Test cases for fetch_all_events function"""

    @patch("events_scraper.lib.scraper_loader.load_scrapers")
    def test_fetch_all_events_single_date(self, mock_load_scrapers):
        """Test fetch_all_events with single date (backward compatibility)"""
        # Mock scraper and events
        mock_scraper = Mock()
        mock_events = Mock()
        # Create mock events with proper time_for_sorting attribute for EventCollection
        mock_event1 = Mock()
        mock_event1.title = "Event 1"
        mock_event1.time_for_sorting = date(2025, 7, 25)
        mock_event2 = Mock()
        mock_event2.title = "Event 2"
        mock_event2.time_for_sorting = date(2025, 7, 25)

        mock_events.to_list.return_value = [mock_event1, mock_event2]
        mock_scraper.fetch.return_value = mock_events
        mock_scraper.__class__.__name__ = "TestScraper"

        mock_load_scrapers.return_value = [mock_scraper]

        # Call with single date
        target_date = date(2025, 7, 25)
        result = fetch_all_events(
            "testcity", target_date=target_date, save_to_database=False
        )

        # Verify behavior
        mock_load_scrapers.assert_called_once_with("testcity", target_date)
        mock_scraper.fetch.assert_called_once()
        self.assertIsInstance(result, EventCollection)
        self.assertEqual(len(result.to_list()), 2)

    @patch("events_scraper.lib.scraper_loader.load_scrapers")
    def test_fetch_all_events_date_range(self, mock_load_scrapers):
        """Test fetch_all_events with date range parameter"""
        # Mock scraper and events
        mock_scraper = Mock()
        mock_events = Mock()

        # Create mock events with proper time_for_sorting attribute
        mock_event1 = Mock()
        mock_event1.title = "Event 1"
        mock_event1.time_for_sorting = date(2025, 7, 25)
        mock_event2 = Mock()
        mock_event2.title = "Event 2"
        mock_event2.time_for_sorting = date(2025, 7, 26)
        mock_event3 = Mock()
        mock_event3.title = "Event 3"
        mock_event3.time_for_sorting = date(2025, 7, 27)

        mock_events.to_list.return_value = [mock_event1, mock_event2, mock_event3]
        mock_scraper.fetch_date_range.return_value = mock_events
        mock_scraper.__class__.__name__ = "TestScraper"

        mock_load_scrapers.return_value = [mock_scraper]

        # Call with date range
        date_range = (date(2025, 7, 25), date(2025, 7, 27))
        result = fetch_all_events(
            "testcity", date_range=date_range, save_to_database=False
        )

        # Verify behavior
        mock_load_scrapers.assert_called_once_with("testcity", date_range[0])
        mock_scraper.fetch_date_range.assert_called_once_with(
            date_range[0], date_range[1]
        )
        self.assertIsInstance(result, EventCollection)
        self.assertEqual(len(result.to_list()), 3)

    @patch("events_scraper.lib.scraper_loader.load_scrapers")
    def test_fetch_all_events_both_parameters_error(self, mock_load_scrapers):
        """Test that providing both target_date and date_range raises error"""
        with self.assertRaises(ValueError) as cm:
            fetch_all_events(
                "testcity",
                target_date=date(2025, 7, 25),
                date_range=(date(2025, 7, 25), date(2025, 7, 27)),
            )

        self.assertIn(
            "Cannot specify both target_date and date_range", str(cm.exception)
        )

    @patch("events_scraper.lib.scraper_loader.load_scrapers")
    def test_fetch_all_events_no_parameters_error(self, mock_load_scrapers):
        """Test that providing neither target_date nor date_range raises error"""
        with self.assertRaises(ValueError) as cm:
            fetch_all_events("testcity")

        self.assertIn("Must specify either target_date or date_range", str(cm.exception))

    @patch("events_scraper.lib.scraper_loader.load_scrapers")
    def test_fetch_all_events_multiple_scrapers_with_range(self, mock_load_scrapers):
        """Test fetch_all_events with multiple scrapers and date range"""
        # Mock two scrapers
        mock_scraper1 = Mock()
        mock_events1 = Mock()

        mock_event1 = Mock()
        mock_event1.title = "Event 1"
        mock_event1.time_for_sorting = date(2025, 7, 25)
        mock_event2 = Mock()
        mock_event2.title = "Event 2"
        mock_event2.time_for_sorting = date(2025, 7, 26)

        mock_events1.to_list.return_value = [mock_event1, mock_event2]
        mock_scraper1.fetch_date_range.return_value = mock_events1
        mock_scraper1.__class__.__name__ = "TestScraper1"

        mock_scraper2 = Mock()
        mock_events2 = Mock()

        mock_event3 = Mock()
        mock_event3.title = "Event 3"
        mock_event3.time_for_sorting = date(2025, 7, 27)

        mock_events2.to_list.return_value = [mock_event3]
        mock_scraper2.fetch_date_range.return_value = mock_events2
        mock_scraper2.__class__.__name__ = "TestScraper2"

        mock_load_scrapers.return_value = [mock_scraper1, mock_scraper2]

        # Call with date range
        date_range = (date(2025, 7, 25), date(2025, 7, 27))
        result = fetch_all_events(
            "testcity", date_range=date_range, save_to_database=False
        )

        # Verify both scrapers were called
        mock_scraper1.fetch_date_range.assert_called_once_with(
            date_range[0], date_range[1]
        )
        mock_scraper2.fetch_date_range.assert_called_once_with(
            date_range[0], date_range[1]
        )

        # Should combine events from both scrapers
        self.assertEqual(len(result.to_list()), 3)

    @patch("events_scraper.lib.scraper_loader.load_scrapers")
    def test_fetch_all_events_scraper_error_continues(self, mock_load_scrapers):
        """Test that scraper errors don't stop other scrapers from running"""
        # Mock two scrapers, first one fails
        mock_scraper1 = Mock()
        mock_scraper1.fetch_date_range.side_effect = Exception("Network error")
        mock_scraper1.__class__.__name__ = "FailingScraper"

        mock_scraper2 = Mock()
        mock_events2 = Mock()

        mock_event1 = Mock()
        mock_event1.title = "Event 1"
        mock_event1.time_for_sorting = date(2025, 7, 25)

        mock_events2.to_list.return_value = [mock_event1]
        mock_scraper2.fetch_date_range.return_value = mock_events2
        mock_scraper2.__class__.__name__ = "WorkingScraper"

        mock_load_scrapers.return_value = [mock_scraper1, mock_scraper2]

        # Call with date range
        date_range = (date(2025, 7, 25), date(2025, 7, 27))
        result = fetch_all_events(
            "testcity", date_range=date_range, save_to_database=False
        )

        # Should still get events from working scraper
        self.assertEqual(len(result.to_list()), 1)
        mock_scraper2.fetch_date_range.assert_called_once()


class TestSaveEventsToDatabase(unittest.TestCase):
    """Unit tests for `_save_events_to_database` behavior."""

    def test_save_uses_event_fields_without_scraper_context(self):
        """Save layer should persist event as-is and keep pre-populated `upstream_id`."""
        event = Mock()
        event.title = "Test Event"
        event.upstream_id = "upstream-123"

        _save_events_to_database([event])

        event.save.assert_called_once()
        self.assertEqual(event.upstream_id, "upstream-123")

    def test_save_does_not_pre_deduplicate_events(self):
        """Save helper must try every event and let DB upsert enforce dedup."""
        event_one = Mock()
        event_one.title = "Duplicate Event"
        event_two = Mock()
        event_two.title = "Duplicate Event"

        _save_events_to_database([event_one, event_two])

        event_one.save.assert_called_once()
        event_two.save.assert_called_once()

    def test_populate_upstream_ids_uses_scraper_extractor(self):
        """Adapter should populate `event.upstream_id` from scraper before save."""
        scraper = Mock()
        scraper.get_upstream_id.return_value = "abc123"
        event = Event(
            title="Test Event",
            date="2026-03-22",
            detail_url="https://example.com/event-abc123",
            scraper="test.scraper",
        )

        _populate_upstream_ids([event], scraper)

        self.assertEqual(event.upstream_id, "abc123")
        scraper.get_upstream_id.assert_called_once_with(event.detail_url)

    def test_fetch_from_single_scraper_populates_upstream_ids_before_save(self):
        """`_fetch_from_single_scraper` should enrich events before save pipeline."""
        scraper = Mock()
        scraper.scraper_name = "test.scraper"
        scraper.get_upstream_id.return_value = "xyz789"
        event = Event(
            title="Test Event",
            date="2026-03-22",
            detail_url="https://example.com/event-xyz789",
            scraper="test.scraper",
        )
        collection = EventCollection([event])
        scraper.fetch.return_value = collection

        result = _fetch_from_single_scraper(
            scraper=scraper,
            target_date=None,
            date_range=None,
            save_to_database=False,
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].upstream_id, "xyz789")

    @patch("events_scraper.lib.scraper_loader._save_events_to_database")
    def test_fetch_from_single_scraper_fetches_details_when_requested(
        self, mock_save_events
    ):
        """`_fetch_from_single_scraper` should fetch detail pages when enabled."""
        scraper = Mock()
        scraper.scraper_name = "test.scraper"
        scraper.fetch_detail_content.return_value = Mock()
        event = Event(
            title="Test Event",
            date="2026-03-22",
            detail_url="https://example.com/detail",
            scraper="test.scraper",
        )
        scraper.fetch.return_value = EventCollection([event])

        result = _fetch_from_single_scraper(
            scraper=scraper,
            target_date=date(2026, 3, 22),
            date_range=None,
            save_to_database=True,
            fetch_details=True,
        )

        self.assertEqual(len(result), 1)
        mock_save_events.assert_called_once()
        scraper.fetch_detail_content.assert_called_once_with(
            "https://example.com/detail"
        )
