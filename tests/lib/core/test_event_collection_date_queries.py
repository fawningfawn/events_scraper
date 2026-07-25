"""
Tests for EventCollection date query methods
"""

import unittest
from datetime import timedelta

from events_scraper.lib import mock_data
from events_scraper.lib.core.database import EventCollection


class TestEventCollectionDateQueries(unittest.TestCase):
    """Test EventCollection date query functionality"""

    def setUp(self):
        """Set up test events"""
        # Use consistent base date for predictable test behavior
        base_date = mock_data.get_date()

        self.events = [
            # Single day events
            mock_data.get_event(date=base_date.strftime("%Y-%m-%d")),
            mock_data.get_event(
                date=(base_date + timedelta(days=1)).strftime("%Y-%m-%d")
            ),
            # Multi-day events
            mock_data.get_event(
                date=base_date.strftime("%Y-%m-%d"),
                end_date=(base_date + timedelta(days=2)).strftime("%Y-%m-%d"),
            ),
            mock_data.get_event(
                date=(base_date + timedelta(days=3)).strftime("%Y-%m-%d"),
                end_date=(base_date + timedelta(days=5)).strftime("%Y-%m-%d"),
            ),
            # Cross-month event
            mock_data.get_event(
                date=(base_date + timedelta(days=5)).strftime("%Y-%m-%d"),
                end_date=(base_date + timedelta(days=8)).strftime("%Y-%m-%d"),
            ),
        ]
        self.collection = EventCollection(self.events)
        self.base_date = base_date

    def test_events_on_date_single_day(self):
        """Test events_on_date for single day events"""
        # Test with date object
        result = self.collection.events_on_date(self.base_date)

        # Should include first single day event (index 0) and first multi-day event (index 2) starting on this date
        self.assertEqual(len(result), 2)
        # Verify we got the right events by checking their dates
        for event in result:
            self.assertTrue(event.contains_date(self.base_date))

    def test_events_on_date_string(self):
        """Test events_on_date with string date"""
        test_date = (self.base_date + timedelta(days=1)).strftime("%Y-%m-%d")
        result = self.collection.events_on_date(test_date)

        # Should include second single day event and first multi-day event containing this date
        self.assertEqual(len(result), 2)
        # Verify we got the right events by checking their dates
        for event in result:
            self.assertTrue(event.contains_date(test_date))

    def test_events_on_date_middle_of_range(self):
        """Test events_on_date for date in middle of multi-day event"""
        # Multi Day 2 runs from base_date+3 to base_date+5, so middle is base_date+4
        middle_date = (self.base_date + timedelta(days=4)).strftime("%Y-%m-%d")
        result = self.collection.events_on_date(middle_date)

        # Should only include the second multi-day event
        self.assertEqual(len(result), 1)
        # Verify we got the right event by checking its date
        self.assertTrue(result[0].contains_date(middle_date))

    def test_events_on_date_cross_month(self):
        """Test events_on_date for cross-month event"""
        # Cross Month runs from base_date+5 to base_date+8, so middle is base_date+6
        cross_date = (self.base_date + timedelta(days=6)).strftime("%Y-%m-%d")
        result = self.collection.events_on_date(cross_date)

        # Should include the cross-month event
        self.assertEqual(len(result), 1)
        # Verify we got the right event by checking its date
        self.assertTrue(result[0].contains_date(cross_date))

    def test_events_on_date_no_matches(self):
        """Test events_on_date with no matching events"""
        # Use date far from our test events
        no_match_date = (self.base_date + timedelta(days=20)).strftime("%Y-%m-%d")
        result = self.collection.events_on_date(no_match_date)
        self.assertEqual(len(result), 0)

    def test_events_on_date_invalid_string(self):
        """Test events_on_date with invalid date string"""
        result = self.collection.events_on_date("invalid-date")
        self.assertEqual(len(result), 0)

    def test_events_overlapping_range_full_overlap(self):
        """Test events_overlapping_range with full overlap"""
        start_date = self.base_date.strftime("%Y-%m-%d")
        end_date = (self.base_date + timedelta(days=2)).strftime("%Y-%m-%d")
        result = self.collection.events_overlapping_range(start_date, end_date)

        # Should include first two single day events and first multi-day event
        self.assertEqual(len(result), 3)
        # Verify all events overlap with the range
        for event in result:
            overlaps = any(
                event.contains_date(self.base_date + timedelta(days=i)) for i in range(3)
            )  # days 0-2
            self.assertTrue(overlaps)

    def test_events_overlapping_range_partial_overlap(self):
        """Test events_overlapping_range with partial overlap"""
        start_date = (self.base_date + timedelta(days=1)).strftime("%Y-%m-%d")
        end_date = (self.base_date + timedelta(days=3)).strftime("%Y-%m-%d")
        result = self.collection.events_overlapping_range(start_date, end_date)

        # Should include events that overlap with this range
        self.assertEqual(len(result), 3)
        # Verify all events have some overlap with the range
        for event in result:
            overlaps = any(
                event.contains_date(self.base_date + timedelta(days=i))
                for i in range(1, 4)
            )  # days 1-3
            self.assertTrue(overlaps)

    def test_events_overlapping_range_cross_month(self):
        """Test events_overlapping_range spanning months"""
        # Test range within the cross-month event (base_date+5 to base_date+8)
        start_date = (self.base_date + timedelta(days=6)).strftime("%Y-%m-%d")
        end_date = (self.base_date + timedelta(days=7)).strftime("%Y-%m-%d")
        result = self.collection.events_overlapping_range(start_date, end_date)

        # Should include cross-month event
        self.assertEqual(len(result), 1)
        # Verify the event contains the dates in our range
        self.assertTrue(result[0].contains_date(self.base_date + timedelta(days=6)))

    def test_events_overlapping_range_no_overlap(self):
        """Test events_overlapping_range with no overlapping events"""
        # Use dates well beyond our test events
        start_date = (self.base_date + timedelta(days=20)).strftime("%Y-%m-%d")
        end_date = (self.base_date + timedelta(days=25)).strftime("%Y-%m-%d")
        result = self.collection.events_overlapping_range(start_date, end_date)
        self.assertEqual(len(result), 0)

    def test_events_overlapping_range_date_objects(self):
        """Test events_overlapping_range with date objects"""
        # Test range that should include the second multi-day event and cross-month event
        start_date = self.base_date + timedelta(days=4)
        end_date = self.base_date + timedelta(days=6)
        result = self.collection.events_overlapping_range(start_date, end_date)

        # Should include events that overlap with this date range
        self.assertGreater(len(result), 0)
        # Verify all events have some overlap with the range
        for event in result:
            overlaps = any(
                event.contains_date(start_date + timedelta(days=i)) for i in range(3)
            )  # check a few days in range
            self.assertTrue(overlaps)

    def test_events_overlapping_range_invalid_dates(self):
        """Test events_overlapping_range with invalid date strings"""
        result = self.collection.events_overlapping_range("invalid", "also-invalid")
        self.assertEqual(len(result), 0)

    def test_method_chaining(self):
        """Test that query methods return EventCollection for chaining"""
        # Use dynamic date instead of hardcoded one
        test_date = (self.base_date + timedelta(days=1)).strftime("%Y-%m-%d")
        result = self.collection.events_on_date(test_date).to_list()

        # Should return events for the specified date
        self.assertGreater(len(result), 0)
        self.assertIsInstance(result, list)
        # Verify all results contain the test date
        for event in result:
            self.assertTrue(event.contains_date(test_date))
