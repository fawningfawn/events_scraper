"""
Unit tests for AI response caching functionality
"""

import hashlib
import json
import unittest
from datetime import datetime
from unittest.mock import patch

from events_scraper.lib.core.ai_cache import AICache


class TestAICache(unittest.TestCase):
    """Test AI response caching with hash-based invalidation"""

    def setUp(self):
        """Create in-memory cache for testing"""
        self.cache = AICache(":memory:")

    def tearDown(self):
        """Clean up cache connection"""
        self.cache.close()

    def test_cache_miss_returns_none(self):
        """Test cache returns None on miss"""
        result = self.cache.get("https://example.com", "<html>content</html>")
        self.assertIsNone(result)

    def test_cache_stores_and_retrieves_response(self):
        """Test cache stores and retrieves AI responses"""
        url = "https://example.com"
        html = "<html>content</html>"
        response = {"title": "Test Event", "date": "2025-06-15"}

        self.cache.set(url, html, response)
        result = self.cache.get(url, html)

        self.assertEqual(result, response)

    def test_cache_invalidates_on_html_change(self):
        """Test cache returns None when HTML content changes"""
        url = "https://example.com"
        old_html = "<html>old content</html>"
        new_html = "<html>new content</html>"
        response = {"title": "Test Event"}

        self.cache.set(url, old_html, response)
        result = self.cache.get(url, new_html)

        self.assertIsNone(result)

    def test_cache_updates_when_html_changes(self):
        """Test cache updates correctly when HTML changes"""
        url = "https://example.com"
        old_html = "<html>old</html>"
        new_html = "<html>new</html>"
        old_response = {"title": "Old Event"}
        new_response = {"title": "New Event"}

        # Store old response
        self.cache.set(url, old_html, old_response)

        # Store new response (should replace old)
        self.cache.set(url, new_html, new_response)

        # Should get new response
        result = self.cache.get(url, new_html)
        self.assertEqual(result, new_response)

        # Old HTML should return None
        old_result = self.cache.get(url, old_html)
        self.assertIsNone(old_result)

    def test_cache_computes_sha256_hash(self):
        """Test cache uses SHA256 for HTML hashing"""
        url = "https://example.com"
        html = "<html>test</html>"
        response = {"title": "Test"}

        self.cache.set(url, html, response)

        # Manually compute expected hash
        expected_hash = hashlib.sha256(html.encode("utf-8")).hexdigest()

        # Verify hash is stored correctly
        cursor = self.cache.conn.cursor()
        cursor.execute("SELECT html_hash FROM ai_cache WHERE url = ?", (url,))
        row = cursor.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], expected_hash)

    def test_cache_stores_json_response(self):
        """Test cache stores response as JSON"""
        url = "https://example.com"
        html = "<html>test</html>"
        response = {"title": "Test", "nested": {"key": "value"}}

        self.cache.set(url, html, response)

        # Verify JSON is stored correctly
        cursor = self.cache.conn.cursor()
        cursor.execute("SELECT response_json FROM ai_cache WHERE url = ?", (url,))
        row = cursor.fetchone()
        self.assertIsNotNone(row)
        stored_response = json.loads(row[0])
        self.assertEqual(stored_response, response)

    def test_cache_stores_timestamp(self):
        """Test cache stores creation timestamp"""
        url = "https://example.com"
        html = "<html>test</html>"
        response = {"title": "Test"}

        before = datetime.now()
        self.cache.set(url, html, response)
        after = datetime.now()

        # Verify timestamp is within expected range
        cursor = self.cache.conn.cursor()
        cursor.execute("SELECT created_at FROM ai_cache WHERE url = ?", (url,))
        row = cursor.fetchone()
        self.assertIsNotNone(row)
        timestamp = datetime.fromisoformat(row[0])
        self.assertGreaterEqual(timestamp, before)
        self.assertLessEqual(timestamp, after)

    def test_cache_hit_logs_message(self):
        """Test cache hit logs appropriate message"""
        url = "https://example.com"
        html = "<html>content</html>"
        response = {"title": "Test Event"}

        self.cache.set(url, html, response)

        with patch("events_scraper.lib.core.ai_cache.logger") as mock_logger:
            self.cache.get(url, html)
            mock_logger.debug.assert_called_once()
            call_args = mock_logger.debug.call_args[0][0]
            self.assertIn("Cache hit", call_args)

    def test_cache_miss_logs_message(self):
        """Test cache miss logs appropriate message"""
        with patch("events_scraper.lib.core.ai_cache.logger") as mock_logger:
            self.cache.get("https://example.com", "<html>test</html>")
            mock_logger.debug.assert_called_once()
            call_args = mock_logger.debug.call_args[0][0]
            self.assertIn("Cache miss", call_args)

    def test_cache_handles_multiple_urls(self):
        """Test cache handles multiple URLs independently"""
        url1 = "https://example.com/1"
        url2 = "https://example.com/2"
        html = "<html>same</html>"
        response1 = {"title": "Event 1"}
        response2 = {"title": "Event 2"}

        self.cache.set(url1, html, response1)
        self.cache.set(url2, html, response2)

        result1 = self.cache.get(url1, html)
        result2 = self.cache.get(url2, html)

        self.assertEqual(result1, response1)
        self.assertEqual(result2, response2)

    def test_cache_table_created_on_init(self):
        """Test ai_cache table is created on initialization"""
        cursor = self.cache.conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master " "WHERE type='table' AND name='ai_cache'"
        )
        table = cursor.fetchone()
        self.assertIsNotNone(table)
        self.assertEqual(table[0], "ai_cache")

    def test_cache_table_has_correct_schema(self):
        """Test ai_cache table has correct columns"""
        cursor = self.cache.conn.cursor()
        cursor.execute("PRAGMA table_info(ai_cache)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        self.assertIn("url", columns)
        self.assertIn("html_hash", columns)
        self.assertIn("response_json", columns)
        self.assertIn("created_at", columns)
        self.assertEqual(columns["url"], "TEXT")
        self.assertEqual(columns["html_hash"], "TEXT")
        self.assertEqual(columns["response_json"], "TEXT")
        self.assertEqual(columns["created_at"], "TEXT")

    def test_cache_url_is_primary_key(self):
        """Test url column is primary key"""
        cursor = self.cache.conn.cursor()
        cursor.execute("PRAGMA table_info(ai_cache)")
        url_column = [row for row in cursor.fetchall() if row[1] == "url"][0]
        self.assertEqual(url_column[5], 1)  # pk column

    def test_cache_handles_unicode_html(self):
        """Test cache handles Unicode characters in HTML"""
        url = "https://example.com"
        html = "<html>日本語 Español 中文</html>"
        response = {"title": "International Event"}

        self.cache.set(url, html, response)
        result = self.cache.get(url, html)

        self.assertEqual(result, response)

    def test_cache_handles_large_html(self):
        """Test cache handles large HTML content"""
        url = "https://example.com"
        html = "<html>" + ("x" * 1000000) + "</html>"  # 1MB+ HTML
        response = {"title": "Large Page Event"}

        self.cache.set(url, html, response)
        result = self.cache.get(url, html)

        self.assertEqual(result, response)
