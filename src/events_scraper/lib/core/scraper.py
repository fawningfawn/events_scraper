"""
Base scraper functionality for event scrapers
"""

import logging
import os
from abc import ABC
from datetime import date
from datetime import timedelta
from pathlib import Path
from typing import Iterator
from typing import List
from typing import Optional
from urllib.parse import urljoin

import certifi
import requests
import requests_cache
from bs4 import BeautifulSoup
from xdg import xdg_cache_home

from events_scraper.lib.constants import APP_CACHE_DIR_NAME
from events_scraper.lib.constants import HTTP_CACHE_DIR_NAME
from events_scraper.lib.constants import HTTP_CACHE_FILENAME
from events_scraper.lib.constants import HTTP_CACHE_TTL_SECONDS
from events_scraper.lib.core.database import EventCollection
from events_scraper.lib.core.geocoding import Geocoder
from events_scraper.lib.core.models import Event
from events_scraper.lib.core.models import EventDetail
from events_scraper.lib.core.orm_models import EventDetail as OrmEventDetail
from events_scraper.lib.core.orm_session import get_session

# Minimal headers that look like a real browser
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


logger = logging.getLogger(__name__)


class NetworkAccessBlockedError(RuntimeError):
    """Raised when a test run attempts a real network request."""


def _ensure_network_allowed_for_tests(url: str) -> None:
    """Block real network calls during test runs."""
    if os.getenv("EVENTS_TEST_RUN") == "1":
        raise NetworkAccessBlockedError(
            f"Network access blocked during tests for URL: {url}. "
            "Mock scraper network methods in tests."
        )


def http_get(
    url: str,
    *,
    timeout: int = 30,
    headers: Optional[dict] = None,
    verify: Optional[str] = None,
):
    """Centralized HTTP GET wrapper for scrapers."""
    _ensure_network_allowed_for_tests(url)
    kwargs = {"timeout": timeout}
    if headers is not None:
        kwargs["headers"] = headers
    if verify is not None:
        kwargs["verify"] = verify
    return requests.get(url, **kwargs)


# Set up HTTP cache (24 hour expiration)
_CACHE_DIR = Path(xdg_cache_home()) / APP_CACHE_DIR_NAME / HTTP_CACHE_DIR_NAME
_CACHE_DIR.mkdir(parents=True, exist_ok=True)
requests_cache.install_cache(
    str(_CACHE_DIR / HTTP_CACHE_FILENAME),
    backend="filesystem",
    expire_after=HTTP_CACHE_TTL_SECONDS,
)


def clear_http_cache():
    """Clear the HTTP cache and report statistics"""
    try:
        # Count cache files before clearing
        try:
            cache_files = list(_CACHE_DIR.glob("scraper_cache*"))
            before_count = len(cache_files)
        except Exception:
            before_count = None

        # Clear the cache
        requests_cache.clear()

        # Report results
        if before_count is not None:
            if before_count == 0:
                print("HTTP cache was already empty")
                logger.info("HTTP cache was already empty")
            else:
                print(f"Cleared {before_count} entries from HTTP cache")
                logger.info(f"Cleared {before_count} HTTP cache entries")
        else:
            # Fallback if we can't count
            print("HTTP cache cleared")
            logger.info("HTTP cache cleared")

    except Exception as e:
        logger.error(f"Error clearing HTTP cache: {e}")
        print(f"Error clearing cache: {e}")


