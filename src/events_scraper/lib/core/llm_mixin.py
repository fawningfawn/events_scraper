"""
LLM analysis mixin for reusable content analysis capabilities

Provides analyze_with_llm() and extract_with_llm() methods that any
BaseEventScraper subclass can use to leverage LLM for HTML parsing.
"""

import hashlib
import json
import logging
import re
from typing import Any
from typing import Dict
from typing import Optional

from bs4 import BeautifulSoup

from events_scraper.lib.core.llm_client import LLMClient

logger = logging.getLogger(__name__)


class LLMAnalysisMixin:
    """
    Mixin providing LLM-powered HTML analysis for event scrapers

    Provides methods to analyze HTML content using LLM, with built-in
    caching and error handling.
    """

    def __init__(self):
        """Initialize LLM analysis mixin"""
        self._llm_client: Optional[LLMClient] = None
        self._llm_cache: Dict[str, Any] = {}  # Simple dict-based cache

    def _get_llm_client(self) -> LLMClient:
        """Get or initialize LLM client (lazy initialization)."""
        if self._llm_client is None:
            self._llm_client = LLMClient.get_provider()
        return self._llm_client

    def _extract_json_from_response(self, response_text: str) -> Any:
        """
        Extract JSON from LLM response (handles extra text)

        Args:
            response_text: Raw LLM response text

        Returns:
            Parsed JSON object (dict, list, etc.)

        Raises:
            json.JSONDecodeError: If no valid JSON found
        """
        # Try to find JSON in response (handles LLM adding extra text)
        json_match = re.search(r"\{.*\}|\[.*\]", response_text, re.DOTALL)
        if json_match:
            response_text = json_match.group(0)

        return json.loads(response_text)

    def analyze_with_llm(
        self,
        html: str,
        prompt: str,
        schema: Optional[Dict] = None,
        use_cache: bool = True,
    ) -> Any:
        """
        Analyze HTML content using LLM

        Args:
            html: HTML content to analyze
            prompt: Instructions for LLM (e.g., "Extract event details")
            schema: Optional JSON schema for response validation
            use_cache: Whether to use caching (default: True)

        Returns:
            Parsed JSON response from LLM

        Raises:
            json.JSONDecodeError: If LLM response is not valid JSON
            LLMError: If LLM API call fails
        """
        # Generate cache key based on HTML hash + prompt
        html_hash = hashlib.sha256(html.encode()).hexdigest()
        cache_key = f"{html_hash}|{prompt}"

        # Check cache first
        if use_cache and cache_key in self._llm_cache:
            logger.debug("Cache hit for LLM analysis")
            return self._llm_cache[cache_key]

        # Build prompt with HTML content
        full_prompt = f"""{prompt}

HTML Content:
{html}

Return valid JSON only, no other text."""

        # Call LLM
        client = self._get_llm_client()
        response_text = client.complete(full_prompt)

        # Parse response
        result = self._extract_json_from_response(response_text)

        # Cache result
        if use_cache:
            self._llm_cache[cache_key] = result

        return result

    def extract_with_llm(
        self,
        html: str,
        selector: str,
        instructions: str,
        schema: Optional[Dict] = None,
    ) -> Optional[Any]:
        """
        Extract content from specific element using CSS selector, then analyze with LLM

        Args:
            html: HTML content containing element
            selector: CSS selector (e.g., "div.details", "p.time")
            instructions: What to extract (e.g., "Extract time and location")
            schema: Optional JSON schema for response validation

        Returns:
            Parsed JSON from LLM, or None if selector doesn't match

        Raises:
            json.JSONDecodeError: If LLM response is invalid JSON
        """
        soup = BeautifulSoup(html, "html.parser")

        # Try CSS selector
        element = soup.select_one(selector)

        # If no match, return None without calling LLM
        if element is None:
            logger.debug(f"Selector did not match: {selector}")
            return None

        # Extract HTML of selected element
        selected_html = str(element)

        # Analyze selected element with LLM
        return self.analyze_with_llm(selected_html, instructions, schema=schema)
