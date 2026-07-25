"""
Unit tests for LLM client functionality
"""

import unittest
from unittest.mock import Mock
from unittest.mock import patch

from events_scraper.lib.core.llm_client import ClaudeProvider
from events_scraper.lib.core.llm_client import DeepSeekProvider
from events_scraper.lib.core.llm_client import GrokProvider
from events_scraper.lib.core.llm_client import LLMClient
from events_scraper.lib.core.llm_client import LLMError
from events_scraper.lib.core.llm_client import OpenAIProvider


class TestClaudeProvider(unittest.TestCase):
    """Test Claude API provider"""

    @patch("events_scraper.lib.core.llm_client.requests.post")
    def test_claude_api_call_success(self, mock_post):
        """Test successful Claude API call"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": [{"type": "text", "text": "test response"}]
        }
        mock_post.return_value = mock_response

        provider = ClaudeProvider(api_key="test-key")
        result = provider.complete("test prompt")

        self.assertEqual(result, "test response")
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertIn("anthropic-version", call_args[1]["headers"])
        self.assertEqual(call_args[1]["headers"]["x-api-key"], "test-key")

    @patch("events_scraper.lib.core.llm_client.requests.post")
    def test_claude_api_call_error(self, mock_post):
        """Test Claude API error handling"""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"
        mock_post.return_value = mock_response

        provider = ClaudeProvider(api_key="test-key")
        with self.assertRaises(LLMError):
            provider.complete("test prompt")

    def test_claude_provider_uses_haiku_model(self):
        """Test Claude provider defaults to Haiku model"""
        provider = ClaudeProvider(api_key="test-key")
        self.assertEqual(provider.model, "claude-haiku-4-5-20251001")


class TestOpenAIProvider(unittest.TestCase):
    """Test OpenAI API provider"""

    @patch("events_scraper.lib.core.llm_client.requests.post")
    def test_openai_api_call_success(self, mock_post):
        """Test successful OpenAI API call"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "test response"}}]
        }
        mock_post.return_value = mock_response

        provider = OpenAIProvider(api_key="test-key")
        result = provider.complete("test prompt")

        self.assertEqual(result, "test response")
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertEqual(call_args[1]["headers"]["Authorization"], "Bearer test-key")

    @patch("events_scraper.lib.core.llm_client.requests.post")
    def test_openai_api_call_error(self, mock_post):
        """Test OpenAI API error handling"""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_post.return_value = mock_response

        provider = OpenAIProvider(api_key="test-key")
        with self.assertRaises(LLMError):
            provider.complete("test prompt")

    def test_openai_provider_uses_gpt4_mini(self):
        """Test OpenAI provider defaults to GPT-4o-mini model"""
        provider = OpenAIProvider(api_key="test-key")
        self.assertEqual(provider.model, "gpt-4o-mini")


class TestGrokProvider(unittest.TestCase):
    """Test Grok API provider"""

    @patch("events_scraper.lib.core.llm_client.requests.post")
    def test_grok_api_call_success(self, mock_post):
        """Test successful Grok API call"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "test response"}}]
        }
        mock_post.return_value = mock_response

        provider = GrokProvider(api_key="test-key")
        result = provider.complete("test prompt")

        self.assertEqual(result, "test response")
        mock_post.assert_called_once()

    def test_grok_provider_uses_grok_model(self):
        """Test Grok provider defaults to Grok model"""
        provider = GrokProvider(api_key="test-key")
        self.assertEqual(provider.model, "grok-2-latest")


class TestLLMClient(unittest.TestCase):
    """Test LLM client factory and configuration"""

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    def test_client_uses_claude(self):
        client = LLMClient.get_provider("claude")
        self.assertIsInstance(client.provider, ClaudeProvider)

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_client_uses_openai(self):
        client = LLMClient.get_provider("openai")
        self.assertIsInstance(client.provider, OpenAIProvider)

    @patch.dict("os.environ", {"XAI_API_KEY": "test-key"})
    def test_client_uses_grok(self):
        client = LLMClient.get_provider("grok")
        self.assertIsInstance(client.provider, GrokProvider)

    @patch.dict("os.environ", {"DEEPSEEK_API_KEY": "test-key"})
    def test_client_uses_deepseek(self):
        client = LLMClient.get_provider("deepseek")
        self.assertIsInstance(client.provider, DeepSeekProvider)

    @patch.dict("os.environ", {}, clear=True)
    def test_client_raises_error_without_api_key(self):
        with self.assertRaises(ValueError):
            LLMClient.get_provider("claude")

    @patch.dict("os.environ", {}, clear=True)
    def test_client_raises_error_for_unknown_provider(self):
        with self.assertRaises(ValueError):
            LLMClient.get_provider("nonexistent")

    @patch("events_scraper.lib.core.llm_client.requests.post")
    def test_client_complete_delegates_to_provider(self, mock_post):
        """Test client.complete() delegates to provider"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": [{"type": "text", "text": "test response"}]
        }
        mock_post.return_value = mock_response

        client = LLMClient(ClaudeProvider(api_key="test-key"))
        result = client.complete("test prompt")

        self.assertEqual(result, "test response")

    @patch("events_scraper.lib.core.llm_client.requests.post")
    @patch("events_scraper.lib.core.llm_client.time.sleep")
    def test_client_retries_on_rate_limit(self, mock_sleep, mock_post):
        """Test client retries on 429 rate limit errors"""
        # First call returns 429, second succeeds
        mock_response_error = Mock()
        mock_response_error.status_code = 429
        mock_response_error.text = "Rate limit exceeded"

        mock_response_success = Mock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {
            "content": [{"type": "text", "text": "success"}]
        }

        mock_post.side_effect = [mock_response_error, mock_response_success]

        client = LLMClient(ClaudeProvider(api_key="test-key"))
        result = client.complete("test prompt", max_retries=2)

        self.assertEqual(result, "success")
        self.assertEqual(mock_post.call_count, 2)
        mock_sleep.assert_called_once()

    @patch("events_scraper.lib.core.llm_client.requests.post")
    def test_client_raises_after_max_retries(self, mock_post):
        """Test client raises LLMError after exhausting retries"""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.text = "Rate limit exceeded"
        mock_post.return_value = mock_response

        client = LLMClient(ClaudeProvider(api_key="test-key"))
        with self.assertRaises(LLMError):
            client.complete("test prompt", max_retries=1)