class BaseEventScraper(ABC):
    """
    Abstract base class for city event scrapers.

    This class provides the foundation for scraping events from city websites.
    Scrapers follow a database-first architecture where events are automatically
    stored in SQLite database for instant loading and caching.

    Architecture Overview:
    - Database-first: Events stored in SQLite, no file caching
    - Smart fallback: Database loading with automatic scraping fallback
    - Progressive enhancement: Basic data first, geocoding on-demand
    - Clean separation: Scrapers parse, database stores, UI displays

    To implement a new scraper:
    1. Inherit from BaseEventScraper
    2. Implement the 3 required abstract methods
    3. Optionally override other methods for customization

    Required Abstract Methods:
    - get_event_containers(): Find event elements on page
    - extract_event_from_container(): Parse single event data
    - find_next_page_url(): Handle pagination

    Example Implementation:
        class MyScraper(BaseEventScraper):
            def __init__(self, target_date=None):
                super().__init__("https://example.com", "City Name", target_date)

            def get_event_containers(self, soup):
                return soup.find_all("div", class_="event-item")

            def extract_event_from_container(self, container, target_date):
                title = container.find("h2").get_text(strip=True)
                date_str = container.find(".date").get_text(strip=True)
                # Parse date_str to match target_date, return None if no match
                if parsed_date != target_date:
                    return None
                return Event(title=title, date=date_str, ...)

            def find_next_page_url(self, soup, current_url):
                next_link = soup.find("a", class_="next-page")
                return urljoin(current_url, next_link["href"]) if next_link else None

    Usage:
        scraper = MyScraper(date(2025, 8, 5))
        events = scraper.fetch()  # Returns EventCollection
        for event in events:
            print(event.title)
    """

    def __init__(
        self,
        base_url: str,
        city_context: str = "",
        target_date: Optional[date] = None,
        only_new: bool = False,
    ):
        """
        Initialize the scraper.

        Args:
            base_url: Base URL of the website to scrape (e.g., "https://example.com")
            city_context: City name for geocoding context (e.g., "Paris, France")
            target_date: Date to scrape events for (defaults to today)
            only_new: If True, only fetch details for events that don't already exist in database
        """
        self.base_url = base_url
        self.target_date = target_date or date.today()
        self.geocoder = Geocoder(city_context) if city_context else None
        self.only_new = only_new
        self._events: Optional[List[Event]] = None

    @property
    def always_tags(self) -> List[str]:
        """
        Tags that should always be added to events from this scraper.

        Subclasses can override this to automatically tag all their events.
        Returns:
            List of tag strings to always add to events
        """
        return []

    def should_stop_pagination(
        self, soup: BeautifulSoup, target_date: date, page_events: List, page_count: int
    ) -> bool:
        """Determine if pagination should stop - can be overridden by subclasses"""
        # Default implementation: just continue until no more events found
        return len(page_events) == 0

    @property
    def content_filters(self) -> List[str]:
        """
        CSS selectors for content sections to ignore during detail parsing.

        Can be overridden by subclasses to provide site-specific filters.
        For complex filtering logic, override filter_content() method instead.

        Returns:
            List of CSS selectors to remove from content
        """
        return []

    def filter_content(self, soup: BeautifulSoup) -> BeautifulSoup:
        """
        Remove unwanted sections from content soup.

        Default implementation removes elements matching content_filters selectors.
        Can be overridden by subclasses for complex filtering logic.

        Args:
            soup: BeautifulSoup object to filter

        Returns:
            Filtered BeautifulSoup object
        """
        for selector in self.content_filters:
            for element in soup.select(selector):
                element.decompose()
        return soup

    def get_detail_url_prefix(self) -> str:
        """Get the prefix for detail URLs in output - can be overridden"""
        return self.base_url

    def get_event_containers(self, soup: BeautifulSoup) -> List:
        """
        Extract event containers from page HTML.

        This method should find all elements on the page that represent individual events.
        Each container should contain the data needed to create an Event object.

        Args:
            soup: BeautifulSoup object of the events page

        Returns:
            List of HTML elements (BeautifulSoup elements) that contain event data

        Example:
            def get_event_containers(self, soup):
                # Find all divs with class 'event-card'
                return soup.find_all("div", class_="event-card")

            # Or find events in a table
            def get_event_containers(self, soup):
                return soup.select("table.events tbody tr")
        """
        # Default implementation for non-HTML scrapers (API-based, etc.)
        return []

    def extract_event_from_container(
        self, container, target_date: date
    ) -> Optional[Event]:
        """
        Extract event data from a single container element.

        This method parses one event container and extracts all relevant information
        to create an Event object. IMPORTANT: Return None if the event doesn't match
        the target_date to filter out irrelevant events.

        Args:
            container: HTML element containing event data (from get_event_containers)
            target_date: The date we're looking for events on

        Returns:
            Event object if the event matches target_date, None otherwise

        Example:
            def extract_event_from_container(self, container, target_date):
                # Extract basic data
                title = container.find("h3").get_text(strip=True)
                date_elem = container.find(".event-date")
                time_elem = container.find(".event-time")

                # Parse date string to date object
                date_str = date_elem.get_text(strip=True)  # e.g., "2025-08-05"
                event_date = datetime.strptime(date_str, "%Y-%m-%d").date()

                # Filter by target date
                if event_date != target_date:
                    return None

                # Build detail URL
                link = container.find("a")
                detail_url = urljoin(self.base_url, link["href"]) if link else None

                return Event(
                    title=title,
                    date=date_str,
                    time=time_elem.get_text(strip=True) if time_elem else None,
                    location="Default Location",
                    detail_url=detail_url,
                    categories=["Entertainment"],
                    scraper="my-scraper"
                )
        """
        # Default implementation for non-HTML scrapers (API-based, etc.)
        return None

    def find_next_page_url(self, soup: BeautifulSoup, current_url: str) -> Optional[str]:
        """
        Find URL for next page of events.

        This method handles pagination by finding the link to the next page.
        Return None if there are no more pages or the site doesn't use pagination.

        Args:
            soup: BeautifulSoup object of current page
            current_url: URL of the current page being processed

        Returns:
            Absolute URL of next page, or None if no next page exists

        Example:
            def find_next_page_url(self, soup, current_url):
                # Find "Next" button/link
                next_link = soup.find("a", class_="pagination-next")
                if next_link and next_link.get("href"):
                    return urljoin(current_url, next_link["href"])
                return None

            # For sites with numbered pagination
            def find_next_page_url(self, soup, current_url):
                # Extract current page number from URL
                page_match = re.search(r'page=(\\d+)', current_url)
                current_page = int(page_match.group(1)) if page_match else 1

                # Check if next page exists
                next_page_link = soup.find("a", {"data-page": str(current_page + 1)})
                if next_page_link:
                    return f"{self.base_url}/events?page={current_page + 1}"
                return None
        """
        # Default implementation for non-HTML scrapers (API-based, etc.)
        return None

    @property
    def scraper_name(self) -> str:
        if hasattr(self, "_scraper_name_override"):
            return self._scraper_name_override
        base_name = getattr(
            self.__class__, "_scraper_name", self.__class__.__name__.lower()
        )
        module_parts = self.__class__.__module__.split(".")
        if "scrapers" in module_parts:
            scraper_idx = module_parts.index("scrapers")
            if scraper_idx + 1 < len(module_parts):
                city = module_parts[scraper_idx + 1]
                if city != "hybrid":
                    if "." not in base_name:
                        return f"{city}.{base_name}"
        return base_name

    def get_upstream_id(self, detail_url: str) -> Optional[str]:
        """
        Extract the website's internal event ID from the detail URL.

        Optional method for scrapers that want to track the source event ID.
        Override this method in subclasses to extract IDs from URLs.

        Args:
            detail_url: The event detail URL from the website

        Returns:
            The upstream event ID if extractable, None otherwise

        Example:
            class MyScraper(BaseEventScraper):
                def get_upstream_id(self, detail_url: str) -> Optional[str]:
                    # Extract event-ID from URLs like https://site.com/event-12345/date-678
                    if "event-" in detail_url:
                        return detail_url.split("event-")[1].split("/")[0]
                    return None
        """
        # Default implementation - no upstream ID extraction
        return None

    def _enrich_event_provenance(self, event: Event) -> Event:
        """Populate scraper provenance fields on an event before save."""
        if not event.scraper:
            event.scraper = self.scraper_name

        if getattr(event, "upstream_id", None) is None and getattr(
            event, "detail_url", None
        ):
            event.upstream_id = self.get_upstream_id(event.detail_url)

        return event

    def extract_events_from_page(
        self, soup: BeautifulSoup, target_date: date
    ) -> List[Event]:
        """Extract events from a page that match the target date"""
        events = []
        event_containers = self.get_event_containers(soup)

        for container in event_containers:
            event = self.extract_event_from_container(container, target_date)
            if event:
                events.append(self._enrich_event_provenance(event))

        return events

    def __iter__(self) -> Iterator[Event]:
        """Make scraper iterable - fetches events if not already done"""
        if self._events is None:
            self._events = self._fetch_single_day_events()
        return iter(self._events)

    def fetch(
        self,
        target_date: Optional[date] = None,
        date_range: Optional[tuple[date, date]] = None,
    ) -> EventCollection:
        """Fetch events for one date or a date range."""
        if target_date is not None and date_range is not None:
            raise ValueError("Cannot specify both target_date and date_range")

        if date_range is not None:
            start_date, end_date = date_range
            return self.fetch_date_range(start_date, end_date)

        if target_date is not None:
            original_target_date = self.target_date
            try:
                self.target_date = target_date
                self._events = self._fetch_single_day_events(target_date)
            finally:
                self.target_date = original_target_date
        elif self._events is None:
            self._events = self._fetch_single_day_events()
        return EventCollection(self._events)

    def fetch_date_range(self, start_date: date, end_date: date) -> EventCollection:
        """
        Fetch events for a date range. Default implementation iterates dates.
        Scrapers can override for more efficient implementation.

        Args:
            start_date: Start date of range (inclusive)
            end_date: End date of range (inclusive)

        Returns:
            EventCollection containing events from all dates in range
        """
        # Check if scraper explicitly doesn't support ranges (optional feature)
        if hasattr(self, "allow_ranges") and not self.allow_ranges:
            logger.debug(
                f"{self.scraper_name} has allow_ranges=False, using day-by-day fallback"
            )

        all_events = []
        original_target_date = self.target_date

        try:
            for current_date in self._iter_dates_inclusive(start_date, end_date):
                try:
                    # Update target_date for this iteration
                    self.target_date = current_date
                    # Clear cached events to ensure fresh scraping for each date
                    self._events = None

                    # Fetch events for this specific date
                    events = self.fetch()
                    all_events.extend(events.to_list())

                    logger.debug(
                        f"Fetched {len(events.to_list())} events for {current_date}"
                    )

                except Exception as e:
                    logger.error(f"Error fetching events for {current_date}: {e}")
                    # Continue with next date instead of failing entire range

        finally:
            # Always restore original target_date
            self.target_date = original_target_date
            self._events = None  # Clear cache

        logger.info(
            f"Fetched total of {len(all_events)} events for date range {start_date} to {end_date}"
        )
        return EventCollection(all_events)

    @staticmethod
    def _iter_dates_inclusive(start_date: date, end_date: date) -> Iterator[date]:
        """Yield each date in an inclusive date range."""
        current_date = start_date
        while current_date <= end_date:
            yield current_date
            current_date += timedelta(days=1)

    def _fetch_single_day_events(
        self, target_date: Optional[date] = None
    ) -> List[Event]:
        """Internal method to fetch all events for a specific date with pagination"""
        if target_date is None:
            target_date = self.target_date

        # Update self.target_date so that events_url property uses correct date
        original_target_date = self.target_date
        self.target_date = target_date

        logger.info(f"Fetching all events for {target_date} from {self.scraper_name}")
        all_events = []
        current_url = self.events_url if hasattr(self, "events_url") else self.base_url
        visited_urls = set()
        max_pages = 50
        page_count = 0

        while current_url and page_count < max_pages:
            if current_url in visited_urls:
                break

            visited_urls.add(current_url)
            page_count += 1

            logger.debug(f"Fetching page {page_count}: {current_url}")

            soup = self._fetch_page_content(current_url)
            if not soup:
                break

            page_events = self.extract_events_from_page(soup, target_date)
            all_events.extend(page_events)
            logger.info(
                f"Found {len(page_events)} events on page {page_count}, total: {len(all_events)}"
            )

            if self.should_stop_pagination(soup, target_date, page_events, page_count):
                break

            current_url = self.find_next_page_url(soup, current_url)
            if current_url:
                logger.debug(f"Next URL: {current_url}")
            else:
                logger.debug(f"No next page found on page {page_count}")
                break

        # Restore original target_date
        self.target_date = original_target_date
        return all_events

    def _fetch_page_content(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch and parse page content with caching"""
        html_content = self._fetch_page_from_web(url)

        if not html_content:
            return None

        return self._parse_html_content(html_content, url)

    def _fetch_page_from_web(self, url: str) -> Optional[str]:
        """Fetch page content from web"""
        logger.info(f"Fetching page from web: {url}")
        try:
            response = http_get(
                url, timeout=30, headers=BROWSER_HEADERS, verify=certifi.where()
            )
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    def _parse_html_content(
        self, html_content: str, url: str
    ) -> Optional[BeautifulSoup]:
        """Parse HTML content into BeautifulSoup object"""
        try:
            return BeautifulSoup(html_content, "html.parser")
        except Exception as e:
            logger.error(f"Error parsing HTML from {url}: {e}")
            return None

    def fetch_detail_content(self, detail_url: str) -> Optional[EventDetail]:
        """Fetch and store event detail content, returning EventDetail object"""
        logger.debug(f"Fetching detail content for: {detail_url}")
        if not detail_url:
            return None

        # Check if we already have this detail in database
        existing_detail = EventDetail.get_detail(detail_url)
        if existing_detail:
            if self.only_new:
                # In only_new mode, don't re-fetch existing details
                logger.debug(f"Only new mode: skipping existing detail for {detail_url}")
                return None
            else:
                # Normal mode: return existing detail
                return existing_detail

        full_url = self._resolve_detail_url(detail_url)

        html_content = self._fetch_content_from_web(full_url)
        if not html_content:
            # Store failure case
            detail = EventDetail(
                url=detail_url,
                content="Error fetching detail content",
                scraper=getattr(self, "scraper_name", "unknown"),
            )
            detail.save()
            return detail

        parsed_content = self._parse_detail_content(html_content)

        # Create and store EventDetail object
        detail = EventDetail(
            url=detail_url,
            content=parsed_content,
            scraper=getattr(self, "scraper_name", "unknown"),
        )

        detail.save()
        return detail

    def _resolve_detail_url(self, detail_url: str) -> str:
        """Convert relative URL to absolute URL"""
        if detail_url.startswith("http"):
            return detail_url
        return urljoin(self.base_url, detail_url)

    def _fetch_content_from_web(self, url: str) -> Optional[str]:
        """Fetch content from web"""
        logger.info(f"Fetching event detail: {url}")
        try:
            response = http_get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.error(f"Error fetching detail: {e}")
            return None

    def _fetch_json_from_web(
        self,
        url: str,
        *,
        timeout: int = 30,
        headers: Optional[dict] = None,
        verify: Optional[str] = None,
    ) -> Optional[dict]:
        """Fetch and parse JSON from web using centralized HTTP wrapper."""
        try:
            response = http_get(
                url,
                timeout=timeout,
                headers=headers,
                verify=verify,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Error fetching JSON from {url}: {e}")
            return None

    def _ensure_network_allowed(self, url: str) -> None:
        """Block real network calls during test runs."""
        _ensure_network_allowed_for_tests(url)

    def _reraise_if_network_blocked(self, exc: Exception) -> None:
        """Re-raise no-network test guard exceptions so they are never swallowed."""
        if isinstance(exc, NetworkAccessBlockedError):
            raise exc

    def _parse_detail_content(self, html_content: str) -> str:
        """Parse detail content from HTML"""
        soup = BeautifulSoup(html_content, "html.parser")

        # Apply content filtering to remove unwanted sections
        soup = self.filter_content(soup)

        content_section = self._find_content_section(soup)
        if content_section:
            return self._extract_structured_text(content_section)

        return self._extract_fallback_content(soup)

    def _find_content_section(self, soup: BeautifulSoup):
        """Find main content section in HTML"""
        return soup.find("section", class_="content") or soup.find(
            "div", class_="content"
        )

    def _extract_structured_text(self, content_section) -> str:
        """Extract structured text from content section"""
        content_text = []
        for element in content_section.find_all(["p", "h2", "h3", "li"]):
            text = element.get_text(strip=True)
            if text:
                if element.name in ["h2", "h3"]:
                    content_text.append(f"\n{text}\n")
                else:
                    content_text.append(text)
        return "\n".join(content_text).strip()

    def _extract_fallback_content(self, soup: BeautifulSoup) -> str:
        """Extract content using fallback method"""
        title_elem = soup.find("h1", class_="headline")
        if title_elem:
            content_container = title_elem.find_next("section") or title_elem.find_next(
                "div", class_="content"
            )
            if content_container:
                return content_container.get_text(strip=True)
        return "Could not extract event details"

    def clear_cache_for_url(self, detail_url: str):
        """Clear cached content for a specific URL from database using ORM"""
        if not detail_url:
            return

        session = get_session()
        try:
            # Find and delete the EventDetail using ORM
            event_detail = (
                session.query(OrmEventDetail)
                .filter(OrmEventDetail.url == detail_url)
                .first()
            )

            if event_detail:
                session.delete(event_detail)
                session.commit()
                logger.info(f"Cleared database cache for URL: {detail_url}")
        finally:
            session.close()

    def geocode_event_location(self, event: Event) -> Event:
        """
        Geocode an event's location and return updated event.

        This should be called by scrapers that want to add coordinates to events.
        By default, this is done lazily/asynchronously to avoid blocking event fetching.

        Args:
            event: Event object to geocode

        Returns:
            Event object with updated coordinates (if successful)
        """
        if not event.location or not self.geocoder or event.latitude is not None:
            return event

        logger.debug(f"Geocoding event location on-demand: {event.location}")
        coordinates = self.geocoder.geocode(event.location)

        if coordinates:
            # Update the event with coordinates
            event.latitude, event.longitude = coordinates
            logger.debug(f"Successfully geocoded {event.location} to {coordinates}")
        else:
            logger.debug(f"Failed to geocode location: {event.location}")

        return event
