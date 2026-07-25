"""
Comprehensive tests for utility functions
"""

import unittest
from datetime import time

from events_scraper.lib.core.utils import _try_parse_hh_format
from events_scraper.lib.core.utils import _try_parse_hh_mm_format
from events_scraper.lib.core.utils import parse_time_string


class TestParseTimeString(unittest.TestCase):
    """Test the parse_time_string function"""

    def test_parse_time_string_empty_input(self):
        """Test parsing empty or whitespace-only input"""
        self.assertIsNone(parse_time_string(""))
        self.assertIsNone(parse_time_string("   "))
        self.assertIsNone(parse_time_string(None))

    def test_parse_time_string_hh_mm_format(self):
        """Test parsing HH:MM format time strings"""
        # Standard times
        result = parse_time_string("14:30")
        self.assertEqual(result, time(14, 30))

        result = parse_time_string("09:15")
        self.assertEqual(result, time(9, 15))

        result = parse_time_string("00:00")
        self.assertEqual(result, time(0, 0))

        result = parse_time_string("23:59")
        self.assertEqual(result, time(23, 59))

    def test_parse_time_string_hh_mm_with_uhr(self):
        """Test parsing HH:MM format with German 'Uhr' suffix"""
        result = parse_time_string("14:30 Uhr")
        self.assertEqual(result, time(14, 30))

        result = parse_time_string("09:15Uhr")
        self.assertEqual(result, time(9, 15))

        result = parse_time_string("20:00  Uhr")
        self.assertEqual(result, time(20, 0))

    def test_parse_time_string_single_digit_hour(self):
        """Test parsing single digit hour in HH:MM format"""
        result = parse_time_string("9:30")
        self.assertEqual(result, time(9, 30))

        result = parse_time_string("1:00")
        self.assertEqual(result, time(1, 0))

    def test_parse_time_string_hh_format(self):
        """Test parsing single hour format"""
        result = parse_time_string("14")
        self.assertEqual(result, time(14, 0))

        result = parse_time_string("9")
        self.assertEqual(result, time(9, 0))

        result = parse_time_string("00")
        self.assertEqual(result, time(0, 0))

        result = parse_time_string("23")
        self.assertEqual(result, time(23, 0))

    def test_parse_time_string_hh_format_with_uhr(self):
        """Test parsing single hour format with German 'Uhr' suffix"""
        result = parse_time_string("14 Uhr")
        self.assertEqual(result, time(14, 0))

        result = parse_time_string("9Uhr")
        self.assertEqual(result, time(9, 0))

        result = parse_time_string("20  Uhr")
        self.assertEqual(result, time(20, 0))

    def test_parse_time_string_invalid_times(self):
        """Test parsing invalid time values"""
        # Invalid hours (>23)
        result = parse_time_string("25:30")
        self.assertEqual(result, "25:30")

        result = parse_time_string("24")
        self.assertEqual(result, "24")

        # Invalid minutes (>59)
        result = parse_time_string("14:60")
        self.assertEqual(result, "14:60")

        result = parse_time_string("12:99")
        self.assertEqual(result, "12:99")

        # Negative values
        result = parse_time_string("-1:30")
        self.assertEqual(result, "-1:30")

    def test_parse_time_string_unparseable_formats(self):
        """Test parsing unparseable time formats"""
        # Text descriptions
        result = parse_time_string("All day")
        self.assertEqual(result, "All day")

        result = parse_time_string("Evening")
        self.assertEqual(result, "Evening")

        result = parse_time_string("varies")
        self.assertEqual(result, "varies")

        # Malformed times
        result = parse_time_string("14:30:45")
        self.assertEqual(result, "14:30:45")

        result = parse_time_string("2pm")
        self.assertEqual(result, "2pm")

        result = parse_time_string("14.30")
        self.assertEqual(result, "14.30")

    def test_parse_time_string_whitespace_handling(self):
        """Test that whitespace is properly handled"""
        result = parse_time_string("  14:30  ")
        self.assertEqual(result, time(14, 30))

        result = parse_time_string("\t9\t")
        self.assertEqual(result, time(9, 0))

        result = parse_time_string(" All day ")
        self.assertEqual(result, "All day")


