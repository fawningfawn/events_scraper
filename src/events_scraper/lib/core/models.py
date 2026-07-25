"""
Data models for events and event details
"""

import dataclasses
import logging
import time as time_module
from dataclasses import dataclass
from datetime import date
from datetime import datetime
from datetime import time
from typing import List
from typing import Optional
from typing import Union

from events_scraper.lib.core import orm_session
from events_scraper.lib.core.orm_models import Event as OrmEvent
from events_scraper.lib.core.orm_models import EventDetail as OrmEventDetail
from events_scraper.lib.core.orm_session import get_session
from events_scraper.lib.core.orm_session import save_event_detail
from events_scraper.lib.core.orm_session import upsert_event

logger = logging.getLogger(__name__)


@dataclass
class Event:
    """Base event data class"""

    title: str
    date: Union[date, str]  # Can be date object (from DB) or string (from scrapers)
    id: Optional[int] = None  # Database ID, populated when loaded from database
    time: Optional[Union[time, str]] = None
    location: Optional[str] = None
    categories: List[str] = None
    detail_url: Optional[str] = None
    upstream_id: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    scraper: Optional[str] = None  # Name/identifier of the scraper that found this event
    cancelled: bool = False  # Whether this event has been marked as cancelled
    ctime: Optional[float] = None  # Creation time, defaults to now
    end_date: Optional[Union[date, str]] = None  # End date for multi-day events

    def __post_init__(self):
        if self.categories is None:
            self.categories = []
        if self.ctime is None:
            self.ctime = time_module.time()
        # Don't auto-store in database - let caller decide when to store
        logger.debug(f"Event created: {self.title}")

    def _parse_date_field(self, date_field: Union[date, str]) -> Optional[date]:
        """Parse a date field (string or date object) into a date object."""
        if isinstance(date_field, str):
            try:
                return datetime.strptime(date_field, "%Y-%m-%d").date()
            except ValueError as e:
                logger.warning(f"Could not parse date '{date_field}': {e}")
                return None
        return date_field

    def _create_orm_event(
        self, parsed_date: date, parsed_end_date: Optional[date]
    ) -> OrmEvent:
        """Create ORM Event object from dataclass Event."""
        return OrmEvent(
            title=self.title,
            date=parsed_date,
            year=parsed_date.year,
            end_date=parsed_end_date,
            time=str(self.time) if self.time else None,
            location=self.location,
            categories_list=self.categories,
            detail_url=self.detail_url,
            upstream_id=self.upstream_id,
            scraper=self.scraper,
            latitude=self.latitude,
            longitude=self.longitude,
            ctime=self.ctime if hasattr(self, "ctime") else time_module.time(),
        )

    def save(self):
        """Save event to database using ORM.

        Converts old dataclass Event to ORM Event and saves using proper SQLAlchemy session.
        """
        # Verify database is initialized
        if not orm_session._engine:
            logger.error("Database engine not initialized - event.save() will fail!")
            return False

        logger.debug(f"Database: {orm_session._engine.url}")

        # Parse dates
        parsed_date = self._parse_date_field(self.date)
        if parsed_date is None:
            logger.warning(f"Skipping event save due to invalid date: {self.date}")
            return False

        parsed_end_date = (
            self._parse_date_field(self.end_date) if self.end_date else None
        )

        # Create and save ORM event
        orm_event = self._create_orm_event(parsed_date, parsed_end_date)

        # Capture fields before session is closed
        scraper = orm_event.scraper
        location = orm_event.location

        try:
            upsert_event(orm_event)
            logger.info(
                f"Saved event: {self.title} on {parsed_date} | "
                f"scraper={scraper} location={location}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to save event '{self.title}': {e}")
            raise

    @property
    def time_for_sorting(self) -> tuple:
        """Get time value optimized for sorting - returns (sort_priority, sort_value)"""
        if isinstance(self.time, time):
            return (0, self.time)  # Priority 0: actual times first
        elif isinstance(self.time, str) and self.time:
            return (1, self.time)  # Priority 1: string times after actual times
        else:
            return (2, "no_time")  # Priority 2: events without time last

    @property
    def formatted_time(self) -> str:
        """Get formatted time string for display"""
        if isinstance(self.time, time):
            return self.time.strftime("%H:%M")
        elif isinstance(self.time, str) and self.time:
            # Strip seconds from string times (e.g., "09:30:00" -> "09:30")
            if ":" in self.time and len(self.time.split(":")) >= 2:
                parts = self.time.split(":")
                return f"{parts[0]}:{parts[1]}"
            else:
                return self.time
        else:
            return ""

    @property
    def date_str(self) -> str:
        """Get date as string in YYYY-MM-DD format"""
        if isinstance(self.date, date):
            return self.date.strftime("%Y-%m-%d")
        else:
            return str(self.date)

    @property
    def end_date_str(self) -> Optional[str]:
        """Get end_date as string in YYYY-MM-DD format"""
        if not self.end_date:
            return None
        if isinstance(self.end_date, date):
            return self.end_date.strftime("%Y-%m-%d")
        else:
            return str(self.end_date)

    @property
    def is_multi_day(self) -> bool:
        """Check if this is a multi-day event"""
        return self.end_date is not None and self.end_date != self.date

    @property
    def duration_days(self) -> int:
        """Get duration in days (1 for single-day events, >1 for multi-day)"""
        if not self.is_multi_day:
            return 1

        try:
            start_date = datetime.strptime(self.date, "%Y-%m-%d").date()
            end_date = datetime.strptime(self.end_date, "%Y-%m-%d").date()
            return (end_date - start_date).days + 1
        except (ValueError, TypeError):
            return 1

    @property
    def formatted_date_range(self) -> str:
        """Get formatted date range for display (Jul 25-29 format)"""
        if not self.is_multi_day:
            return self.date

        try:
            start_date = datetime.strptime(self.date, "%Y-%m-%d").date()
            end_date = datetime.strptime(self.end_date, "%Y-%m-%d").date()

            # If same month, show "Jul 25-29" format
            if start_date.month == end_date.month:
                return f"{start_date.strftime('%b %d')}-{end_date.day}"
            else:
                return f"{start_date.strftime('%b %d')}-{end_date.strftime('%b %d')}"
        except (ValueError, TypeError):
            return self.date

    def contains_date(self, target_date: Union[str, date]) -> bool:
        """Check if the event is active on the given date"""
        if isinstance(target_date, date):
            target_str = target_date.strftime("%Y-%m-%d")
        else:
            target_str = target_date

        # Single day event
        if not self.is_multi_day:
            return self.date == target_str

        # Multi-day event - check if target is within range
        try:
            target_dt = datetime.strptime(target_str, "%Y-%m-%d").date()
            start_dt = datetime.strptime(self.date, "%Y-%m-%d").date()
            end_dt = datetime.strptime(self.end_date, "%Y-%m-%d").date()
            return start_dt <= target_dt <= end_dt
        except (ValueError, TypeError):
            # Fallback to exact match if parsing fails
            return self.date == target_str

    def save_to_database(self):
        """Explicitly store event in database - delegates to save() method"""
        self.save()

    def as_dict(self):
        """Return event data as dictionary for easy duplication"""
        result = dataclasses.asdict(self)
        # Deep copy lists to avoid shared references
        if result.get("categories"):
            result["categories"] = result["categories"].copy()
        # Exclude cancelled from dict since it's a user-set flag, not from scrapers
        result.pop("cancelled", None)
        return result


