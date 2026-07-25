"""
Unit tests for LLM analysis mixin functionality

Tests for reusable LLM content analysis capabilities that can be mixed
into any BaseEventScraper subclass.
"""

import json
import unittest
from unittest.mock import Mock
from unittest.mock import patch

from events_scraper.lib.core.llm_client import LLMError
from events_scraper.lib.core.llm_mixin import LLMAnalysisMixin


class MockLLMScraper(LLMAnalysisMixin):
    """Test scraper that uses LLM analysis mixin"""

    def __init__(self):
        """Initialize test scraper"""
        super().__init__()


class TestLLMAnalysisMixinBasics(unittest.TestCase):
    """Test basic LLM analysis mixin functionality"""

    def setUp(self):
        """Create scraper instance for testing"""
        self.scraper = MockLLMScraper()

    def test_mixin_has_analyze_with_llm_method(self):
        """Test mixin provides analyze_with_llm method"""
        self.assertTrue(hasattr(self.scraper, "analyze_with_llm"))
        self.assertTrue(callable(self.scraper.analyze_with_llm))

    def test_mixin_has_extract_with_llm_method(self):
        """Test mixin provides extract_with_llm method"""
        self.assertTrue(hasattr(self.scraper, "extract_with_llm"))
        self.assertTrue(callable(self.scraper.extract_with_llm))

    @patch("events_scraper.lib.core.llm_mixin.LLMClient.get_provider")
    def test_llm_client_lazy_initialized(self, mock_get_provider):
        """Test LLM client is lazy initialized on first use"""
        mock_client = Mock()
        mock_client.complete.return_value = '{"result": "test"}'
        mock_get_provider.return_value = mock_client

        # Client should not be initialized yet
        self.assertIsNone(self.scraper._llm_client)

        # First call should initialize
        self.scraper.analyze_with_llm("<html>test</html>", "test prompt")

        # Now should be initialized
        self.assertIsNotNone(self.scraper._llm_client)
        mock_get_provider.assert_called_once()

    @patch("events_scraper.lib.core.llm_mixin.LLMClient.get_provider")
    def test_llm_client_reused(self, mock_get_provider):
        """Test LLM client is reused on subsequent calls"""
        mock_client = Mock()
        mock_client.complete.return_value = '{"result": "test"}'
        mock_get_provider.return_value = mock_client

        # Make two calls
        self.scraper.analyze_with_llm("<html>test</html>", "prompt 1")
        self.scraper.analyze_with_llm("<html>test</html>", "prompt 2")

        # Should only initialize once
        mock_get_provider.assert_called_once()
        self.assertEqual(mock_client.complete.call_count, 2)


