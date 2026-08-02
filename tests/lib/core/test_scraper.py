"""
Comprehensive tests for scraper functionality
"""

import unittest
from datetime import date
from unittest.mock import Mock
from unittest.mock import patch

import requests
from bs4 import BeautifulSoup

from events_scraper.lib.core.models import Event
from events_scraper.lib.core.models import EventDetail
from events_scraper.lib.core.orm_models import EventDetail as OrmEventDetail
from events_scraper.lib.core.orm_session import get_session
from events_scraper.lib.core.scraper import BaseEventScraper
from tests.lib.core.test_base import DatabaseTestCase


class ConcreteEventScraper(BaseEventScraper):
    """Concrete implementation of BaseEventScraper for testing"""

    @property
    def scraper_name(self) -> str:
        return "test_scraper"

    def get_event_containers(self, soup):
        return soup.find_all("div", class_="event")

    def extract_event_from_container(self, container, target_date):
        title_elem = container.find("h3")
        if not title_elem:
            return None

        return Event(
            title=title_elem.text.strip(),
            date=target_date,
            location="Test Location",
            detail_url="/event/1",
            scraper="test_scraper",
        )

    def find_next_page_url(self, soup, current_url):
        next_link = soup.find("a", class_="next")
        return next_link.get("href") if next_link else None


class UpstreamEventScraper(ConcreteEventScraper):
    """Concrete scraper that implements upstream-id extraction."""

    def get_upstream_id(self, detail_url: str):
        if "event-" in detail_url:
            return detail_url.split("event-")[1]
        if "/event/" in detail_url:
            return detail_url.rsplit("/event/", 1)[1]
        return None