@dataclass
class EventDetail:
    """Event detail content with URL as primary key"""

    url: str
    content: str
    fetched_at: Optional[float] = None  # Unix timestamp
    scraper: Optional[str] = None  # Which scraper fetched this detail

    def __post_init__(self):
        if self.fetched_at is None:
            self.fetched_at = time_module.time()

    def _store_in_database(self):
        """Store event detail in database using ORM

        MIGRATION: Now uses ORM internally for proper type handling and schema compatibility.
        Converts old dataclass EventDetail to ORM EventDetail and saves using proper SQLAlchemy session.
        """

        # Convert old dataclass EventDetail to ORM EventDetail
        orm_event_detail = OrmEventDetail(
            url=self.url,
            content=self.content,
            fetched_at=self.fetched_at if self.fetched_at else time_module.time(),
            scraper=self.scraper,
        )

        # Save using ORM (handles upsert automatically via merge)
        save_event_detail(orm_event_detail)

    def save(self):
        """Save event detail to database (public API method)"""
        self._store_in_database()

    @classmethod
    def get_detail(cls, url: str) -> Optional["EventDetail"]:
        """Get EventDetail by URL using ORM

        MIGRATION: Now uses ORM internally but converts back to old EventDetail dataclass for API compatibility.
        """
        if not url:
            return None

        session = get_session()
        try:
            # Query using ORM
            orm_detail = (
                session.query(OrmEventDetail).filter(OrmEventDetail.url == url).first()
            )

            if orm_detail:
                # Convert ORM EventDetail back to dataclass EventDetail for compatibility
                return cls(
                    url=orm_detail.url,
                    content=orm_detail.content,
                    fetched_at=orm_detail.fetched_at,
                    scraper=orm_detail.scraper,
                )
            return None
        finally:
            session.close()