class TestAnalyzeWithLLM(unittest.TestCase):
    """Test analyze_with_llm method"""

    def setUp(self):
        """Create scraper instance for testing"""
        self.scraper = MockLLMScraper()

    @patch("events_scraper.lib.core.llm_mixin.LLMClient.get_provider")
    def test_analyze_with_llm_basic(self, mock_get_provider):
        """Test basic analyze_with_llm call"""
        mock_client = Mock()
        expected_response = {"title": "Test Event", "date": "2025-06-15"}
        mock_client.complete.return_value = json.dumps(expected_response)
        mock_get_provider.return_value = mock_client

        html = "<html><h1>Test Event</h1><p>June 15, 2025</p></html>"
        prompt = "Extract event details"

        result = self.scraper.analyze_with_llm(html, prompt)

        self.assertEqual(result, expected_response)
        mock_client.complete.assert_called_once()

    @patch("events_scraper.lib.core.llm_mixin.LLMClient.get_provider")
    def test_analyze_with_llm_passes_html_in_prompt(self, mock_get_provider):
        """Test analyze_with_llm includes HTML in prompt"""
        mock_client = Mock()
        mock_client.complete.return_value = '{"result": "test"}'
        mock_get_provider.return_value = mock_client

        html = "<html>content</html>"
        prompt = "Extract data"

        self.scraper.analyze_with_llm(html, prompt)

        call_args = mock_client.complete.call_args[0][0]
        self.assertIn("content", call_args)
        self.assertIn("Extract data", call_args)

    @patch("events_scraper.lib.core.llm_mixin.LLMClient.get_provider")
    def test_analyze_with_llm_handles_array_response(self, mock_get_provider):
        """Test analyze_with_llm can handle array JSON responses"""
        mock_client = Mock()
        expected_response = [
            {"title": "Event 1", "date": "2025-06-15"},
            {"title": "Event 2", "date": "2025-06-16"},
        ]
        mock_client.complete.return_value = json.dumps(expected_response)
        mock_get_provider.return_value = mock_client

        html = "<html>multiple events</html>"
        result = self.scraper.analyze_with_llm(html, "Extract events")

        self.assertEqual(result, expected_response)

    @patch("events_scraper.lib.core.llm_mixin.LLMClient.get_provider")
    def test_analyze_with_llm_handles_nested_json(self, mock_get_provider):
        """Test analyze_with_llm handles nested JSON structures"""
        mock_client = Mock()
        expected_response = {
            "events": [{"title": "Event 1", "details": {"date": "2025-06-15"}}]
        }
        mock_client.complete.return_value = json.dumps(expected_response)
        mock_get_provider.return_value = mock_client

        result = self.scraper.analyze_with_llm("<html>test</html>", "Extract")

        self.assertEqual(result["events"][0]["details"]["date"], "2025-06-15")

    @patch("events_scraper.lib.core.llm_mixin.LLMClient.get_provider")
    def test_analyze_with_llm_raises_on_invalid_json(self, mock_get_provider):
        """Test analyze_with_llm raises error on invalid JSON response"""
        mock_client = Mock()
        mock_client.complete.return_value = "not valid json {{"
        mock_get_provider.return_value = mock_client

        with self.assertRaises(json.JSONDecodeError):
            self.scraper.analyze_with_llm("<html>test</html>", "Extract")

    @patch("events_scraper.lib.core.llm_mixin.LLMClient.get_provider")
    def test_analyze_with_llm_extracts_json_from_extra_text(self, mock_get_provider):
        """Test analyze_with_llm extracts JSON even if LLM adds extra text"""
        mock_client = Mock()
        mock_client.complete.return_value = (
            "Here's the data:\n"
            '{"title": "Event", "date": "2025-06-15"}\n'
            "Hope this helps!"
        )
        mock_get_provider.return_value = mock_client

        result = self.scraper.analyze_with_llm("<html>test</html>", "Extract")

        self.assertEqual(result["title"], "Event")
        self.assertEqual(result["date"], "2025-06-15")

    @patch("events_scraper.lib.core.llm_mixin.LLMClient.get_provider")
    def test_analyze_with_llm_respects_custom_schema(self, mock_get_provider):
        """Test analyze_with_llm accepts custom schema parameter"""
        mock_client = Mock()
        expected_response = {"custom_field": "custom_value"}
        mock_client.complete.return_value = json.dumps(expected_response)
        mock_get_provider.return_value = mock_client

        schema = {"type": "object", "properties": {"custom_field": {"type": "string"}}}
        result = self.scraper.analyze_with_llm(
            "<html>test</html>", "Extract", schema=schema
        )

        self.assertEqual(result["custom_field"], "custom_value")


class TestExtractWithLLM(unittest.TestCase):
    """Test extract_with_llm method with selector support"""

    def setUp(self):
        """Create scraper instance for testing"""
        self.scraper = MockLLMScraper()

    @patch("events_scraper.lib.core.llm_mixin.LLMClient.get_provider")
    def test_extract_with_llm_basic(self, mock_get_provider):
        """Test basic extract_with_llm with CSS selector"""
        mock_client = Mock()
        expected_response = {"time": "19:00", "location": "Theater"}
        mock_client.complete.return_value = json.dumps(expected_response)
        mock_get_provider.return_value = mock_client

        html = '<div class="details"><p>Time: 19:00</p><p>Theater</p></div>'
        selector = "div.details"
        instructions = "Extract time and location"

        result = self.scraper.extract_with_llm(html, selector, instructions)

        self.assertEqual(result["time"], "19:00")
        self.assertEqual(result["location"], "Theater")

    @patch("events_scraper.lib.core.llm_mixin.LLMClient.get_provider")
    def test_extract_with_llm_extracts_selected_content(self, mock_get_provider):
        """Test extract_with_llm sends only selected element content to LLM"""
        mock_client = Mock()
        mock_client.complete.return_value = '{"time": "19:00"}'
        mock_get_provider.return_value = mock_client

        html = (
            '<div class="header">Header</div>'
            '<div class="details"><p>Time: 19:00</p></div>'
            '<div class="footer">Footer</div>'
        )

        self.scraper.extract_with_llm(html, "div.details", "Extract time")

        # LLM should receive only the selected content
        call_args = mock_client.complete.call_args[0][0]
        self.assertIn("Time: 19:00", call_args)
        # Should not receive full HTML
        self.assertNotIn("Header", call_args)
        self.assertNotIn("Footer", call_args)

    @patch("events_scraper.lib.core.llm_mixin.LLMClient.get_provider")
    def test_extract_with_llm_with_attribute_selector(self, mock_get_provider):
        """Test extract_with_llm works with attribute selectors"""
        mock_client = Mock()
        mock_client.complete.return_value = '{"time": "19:00"}'
        mock_get_provider.return_value = mock_client

        html = '<p data-time="19:00">Event at 7 PM</p>'

        # CSS attribute selector
        result = self.scraper.extract_with_llm(
            html, "p[data-time]", "Extract time from this element"
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["time"], "19:00")

    @patch("events_scraper.lib.core.llm_mixin.LLMClient.get_provider")
    def test_extract_with_llm_no_match_returns_none(self, mock_get_provider):
        """Test extract_with_llm returns None if selector matches nothing"""
        mock_client = Mock()
        mock_get_provider.return_value = mock_client

        html = "<div>Content</div>"

        result = self.scraper.extract_with_llm(html, "div.nonexistent", "Extract")

        self.assertIsNone(result)
        # LLM should not be called if selector doesn't match
        mock_client.complete.assert_not_called()


