"""Tests for event content hash deduplication"""

import unittest

from events_scraper.lib.core.deduplication import compute_content_hash


class TestContentHash(unittest.TestCase):
    """Test content hash computation for deduplication"""

    def test_hash_is_32_char_hex(self):
        """Content hash should be 32-character hex string"""
        hash_val = compute_content_hash("Event Title", "Location", "10:00")
        self.assertIsInstance(hash_val, str)
        self.assertEqual(len(hash_val), 32)
        self.assertTrue(all(c in "0123456789abcdef" for c in hash_val))

    def test_normalize_whitespace(self):
        """Whitespace differences should not affect hash"""
        hash1 = compute_content_hash("Event Title", "Location", "10:00")
        hash2 = compute_content_hash("  Event Title  ", "  Location  ", "10:00")
        hash3 = compute_content_hash("Event\nTitle", "Location", "10:00")
        self.assertEqual(hash1, hash2)
        self.assertEqual(hash1, hash3)

    def test_normalize_case(self):
        """Case differences should not affect hash"""
        hash1 = compute_content_hash("event title", "location", "10:00")
        hash2 = compute_content_hash("EVENT TITLE", "LOCATION", "10:00")
        hash3 = compute_content_hash("Event Title", "Location", "10:00")
        self.assertEqual(hash1, hash2)
        self.assertEqual(hash1, hash3)

    def test_null_time_as_empty_string(self):
        """NULL/None time should hash same as empty string"""
        hash1 = compute_content_hash("Event Title", "Location", None)
        hash2 = compute_content_hash("Event Title", "Location", "")
        self.assertEqual(hash1, hash2)

    def test_different_content_different_hash(self):
        """Different content should produce different hashes"""
        hash1 = compute_content_hash("Event A", "Location", "10:00")
        hash2 = compute_content_hash("Event B", "Location", "10:00")
        hash3 = compute_content_hash("Event A", "Location 2", "10:00")
        hash4 = compute_content_hash("Event A", "Location", "11:00")

        self.assertNotEqual(hash1, hash2)
        self.assertNotEqual(hash1, hash3)
        self.assertNotEqual(hash1, hash4)
        self.assertNotEqual(hash2, hash3)
        self.assertNotEqual(hash2, hash4)
        self.assertNotEqual(hash3, hash4)

    def test_idempotent(self):
        """Computing hash multiple times should give same result"""
        title = "Event Title"
        location = "Location"
        time = "10:00"

        hash1 = compute_content_hash(title, location, time)
        hash2 = compute_content_hash(title, location, time)
        hash3 = compute_content_hash(title, location, time)

        self.assertEqual(hash1, hash2)
        self.assertEqual(hash2, hash3)

    def test_same_content_different_order_different_hash(self):
        """Swapping title and location should produce different hash"""
        hash1 = compute_content_hash("Event", "Location", "10:00")
        hash2 = compute_content_hash("Location", "Event", "10:00")
        self.assertNotEqual(hash1, hash2)

    def test_unicode_handling(self):
        """Should handle unicode characters correctly"""
        hash1 = compute_content_hash("Festival de Jazz", "Paris", "19:00")
        hash2 = compute_content_hash("festival de jazz", "paris", "19:00")
        # Case normalized, should be same
        self.assertEqual(hash1, hash2)

    def test_empty_strings(self):
        """Should handle empty strings"""
        hash1 = compute_content_hash("", "", "")
        hash2 = compute_content_hash("", "", None)
        self.assertEqual(hash1, hash2)
        self.assertEqual(len(hash1), 32)
