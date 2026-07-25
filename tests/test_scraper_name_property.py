"""Mechanism test for canonical `scraper_name` generation."""

from events_scraper.lib.core import EventCollection
from events_scraper.lib.core.scraper import BaseEventScraper


class _CityScraper(BaseEventScraper):
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


def test_scraper_name_generation_mechanism():
    s = _CityScraper()
    s._scraper_name_override = "paris.testscraper"
    assert s.scraper_name == "paris.testscraper"