class TestLLMAnalysisMixinCaching(unittest.TestCase):
    """Test caching behavior of LLM analysis mixin"""

    def setUp(self):
        """Create scraper instance for testing"""
        self.scraper = MockLLMScraper()

    @patch("events_scraper.lib.core.llm_mixin.LLMClient.get_provider")
    def test_caching_enabled_by_default(self, mock_get_provider):
        """Test caching is enabled by default"""
        mock_client = Mock()
        mock_client.complete.return_value = '{"result": "test"}'
        mock_get_provider.return_value = mock_client

        html = "<html>test</html>"
        prompt = "Extract data"

        # First call
        self.scraper.analyze_with_llm(html, prompt)
        # Second call with same HTML and prompt
        self.scraper.analyze_with_llm(html, prompt)

        # LLM should only be called once (second cached)
        self.assertEqual(mock_client.complete.call_count, 1)

    @patch("events_scraper.lib.core.llm_mixin.LLMClient.get_provider")
    def test_cache_invalidates_on_html_change(self, mock_get_provider):
        """Test cache invalidates when HTML changes"""
        mock_client = Mock()
        mock_client.complete.return_value = '{"result": "test"}'
        mock_get_provider.return_value = mock_client

        prompt = "Extract data"

        # First call with one HTML
        self.scraper.analyze_with_llm("<html>old</html>", prompt)
        # Second call with different HTML
        self.scraper.analyze_with_llm("<html>new</html>", prompt)

        # LLM should be called twice (different HTML)
        self.assertEqual(mock_client.complete.call_count, 2)

    @patch("events_scraper.lib.core.llm_mixin.LLMClient.get_provider")
    def test_cache_invalidates_on_prompt_change(self, mock_get_provider):
        """Test cache invalidates when prompt changes"""
        mock_client = Mock()
        mock_client.complete.return_value = '{"result": "test"}'
        mock_get_provider.return_value = mock_client

        html = "<html>test</html>"

        # First call with one prompt
        self.scraper.analyze_with_llm(html, "Prompt 1")
        # Second call with different prompt
        self.scraper.analyze_with_llm(html, "Prompt 2")

        # LLM should be called twice (different prompt)
        self.assertEqual(mock_client.complete.call_count, 2)

    @patch("events_scraper.lib.core.llm_mixin.LLMClient.get_provider")
    def test_caching_can_be_disabled(self, mock_get_provider):
        """Test caching can be disabled with parameter"""
        mock_client = Mock()
        mock_client.complete.return_value = '{"result": "test"}'
        mock_get_provider.return_value = mock_client

        html = "<html>test</html>"
        prompt = "Extract data"

        # First call with cache disabled
        self.scraper.analyze_with_llm(html, prompt, use_cache=False)
        # Second call with cache disabled
        self.scraper.analyze_with_llm(html, prompt, use_cache=False)

        # LLM should be called twice (caching disabled)
        self.assertEqual(mock_client.complete.call_count, 2)


class TestLLMAnalysisMixinErrorHandling(unittest.TestCase):
    """Test error handling in LLM analysis mixin"""

    def setUp(self):
        """Create scraper instance for testing"""
        self.scraper = MockLLMScraper()

    @patch("events_scraper.lib.core.llm_mixin.LLMClient.get_provider")
    def test_handles_llm_error(self, mock_get_provider):
        """Test mixin handles LLMError gracefully"""
        mock_client = Mock()
        mock_client.complete.side_effect = LLMError("API error")
        mock_get_provider.return_value = mock_client

        with self.assertRaises(LLMError):
            self.scraper.analyze_with_llm("<html>test</html>", "Extract")

    @patch("events_scraper.lib.core.llm_mixin.LLMClient.get_provider")
    def test_handles_connection_error(self, mock_get_provider):
        """Test mixin handles connection errors"""
        mock_client = Mock()
        mock_client.complete.side_effect = ConnectionError("Network error")
        mock_get_provider.return_value = mock_client

        with self.assertRaises(ConnectionError):
            self.scraper.analyze_with_llm("<html>test</html>", "Extract")

    @patch("events_scraper.lib.core.llm_mixin.LLMClient.get_provider")
    def test_empty_response_raises_error(self, mock_get_provider):
        """Test mixin raises error on empty LLM response"""
        mock_client = Mock()
        mock_client.complete.return_value = ""
        mock_get_provider.return_value = mock_client

        with self.assertRaises(json.JSONDecodeError):
            self.scraper.analyze_with_llm("<html>test</html>", "Extract")
