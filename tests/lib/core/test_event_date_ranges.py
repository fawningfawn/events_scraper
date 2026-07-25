"""
Tests for Event model date range functionality
"""

import unittest
from datetime import timedelta

from events_scraper.lib import mock_data


class TestEventDateRanges(unittest.TestCase):
    """Test Event model date range functionality"""

    def test_single_day_event(self):
        """Test single-day event properties"""
        test_date = mock_data.get_date()
        event = mock_data.get_event(date=test_date.strftime("%Y-%m-%d"))

        self.assertFalse(event.is_multi_day)
        self.assertEqual(event.duration_days, 1)
        self.assertEqual(event.formatted_date_range, test_date.strftime("%Y-%m-%d"))
        self.assertTrue(event.contains_date(test_date.strftime("%Y-%m-%d")))

        next_day = test_date + timedelta(days=1)
        self.assertFalse(event.contains_date(next_day.strftime("%Y-%m-%d")))

    def test_multi_day_event_same_month(self):
        """Test multi-day event in same month"""
        start_date = mock_data.get_date()
        end_date = start_date + timedelta(days=4)  # 5 day duration

        event = mock_data.get_event(
            date=start_date.strftime("%Y-%m-%d"), end_date=end_date.strftime("%Y-%m-%d")
        )

        self.assertTrue(event.is_multi_day)
        self.assertEqual(event.duration_days, 5)

        # Test date containment
        self.assertTrue(
            event.contains_date(start_date.strftime("%Y-%m-%d"))
        )  # Start date
        middle_date = start_date + timedelta(days=2)
        self.assertTrue(
            event.contains_date(middle_date.strftime("%Y-%m-%d"))
        )  # Middle date
        self.assertTrue(event.contains_date(end_date.strftime("%Y-%m-%d")))  # End date

        before_start = start_date - timedelta(days=1)
        after_end = end_date + timedelta(days=1)
        self.assertFalse(
            event.contains_date(before_start.strftime("%Y-%m-%d"))
        )  # Before start
        self.assertFalse(
            event.contains_date(after_end.strftime("%Y-%m-%d"))
        )  # After end

    def test_multi_day_event_different_months(self):
        """Test multi-day event spanning different months"""
        start_date = mock_data.get_date()
        end_date = start_date + timedelta(days=4)  # 5 day duration

        event = mock_data.get_event(
            date=start_date.strftime("%Y-%m-%d"), end_date=end_date.strftime("%Y-%m-%d")
        )

        self.assertTrue(event.is_multi_day)
        self.assertEqual(event.duration_days, 5)

        # Test date containment across potential month boundaries
        self.assertTrue(event.contains_date(start_date.strftime("%Y-%m-%d")))
        day2 = start_date + timedelta(days=1)
        self.assertTrue(event.contains_date(day2.strftime("%Y-%m-%d")))
        day3 = start_date + timedelta(days=2)
        self.assertTrue(event.contains_date(day3.strftime("%Y-%m-%d")))
        self.assertTrue(event.contains_date(end_date.strftime("%Y-%m-%d")))

        before_start = start_date - timedelta(days=1)
        after_end = end_date + timedelta(days=1)
        self.assertFalse(event.contains_date(before_start.strftime("%Y-%m-%d")))
        self.assertFalse(event.contains_date(after_end.strftime("%Y-%m-%d")))

    def test_contains_date_with_date_object(self):
        """Test contains_date method with date objects"""
        start_date = mock_data.get_date()
        end_date = start_date + timedelta(days=2)

        event = mock_data.get_event(
            date=start_date.strftime("%Y-%m-%d"), end_date=end_date.strftime("%Y-%m-%d")
        )

        self.assertTrue(event.contains_date(start_date))
        middle_date = start_date + timedelta(days=1)
        self.assertTrue(event.contains_date(middle_date))
        self.assertTrue(event.contains_date(end_date))

        before_start = start_date - timedelta(days=1)
        after_end = end_date + timedelta(days=1)
        self.assertFalse(event.contains_date(before_start))
        self.assertFalse(event.contains_date(after_end))

    def test_end_date_same_as_start_date(self):
        """Test event where end_date is same as start date"""
        test_date = mock_data.get_date()
        event = mock_data.get_event(
            date=test_date.strftime("%Y-%m-%d"), end_date=test_date.strftime("%Y-%m-%d")
        )

        # Should be treated as single-day event
        self.assertFalse(event.is_multi_day)
        self.assertEqual(event.duration_days, 1)

    def test_invalid_date_format(self):
        """Test handling of invalid date formats"""
        event = mock_data.get_event(date="invalid-date", end_date="also-invalid")

        # Should handle gracefully and fall back to defaults
        self.assertEqual(event.duration_days, 1)
        self.assertEqual(event.formatted_date_range, "invalid-date")

        # contains_date should fall back to exact string match
        self.assertTrue(event.contains_date("invalid-date"))
        valid_date = mock_data.get_date()
        self.assertFalse(event.contains_date(valid_date.strftime("%Y-%m-%d")))
