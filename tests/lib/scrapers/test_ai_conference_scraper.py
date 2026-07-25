"""
Unit tests for AI-powered conference scraper
"""

import json
from unittest.mock import Mock
from unittest.mock import patch

from events_scraper.lib.core.year_window import get_year_window
from events_scraper.lib.scrapers.ai_scraper import AIScraper
from tests.lib.core.test_base import DatabaseTestCase


class TestAIScraper(DatabaseTestCase):
    """Test AI-powered conference scraping"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self._domain_patcher = patch(
            "events_scraper.lib.scrapers.ai_scraper.TICKET_PLATFORMS",
            ["ticket.example.com"],
        )
        self._domain_patcher.start()
        self.valid_year, _ = get_year_window(past_years=0, future_years=2)
        self.valid_date = f"{self.valid_year}-06-15"
        self.test_url = "https://example.com"
        self.test_html = f"<html><body>Test Conference {self.valid_year}</body></html>"

    def tearDown(self):
        self._domain_patcher.stop()
        super().tearDown()

    @patch("events_scraper.lib.scrapers.ai_scraper.http_get")
    @patch("events_scraper.lib.scrapers.ai_scraper.AICache")
    @patch("events_scraper.lib.core.llm_mixin.LLMClient")
    def test_scraper_checks_cache_first(self, mock_llm, mock_cache_class, mock_get):
        """Test scraper checks cache before calling LLM"""
        mock_cache = Mock()
        mock_cache.get.return_value = {
            "events": [{"title": "Cached Event", "date": self.valid_date}]
        }
        mock_cache_class.return_value = mock_cache

        mock_response = Mock()
        mock_response.text = self.test_html
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        scraper = AIScraper(self.test_url, "Test Conf")
        events = scraper.fetch()

        mock_cache.get.assert_called_once()
        mock_llm.assert_not_called()  # Should not call LLM if cached
        self.assertEqual(len(events), 1)

    @patch("events_scraper.lib.scrapers.ai_scraper.http_get")
    @patch("events_scraper.lib.scrapers.ai_scraper.AICache")
    @patch("events_scraper.lib.core.llm_mixin.LLMClient")
    def test_scraper_calls_llm_on_cache_miss(
        self, mock_llm_class, mock_cache_class, mock_get
    ):
        """Test scraper calls LLM on cache miss"""
        mock_cache = Mock()
        mock_cache.get.return_value = None  # Cache miss
        mock_cache_class.return_value = mock_cache

        mock_llm = Mock()
        mock_llm.complete.return_value = json.dumps(
            {"events": [{"title": "Test Event", "date": self.valid_date}]}
        )
        mock_llm_class.get_provider.return_value = mock_llm

        mock_response = Mock()
        mock_response.text = self.test_html
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        scraper = AIScraper(self.test_url, "Test Conf")
        scraper.fetch()

        mock_cache.get.assert_called_once()
        mock_llm.complete.assert_called_once()
        mock_cache.set.assert_called_once()  # Should cache result

    @patch("events_scraper.lib.scrapers.ai_scraper.http_get")
    @patch("events_scraper.lib.scrapers.ai_scraper.AICache")
    @patch("events_scraper.lib.core.llm_mixin.LLMClient")
    def test_scraper_parses_json_response(
        self, mock_llm_class, mock_cache_class, mock_get
    ):
        """Test scraper parses LLM JSON response into Events"""
        mock_cache = Mock()
        mock_cache.get.return_value = None
        mock_cache_class.return_value = mock_cache

        mock_llm = Mock()
        mock_llm.complete.return_value = json.dumps(
            {
                "events": [
                    {
                        "title": f"Test Conference {self.valid_year}",
                        "date": self.valid_date,
                        "location": "Miami, FL",
                    }
                ]
            }
        )
        mock_llm_class.get_provider.return_value = mock_llm

        mock_response = Mock()
        mock_response.text = self.test_html
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        scraper = AIScraper(self.test_url, "Test Conf")
        events = scraper.fetch()

        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event.title, f"Test Conference {self.valid_year}")
        self.assertEqual(event.date, self.valid_date)
        self.assertEqual(event.location, "Miami, FL")

    @patch("events_scraper.lib.scrapers.ai_scraper.http_get")
    @patch("events_scraper.lib.scrapers.ai_scraper.AICache")
    @patch("events_scraper.lib.core.llm_mixin.LLMClient")
    def test_scraper_handles_date_ranges(
        self, mock_llm_class, mock_cache_class, mock_get
    ):
        """Test scraper handles date ranges (e.g., June 15-17)."""
        mock_cache = Mock()
        mock_cache.get.return_value = None
        mock_cache_class.return_value = mock_cache

        mock_llm = Mock()
        mock_llm.complete.return_value = json.dumps(
            {
                "events": [
                    {
                        "title": f"Test Conference {self.valid_year}",
                        "date": f"{self.valid_year}-06-15 to {self.valid_year}-06-17",
                        "location": "Miami, FL",
                    }
                ]
            }
        )
        mock_llm_class.get_provider.return_value = mock_llm

        mock_response = Mock()
        mock_response.text = self.test_html
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        scraper = AIScraper(self.test_url, "Test Conf")
        events = scraper.fetch()

        self.assertEqual(len(events), 1)
        # Date range should be parsed into date and end_date
        self.assertEqual(events[0].date, f"{self.valid_year}-06-15")
        self.assertEqual(events[0].end_date, f"{self.valid_year}-06-17")

    @patch("events_scraper.lib.scrapers.ai_scraper.http_get")
    @patch("events_scraper.lib.scrapers.ai_scraper.AICache")
    @patch("events_scraper.lib.core.llm_mixin.LLMClient")
    def test_scraper_filters_invalid_years(
        self, mock_llm_class, mock_cache_class, mock_get
    ):
        """Test scraper filters out events outside rolling year window."""
        start_year, end_year = get_year_window(past_years=0, future_years=2)
        mock_cache = Mock()
        mock_cache.get.return_value = None
        mock_cache_class.return_value = mock_cache

        mock_llm = Mock()
        mock_llm.complete.return_value = json.dumps(
            {
                "events": [
                    {"title": "Old Event", "date": f"{start_year - 1}-06-15"},
                    {"title": "Valid Event", "date": f"{start_year}-06-15"},
                    {"title": "Future Event", "date": f"{end_year + 1}-06-15"},
                ]
            }
        )
        mock_llm_class.get_provider.return_value = mock_llm

        mock_response = Mock()
        mock_response.text = self.test_html
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        scraper = AIScraper(self.test_url, "Test Conf")
        events = scraper.fetch()

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].title, "Valid Event")

    @patch("events_scraper.lib.scrapers.ai_scraper.http_get")
    @patch("events_scraper.lib.scrapers.ai_scraper.AICache")
    @patch("events_scraper.lib.core.llm_mixin.LLMClient")
    def test_scraper_handles_multiple_events(
        self, mock_llm_class, mock_cache_class, mock_get
    ):
        """Test scraper handles multiple events from single page"""
        mock_cache = Mock()
        mock_cache.get.return_value = None
        mock_cache_class.return_value = mock_cache

        mock_llm = Mock()
        mock_llm.complete.return_value = json.dumps(
            {
                "events": [
                    {"title": "Event 1", "date": f"{self.valid_year}-06-15"},
                    {"title": "Event 2", "date": f"{self.valid_year}-07-20"},
                    {"title": "Event 3", "date": f"{self.valid_year}-08-10"},
                ]
            }
        )
        mock_llm_class.get_provider.return_value = mock_llm

        mock_response = Mock()
        mock_response.text = self.test_html
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        scraper = AIScraper(self.test_url, "Test Conf")
        events = scraper.fetch()

        self.assertEqual(len(events), 3)

    @patch("events_scraper.lib.scrapers.ai_scraper.http_get")
    @patch("events_scraper.lib.scrapers.ai_scraper.AICache")
    @patch("events_scraper.lib.core.llm_mixin.LLMClient")
    def test_scraper_handles_no_events(self, mock_llm_class, mock_cache_class, mock_get):
        """Test scraper handles pages with no events"""
        mock_cache = Mock()
        mock_cache.get.return_value = None
        mock_cache_class.return_value = mock_cache

        mock_llm = Mock()
        mock_llm.complete.return_value = json.dumps({"events": []})
        mock_llm_class.get_provider.return_value = mock_llm

        mock_response = Mock()
        mock_response.text = self.test_html
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        scraper = AIScraper(self.test_url, "Test Conf")
        events = scraper.fetch()

        self.assertEqual(len(events), 0)

    @patch("events_scraper.lib.scrapers.ai_scraper.http_get")
    @patch("events_scraper.lib.scrapers.ai_scraper.AICache")
    @patch("events_scraper.lib.core.llm_mixin.LLMClient")
    def test_scraper_sets_scraper_name(self, mock_llm_class, mock_cache_class, mock_get):
        """Test scraper sets scraper name on events"""
        mock_cache = Mock()
        mock_cache.get.return_value = None
        mock_cache_class.return_value = mock_cache

        mock_llm = Mock()
        mock_llm.complete.return_value = json.dumps(
            {"events": [{"title": "Test", "date": self.valid_date}]}
        )
        mock_llm_class.get_provider.return_value = mock_llm

        mock_response = Mock()
        mock_response.text = self.test_html
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        scraper = AIScraper(self.test_url, "testconf")
        events = scraper.fetch()

        self.assertEqual(events[0].scraper, "testconf")

    @patch("events_scraper.lib.scrapers.ai_scraper.http_get")
    @patch("events_scraper.lib.scrapers.ai_scraper.AICache")
    @patch("events_scraper.lib.core.llm_mixin.LLMClient")
    def test_scraper_handles_llm_errors(
        self, mock_llm_class, mock_cache_class, mock_get
    ):
        """Test scraper handles LLM API errors gracefully"""
        mock_cache = Mock()
        mock_cache.get.return_value = None
        mock_cache_class.return_value = mock_cache

        mock_llm = Mock()
        mock_llm.complete.side_effect = Exception("API Error")
        mock_llm_class.get_provider.return_value = mock_llm

        mock_response = Mock()
        mock_response.text = self.test_html
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        scraper = AIScraper(self.test_url, "Test Conf")
        events = scraper.fetch()

        # Should return empty list on error, not crash
        self.assertEqual(len(events), 0)

    @patch("events_scraper.lib.scrapers.ai_scraper.http_get")
    @patch("events_scraper.lib.scrapers.ai_scraper.AICache")
    @patch("events_scraper.lib.core.llm_mixin.LLMClient")
    def test_scraper_handles_invalid_json(
        self, mock_llm_class, mock_cache_class, mock_get
    ):
        """Test scraper handles invalid JSON from LLM"""
        mock_cache = Mock()
        mock_cache.get.return_value = None
        mock_cache_class.return_value = mock_cache

        mock_llm = Mock()
        mock_llm.complete.return_value = "Invalid JSON {{"
        mock_llm_class.get_provider.return_value = mock_llm

        mock_response = Mock()
        mock_response.text = self.test_html
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        scraper = AIScraper(self.test_url, "Test Conf")
        events = scraper.fetch()

        # Should return empty list on parse error
        self.assertEqual(len(events), 0)

    def test_scraper_generates_prompt(self):
        """Test scraper generates appropriate LLM prompt"""
        start_year, end_year = get_year_window(past_years=0, future_years=2)
        scraper = AIScraper(self.test_url, "testconf")
        prompt = scraper._generate_prompt(self.test_html, self.test_url)

        self.assertIn("conference", prompt.lower())
        self.assertIn(str(start_year), prompt)
        self.assertIn(str(end_year), prompt)
        self.assertIn("json", prompt.lower())
        self.assertIn(self.test_url, prompt)

    def test_find_ticket_links_single(self):
        """Test finding ticket platform links"""
        html = """<html><body>
            <a href="https://ticket.example.com/event">Buy Tickets</a>
            <a href="https://example.com">Other Link</a>
        </body></html>"""

        scraper = AIScraper(self.test_url, "test")
        links = scraper._find_ticket_links(html)

        self.assertEqual(len(links), 1)
        self.assertIn("ticket.example.com", links[0])

    @patch(
        "events_scraper.lib.scrapers.ai_scraper.TICKET_PLATFORMS",
        ["a.example.com", "b.example.com", "c.example.com"],
    )
    def test_find_ticket_links_multiple_platforms(self):
        """Test finding multiple ticket platform links"""
        html = """<html><body>
            <a href="https://a.example.com/event1">A</a>
            <a href="https://b.example.com/event2">B</a>
            <a href="https://c.example.com/event3">C</a>
        </body></html>"""

        scraper = AIScraper(self.test_url, "test")
        links = scraper._find_ticket_links(html)

        self.assertEqual(len(links), 3)

    def test_find_ticket_links_relative_url(self):
        """Test converting relative ticket URLs to absolute"""
        html = '<html><body><a href="/ticket/ticket.example.com/event">Tickets</a></body></html>'

        scraper = AIScraper("https://example.com", "test")
        links = scraper._find_ticket_links(html)

        self.assertEqual(len(links), 1)
        self.assertTrue(links[0].startswith("https://example.com/"))

    def test_find_ticket_links_no_links(self):
        """Test handling HTML with no ticket links"""
        html = "<html><body><a href='https://example.com'>No tickets</a></body></html>"

        scraper = AIScraper(self.test_url, "test")
        links = scraper._find_ticket_links(html)

        self.assertEqual(len(links), 0)

    @patch("events_scraper.lib.scrapers.ai_scraper.http_get")
    @patch("events_scraper.lib.scrapers.ai_scraper.AICache")
    @patch("events_scraper.lib.core.llm_mixin.LLMClient")
    def test_scraper_fetches_ticket_pages(
        self, mock_llm_class, mock_cache_class, mock_get
    ):
        """Test scraper fetches ticket pages and passes as documents"""
        mock_cache = Mock()
        mock_cache.get.return_value = None
        mock_cache_class.return_value = mock_cache

        mock_llm = Mock()
        mock_llm.complete.return_value = json.dumps(
            {"events": [{"title": "Test Event", "date": self.valid_date}]}
        )
        mock_llm_class.get_provider.return_value = mock_llm

        # Main page with ticket link
        html_with_ticket = (
            '<html><a href="https://ticket.example.com/event">Tickets</a></html>'
        )
        main_response = Mock()
        main_response.text = html_with_ticket
        main_response.status_code = 200

        # Ticket page
        ticket_response = Mock()
        ticket_response.text = f"<html>Event: June 15, {self.valid_year}</html>"
        ticket_response.status_code = 200

        # Configure mock_get to return different responses
        mock_get.side_effect = [main_response, ticket_response]

        scraper = AIScraper(self.test_url, "Test")
        scraper.fetch()

        # Verify ticket page was fetched
        self.assertEqual(mock_get.call_count, 2)  # Main page + ticket page

        # Verify LLM was called with documents
        mock_llm.complete.assert_called_once()
        call_args = mock_llm.complete.call_args
        self.assertIsNotNone(call_args[1].get("documents"))  # Documents passed
        self.assertEqual(len(call_args[1]["documents"]), 1)

    @patch("events_scraper.lib.scrapers.ai_scraper.http_get")
    @patch("events_scraper.lib.scrapers.ai_scraper.AICache")
    @patch("events_scraper.lib.core.llm_mixin.LLMClient")
    def test_scraper_handles_ticket_fetch_failure(
        self, mock_llm_class, mock_cache_class, mock_get
    ):
        """Test scraper gracefully handles ticket page fetch failures"""
        mock_cache = Mock()
        mock_cache.get.return_value = None
        mock_cache_class.return_value = mock_cache

        mock_llm = Mock()
        mock_llm.complete.return_value = json.dumps(
            {"events": [{"title": "Test", "date": self.valid_date}]}
        )
        mock_llm_class.get_provider.return_value = mock_llm

        html_with_ticket = (
            '<html><a href="https://ticket.example.com/event">Tickets</a></html>'
        )
        main_response = Mock()
        main_response.text = html_with_ticket
        main_response.status_code = 200

        # Ticket page fails
        ticket_response = Mock()
        ticket_response.status_code = 404

        mock_get.side_effect = [main_response, ticket_response]

        scraper = AIScraper(self.test_url, "Test")
        events = scraper.fetch()

        # Should still work, just without ticket page
        self.assertEqual(len(events), 1)
        # LLM called with no documents (ticket fetch failed)
        call_args = mock_llm.complete.call_args
        docs = call_args[1].get("documents")
        self.assertTrue(docs is None or len(docs) == 0)