class TestBaseEventScraper(unittest.TestCase):
    """Test the BaseEventScraper abstract class"""

    def setUp(self):
        """Set up test environment"""
        self.test_date = date(2025, 7, 26)
        self.scraper = ConcreteEventScraper(
            base_url="https://example.com",
            city_context="Test City, Country",
            target_date=self.test_date,
        )

    def test_init_with_all_params(self):
        """Test scraper initialization with all parameters"""
        scraper = ConcreteEventScraper(
            base_url="https://test.com",
            city_context="Paris, France",
            target_date=date(2025, 1, 1),
        )

        self.assertEqual(scraper.base_url, "https://test.com")
        self.assertEqual(scraper.target_date, date(2025, 1, 1))
        self.assertIsNotNone(scraper.geocoder)
        self.assertEqual(scraper.geocoder.city_context, "Paris, France")
        self.assertIsNone(scraper._events)

    def test_init_defaults(self):
        """Test scraper initialization with default parameters"""
        with patch("events_scraper.lib.core.scraper.date") as mock_date:
            mock_date.today.return_value = date(2025, 7, 26)
            mock_date.side_effect = lambda *args, **kw: date(*args, **kw)

            scraper = ConcreteEventScraper(base_url="https://test.com")

            self.assertEqual(scraper.target_date, date(2025, 7, 26))
            self.assertIsNone(scraper.geocoder)

    def test_should_stop_pagination_default(self):
        """Test default pagination stopping logic"""
        soup = BeautifulSoup("<html></html>", "html.parser")

        # Should continue if events found
        result = self.scraper.should_stop_pagination(soup, self.test_date, [1, 2, 3], 1)
        self.assertFalse(result)

        # Should stop if no events found
        result = self.scraper.should_stop_pagination(soup, self.test_date, [], 1)
        self.assertTrue(result)

    def test_get_detail_url_prefix_default(self):
        """Test default detail URL prefix"""
        result = self.scraper.get_detail_url_prefix()
        self.assertEqual(result, "https://example.com")

    def test_extract_events_from_page(self):
        """Test extracting events from a page"""
        html = """
        <html>
            <div class="event">
                <h3>Event 1</h3>
            </div>
            <div class="event">
                <h3>Event 2</h3>
            </div>
            <div class="other">
                <h3>Not an event</h3>
            </div>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")

        events = self.scraper.extract_events_from_page(soup, self.test_date)

        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].title, "Event 1")
        self.assertEqual(events[1].title, "Event 2")
        for event in events:
            self.assertEqual(event.date, self.test_date)

    def test_extract_events_from_page_populates_upstream_id(self):
        """Base extraction path should populate `upstream_id` from scraper hook."""
        scraper = UpstreamEventScraper(
            base_url="https://example.com",
            city_context="Test City, Country",
            target_date=self.test_date,
        )
        html = """
        <html>
            <div class="event">
                <h3>Event 1</h3>
            </div>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")

        events = scraper.extract_events_from_page(soup, self.test_date)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].upstream_id, "1")

    def test_extract_events_from_page_no_containers(self):
        """Test extracting events when no containers found"""
        html = "<html><div class='other'>Not an event</div></html>"
        soup = BeautifulSoup(html, "html.parser")

        events = self.scraper.extract_events_from_page(soup, self.test_date)

        self.assertEqual(len(events), 0)

    def test_extract_events_from_page_invalid_containers(self):
        """Test extracting events with invalid containers"""
        html = """
        <html>
            <div class="event">
                <!-- No h3 element -->
                <p>Invalid event</p>
            </div>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")

        events = self.scraper.extract_events_from_page(soup, self.test_date)

        self.assertEqual(len(events), 0)

    def test_iter_fetches_events_once(self):
        """Test that iterator fetches events only once"""
        with patch.object(self.scraper, "_fetch_single_day_events") as mock_fetch:
            mock_fetch.return_value = [
                Event(title="Event 1", date=self.test_date, scraper="test"),
                Event(title="Event 2", date=self.test_date, scraper="test"),
            ]

            # First iteration
            events1 = list(self.scraper)
            # Second iteration
            events2 = list(self.scraper)

            # Should only fetch once
            mock_fetch.assert_called_once()
            self.assertEqual(len(events1), 2)
            self.assertEqual(len(events2), 2)

    def test_fetch_returns_event_collection(self):
        """Test that fetch returns EventCollection"""
        with patch.object(self.scraper, "_fetch_single_day_events") as mock_fetch:
            mock_events = [Event(title="Test", date=self.test_date, scraper="test")]
            mock_fetch.return_value = mock_events

            result = self.scraper.fetch()

            # Check that it returns EventCollection-like object
            self.assertEqual(len(result.events), 1)
            self.assertEqual(result.events[0].title, "Test")

    def test_fetch_with_target_date(self):
        """Test fetch(target_date=...) path"""
        with patch.object(self.scraper, "_fetch_single_day_events") as mock_fetch:
            mock_events = [Event(title="Test", date=self.test_date, scraper="test")]
            mock_fetch.return_value = mock_events

            result = self.scraper.fetch(target_date=self.test_date)

            mock_fetch.assert_called_once_with(self.test_date)
            self.assertEqual(result.to_list(), mock_events)

    @patch("events_scraper.lib.core.scraper.logger")
    def test_fetch_single_day_events_basic_flow(self, mock_logging):
        """Test basic flow of `_fetch_single_day_events`"""
        # Mock the scraper methods
        with (
            patch.object(self.scraper, "_fetch_page_content") as mock_fetch_page,
            patch.object(self.scraper, "extract_events_from_page") as mock_extract,
            patch.object(self.scraper, "find_next_page_url") as mock_find_next,
        ):

            # Setup mocks
            mock_soup = BeautifulSoup("<html></html>", "html.parser")
            mock_fetch_page.return_value = mock_soup
            mock_extract.return_value = [
                Event(title="Test", date=self.test_date, scraper="test")
            ]
            mock_find_next.return_value = None  # No next page

            result = self.scraper._fetch_single_day_events()

            self.assertEqual(len(result), 1)
            self.assertEqual(result[0].title, "Test")
            mock_fetch_page.assert_called_once()
            mock_extract.assert_called_once_with(mock_soup, self.test_date)

    @patch("events_scraper.lib.core.scraper.logger")
    def test_fetch_single_day_events_pagination(self, mock_logging):
        """Test `_fetch_single_day_events` with pagination"""
        with (
            patch.object(self.scraper, "_fetch_page_content") as mock_fetch_page,
            patch.object(self.scraper, "extract_events_from_page") as mock_extract,
            patch.object(self.scraper, "find_next_page_url") as mock_find_next,
        ):

            # Setup pagination: page 1 -> page 2 -> None
            mock_soup1 = BeautifulSoup(
                "<html><a class='next' href='/page2'></a></html>", "html.parser"
            )
            mock_soup2 = BeautifulSoup("<html></html>", "html.parser")
            mock_fetch_page.side_effect = [mock_soup1, mock_soup2]

            mock_extract.side_effect = [
                [Event(title="Event 1", date=self.test_date, scraper="test")],
                [Event(title="Event 2", date=self.test_date, scraper="test")],
            ]
            mock_find_next.side_effect = ["/page2", None]

            result = self.scraper._fetch_single_day_events()

            self.assertEqual(len(result), 2)
            self.assertEqual(mock_fetch_page.call_count, 2)
            self.assertEqual(mock_extract.call_count, 2)

    @patch("events_scraper.lib.core.scraper.logger")
    def test_fetch_single_day_events_circular_pagination_protection(self, mock_logging):
        """Test protection against circular pagination"""
        with (
            patch.object(self.scraper, "_fetch_page_content") as mock_fetch_page,
            patch.object(self.scraper, "extract_events_from_page") as mock_extract,
            patch.object(self.scraper, "find_next_page_url") as mock_find_next,
        ):

            mock_soup = BeautifulSoup("<html></html>", "html.parser")
            mock_fetch_page.return_value = mock_soup
            mock_extract.return_value = [
                Event(title="Test", date=self.test_date, scraper="test")
            ]
            mock_find_next.return_value = "https://example.com"  # Same URL always

            self.scraper._fetch_single_day_events()

            # Should only fetch once due to circular protection
            self.assertEqual(mock_fetch_page.call_count, 1)

    @patch("events_scraper.lib.core.scraper.logger")
    def test_fetch_single_day_events_max_pages_protection(self, mock_logging):
        """Test protection against infinite pagination"""
        with (
            patch.object(self.scraper, "_fetch_page_content") as mock_fetch_page,
            patch.object(self.scraper, "extract_events_from_page") as mock_extract,
            patch.object(self.scraper, "find_next_page_url") as mock_find_next,
        ):

            mock_soup = BeautifulSoup("<html></html>", "html.parser")
            mock_fetch_page.return_value = mock_soup
            mock_extract.return_value = [
                Event(title="Test", date=self.test_date, scraper="test")
            ]
            # Always return a new URL to trigger max pages
            mock_find_next.side_effect = lambda soup, url: f"{url}/next"

            self.scraper._fetch_single_day_events()

            # Should stop at max_pages (50)
            self.assertEqual(mock_fetch_page.call_count, 50)

    @patch("events_scraper.lib.core.scraper.logger")
    def test_fetch_single_day_events_with_events_url_attribute(self, mock_logging):
        """Test that events_url attribute is used if present"""
        self.scraper.events_url = "https://example.com/events"

        with (
            patch.object(self.scraper, "_fetch_page_content") as mock_fetch_page,
            patch.object(self.scraper, "extract_events_from_page") as mock_extract,
            patch.object(self.scraper, "find_next_page_url") as mock_find_next,
        ):

            mock_soup = BeautifulSoup("<html></html>", "html.parser")
            mock_fetch_page.return_value = mock_soup
            mock_extract.return_value = []
            mock_find_next.return_value = None

            self.scraper._fetch_single_day_events()

            mock_fetch_page.assert_called_once_with("https://example.com/events")


class TestBaseEventScraperDateRange(DatabaseTestCase):
    """Test BaseEventScraper date range functionality"""

    def setUp(self):
        """Set up test environment"""
        super().setUp()  # Initialize database
        self.test_date = date(2025, 7, 25)
        self.end_date = date(2025, 7, 27)
        self.scraper = ConcreteEventScraper(
            base_url="https://example.com",
            city_context="Test City, Germany",
            target_date=self.test_date,
        )

    def test_fetch_date_range_default_implementation(self):
        """Test that fetch_date_range calls fetch() for each date by default"""
        with patch.object(self.scraper, "fetch") as mock_fetch:
            # Mock fetch to return different events for each date
            mock_events_day1 = Mock()
            mock_event1 = Mock()
            mock_event1.title = "Event 1"
            mock_event1.time_for_sorting = date(2025, 7, 25)
            mock_events_day1.to_list.return_value = [mock_event1]

            mock_events_day2 = Mock()
            mock_event2 = Mock()
            mock_event2.title = "Event 2"
            mock_event2.time_for_sorting = date(2025, 7, 26)
            mock_events_day2.to_list.return_value = [mock_event2]

            mock_events_day3 = Mock()
            mock_event3 = Mock()
            mock_event3.title = "Event 3"
            mock_event3.time_for_sorting = date(2025, 7, 27)
            mock_events_day3.to_list.return_value = [mock_event3]

            mock_fetch.side_effect = [
                mock_events_day1,
                mock_events_day2,
                mock_events_day3,
            ]

            # Call fetch_date_range
            result = self.scraper.fetch_date_range(self.test_date, self.end_date)

            # Should call fetch() for each date in range
            self.assertEqual(mock_fetch.call_count, 3)

            # Should return EventCollection with combined events
            self.assertEqual(len(result.to_list()), 3)

    def test_fetch_date_range_single_day(self):
        """Test fetch_date_range with single day (start_date == end_date)"""
        with patch.object(self.scraper, "fetch") as mock_fetch:
            mock_events = Mock()
            mock_event = Mock()
            mock_event.title = "Event 1"
            mock_event.time_for_sorting = date(2025, 7, 25)
            mock_events.to_list.return_value = [mock_event]
            mock_fetch.return_value = mock_events

            # Call with same start and end date
            result = self.scraper.fetch_date_range(self.test_date, self.test_date)

            # Should call fetch() once
            mock_fetch.assert_called_once()
            self.assertEqual(len(result.to_list()), 1)

    def test_fetch_date_range_allow_ranges_false(self):
        """Test that scrapers can opt out of date range support"""

        # Create a scraper that doesn't support ranges
        class NonRangeScraper(ConcreteEventScraper):
            allow_ranges = False

        scraper = NonRangeScraper(
            base_url="https://example.com", target_date=self.test_date
        )

        with patch.object(scraper, "fetch") as mock_fetch:
            mock_events = Mock()
            mock_event = Mock()
            mock_event.title = "Event 1"
            mock_event.time_for_sorting = date(2025, 7, 25)
            mock_events.to_list.return_value = [mock_event]
            mock_fetch.return_value = mock_events

            # Should fall back to day-by-day even with allow_ranges=False
            scraper.fetch_date_range(self.test_date, self.end_date)

            # Should still call fetch() for each date
            self.assertEqual(mock_fetch.call_count, 3)

    def test_fetch_date_range_respects_target_date_changes(self):
        """Test that fetch_date_range updates target_date for each day"""
        fetch_dates = []

        def mock_fetch():
            # Capture the target_date when fetch is called
            fetch_dates.append(self.scraper.target_date)
            mock_events = Mock()
            mock_event = Mock()
            mock_event.title = f"Event {len(fetch_dates)}"
            mock_event.time_for_sorting = self.scraper.target_date
            mock_events.to_list.return_value = [mock_event]
            return mock_events

        with patch.object(self.scraper, "fetch", side_effect=mock_fetch):
            result = self.scraper.fetch_date_range(self.test_date, self.end_date)

            # Should have called fetch for each date in sequence
            expected_dates = [date(2025, 7, 25), date(2025, 7, 26), date(2025, 7, 27)]
            self.assertEqual(fetch_dates, expected_dates)
            self.assertEqual(len(result.to_list()), 3)

    def test_fetch_date_range_error_handling(self):
        """Test that errors in individual days don't stop the entire range"""

        def mock_fetch_with_error():
            if self.scraper.target_date == date(2025, 7, 26):
                raise requests.RequestException("Network error on day 2")
            mock_events = Mock()
            mock_event = Mock()
            mock_event.title = f"Event {self.scraper.target_date.day}"
            mock_event.time_for_sorting = self.scraper.target_date
            mock_events.to_list.return_value = [mock_event]
            return mock_events

        with patch.object(self.scraper, "fetch", side_effect=mock_fetch_with_error):
            result = self.scraper.fetch_date_range(self.test_date, self.end_date)

            # Should get events from days that worked (25th and 27th)
            self.assertEqual(len(result.to_list()), 2)

    @patch("events_scraper.lib.core.scraper.http_get")
    def test_fetch_page_from_web_success(self, mock_get):
        """Test successful web page fetching"""
        mock_response = Mock()
        mock_response.text = "<html><body>Test content</body></html>"
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = self.scraper._fetch_page_from_web("https://example.com")

        self.assertEqual(result, "<html><body>Test content</body></html>")
        # Verify it was called with BROWSER_HEADERS and certifi
        self.assertEqual(mock_get.call_count, 1)
        call_args = mock_get.call_args
        self.assertEqual(call_args[1]["timeout"], 30)
        self.assertIn("User-Agent", call_args[1]["headers"])
        self.assertIsNotNone(call_args[1]["verify"])

    @patch("events_scraper.lib.core.scraper.http_get")
    @patch("events_scraper.lib.core.scraper.logger")
    def test_fetch_page_from_web_request_exception(self, mock_logging, mock_get):
        """Test web page fetching with request exception"""
        mock_get.side_effect = requests.RequestException("Network error")

        result = self.scraper._fetch_page_from_web("https://example.com")

        self.assertIsNone(result)
        mock_logging.error.assert_called_once()

    def test_parse_html_content_success(self):
        """Test successful HTML parsing"""
        html_content = "<html><body><h1>Test</h1></body></html>"

        result = self.scraper._parse_html_content(html_content, "https://example.com")

        self.assertIsInstance(result, BeautifulSoup)
        self.assertIsNotNone(result.find("h1"))
        self.assertEqual(result.find("h1").text, "Test")

    @patch("events_scraper.lib.core.scraper.logger")
    def test_parse_html_content_exception(self, mock_logging):
        """Test HTML parsing with exception"""
        # This is hard to trigger with BeautifulSoup, so we'll mock it
        with patch("events_scraper.lib.core.scraper.BeautifulSoup") as mock_bs:
            mock_bs.side_effect = Exception("Parse error")

            result = self.scraper._parse_html_content("invalid", "https://example.com")

            self.assertIsNone(result)
            mock_logging.error.assert_called_once()

    def test_fetch_page_content_success(self):
        """Test successful page content fetching"""
        with (
            patch.object(self.scraper, "_fetch_page_from_web") as mock_fetch,
            patch.object(self.scraper, "_parse_html_content") as mock_parse,
        ):

            mock_fetch.return_value = "<html></html>"
            mock_soup = BeautifulSoup("<html></html>", "html.parser")
            mock_parse.return_value = mock_soup

            result = self.scraper._fetch_page_content("https://example.com")

            self.assertEqual(result, mock_soup)
            mock_fetch.assert_called_once_with("https://example.com")
            mock_parse.assert_called_once_with("<html></html>", "https://example.com")

    def test_fetch_page_content_web_failure(self):
        """Test page content fetching when web fetch fails"""
        with patch.object(self.scraper, "_fetch_page_from_web") as mock_fetch:
            mock_fetch.return_value = None

            result = self.scraper._fetch_page_content("https://example.com")

            self.assertIsNone(result)

    def test_resolve_detail_url_absolute(self):
        """Test resolving absolute detail URLs"""
        result = self.scraper._resolve_detail_url("https://other.com/event/1")
        self.assertEqual(result, "https://other.com/event/1")

    def test_resolve_detail_url_relative(self):
        """Test resolving relative detail URLs"""
        result = self.scraper._resolve_detail_url("/event/1")
        self.assertEqual(result, "https://example.com/event/1")

        result = self.scraper._resolve_detail_url("event/1")
        self.assertEqual(result, "https://example.com/event/1")

    @patch("events_scraper.lib.core.models.EventDetail.get_detail")
    def test_fetch_detail_content_cached(self, mock_get_detail):
        """Test fetching detail content from cache"""
        mock_detail = EventDetail(
            url="/event/1", content="Cached content", scraper="test_scraper"
        )
        mock_get_detail.return_value = mock_detail

        result = self.scraper.fetch_detail_content("/event/1")

        self.assertEqual(result, mock_detail)
        mock_get_detail.assert_called_once_with("/event/1")

    @patch("events_scraper.lib.core.models.EventDetail.get_detail")
    def test_fetch_detail_content_empty_url(self, mock_get_detail):
        """Test fetching detail content with empty URL"""
        result = self.scraper.fetch_detail_content("")
        self.assertIsNone(result)

        result = self.scraper.fetch_detail_content(None)
        self.assertIsNone(result)

        mock_get_detail.assert_not_called()

    @patch("events_scraper.lib.core.models.save_event_detail")
    @patch("events_scraper.lib.core.models.EventDetail.get_detail")
    def test_fetch_detail_content_web_failure(self, mock_get_detail, mock_save_detail):
        """Test fetching detail content when web fetch fails.

        A failed fetch must NOT be persisted - otherwise the error is returned
        forever via the existing-detail fast path on subsequent runs.
        """
        mock_get_detail.return_value = None

        with patch.object(self.scraper, "_fetch_content_from_web") as mock_fetch:
            mock_fetch.return_value = None

            result = self.scraper.fetch_detail_content("/event/1")

            self.assertIsNone(result)
            mock_save_detail.assert_not_called()

    @patch("events_scraper.lib.core.models.save_event_detail")
    @patch("events_scraper.lib.core.models.EventDetail.get_detail")
    def test_fetch_detail_content_failure_not_cached(
        self, mock_get_detail, mock_save_detail
    ):
        """A failed fetch must be retried on the next run, not served from cache."""
        mock_get_detail.return_value = None

        with patch.object(self.scraper, "_fetch_content_from_web") as mock_fetch:
            mock_fetch.return_value = None

            # First attempt fails - must not write anything to the database
            self.scraper.fetch_detail_content("/event/1")
            mock_save_detail.assert_not_called()

            # Second attempt should try the network again (still no cached entry)
            self.scraper.fetch_detail_content("/event/1")
            self.assertEqual(mock_fetch.call_count, 2)

    @patch("events_scraper.lib.core.models.save_event_detail")
    @patch("events_scraper.lib.core.models.EventDetail.get_detail")
    def test_fetch_detail_content_success(self, mock_get_detail, mock_save_detail):
        """Test successful detail content fetching"""
        mock_get_detail.return_value = None

        with (
            patch.object(self.scraper, "_fetch_content_from_web") as mock_fetch,
            patch.object(self.scraper, "_parse_detail_content") as mock_parse,
        ):

            mock_fetch.return_value = "<html>Detail content</html>"
            mock_parse.return_value = "Parsed detail content"

            result = self.scraper.fetch_detail_content("/event/1")

            self.assertIsNotNone(result)
            self.assertEqual(result.url, "/event/1")
            self.assertEqual(result.content, "Parsed detail content")
            self.assertEqual(result.scraper, "test_scraper")
            mock_save_detail.assert_called_once()

    @patch("events_scraper.lib.core.scraper.http_get")
    def test_fetch_content_from_web_success(self, mock_get):
        """Test successful content fetching from web"""
        mock_response = Mock()
        mock_response.text = "Detail content"
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = self.scraper._fetch_content_from_web("https://example.com/detail")

        self.assertEqual(result, "Detail content")
        mock_get.assert_called_once_with("https://example.com/detail", timeout=30)

    @patch("events_scraper.lib.core.scraper.http_get")
    @patch("events_scraper.lib.core.scraper.logger")
    def test_fetch_content_from_web_exception(self, mock_logging, mock_get):
        """Test content fetching with exception"""
        mock_get.side_effect = requests.RequestException("Network error")

        result = self.scraper._fetch_content_from_web("https://example.com/detail")

        self.assertIsNone(result)
        mock_logging.error.assert_called_once()

    def test_parse_detail_content_with_content_section(self):
        """Test parsing detail content with content section"""
        html = """
        <html>
            <section class="content">
                <h2>Event Details</h2>
                <p>Description of the event</p>
                <h3>Location Info</h3>
                <p>Address details</p>
            </section>
        </html>
        """

        result = self.scraper._parse_detail_content(html)

        self.assertIn("Event Details", result)
        self.assertIn("Description of the event", result)
        self.assertIn("Location Info", result)
        self.assertIn("Address details", result)

    def test_parse_detail_content_fallback(self):
        """Test parsing detail content with fallback method"""
        html = """
        <html>
            <h1 class="headline">Event Title</h1>
            <section>
                <p>Fallback content</p>
            </section>
        </html>
        """

        result = self.scraper._parse_detail_content(html)

        self.assertIn("Fallback content", result)

    def test_parse_detail_content_no_content(self):
        """Test parsing detail content when no content found"""
        html = "<html><body>No structured content</body></html>"

        result = self.scraper._parse_detail_content(html)

        self.assertEqual(result, "Could not extract event details")

    def test_find_content_section(self):
        """Test finding content section in HTML"""
        html = """
        <html>
            <section class="content">Content here</section>
            <div class="content">Also content</div>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")

        result = self.scraper._find_content_section(soup)

        self.assertIsNotNone(result)
        self.assertEqual(result.name, "section")

    def test_extract_structured_text(self):
        """Test extracting structured text from content section"""
        html = """
        <div>
            <h2>Main Title</h2>
            <p>First paragraph</p>
            <h3>Subtitle</h3>
            <p>Second paragraph</p>
            <li>List item</li>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        content_section = soup.find("div")

        result = self.scraper._extract_structured_text(content_section)

        self.assertIn("Main Title", result)
        self.assertIn("First paragraph", result)
        self.assertIn("Subtitle", result)
        self.assertIn("Second paragraph", result)
        self.assertIn("List item", result)

    def test_extract_fallback_content(self):
        """Test extracting content using fallback method"""
        html = """
        <html>
            <h1 class="headline">Title</h1>
            <section>Fallback content here</section>
        </html>
        """
        soup = BeautifulSoup(html, "html.parser")

        result = self.scraper._extract_fallback_content(soup)

        self.assertEqual(result, "Fallback content here")

    def test_extract_fallback_content_no_headline(self):
        """Test fallback content extraction with no headline"""
        html = "<html><body>No headline</body></html>"
        soup = BeautifulSoup(html, "html.parser")

        result = self.scraper._extract_fallback_content(soup)

        self.assertEqual(result, "Could not extract event details")

    def test_clear_cache_for_url_success(self):
        """Test successful cache clearing"""
        # First create an EventDetail to delete
        detail = EventDetail(
            url="/event/1", content="Test content", scraper="test_scraper"
        )
        detail.save()

        # Verify it exists

        session = get_session()
        try:
            existing = (
                session.query(OrmEventDetail)
                .filter(OrmEventDetail.url == "/event/1")
                .first()
            )
            self.assertIsNotNone(existing)
        finally:
            session.close()

        # Clear the cache
        self.scraper.clear_cache_for_url("/event/1")

        # Verify it was deleted
        session = get_session()
        try:
            existing = (
                session.query(OrmEventDetail)
                .filter(OrmEventDetail.url == "/event/1")
                .first()
            )
            self.assertIsNone(existing)
        finally:
            session.close()

    def test_clear_cache_for_url_empty(self):
        """Test cache clearing with empty URL"""
        # Should not raise any exception and should handle gracefully
        self.scraper.clear_cache_for_url("")
        self.scraper.clear_cache_for_url(None)
        # Test passes if no exception is raised
        self.assertTrue(True)  # Explicit assertion

    def test_geocode_event_location_no_location(self):
        """Test geocoding event with no location"""
        event = Event(title="Test", date=self.test_date, scraper="test")

        result = self.scraper.geocode_event_location(event)

        self.assertEqual(result, event)
        self.assertIsNone(result.latitude)

    def test_geocode_event_location_no_geocoder(self):
        """Test geocoding event with no geocoder"""
        scraper = ConcreteEventScraper(base_url="https://example.com")  # No city_context
        event = Event(
            title="Test", date=self.test_date, location="Test Location", scraper="test"
        )

        result = scraper.geocode_event_location(event)

        self.assertEqual(result, event)
        self.assertIsNone(result.latitude)

    def test_geocode_event_location_already_geocoded(self):
        """Test geocoding event that already has coordinates"""
        event = Event(
            title="Test",
            date=self.test_date,
            location="Test Location",
            latitude=49.0,
            longitude=6.0,
            scraper="test",
        )

        result = self.scraper.geocode_event_location(event)

        self.assertEqual(result, event)
        self.assertEqual(result.latitude, 49.0)

    def test_geocode_event_location_success(self):
        """Test successful event location geocoding"""
        event = Event(
            title="Test", date=self.test_date, location="Test Location", scraper="test"
        )

        with patch.object(self.scraper.geocoder, "geocode") as mock_geocode:
            mock_geocode.return_value = (49.2401, 6.9969)

            result = self.scraper.geocode_event_location(event)

            self.assertEqual(result.latitude, 49.2401)
            self.assertEqual(result.longitude, 6.9969)
            mock_geocode.assert_called_once_with("Test Location")

    def test_geocode_event_location_failure(self):
        """Test failed event location geocoding"""
        event = Event(
            title="Test",
            date=self.test_date,
            location="Unknown Location",
            scraper="test",
        )

        with patch.object(self.scraper.geocoder, "geocode") as mock_geocode:
            mock_geocode.return_value = None

            result = self.scraper.geocode_event_location(event)

            self.assertIsNone(result.latitude)
            self.assertIsNone(result.longitude)
