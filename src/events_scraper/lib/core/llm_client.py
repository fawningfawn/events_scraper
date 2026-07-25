"""
LLM client for AI-powered event scraping.

Supports multiple providers: Claude (Anthropic), OpenAI, Grok (xAI), DeepSeek.
"""

import base64
import logging
import os
import time
from abc import ABC
from abc import abstractmethod
from typing import Optional

import requests

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Error raised when LLM API call fails"""


class LLMProvider(ABC):
    """Abstract base class for LLM providers"""

    def __init__(self, api_key: str = "", model: Optional[str] = None):
        self.api_key = api_key
        self.model = model or self.default_model()

    @abstractmethod
    def default_model(self) -> str:
        """Return the default model for this provider"""

    @abstractmethod
    def complete(self, prompt: str, documents: Optional[list] = None) -> str:
        """Send prompt with optional documents to LLM and return response"""


class MockLLMProvider(LLMProvider):
    """Mock LLM provider for tests"""

    def default_model(self) -> str:
        return "mock-model"

    def complete(self, prompt: str, documents: Optional[list] = None) -> str:
        return '{"events": []}'


class ClaudeProvider(LLMProvider):
    """Anthropic Claude API provider"""

    def default_model(self) -> str:
        return "claude-haiku-4-5-20251001"

    def complete(self, prompt: str, documents: Optional[list] = None) -> str:
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        content = [{"type": "text", "text": prompt}]

        if documents:
            for i, doc in enumerate(documents, 1):
                decoded_html = base64.b64decode(doc["data"]).decode(
                    "utf-8", errors="ignore"
                )
                content.append(
                    {
                        "type": "text",
                        "text": f"\n\n--- ATTACHED DOCUMENT {i} (Ticket/Purchase Page) ---\n{decoded_html}\n--- END DOCUMENT {i} ---",
                    }
                )

        data = {
            "model": self.model,
            "max_tokens": 2000,
            "messages": [{"role": "user", "content": content}],
        }

        response = requests.post(url, headers=headers, json=data, timeout=30)

        if response.status_code != 200:
            raise LLMError(f"Claude API error {response.status_code}: {response.text}")

        result = response.json()
        return result["content"][0]["text"]


class OpenAIProvider(LLMProvider):
    """OpenAI API provider"""

    def default_model(self) -> str:
        return "gpt-4o-mini"

    def complete(self, prompt: str, documents: Optional[list] = None) -> str:
        if documents:
            logger.warning(
                "OpenAI provider does not support document attachments, using text-only"
            )

        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 2000,
        }

        response = requests.post(url, headers=headers, json=data, timeout=30)

        if response.status_code != 200:
            raise LLMError(f"OpenAI API error {response.status_code}: {response.text}")

        result = response.json()
        return result["choices"][0]["message"]["content"]


class GrokProvider(LLMProvider):
    """xAI Grok API provider"""

    def default_model(self) -> str:
        return "grok-2-latest"

    def complete(self, prompt: str, documents: Optional[list] = None) -> str:
        if documents:
            logger.warning(
                "Grok provider does not support document attachments, using text-only"
            )

        url = "https://api.x.ai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 2000,
        }

        response = requests.post(url, headers=headers, json=data, timeout=30)

        if response.status_code != 200:
            raise LLMError(f"Grok API error {response.status_code}: {response.text}")

        result = response.json()
        return result["choices"][0]["message"]["content"]


class DeepSeekProvider(LLMProvider):
    """DeepSeek API provider (OpenAI-compatible)"""

    def default_model(self) -> str:
        return "deepseek-chat"

    def complete(self, prompt: str, documents: Optional[list] = None) -> str:
        if documents:
            logger.warning(
                "DeepSeek provider does not support document attachments, using text-only"
            )

        url = "https://api.deepseek.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 2000,
        }

        response = requests.post(url, headers=headers, json=data, timeout=30)

        if response.status_code != 200:
            raise LLMError(f"DeepSeek API error {response.status_code}: {response.text}")

        result = response.json()
        return result["choices"][0]["message"]["content"]


_PROVIDER_MAP = {
    "claude": (("ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY_EVENTS"), ClaudeProvider),
    "openai": (("OPENAI_API_KEY",), OpenAIProvider),
    "grok": (("XAI_API_KEY",), GrokProvider),
    "deepseek": (("DEEPSEEK_API_KEY",), DeepSeekProvider),
}


def _resolve_provider_config(provider_name, api_key, model):
    """Read LLM provider settings from config if not explicitly given."""
    if provider_name:
        return provider_name, api_key, model
    from events_scraper.lib.config import load_config  # noqa: E402

    config = load_config()
    provider_name = config.get_llm_provider()
    if not provider_name:
        raise ValueError("llm.provider not set in config")
    api_key = api_key or config.get_llm_api_key()
    model = model or config.get_llm_model()
    return provider_name, api_key, model


def _resolve_api_key(env_vars, api_key):
    """Try env vars if no api_key given, raise if still none."""
    if api_key:
        return api_key
    for var in env_vars:
        api_key = os.getenv(var)
        if api_key:
            return api_key
    if os.getenv("PYTEST_CURRENT_TEST"):
        return None
    raise ValueError(
        f"No API key found. Set llm.api_key in config "
        f"or the {env_vars[0]} environment variable."
    )


class LLMClient:
    """LLM client with config-driven provider selection and retry logic."""

    def __init__(self, provider: LLMProvider):
        self.provider = provider

    @classmethod
    def get_provider(
        cls,
        provider_name: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ) -> "LLMClient":
        provider_name, api_key, model = _resolve_provider_config(
            provider_name, api_key, model
        )
        provider_name = provider_name.lower()
        entry = _PROVIDER_MAP.get(provider_name)
        if entry is None:
            raise ValueError(
                f"Unknown llm_provider: {provider_name}. "
                f"Must be one of: {', '.join(_PROVIDER_MAP)}"
            )

        env_vars, provider_class = entry
        api_key = _resolve_api_key(env_vars, api_key)
        if not api_key:
            return cls(provider=MockLLMProvider())

        return cls(provider=provider_class(api_key=api_key, model=model))

    def complete(
        self,
        prompt: str,
        documents: Optional[list] = None,
        max_retries: int = 3,
        retry_delay: float = 2.0,
    ) -> str:
        """
        Send prompt with optional documents to LLM with retry logic

        Args:
            prompt: The prompt to send
            documents: Optional list of document dicts with base64 encoded data
            max_retries: Maximum number of retries on rate limit errors
            retry_delay: Delay in seconds between retries

        Returns:
            LLM response text

        Raises:
            LLMError: If API call fails after all retries
        """
        last_error = None

        for attempt in range(max_retries):
            try:
                return self.provider.complete(prompt, documents)
            except LLMError as e:
                last_error = e
                # Retry on rate limit errors (429)
                if "429" in str(e) and attempt < max_retries - 1:
                    logger.warning(
                        f"Rate limit hit, retrying in {retry_delay}s "
                        f"(attempt {attempt + 1}/{max_retries})"
                    )
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    raise

        raise last_error
