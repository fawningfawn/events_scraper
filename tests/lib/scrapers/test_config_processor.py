"""
Unit tests for conference config processor
"""

import unittest
from datetime import date

from events_scraper.lib.scrapers.config_processor import expand_url_variables


class TestExpandUrlVariables(unittest.TestCase):
    """Test URL variable expansion"""

    def test_no_variables_returns_single_url(self):
        """Test URL without variables returns single-element list"""
        url = "https://example.com/conference/"
        result = expand_url_variables(url)
        self.assertEqual(result, ["https://example.com/conference/"])

    def test_year_variable_with_default_range(self):
        """Test {year} expands to current+next year by default"""
        url = "https://example.com/{year}/"
        current_year = date.today().year
        result = expand_url_variables(url)

        expected = [
            f"https://example.com/{current_year}/",
            f"https://example.com/{current_year + 1}/",
        ]
        self.assertEqual(result, expected)

    def test_yy_variable_with_default_range(self):
        """Test {yy} expands to 2-digit years by default"""
        url = "https://example.com/{yy}/"
        current_year = date.today().year
        yy_current = str(current_year)[-2:]
        yy_next = str(current_year + 1)[-2:]

        result = expand_url_variables(url)

        expected = [
            f"https://example.com/{yy_current}/",
            f"https://example.com/{yy_next}/",
        ]
        self.assertEqual(result, expected)

    def test_year_variable_with_custom_range(self):
        """Test {year} expands across custom date range"""
        url = "https://example.com/{year}/"
        date_range = (date(2025, 1, 1), date(2027, 12, 31))
        result = expand_url_variables(url, date_range)

        expected = [
            "https://example.com/2025/",
            "https://example.com/2026/",
            "https://example.com/2027/",
        ]
        self.assertEqual(result, expected)

    def test_yy_variable_with_custom_range(self):
        """Test {yy} expands with 2-digit years across custom range"""
        url = "https://example.com/{yy}/"
        date_range = (date(2025, 1, 1), date(2027, 12, 31))
        result = expand_url_variables(url, date_range)

        expected = [
            "https://example.com/25/",
            "https://example.com/26/",
            "https://example.com/27/",
        ]
        self.assertEqual(result, expected)

    def test_year_in_middle_of_path(self):
        """Test {year} works when embedded in path"""
        url = "https://example.com/event{year}/home"
        date_range = (date(2025, 1, 1), date(2026, 12, 31))
        result = expand_url_variables(url, date_range)

        expected = [
            "https://example.com/event2025/home",
            "https://example.com/event2026/home",
        ]
        self.assertEqual(result, expected)

    def test_yy_in_middle_of_path(self):
        """Test {yy} works when embedded in path"""
        url = "https://example.com/bbb-{yy}/"
        date_range = (date(2025, 1, 1), date(2026, 12, 31))
        result = expand_url_variables(url, date_range)

        expected = [
            "https://example.com/bbb-25/",
            "https://example.com/bbb-26/",
        ]
        self.assertEqual(result, expected)

    def test_single_year_range(self):
        """Test single-year range returns single URL"""
        url = "https://example.com/{year}/"
        date_range = (date(2025, 1, 1), date(2025, 12, 31))
        result = expand_url_variables(url, date_range)

        expected = ["https://example.com/2025/"]
        self.assertEqual(result, expected)

    def test_year_spanning_decade(self):
        """Test {yy} works across decade boundary"""
        url = "https://example.com/{yy}/"
        date_range = (date(2029, 1, 1), date(2031, 12, 31))
        result = expand_url_variables(url, date_range)

        expected = [
            "https://example.com/29/",
            "https://example.com/30/",
            "https://example.com/31/",
        ]
        self.assertEqual(result, expected)

    def test_multiple_year_variables_in_url(self):
        """Test URL with multiple {year} occurrences"""
        url = "https://example.com/{year}/event-{year}/"
        date_range = (date(2025, 1, 1), date(2026, 12, 31))
        result = expand_url_variables(url, date_range)

        expected = [
            "https://example.com/2025/event-2025/",
            "https://example.com/2026/event-2026/",
        ]
        self.assertEqual(result, expected)

    def test_url_with_query_params(self):
        """Test {year} in URL with query parameters"""
        url = "https://example.com/{year}/?lang=en"
        date_range = (date(2025, 1, 1), date(2026, 12, 31))
        result = expand_url_variables(url, date_range)

        expected = [
            "https://example.com/2025/?lang=en",
            "https://example.com/2026/?lang=en",
        ]
        self.assertEqual(result, expected)
