"""
AI-powered AI scraper using LLM for HTML parsing

Instead of brittle CSS selectors, uses Claude/OpenAI/Grok to extract
event information directly from HTML.
"""

import base64
import json
import logging
import re
import time
from datetime import date
from typing import List
from typing import Optional
from urllib.parse import urlparse

import html2text
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from events_scraper.lib.core.ai_cache import AICache
from events_scraper.lib.core.database import EventCollection
from events_scraper.lib.core.llm_client import LLMError
from events_scraper.lib.core.llm_mixin import LLMAnalysisMixin
from events_scraper.lib.core.models import Event
from events_scraper.lib.core.orm_models import ScraperStatus
from events_scraper.lib.core.orm_session import get_session
from events_scraper.lib.core.scraper import BROWSER_HEADERS
from events_scraper.lib.core.scraper import http_get
from events_scraper.lib.core.year_window import get_year_window

logger = logging.getLogger(__name__)


# Ticket platforms to follow for additional event information
TICKET_PLATFORMS = [
    "zaprite.com",
    "luma.com",
    "eventbrite.com",
    "tickettailor.com",
    "eventpop.me",
]


class AIScraper(LLMAnalysisMixin):
    """
    Scraper using LLM for parsing.

    Uses AI to extract event dates and information from HTML,
    eliminating the need for brittle CSS selectors.
    """

    def __init__(
        self,
        url: str,
        scraper_name: str,
        multiple_events: bool = False,
        categories: list = None,
        use_playwright: bool = False,
        llm_hints: list = None,
        selector_remove: list = None,
        selector_keep: list = None,
    ):
        """
        Initialize AI AI scraper

        Args:
            url: Page URL
            scraper_name: Unique name for this scraper
            multiple_events: If True, page has multiple events with individual URLs
            categories: List of categories from config (e.g., ['bitcoin', 'developers'])
            use_playwright: If True, use Playwright to render JS-heavy pages
            llm_hints: List of hints to help LLM find events on the page
            selector_remove: CSS selectors to remove from page before parsing
            selector_keep: CSS selectors to keep (if present, only parse these sections)
        """
        super().__init__()  # Initialize mixin
        self.url = url
        self._scraper_name = scraper_name
        self.multiple_events = multiple_events
        self.categories = categories or []
        self.use_playwright = use_playwright
        self.llm_hints = llm_hints or []
        self.selector_remove = selector_remove or []
        self.selector_keep = selector_keep or []
        self.cache = AICache()  # Persistent cache for AI scraper

    @property
    def scraper_name(self) -> str:
        if hasattr(self, "_scraper_name_override"):
            return self._scraper_name_override
        return self._scraper_name

    def __del__(self):
        """Close cache connection on cleanup"""
        try:
            if hasattr(self, "cache") and self.cache:
                self.cache.close()
        except Exception:
            pass  # Ignore errors during cleanup

    def _apply_selector_keep(self, soup):
        """Keep only elements matching selector_keep, discard rest."""
        kept_content = soup.new_tag("div")
        for selector in self.selector_keep:
            for elem in soup.select(selector):
                kept_content.append(elem)
        return BeautifulSoup(str(kept_content), "lxml")

    def _remove_unwanted_tags(self, soup):
        """Remove script, style, meta, noscript tags."""
        for tag in soup.find_all(["script", "style", "meta", "noscript"]):
            tag.decompose()

    def _clean_attributes(self, soup):
        """Remove unnecessary attributes, keep only essential ones."""
        essential_attrs = {"a": ["href"], "img": ["src", "alt"], "form": ["action"]}
        for tag in soup.find_all(True):
            keep = essential_attrs.get(tag.name, [])
            for attr in list(tag.attrs.keys()):
                if attr not in keep:
                    del tag[attr]

    def _clean_html(self, html: str) -> str:
        """Clean HTML to remove superfluous markup and reduce token count."""
        soup = BeautifulSoup(html, "lxml")

        if self.selector_keep:
            soup = self._apply_selector_keep(soup)
            logger.debug(f"Applied selector_keep: {self.selector_keep}")

        for selector in self.selector_remove:
            for elem in soup.select(selector):
                elem.decompose()
            logger.debug(f"Removed selector: {selector}")

        self._remove_unwanted_tags(soup)
        self._clean_attributes(soup)
        return str(soup)

    def _generate_prompt(
        self, html: str, url: str, has_ticket_pages: bool = False
    ) -> str:
        """
        Generate LLM prompt for event extraction

        Args:
            html: HTML content of event page
            url: URL of the event page
            has_ticket_pages: Whether ticket/purchase pages are attached as documents

        Returns:
            Prompt string for LLM
        """
        content = html
        content_type = "HTML Content"

        # If HTML is large, convert to text first to reduce token count
        if len(html) > 50000:
            logger.debug(f"HTML large ({len(html)} chars), converting to text...")
            h = html2text.HTML2Text()
            h.ignore_links = False  # Keep URLs for context
            content = h.handle(html)
            content_type = "Text Content"
            logger.debug(f"Converted to text ({len(content)} chars)")
        else:
            content = html
            # If not too large, optionally clean it to remove superfluous markup
            if len(html) > 30000:
                logger.debug(f"HTML moderate size ({len(html)} chars), cleaning...")
                content = self._clean_html(html)
                logger.debug(f"HTML cleaned ({len(html)} -> {len(content)} chars)")

        # If content is still too large, truncate to keep important top portion
        MAX_CONTENT_SIZE = 80000
        if len(content) > MAX_CONTENT_SIZE:
            logger.debug(
                f"Content too large ({len(content)} chars), truncating to {MAX_CONTENT_SIZE}..."
            )
            content = content[:MAX_CONTENT_SIZE]
            logger.debug(f"Truncated content (kept first {MAX_CONTENT_SIZE} chars)")

        logger.debug(f"Final content size: {len(content)} chars, type: {content_type}")

        # Log content for debugging
        logger.debug(f"Content being sent to LLM (first 2000 chars):\n{content[:2000]}")
        logger.debug(f"Content being sent to LLM (last 2000 chars):\n{content[-2000:]}")

        # Build prompt based on whether we need individual URLs and have ticket pages
        extra_instructions = []

        if self.multiple_events:
            extra_instructions.append(
                "5. If multiple events are listed, extract them ONLY if each has its own event page URL"
            )
            extra_instructions.append(
                "6. If events share the same page (no individual URLs), return ONLY the main/primary event"
            )
            extra_instructions.append(
                "7. For each event, include the full URL by combining the base domain with relative links found in the page"
            )
            # Add scraper-specific hints
            for i, hint in enumerate(self.llm_hints, start=8):
                extra_instructions.append(f"{i}. {hint}")
            url_field = ',\n      "url": "https://example.com/specific-event (required if multiple events)"'
        else:
            url_field = ""

        if has_ticket_pages:
            extra_instructions.append(
                f"{'7' if self.multiple_events else '5'}. Additional ticket/purchase pages are attached as documents - use them to find accurate event dates"
            )

        url_instruction = "\n".join(extra_instructions) if extra_instructions else ""

        start_year, end_year = self._get_valid_year_window()
        return f"""Extract AI scraper/event information from this page.

URL: {url}

{content_type}:
{content}

Please extract AI scrapers or events mentioned on this page and return them as JSON.

IMPORTANT RULES:
1. Only extract events with dates between {start_year} and {end_year} (inclusive)
2. Return dates in YYYY-MM-DD format (e.g., "{start_year}-06-15")
3. For date ranges, use format "YYYY-MM-DD to YYYY-MM-DD"
4. If no valid events found, return empty events array
{url_instruction}

Return JSON in this exact format:
{{
  "events": [
    {{
      "title": "Event name",
      "date": "{start_year}-06-15" or "{start_year}-06-15 to {start_year}-06-17",
      "location": "City, Country (optional)"{url_field}
    }}
  ]
}}

Only return the JSON, no other text."""

    def _parse_llm_response(self, response_text: str) -> List[dict]:
        """
        Parse LLM JSON response and extract events

        Args:
            response_text: Raw text response from LLM

        Returns:
            List of event dicts

        Raises:
            json.JSONDecodeError: If response is not valid JSON
        """
        # Use mixin's JSON extraction method
        data = self._extract_json_from_response(response_text)
        return data.get("events", [])

    def _get_valid_year_window(self) -> tuple[int, int]:
        """Return inclusive year window for year filtering."""
        return get_year_window(past_years=0, future_years=2)

    def _is_valid_year(self, date_str: str) -> bool:
        """
        Check if date contains valid year in configured rolling window.

        Args:
            date_str: Date string to check

        Returns:
            True if date contains year in the accepted window
        """
        # Extract all 4-digit years from the string
        years = re.findall(r"20\d{2}", date_str)
        if not years:
            return False

        # Check if at least one year is in valid range
        start_year, end_year = self._get_valid_year_window()
        return any(start_year <= int(year) <= end_year for year in years)

    def _fetch_main_html(self) -> tuple[str, int]:
        """
        Fetch HTML from main URL. This is where the primary HTTP request is made.

        Returns:
            Tuple of (html_content, status_code)

        Raises:
            requests.HTTPError: For HTTP errors (404, 403, 500, etc.)
        """
        logger.debug(f"Fetching main page: {self.url}")
        if self.use_playwright:
            html = self._fetch_html_with_playwright()
            return html, 200  # Playwright returns rendered page
        else:
            response = http_get(
                self.url,
                headers=BROWSER_HEADERS,
                timeout=30,
            )
            response.raise_for_status()  # Raise HTTPError for bad status codes
            return response.text, response.status_code

    def _fetch_ticket_pages(self, html: str) -> List[dict]:
        """
        Fetch optional ticket/purchase pages for additional event information.
        Makes HTTP requests to ticket platform URLs found in HTML.

        Args:
            html: HTML content to parse for ticket links

        Returns:
            List of base64-encoded documents
        """
        ticket_links = self._find_ticket_links(html)
        documents = []

        if not ticket_links:
            return documents

        logger.info(f"Found {len(ticket_links)} ticket link(s), fetching...")
        for ticket_url in ticket_links[:3]:  # Limit to 3
            try:
                logger.debug(f"Fetching ticket page: {ticket_url}")
                response = http_get(ticket_url, headers=BROWSER_HEADERS, timeout=10)
                if response.status_code == 200:
                    encoded = base64.b64encode(response.text.encode()).decode()
                    documents.append({"media_type": "text/html", "data": encoded})
                    logger.debug(f"Successfully fetched ticket page: {ticket_url}")
                else:
                    logger.warning(
                        f"Failed to fetch ticket page {ticket_url}: HTTP {response.status_code}"
                    )
            except requests.RequestException as e:
                logger.warning(f"Error fetching ticket page {ticket_url}: {e}")
            except Exception as e:
                logger.warning(
                    f"Unexpected error fetching ticket page {ticket_url}: {e}"
                )

        return documents

    def _call_llm_for_events(self, html: str, documents: List[dict]) -> List[dict]:
        """
        Call LLM to extract events from HTML. This is where the LLM API request is made.

        Args:
            html: HTML content to analyze
            documents: Additional documents for LLM context

        Returns:
            List of extracted event dicts

        Raises:
            LLMError: If LLM API call fails
            json.JSONDecodeError: If LLM response is not valid JSON
        """
        logger.info(f"Calling LLM for {self.url}")

        prompt = self._generate_prompt(
            html, self.url, has_ticket_pages=len(documents) > 0
        )
        logger.debug(f"Prompt (last 500 chars):\n{prompt[-500:]}")

        client = self._get_llm_client()
        response_text = client.complete(
            prompt, documents=documents if documents else None
        )

        logger.debug(f"LLM Response:\n{response_text}")
        events_data = self._parse_llm_response(response_text)
        logger.info(f"Parsed {len(events_data)} events from LLM response")

        if len(events_data) == 0:
            logger.debug(f"LLM response (first 500 chars): {response_text[:500]}")

        return events_data

    def _find_ticket_links(self, html: str) -> List[str]:
        """
        Find ticket/purchase platform links in HTML

        Args:
            html: HTML content to parse

        Returns:
            List of ticket platform URLs found
        """
        try:
            soup = BeautifulSoup(html, "lxml")
            ticket_links = []

            for link in soup.find_all("a", href=True):
                href = link["href"]
                # Check if link contains any ticket platform domain
                if any(platform in href.lower() for platform in TICKET_PLATFORMS):
                    # Make absolute if relative
                    if href.startswith("/"):
                        parsed_base = urlparse(self.url)
                        href = f"{parsed_base.scheme}://{parsed_base.netloc}{href}"
                    elif not href.startswith("http"):
                        # Skip invalid URLs
                        continue

                    ticket_links.append(href)

            # Deduplicate
            return list(set(ticket_links))

        except Exception as e:
            logger.warning(f"Error finding ticket links: {e}")
            return []

    def _fetch_html_with_playwright(self) -> str:
        """
        Fetch HTML using Playwright to render JavaScript-heavy pages

        Returns:
            HTML content of rendered page

        Raises:
            Exception: If page fetch/render fails
        """
        try:
            logger.debug(f"Fetching with Playwright: {self.url}")
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(self.url, timeout=30000, wait_until="networkidle")
                html = page.content()
                browser.close()
                logger.debug(f"Successfully rendered {self.url} with Playwright")
                return html
        except Exception as e:
            logger.error(f"Error fetching with Playwright: {e}")
            raise

    def _create_event(self, event_dict: dict) -> Event:
        """
        Create Event object from parsed dict

        Args:
            event_dict: Dict with event data from LLM

        Returns:
            Event object
        """
        # Parse date - handle both single dates and date ranges
        date_str = event_dict.get("date", "")
        start_date = date_str
        end_date = None

        # Check if this is a date range (e.g., "2025-06-15 to 2025-06-17")
        if " to " in date_str:
            parts = date_str.split(" to ")
            if len(parts) == 2:
                start_date = parts[0].strip()
                end_date = parts[1].strip()

        # Use extracted URL if available (for multiple_events), otherwise use page URL
        if self.multiple_events and event_dict.get("url"):
            extracted_url = event_dict.get("url")
            # Handle relative URLs
            if extracted_url.startswith("/"):
                # Relative URL - make absolute using base domain
                parsed_base = urlparse(self.url)
                detail_url = (
                    f"{parsed_base.scheme}://{parsed_base.netloc}{extracted_url}"
                )
            else:
                detail_url = extracted_url
        else:
            detail_url = self.url

        return Event(
            title=event_dict.get("title", "Unknown Event"),
            date=start_date,
            end_date=end_date,
            time=event_dict.get("time"),
            location=event_dict.get("location", ""),
            detail_url=detail_url,
            categories=self.categories,  # Categories from scraper config
            scraper=self.scraper_name,
        )

    def _log_status(self, status_code: int, error_message: str = None):
        """
        Log scraper status to database

        Args:
            status_code: HTTP status code or -1 for exceptions
            error_message: Error message if any
        """
        session = get_session()
        try:
            status = ScraperStatus(
                scraper_name=self.scraper_name,
                url=self.url,
                timestamp=time.time(),
                status_code=status_code,
                error_message=error_message,
            )
            session.add(status)
            session.commit()
        finally:
            session.close()

    def _filter_and_create_events(self, events_data: List[dict]) -> List[Event]:
        """Filter events by year and create Event objects."""
        events = []
        logger.debug(
            f"AI scraper {self.scraper_name}: parsing {len(events_data)} events from LLM"
        )
        for event_dict in events_data:
            date_str = event_dict.get("date", "")
            title = event_dict.get("title", "N/A")
            logger.debug(f"  Checking event: {title} ({date_str})")
            if self._is_valid_year(date_str):
                logger.debug("    ✓ Year valid, creating event")
                event = self._create_event(event_dict)
                events.append(event)
            else:
                logger.debug(f"    ✗ Filtered out - invalid year: {event_dict}")

        logger.debug(
            f"AI scraper {self.scraper_name}: "
            f"found {len(events)} valid events out of {len(events_data)}"
        )
        return events

    def _fetch_html_safe(self):
        """Fetch HTML with error handling."""
        try:
            html, status_code = self._fetch_main_html()
            self._log_status(status_code)
            return html
        except requests.HTTPError as e:
            status_code = -1
            if hasattr(e, "response") and e.response is not None:
                status_code = getattr(e.response, "status_code", -1)
            self._log_status(status_code, str(e))
            logger.error(f"HTTP error: {e}")
            raise
        except (requests.RequestException, Exception) as e:
            self._log_status(-1, f"{type(e).__name__}: {str(e)}")
            logger.error(f"Request error: {e}")
            raise

    def _get_cached_or_fetch_events(self, html, documents, cache_metadata):
        """Get events from cache or fetch via LLM."""
        cached_result = self.cache.get(self.url, html, metadata=cache_metadata)
        if cached_result is not None:
            logger.debug(f"Using cached AI response for {self.url}")
            return cached_result.get("events", [])

        events_data = self._call_llm_for_events(html, documents)
        self.cache.set(self.url, html, {"events": events_data}, metadata=cache_metadata)
        logger.debug(f"Cached AI response for {self.url}")
        return events_data

    def fetch(
        self,
        target_date: Optional[date] = None,
        date_range: Optional[tuple[date, date]] = None,
    ) -> EventCollection:
        """Fetch events using AI parsing."""
        del target_date, date_range
        try:
            html = self._fetch_html_safe()

            documents = self._fetch_ticket_pages(html)

            cache_metadata = {
                "categories": self.categories,
                "multiple_events": self.multiple_events,
                "ticket_page_hashes": [
                    self.cache._compute_hash(doc.get("data", "")) for doc in documents
                ],
            }

            events_data = self._get_cached_or_fetch_events(
                html, documents, cache_metadata
            )
            return EventCollection(self._filter_and_create_events(events_data))
        except (LLMError, json.JSONDecodeError) as e:
            self._log_status(-1, f"{type(e).__name__}: {str(e)}")
            logger.error(f"LLM error: {e}")
            return EventCollection([])
        except Exception:
            return EventCollection([])
