"""Tests for HybridScraper base class"""

import unittest
from unittest.mock import patch

from events_scraper.lib.scrapers.hybrid import HybridScraper


class ConcreteHybridScraper(HybridScraper):
    """Concrete implementation for testing"""

    def get_api_url(self, page: int) -> str:
        """Return API URL for page"""
        return f"https://api.example.com/events?page={page}"

    def parse_api_response(self, response_json: dict) -> tuple:
        """Parse API response, return (events_data, has_more_pages)"""
        events = response_json.get("events", [])
        has_more = response_json.get("has_more", False)
        return events, has_more

    def get_detail_url_from_event(self, event_data: dict) -> str:
        """Get detail URL from event data"""
        return event_data.get("detail_url", "")


class TestHybridScraperDetailFetching(unittest.TestCase):
    """Test detail page fetching"""

    def test_fetches_detail_pages(self):
        """Should fetch detail pages for events"""
        scraper = ConcreteHybridScraper(
            base_url="https://example.com",
            scraper_name="test-scraper",
        )

        detail_url = "https://example.com/event/1"
        detail_html = "<html><h1>Event Title</h1></html>"

        with patch.object(scraper, "_fetch_page_from_web", return_value=detail_html):
            result = scraper._fetch_page_content(detail_url)

            self.assertIsNotNone(result)


class TestHybridScraperAIIntegration(unittest.TestCase):
    """Test AI detail page parsing integration"""

    def test_parses_detail_with_llm(self):
        """Should use LLMAnalysisMixin to parse detail pages"""
        scraper = ConcreteHybridScraper(
            base_url="https://example.com",
            scraper_name="test-scraper",
        )

        detail_html = "<html><h1>Concert</h1><p>Feb 15, 2026 at 19:30</p></html>"

        # Should inherit analyze_with_llm from LLMAnalysisMixin
        self.assertTrue(hasattr(scraper, "analyze_with_llm"))

        with patch.object(scraper, "analyze_with_llm") as mock_analyze:
            mock_analyze.return_value = {
                "title": "Concert",
                "date": "2026-02-15",
                "time": "19:30",
                "location": "Hall",
            }

            result = scraper.analyze_with_llm(detail_html, "Extract event details")

            self.assertEqual(result["title"], "Concert")
            self.assertTrue(mock_analyze.called)


class TestHybridScraperAPIIntegration(unittest.TestCase):
    """Test API integration with HybridScraper"""

    def test_parses_api_response(self):
        """Should parse API response correctly"""
        scraper = ConcreteHybridScraper(
            base_url="https://example.com",
            scraper_name="test-scraper",
        )

        api_response = {
            "events": [
                {
                    "id": 1,
                    "title": "Event 1",
                    "date": "2026-01-15",
                    "detail_url": "https://example.com/event/1",
                }
            ],
            "has_more": False,
        }

        events, has_more = scraper.parse_api_response(api_response)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["id"], 1)
        self.assertFalse(has_more)

    def test_extracts_detail_url(self):
        """Should extract detail URL from event data"""
        scraper = ConcreteHybridScraper(
            base_url="https://example.com",
            scraper_name="test-scraper",
        )

        event_data = {
            "id": 1,
            "title": "Event",
            "detail_url": "https://example.com/event/1",
        }

        detail_url = scraper.get_detail_url_from_event(event_data)

        self.assertEqual(detail_url, "https://example.com/event/1")

    def test_generates_correct_api_url(self):
        """Should generate correct API URL for pagination"""
        scraper = ConcreteHybridScraper(
            base_url="https://example.com",
            scraper_name="test-scraper",
        )

        url_page_1 = scraper.get_api_url(1)
        url_page_2 = scraper.get_api_url(2)

        self.assertIn("page=1", url_page_1)
        self.assertIn("page=2", url_page_2)
