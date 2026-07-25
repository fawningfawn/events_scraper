"""
Unit tests for conference date parsing with mixed content
"""

import unittest
from datetime import date

from events_scraper.lib.core.utils import parse_date_range


class TestConferenceDateParsing(unittest.TestCase):
    """Test parsing dates from conference websites with mixed content"""

    def test_date_with_location_suffix(self):
        """Test date parsing when location info follows the date"""
        # Common pattern: "December 3-5, Caudan Arts Centre, Port Louis, Mauritius"
        start, end = parse_date_range(
            "December 3-5, Caudan Arts Centre, Port Louis, Mauritius"
        )
        self.assertIsNotNone(start)
        self.assertIsNotNone(end)
        self.assertEqual(start.month, 12)
        self.assertEqual(start.day, 3)
        self.assertEqual(end.month, 12)
        self.assertEqual(end.day, 5)

    def test_date_range_with_year(self):
        """Test date range with explicit year"""
        start, end = parse_date_range("April 25-27, 2026")
        self.assertIsNotNone(start)
        self.assertIsNotNone(end)
        self.assertEqual(start, date(2026, 4, 25))
        self.assertEqual(end, date(2026, 4, 27))

    def test_simple_date_range(self):
        """Test simple date range without extra text"""
        start, end = parse_date_range("December 3-5")
        self.assertIsNotNone(start)
        self.assertIsNotNone(end)
        self.assertEqual(start.month, 12)
        self.assertEqual(start.day, 3)
        self.assertEqual(end.month, 12)
        self.assertEqual(end.day, 5)

    def test_date_with_parentheses(self):
        """Test date extraction from parentheses"""
        # Pattern: "Conference Title (April 25-27, 2026)"
        start, end = parse_date_range("(April 25-27, 2026)")
        self.assertIsNotNone(start)
        self.assertEqual(start, date(2026, 4, 25))
        self.assertEqual(end, date(2026, 4, 27))

    def test_date_range_with_year_in_prefix(self):
        """Test date range where year is mentioned before the range"""
        # Pattern: "Test Conference 2026 will happen in Poland on June 4-7!"
        start, end = parse_date_range(
            "Test Conference 2026 will happen in Poland on June 4-7!"
        )
        self.assertIsNotNone(start)
        self.assertIsNotNone(end)
        self.assertEqual(start, date(2026, 6, 4))
        self.assertEqual(end, date(2026, 6, 7))

    def test_emoji_prefix_date(self):
        """Test date with emoji prefix and abbreviated year"""
        # Pattern: "🗓️ BFF'26 | June 4-7, Warsaw"
        start, end = parse_date_range("🗓️ BFF'26 | June 4-7, Warsaw")
        self.assertIsNotNone(start)
        self.assertIsNotNone(end)
        self.assertEqual(start, date(2026, 6, 4))
        self.assertEqual(end, date(2026, 6, 7))

    def test_date_range_no_year_in_text(self):
        """Test date range with no year information at all"""
        # Pattern: "14 — 15 NOVEMBER" (should infer current or next year)
        start, end = parse_date_range("14 — 15 NOVEMBER")
        self.assertIsNotNone(start)
        self.assertIsNotNone(end)
        self.assertEqual(start.month, 11)
        self.assertEqual(start.day, 14)
        self.assertEqual(end.month, 11)
        self.assertEqual(end.day, 15)
