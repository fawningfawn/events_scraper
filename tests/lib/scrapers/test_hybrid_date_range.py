"""Test that HybridScraper respects date range and doesn't paginate infinitely"""

import unittest
from datetime import date
from unittest.mock import patch

from events_scraper.lib.core.models import Event
from events_scraper.lib.scrapers.hybrid.hybrid_scraper import HybridScraper


class TestHybridScraperDateRange(unittest.TestCase):
    """Test HybridScraper pagination stops at date range boundaries"""

    def setUp(self):
        """Set up test scraper"""

        class TestHybridScraper(HybridScraper):
            def get_api_url(self, page: int) -> str:
                return f"https://example.com/api/events/?page={page}"

            def parse_api_response(self, response_json):
                events = response_json.get("results", [])
                has_more = response_json.get("next") is not None
                return events, has_more

            def get_detail_url_from_event(self, event_data):
                return event_data.get("url", "")

        self.scraper_class = TestHybridScraper

    def test_pagination_stops_when_events_are_after_date_range(self):
        """Test that pagination stops when encountering events after end_date"""
        scraper = self.scraper_class(
            base_url="https://example.com/",
            scraper_name="test.scraper",
            target_date=date(2026, 3, 21),
        )

        start_date = date(2026, 3, 21)
        end_date = date(2026, 3, 22)

        # Page 1: Events on 2026-03-21 and 2026-03-22 (within range)
        # Page 2: Events on 2026-04-01 (after range) - should trigger stop
        pages_fetched = []

        def mock_fetch_api_page(page):
            pages_fetched.append(page)

            if page == 1:
                # Events within range
                return [
                    {
                        "id": 1,
                        "slug": "event1",
                        "url": "https://example.com/event1",
                        "start_date": "2026-03-21T10:00:00",
                    },
                    {
                        "id": 2,
                        "slug": "event2",
                        "url": "https://example.com/event2",
                        "start_date": "2026-03-22T10:00:00",
                    },
                ], True  # has_more=True
            elif page == 2:
                # Event after range - should trigger stop
                return [
                    {
                        "id": 3,
                        "slug": "event3",
                        "url": "https://example.com/event3",
                        "start_date": "2026-04-01T10:00:00",  # After end_date
                    },
                ], True  # has_more=True (but should stop anyway)
            else:
                # Should never reach here
                return [], False

        with patch.object(scraper, "_fetch_api_page", side_effect=mock_fetch_api_page):
            with patch.object(scraper, "_fetch_and_parse_detail") as mock_detail:
                # Mock detail parsing to return events
                mock_detail.side_effect = (
                    lambda event_data, detail_url, start_date, end_date: (
                        Event(
                            title=event_data.get("slug"),
                            date=event_data.get("start_date", "").split("T")[0],
                            scraper="test.scraper",
                            detail_url=detail_url,
                        )
                        if event_data.get("start_date", "").startswith(
                            start_date.isoformat()
                        )
                        or event_data.get("start_date", "").startswith(
                            end_date.isoformat()
                        )
                        else None
                    )
                )

                scraper.fetch_date_range(start_date, end_date)

        # Should have fetched page 1 and page 2, but NOT page 3
        # Page 2 has event after range, so pagination should stop
        self.assertLessEqual(
            len(pages_fetched),
            2,
            f"Expected to fetch at most 2 pages, but fetched {len(pages_fetched)} pages. "
            f"Pagination should stop when encountering events after the date range",
        )
