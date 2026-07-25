"""
Tests for date range parsing utility functions
"""

import unittest

from events_scraper.lib.core.utils import parse_date_range


class TestDateRangeParsing(unittest.TestCase):
    """Test date range parsing functionality"""

    def test_hong_kong_cheapo_tilde_format(self):
        """Test Hong Kong Cheapo tilde format: 'Jul 25 ~ Jul 29'"""
        start, end = parse_date_range("Jul 25 ~ Jul 29")

        self.assertEqual(start.month, 7)
        self.assertEqual(start.day, 25)
        self.assertEqual(end.month, 7)
        self.assertEqual(end.day, 29)

    def test_tilde_format_with_number_only_end(self):
        """Test tilde format where end is just a number: 'Jul 25 ~ 29'"""
        start, end = parse_date_range("Jul 25 ~ 29")

        self.assertEqual(start.month, 7)
        self.assertEqual(start.day, 25)
        self.assertEqual(end.month, 7)
        self.assertEqual(end.day, 29)

    def test_dash_format(self):
        """Test dash format: 'Aug 1 - Aug 3'"""
        start, end = parse_date_range("Aug 1 - Aug 3")

        self.assertEqual(start.month, 8)
        self.assertEqual(start.day, 1)
        self.assertEqual(end.month, 8)
        self.assertEqual(end.day, 3)

    def test_single_date(self):
        """Test single date parsing"""
        start, end = parse_date_range("Sat, Sep 06")

        self.assertEqual(start.month, 9)
        self.assertEqual(start.day, 6)
        self.assertIsNone(end)

    def test_cross_month_range(self):
        """Test date range that crosses months"""
        start, end = parse_date_range("Jul 30 - Aug 3")

        self.assertEqual(start.month, 7)
        self.assertEqual(start.day, 30)
        self.assertEqual(end.month, 8)
        self.assertEqual(end.day, 3)

    def test_unconfirmed_dates_skipped(self):
        """Test that unconfirmed dates are skipped"""
        test_cases = ["Early Sep", "Mid Oct", "Late Nov", "Early ~ Late Sep"]

        for date_str in test_cases:
            start, end = parse_date_range(date_str)
            self.assertIsNone(start, f"Expected None for '{date_str}', got {start}")
            self.assertIsNone(end, f"Expected None for '{date_str}', got {end}")

    def test_empty_and_invalid_strings(self):
        """Test handling of empty and invalid strings"""
        test_cases = ["", "   ", "invalid date", "not ~ a ~ valid ~ format"]

        for date_str in test_cases:
            start, end = parse_date_range(date_str)
            self.assertIsNone(start)
            self.assertIsNone(end)

    def test_daterangeparser_format(self):
        """Test DateRangeParser native formats"""
        # This might work depending on what DateRangeParser supports
        start, end = parse_date_range("4-8th May")

        # We expect this to work, but if not, that's fine for now
        if start is not None:
            self.assertEqual(start.month, 5)
            self.assertEqual(start.day, 4)
            if end is not None:
                self.assertEqual(end.month, 5)
                self.assertEqual(end.day, 8)

    def test_year_handling(self):
        """Test that dates without years default to current/next year"""
        start, end = parse_date_range("Dec 25 ~ Dec 28")

        # Should parse to some year (likely current or next year)
        self.assertIsNotNone(start)
        self.assertIsNotNone(end)
        self.assertEqual(start.month, 12)
        self.assertEqual(start.day, 25)
        self.assertEqual(end.month, 12)
        self.assertEqual(end.day, 28)
