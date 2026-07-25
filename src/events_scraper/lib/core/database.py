"""
Database functionality for events and event collections
"""

import logging
import os
import re
from datetime import date
from datetime import datetime
from typing import Iterator
from typing import List
from typing import Optional
from typing import Union

from sqlalchemy.engine import make_url

from events_scraper.lib.core.orm_session import count_events_by_scraper
from events_scraper.lib.core.orm_session import init_database
from events_scraper.lib.core.orm_session import load_events_by_date
from events_scraper.lib.core.orm_session import load_events_by_date_range
from events_scraper.lib.core.orm_session import load_events_by_scraper_paginated

logger = logging.getLogger(__name__)


def load_events_from_database(
    target_date: Optional[date],
    group: str = None,
    scraper: str = None,
    include_cancelled: bool = False,
) -> List:
    """
    Load events from database for a specific date (including multi-day
    events active on that date)

    Returns ORM events directly.
    """
    events = load_events_by_date(target_date, group, scraper, include_cancelled)
    logger.debug(f"Loaded {len(events)} events from database for {target_date}")
    return events


class EventCollection:
    """Collection of events with filtering capabilities"""

    def __init__(self, events: List):
        # Events from database are already sorted, but manually created collections need sorting
        # Use try/except to handle mock objects in tests
        try:

            def sort_key(event):
                # Normalize date to date object for comparison
                if isinstance(event.date, str):
                    event_date = datetime.strptime(event.date, "%Y-%m-%d").date()
                else:
                    event_date = event.date
                return (event_date, self._event_time_for_sorting(event))

            self.events = sorted(events, key=sort_key)
        except (TypeError, AttributeError, ValueError):
            # If sorting fails (e.g., mock objects in tests), keep original order
            self.events = list(events)

    @staticmethod
    def _event_categories(event) -> List[str]:
        """Return normalized categories list for dataclass and ORM event objects."""
        categories = getattr(event, "categories", None)
        if isinstance(categories, list):
            return categories
        if isinstance(categories, str):
            return [cat.strip() for cat in categories.split(",") if cat.strip()]
        if hasattr(event, "categories_list"):
            return event.categories_list or []
        return []

    @staticmethod
    def _event_time_for_sorting(event) -> tuple:
        """Return sorting tuple for event time across dataclass and ORM events."""
        if hasattr(event, "time_for_sorting"):
            return event.time_for_sorting
        event_time = getattr(event, "time", None)
        if not event_time:
            return (2, "no_time")
        return (1, str(event_time))

    @classmethod
    def from_database(
        cls,
        target_date: Optional[date] = None,
        group: str = None,
        scraper: str = None,
        include_cancelled: bool = False,
    ) -> "EventCollection":
        """Create EventCollection by loading from database only (no scraping fallback)"""
        events = load_events_from_database(
            target_date, group, scraper, include_cancelled
        )
        return cls(events)

    @classmethod
    def from_database_by_scraper(
        cls, scraper: str, page: int = 1, per_page: int = 100, include_past: bool = False
    ) -> "EventCollection":
        """Create EventCollection by loading events for a scraper with pagination"""
        events = load_events_by_scraper_paginated(scraper, page, per_page, include_past)
        collection = cls(events)

        total_events = count_events_by_scraper(scraper, include_past)
        collection.pagination = {
            "page": page,
            "per_page": per_page,
            "total": total_events,
            "pages": (total_events + per_page - 1) // per_page,
            "has_prev": page > 1,
            "has_next": page * per_page < total_events,
        }

        return collection

    @classmethod
    def from_database_by_date_range(
        cls,
        start_date: date,
        end_date: date,
        group: str = None,
        scraper: str = None,
        include_cancelled: bool = False,
    ) -> "EventCollection":
        """Create EventCollection by loading from database for date range"""

        events = load_events_by_date_range(
            start_date, end_date, group, scraper, include_cancelled
        )
        return cls(events)

    def __iter__(self) -> Iterator:
        """Make EventCollection iterable"""
        return iter(self.events)

    def __len__(self) -> int:
        """Return number of events"""
        return len(self.events)

    def __getitem__(self, index):
        """Allow indexing"""
        return self.events[index]

    def _create_filtered_collection(self, filtered_events: List) -> "EventCollection":
        """Create a new EventCollection from filtered events, preserving pagination info"""
        new_collection = EventCollection(filtered_events)
        # Preserve pagination attribute if it exists
        if hasattr(self, "pagination"):
            new_collection.pagination = self.pagination
        return new_collection

    def exclude_categories(
        self, categories: List[Union[str, "re.Pattern"]]
    ) -> "EventCollection":
        """Return new collection excluding events with specified categories (exact match)"""
        filtered_events = []

        for event in self.events:
            should_exclude = False

            for category_filter in categories:
                # Use exact match for categories (not substring)
                if isinstance(category_filter, str):
                    if any(
                        cat.lower() == category_filter.lower()
                        for cat in self._event_categories(event)
                    ):
                        should_exclude = True
                        break
                else:
                    # Regex pattern
                    for event_category in self._event_categories(event):
                        if category_filter.search(event_category):
                            should_exclude = True
                            break
                if should_exclude:
                    break

            if not should_exclude:
                filtered_events.append(event)

        return self._create_filtered_collection(filtered_events)

    def include_categories(
        self, categories: List[Union[str, "re.Pattern"]]
    ) -> "EventCollection":
        """Return new collection including only events with specified categories (exact match)"""
        if not categories:
            return self._create_filtered_collection(self.events[:])

        filtered_events = []

        for event in self.events:
            should_include = False

            for category_filter in categories:
                # Use exact match for categories (not substring)
                if isinstance(category_filter, str):
                    if any(
                        cat.lower() == category_filter.lower()
                        for cat in self._event_categories(event)
                    ):
                        should_include = True
                        break
                else:
                    # Regex pattern
                    for event_category in self._event_categories(event):
                        if category_filter.search(event_category):
                            should_include = True
                            break
                if should_include:
                    break

            if should_include:
                filtered_events.append(event)

        return self._create_filtered_collection(filtered_events)

    def _matches_filter(self, text: str, filter_item: Union[str, "re.Pattern"]) -> bool:
        """Check if text matches a filter (string first, then regex fallback)"""

        if isinstance(filter_item, str):
            # First try string matching (case-insensitive substring)
            if filter_item.lower() in text.lower():
                return True

            # If string matching fails, try as regex pattern
            try:
                pattern = re.compile(filter_item, re.IGNORECASE)
                return bool(pattern.search(text))
            except re.error:
                # If regex compilation fails, stick with string match result (False)
                return False
        else:
            # Already compiled regex pattern
            return bool(filter_item.search(text))

    def exclude_titles(
        self, titles: List[Union[str, "re.Pattern"]]
    ) -> "EventCollection":
        """Return new collection excluding events with specified titles (string or regex)"""
        filtered_events = []
        for event in self.events:
            should_exclude = False
            for title_filter in titles:
                if self._matches_filter(event.title, title_filter):
                    should_exclude = True
                    break
            if not should_exclude:
                filtered_events.append(event)
        return self._create_filtered_collection(filtered_events)

    def exclude_locations(
        self, locations: List[Union[str, "re.Pattern"]]
    ) -> "EventCollection":
        """Return new collection excluding events with specified locations (string or regex)"""
        filtered_events = []
        for event in self.events:
            should_exclude = False
            if event.location:
                for location_filter in locations:
                    if self._matches_filter(event.location, location_filter):
                        should_exclude = True
                        break
            if not should_exclude:
                filtered_events.append(event)
        return self._create_filtered_collection(filtered_events)

    def include_titles(
        self, titles: List[Union[str, "re.Pattern"]]
    ) -> "EventCollection":
        """Return new collection including only events with specified titles (string or regex)"""
        if not titles:
            return self._create_filtered_collection(self.events[:])

        filtered_events = []
        for event in self.events:
            should_include = False
            for title_filter in titles:
                if self._matches_filter(event.title, title_filter):
                    should_include = True
                    break
            if should_include:
                filtered_events.append(event)
        return self._create_filtered_collection(filtered_events)

    def events_on_date(self, target_date) -> "EventCollection":
        """Return new collection containing only events active on the specified date"""
        if isinstance(target_date, str):
            try:
                target_date = date.fromisoformat(target_date)
            except ValueError:
                # If string parsing fails, return empty collection
                return self._create_filtered_collection([])

        filtered_events = []
        for event in self.events:
            if event.contains_date(target_date):
                filtered_events.append(event)

        return self._create_filtered_collection(filtered_events)

    def events_overlapping_range(self, start_date, end_date) -> "EventCollection":
        """Return new collection containing events that overlap with the specified date range"""
        # Convert string dates to date objects if needed
        start_date = self._parse_date_input(start_date)
        end_date = self._parse_date_input(end_date)

        if start_date is None or end_date is None:
            return self._create_filtered_collection([])

        filtered_events = []
        for event in self.events:
            if self._event_overlaps_range(event, start_date, end_date):
                filtered_events.append(event)

        return self._create_filtered_collection(filtered_events)

    def _parse_date_input(self, date_input):
        """Parse date input (string or date object) and return date object or None"""
        if isinstance(date_input, str):
            try:
                return date.fromisoformat(date_input)
            except ValueError:
                return None
        return date_input

    def _event_overlaps_range(self, event, start_date, end_date):
        """Check if event overlaps with the given date range"""
        try:
            # Handle both string and date object formats
            if isinstance(event.date, str):
                event_start = date.fromisoformat(event.date)
            else:
                event_start = event.date

            if event.end_date:
                if isinstance(event.end_date, str):
                    event_end = date.fromisoformat(event.end_date)
                else:
                    event_end = event.end_date
            else:
                event_end = event_start
            # Check for overlap: events overlap if start1 <= end2 and start2 <= end1
            return event_start <= end_date and start_date <= event_end
        except ValueError:
            # Skip events with invalid date formats
            return False

    def to_list(self) -> List:
        """Return list of events (for compatibility)"""
        return list(self.events)