class TestTryParseHhMmFormat(unittest.TestCase):
    """Test the _try_parse_hh_mm_format helper function"""

    def test_valid_hh_mm_formats(self):
        """Test valid HH:MM format parsing"""
        result = _try_parse_hh_mm_format("14:30")
        self.assertEqual(result, time(14, 30))

        result = _try_parse_hh_mm_format("09:15")
        self.assertEqual(result, time(9, 15))

        result = _try_parse_hh_mm_format("23:59")
        self.assertEqual(result, time(23, 59))

        result = _try_parse_hh_mm_format("00:00")
        self.assertEqual(result, time(0, 0))

    def test_valid_hh_mm_with_uhr(self):
        """Test valid HH:MM format with Uhr suffix"""
        result = _try_parse_hh_mm_format("14:30 Uhr")
        self.assertEqual(result, time(14, 30))

        result = _try_parse_hh_mm_format("09:15Uhr")
        self.assertEqual(result, time(9, 15))

    def test_single_digit_hour(self):
        """Test single digit hour in HH:MM format"""
        result = _try_parse_hh_mm_format("9:30")
        self.assertEqual(result, time(9, 30))

        result = _try_parse_hh_mm_format("1:00")
        self.assertEqual(result, time(1, 0))

    def test_invalid_hh_mm_formats(self):
        """Test invalid HH:MM format inputs"""
        # Invalid hour
        result = _try_parse_hh_mm_format("25:30")
        self.assertIsNone(result)

        result = _try_parse_hh_mm_format("24:00")
        self.assertIsNone(result)

        # Invalid minute
        result = _try_parse_hh_mm_format("14:60")
        self.assertIsNone(result)

        result = _try_parse_hh_mm_format("12:99")
        self.assertIsNone(result)

        # Wrong format
        result = _try_parse_hh_mm_format("14")
        self.assertIsNone(result)

        result = _try_parse_hh_mm_format("14:30:45")
        self.assertIsNone(result)

        result = _try_parse_hh_mm_format("abc:def")
        self.assertIsNone(result)

    def test_edge_cases(self):
        """Test edge cases for HH:MM parsing"""
        # Boundary values - invalid format should return None
        result = _try_parse_hh_mm_format("0:0")
        self.assertIsNone(result)  # Invalid format (minutes must be 2 digits)

        result = _try_parse_hh_mm_format("23:0")
        self.assertIsNone(result)  # Invalid format (minutes must be 2 digits)

        result = _try_parse_hh_mm_format("0:59")
        self.assertEqual(result, time(0, 59))


class TestTryParseHhFormat(unittest.TestCase):
    """Test the _try_parse_hh_format helper function"""

    def test_valid_hh_formats(self):
        """Test valid single hour format parsing"""
        result = _try_parse_hh_format("14")
        self.assertEqual(result, time(14, 0))

        result = _try_parse_hh_format("09")
        self.assertEqual(result, time(9, 0))

        result = _try_parse_hh_format("9")
        self.assertEqual(result, time(9, 0))

        result = _try_parse_hh_format("00")
        self.assertEqual(result, time(0, 0))

        result = _try_parse_hh_format("23")
        self.assertEqual(result, time(23, 0))

    def test_valid_hh_with_uhr(self):
        """Test valid single hour format with Uhr suffix"""
        result = _try_parse_hh_format("14 Uhr")
        self.assertEqual(result, time(14, 0))

        result = _try_parse_hh_format("9Uhr")
        self.assertEqual(result, time(9, 0))

        result = _try_parse_hh_format("20  Uhr")
        self.assertEqual(result, time(20, 0))

    def test_invalid_hh_formats(self):
        """Test invalid single hour format inputs"""
        # Invalid hour
        result = _try_parse_hh_format("24")
        self.assertIsNone(result)

        result = _try_parse_hh_format("25")
        self.assertIsNone(result)

        result = _try_parse_hh_format("-1")
        self.assertIsNone(result)

        # Wrong format
        result = _try_parse_hh_format("14:30")
        self.assertIsNone(result)

        result = _try_parse_hh_format("abc")
        self.assertIsNone(result)

        result = _try_parse_hh_format("14:30:45")
        self.assertIsNone(result)

    def test_edge_cases(self):
        """Test edge cases for single hour parsing"""
        # Boundary values
        result = _try_parse_hh_format("0")
        self.assertEqual(result, time(0, 0))

        result = _try_parse_hh_format("23")
        self.assertEqual(result, time(23, 0))

    def test_value_error_handling(self):
        """Test handling of ValueError in parsing"""
        # This is hard to trigger with the current regex, but let's ensure robustness
        result = _try_parse_hh_format("999999999999999999999")  # Very large number
        self.assertIsNone(result)


class TestUtilsIntegration(unittest.TestCase):
    """Integration tests for utility functions"""

    def test_time_parsing_integration(self):
        """Test time parsing with various real-world inputs"""
        test_cases = [
            ("14:30", time(14, 30)),
            ("9:00 Uhr", time(9, 0)),
            ("20", time(20, 0)),
            ("All day", "All day"),
            ("varies", "varies"),
            ("", None),
            ("  19:45  ", time(19, 45)),
        ]

        for input_str, expected in test_cases:
            with self.subTest(input_str=input_str):
                result = parse_time_string(input_str)
                self.assertEqual(result, expected)
