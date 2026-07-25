"""
Core functionality for event scraping - public API

This module maintains backward compatibility by re-exporting all public classes and functions
from the split modules.
"""

# Re-export external dependencies that tests might expect
import requests
from geopy.geocoders import Nominatim

# Import all public APIs from split modules
from events_scraper.lib.core.database import configure_database
from events_scraper.lib.core.database import EventCollection
from events_scraper.lib.core.database import load_events_from_database
from events_scraper.lib.core.geocoding import GeocodeCache
from events_scraper.lib.core.geocoding import Geocoder
from events_scraper.lib.core.logging import setup_logging
from events_scraper.lib.core.models import Event
from events_scraper.lib.core.models import EventDetail
from events_scraper.lib.core.scraper import BaseEventScraper
from events_scraper.lib.core.utils import parse_day_month_with_reference_year
from events_scraper.lib.core.utils import parse_time_string

# Define what gets exported when using "from events_scraper.lib.core import *"
__all__ = [
    # Models
    "Event",
    "EventDetail",
    # Database functionality
    "EventCollection",
    "configure_database",
    "load_events_from_database",
    # Geocoding
    "GeocodeCache",
    "Geocoder",
    # Scraper base class
    "BaseEventScraper",
    # Utilities
    "parse_time_string",
    "parse_day_month_with_reference_year",
    # Logging
    "setup_logging",
    # External dependencies
    "requests",
    "Nominatim",
]
