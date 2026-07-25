"""
Unit tests for HTTP caching functionality
"""

import unittest
from pathlib import Path
from unittest.mock import patch

from xdg import xdg_cache_home

from events_scraper.lib.core.scraper import clear_http_cache


class TestHttpCaching(unittest.TestCase):
    """Test HTTP caching for scrapers"""

    @patch("events_scraper.lib.core.scraper.requests_cache.clear")
    def test_clear_cache_calls_requests_cache(self, mock_clear):
        """Test clear_http_cache() calls requests_cache.clear()"""
        clear_http_cache()

        mock_clear.assert_called_once()

    def test_cache_directory_created(self):
        """Test HTTP cache directory is created on import"""

        cache_dir = Path(xdg_cache_home()) / "events_scraper" / "http_cache"
        self.assertTrue(cache_dir.exists())
        self.assertTrue(cache_dir.is_dir())
