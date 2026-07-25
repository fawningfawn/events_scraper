"""
HybridScraper: Combines API pagination with AI detail page parsing

Reuses BaseEventScraper for pagination/listing functionality.
Only adds AI-powered detail page parsing via LLMAnalysisMixin.
"""

import logging
import time
from abc import abstractmethod
from datetime import date
from datetime import datetime
from datetime import timedelta
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

from bs4 import BeautifulSoup

from events_scraper.lib.core.database import EventCollection
from events_scraper.lib.core.llm_mixin import LLMAnalysisMixin
from events_scraper.lib.core.models import Event
from events_scraper.lib.core.scraper import BaseEventScraper

logger = logging.getLogger(__name__)


class HybridScraper(BaseEventScraper, LLMAnalysisMixin):
    """
    Base class for scrapers that use API pagination + AI detail parsing.

    Reuses BaseEventScraper for pagination/listing functionality.
    Adds AI-powered detail page parsing via LLMAnalysisMixin.

    Subclasses must implement:
    - get_api_url(page): Get API URL for given page number
    - parse_api_response(response_json): Parse API response, return (events_data, has_more)
    - get_detail_url_from_event(event_data): Extract detail URL from event data
    """

    # Rate limiting delay between requests (in seconds)
    rate_limit_delay = 0.5

    def __init__(
        self,
        base_url: str,
        scraper_name: str,
        city_context: str = "",
        target_date: Optional[date] = None,
        only_new: bool = False,
    ):
        """
        Initialize HybridScraper.

        Args:
            base_url: Base URL of the website
            scraper_name: Unique identifier for this scraper
            city_context: City name for geocoding context
            target_date: Date to scrape events for
            only_new: If True, only fetch new events
        """
        BaseEventScraper.__init__(self, base_url, city_context, target_date, only_new)
        LLMAnalysisMixin.__init__(self)
        self._scraper_name = scraper_name

    @property
    def scraper_name(self) -> str:
        """Return the scraper name identifier"""
        return self._scraper_name

    def fetch(
        self,
        target_date: Optional[date] = None,
        date_range: Optional[tuple[date, date]] = None,
    ) -> EventCollection:
        """Fetch events using API pagination + AI detail parsing.

        Calls fetch_date_range() with appropriate date range based on target_date.
        """
        if target_date is not None and date_range is not None:
            raise ValueError("Cannot specify both target_date and date_range")
        if date_range is not None:
            return self.fetch_date_range(date_range[0], date_range[1])
        if target_date is not None:
            return self.fetch_date_range(target_date, target_date)
        if self.target_date:
            return self.fetch_date_range(self.target_date, self.target_date)
        # For no target date, fetch today onwards for next 30 days
        today = date.today()
        thirty_days = today + timedelta(days=30)
        return self.fetch_date_range(today, thirty_days)

    @abstractmethod
    def get_api_url(self, page: int) -> str:
        """
        Get API URL for given page number.

        Args:
            page: Page number (1-indexed)

        Returns:
            Full URL to API endpoint for this page
        """
        raise NotImplementedError

    @abstractmethod
    def parse_api_response(self, response_json: Dict) -> Tuple[List[Dict], bool]:
        """
        Parse API response to extract events and pagination info.

        Args:
            response_json: Parsed JSON response from API

        Returns:
            Tuple of (events_list, has_more_pages)
            - events_list: List of event data dicts
            - has_more_pages: Boolean indicating if more pages exist
        """
        raise NotImplementedError

    @abstractmethod
    def get_detail_url_from_event(self, event_data: Dict) -> str:
        """
        Extract detail page URL from event data.

        Args:
            event_data: Event data from API response

        Returns:
            Full URL to event detail page
        """
        raise NotImplementedError

    def fetch_date_range(self, start_date: date, end_date: date) -> EventCollection:
        """
        Fetch events for date range using API pagination.

        Paginate through API until all events within date range are fetched,
        then parse detail pages with AI.

        Args:
            start_date: Start date for event range
            end_date: End date for event range

        Returns:
            EventCollection with fetched events
        """
        logger.info(f"Fetching events from {start_date} to {end_date} via API")

        all_events = []
        page = 1
        should_continue = True

        while should_continue:
            events_data, has_more = self._fetch_api_page(page)

            if not events_data:
                logger.debug(f"No events on page {page}, stopping pagination")
                break

            new_events, found_after_range = self._process_events_page(
                events_data, start_date, end_date
            )
            all_events.extend(new_events)

            should_continue = has_more and not found_after_range
            page += 1

        logger.info(
            f"Found {len(all_events)} events for date range {start_date} to {end_date}"
        )
        return EventCollection(all_events)

    def _fetch_api_page(self, page: int) -> tuple:
        """Fetch a single API page and return (events_data, has_more)"""
        api_url = self.get_api_url(page)
        logger.info(f"Fetching API page {page}: {api_url}")

        try:
            api_response = self._fetch_json_from_web(api_url)
            if not api_response:
                return [], False
            events_data, has_more = self.parse_api_response(api_response)
            logger.info(
                f"API page {page}: got {len(events_data)} events, has_more={has_more}"
            )
            return events_data, has_more
        except Exception as e:  # ap-ignore
            self._reraise_if_network_blocked(e)
            logger.error(f"Error fetching API page {page}: {e}")
            return [], False

    def _process_events_page(
        self, events_data: List[Dict], start_date: date, end_date: date
    ) -> tuple:
        """Process events from API page, return (events, found_after_range)"""
        all_events = []
        found_after_range = False

        for event_data in events_data:
            try:
                detail_url = self.get_detail_url_from_event(event_data)
                if not detail_url:
                    logger.debug("No detail URL found for event, skipping")
                    continue

                event = self._fetch_and_parse_detail(
                    event_data, detail_url, start_date, end_date
                )
                if event:
                    all_events.append(event)
                elif self._is_event_after_range(event_data, end_date):
                    found_after_range = True

                time.sleep(self.rate_limit_delay)

            except Exception as e:  # ap-ignore
                self._reraise_if_network_blocked(e)
                logger.debug(f"Error processing event: {e}")
                continue

        return all_events, found_after_range

    def _is_event_after_range(self, event_data: Dict, end_date: date) -> bool:
        """Check if event date is after end_date"""
        if not hasattr(event_data, "get"):
            return False

        # Try multiple date field names (different APIs use different conventions)
        event_date_str = event_data.get("start_date") or event_data.get("date")
        if not event_date_str:
            return False

        try:
            event_date = datetime.fromisoformat(event_date_str).date()
            return event_date > end_date
        except (ValueError, TypeError):
            return False

    def _fetch_and_parse_detail(
        self, event_data: Dict, detail_url: str, start_date: date, end_date: date
    ) -> Optional[Event]:
        """
        Fetch and parse event detail page with AI.

        Args:
            event_data: Event data from API
            detail_url: URL to event detail page
            start_date: Start date for filtering
            end_date: End date for filtering

        Returns:
            Event object if successfully parsed, None otherwise
        """
        try:
            # Fetch detail page HTML
            html = self._fetch_page_from_web(detail_url)
            if not html:
                return None

            # Parse with AI
            prompt = """
Extract event details from this HTML page. Return JSON with:
- title (string): Event name
- date (YYYY-MM-DD format): Event date
- time (HH:MM format, or null if unknown): Event time
- location (string, or null): Event location/venue
- description (string, or null): Event description

Only include the JSON object, no other text.
"""
            detail_info = self.analyze_with_llm(html, prompt)

            if not detail_info or not isinstance(detail_info, dict):
                logger.debug(f"Failed to parse detail page: {detail_url}")
                return None

            # Validate date is in range
            detail_date_str = detail_info.get("date")
            if detail_date_str:
                try:
                    detail_date = datetime.fromisoformat(detail_date_str).date()
                    if not (start_date <= detail_date <= end_date):
                        return None
                except (ValueError, TypeError) as e:
                    logger.debug(f"Error parsing detail date: {e}")
                    return None

            # Create Event object
            event = Event(
                title=detail_info.get("title", "Untitled"),
                date=detail_date_str or "",
                time=detail_info.get("time"),
                location=detail_info.get("location"),
                categories=list(self.always_tags) if self.always_tags else [],
                scraper=self.scraper_name,
                detail_url=detail_url,
            )

            return event

        except Exception as e:
            self._reraise_if_network_blocked(e)
            logger.debug(f"Error fetching/parsing detail page {detail_url}: {e}")
            return None

    # BaseEventScraper abstract methods - not used in HybridScraper
    # but required by ABC

    def get_event_containers(self, soup: BeautifulSoup) -> List:
        """Not used in HybridScraper - uses API instead"""
        return []

    def extract_event_from_container(
        self, container, target_date: date
    ) -> Optional[Event]:
        """Not used in HybridScraper - uses API instead"""
        return None

    def find_next_page_url(self, soup: BeautifulSoup, current_url: str) -> Optional[str]:
        """Not used in HybridScraper - uses API instead"""
        return None
