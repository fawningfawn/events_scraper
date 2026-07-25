"""Contract tests for unified scraper `fetch()` signature."""

import inspect
import unittest

from events_scraper.lib.core import EventCollection
from events_scraper.lib.core.scraper import BaseEventScraper
from events_scraper.lib.scrapers.ai_scraper import AIScraper
from events_scraper.lib.scrapers.hybrid.hybrid_scraper import HybridScraper


class _TestCityScraper(BaseEventScraper):
    def __init__(self):
        pass

    def get_event_containers(self, soup):
        return []

    def extract_event_from_container(self, container, target_date):
        return None

    def find_next_page_url(self, soup, current_url):
        return None

    def fetch(self, target_date=None, date_range=None):

        return EventCollection([])


class TestFetchContract(unittest.TestCase):
    def test_fetch_signature_consistent_across_scraper_types(self):
        for scraper_class in (
            BaseEventScraper,
            _TestCityScraper,
            HybridScraper,
            AIScraper,
        ):
            signature = inspect.signature(scraper_class.fetch)
            target_param = signature.parameters.get("target_date")
            range_param = signature.parameters.get("date_range")

            self.assertIsNotNone(target_param, scraper_class.__name__)
            self.assertIsNotNone(range_param, scraper_class.__name__)
            self.assertIsNone(target_param.default, scraper_class.__name__)
            self.assertIsNone(range_param.default, scraper_class.__name__)
