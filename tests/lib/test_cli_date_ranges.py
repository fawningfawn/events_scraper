"""
Tests for CLI date range functionality
"""

import unittest
from datetime import date
from unittest.mock import patch

from events_scraper.lib.manage_helpers import parse_date_argument


class TestCLIDateRanges(unittest.TestCase):
    """Test CLI date range argument parsing"""

    def test_parse_today(self):
        """Test parsing 'today' returns current date"""
        result = parse_date_argument("today")
        self.assertEqual(result, date.today())

    @patch("dateparser.parse")
    def test_parse_single_date_dateparser(self, mock_dateparser):
        """Test parsing single date using dateparser"""
        mock_dateparser.return_value.date.return_value = date(2025, 7, 25)

        result = parse_date_argument("2025-07-25")

        mock_dateparser.assert_called_once_with("2025-07-25")
        self.assertEqual(result, date(2025, 7, 25))

    def test_parse_date_range_fallback(self):
        """Test that date range parsing works when dateparser fails"""
        # Test a format that dateparser typically can't handle but our range parser can
        result = parse_date_argument("Jul 25 ~ Jul 29")

        # Should return tuple for date range
        self.assertIsInstance(result, tuple)
        start_date, end_date = result
        self.assertEqual(start_date.month, 7)
        self.assertEqual(start_date.day, 25)
        self.assertEqual(end_date.month, 7)
        self.assertEqual(end_date.day, 29)

    @patch("dateparser.parse")
    def test_parse_single_date_from_range_parser(self, mock_dateparser):
        """Test that single date parsing fails when dateparser fails"""
        mock_dateparser.return_value = None  # dateparser fails

        # Should raise ValueError when dateparser fails on a simple date
        with self.assertRaises(ValueError) as context:
            parse_date_argument("Jul 25")

        self.assertIn("Could not parse date or date range", str(context.exception))

    def test_parse_tilde_range(self):
        """Test tilde-separated date range"""
        result = parse_date_argument("Jul 25 ~ Jul 29")

        self.assertIsInstance(result, tuple)
        start_date, end_date = result
        self.assertEqual(start_date.month, 7)
        self.assertEqual(start_date.day, 25)
        self.assertEqual(end_date.month, 7)
        self.assertEqual(end_date.day, 29)

    def test_parse_dash_range(self):
        """Test dash-separated date range"""
        result = parse_date_argument("Jul 25 - Jul 29")

        self.assertIsInstance(result, tuple)
        start_date, end_date = result
        self.assertEqual(start_date.day, 25)
        self.assertEqual(end_date.day, 29)

    @patch("dateparser.parse")
    def test_parse_dash_separator_range(self, mock_dateparser):
        """Test dash-separated date range with full dates"""
        mock_dateparser.return_value = None  # dateparser fails

        result = parse_date_argument("Jul 25 - Jul 29")

        self.assertIsInstance(result, tuple)
        start_date, end_date = result
        self.assertEqual(start_date.month, 7)
        self.assertEqual(start_date.day, 25)
        self.assertEqual(end_date.month, 7)
        self.assertEqual(end_date.day, 29)

    @patch("dateparser.parse")
    def test_parse_invalid_date_exits(self, mock_dateparser):
        """Test that invalid date raises ValueError"""
        mock_dateparser.return_value = None  # dateparser fails

        with self.assertRaises(ValueError) as context:
            parse_date_argument("invalid-unparseable-date")

        self.assertIn("Could not parse date or date range", str(context.exception))

    def test_parse_result_types(self):
        """Test that return types are correct for different inputs"""
        # Single date should return date object
        result = parse_date_argument("today")
        self.assertIsInstance(result, date)

        # Date range should return tuple of dates
        result = parse_date_argument("Jul 25 ~ Jul 29")
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], date)
        self.assertIsInstance(result[1], date)