def _check_sqlite_directory(normalized_url: str):
    """Ensure the parent directory of a SQLite file URL exists.

    Creates the directory tree if missing. Skips in-memory databases
    and non-SQLite URLs. Raises on bad URL syntax.
    """
    url_obj = make_url(normalized_url)

    if url_obj.drivername != "sqlite":
        return

    db_path = url_obj.database
    if not db_path or db_path == ":memory:":
        return

    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)


def configure_database(database_url: str = None, config=None):
    """Configure the database using ORM

    MIGRATION COMPLETE: Now uses only ORM initialization.
    """
    # Priority: CLI argument > config file > in-memory default
    if database_url:
        url = database_url
    elif config and config.get_database_url():
        url = config.get_database_url()
    else:
        # Default case: in-memory database (for tests, CLI, and simple usage)
        url = "sqlite:///:memory:"

    # Normalize URL - convert None and simple paths to proper SQLAlchemy URLs
    if url is None or url == ":memory:":
        normalized_url = "sqlite:///:memory:"
    elif not url.startswith(("sqlite://", "postgresql://", "mysql://")):
        # Convert simple file path to SQLite URL
        normalized_url = f"sqlite:///{url}"
    else:
        normalized_url = url

    # For SQLite file databases, ensure the parent directory exists
    if normalized_url.startswith("sqlite:///") and not normalized_url.endswith(
        ":memory:"
    ):
        _check_sqlite_directory(normalized_url)

    logger.debug(f"configure_database called: url={url}, normalized={normalized_url}")

    # Initialize ORM database with the configured URL
    logger.debug(f"Initializing ORM database with URL: {normalized_url}")
    init_database(normalized_url)
