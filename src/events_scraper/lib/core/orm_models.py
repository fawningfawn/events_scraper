"""
SQLAlchemy ORM models for events and event details
"""

import time as time_module
from datetime import date as DateType
from datetime import datetime as dt
from datetime import time as time_cls
from datetime import timedelta
from typing import List
from typing import Optional

from sqlalchemy import Boolean
from sqlalchemy import Date
from sqlalchemy import event
from sqlalchemy import Float
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship
from sqlalchemy.types import TIMESTAMP

from events_scraper.lib.core.deduplication import compute_content_hash

Base = declarative_base()


class User(Base):
    """SQLAlchemy ORM model for users"""

    __tablename__ = "users"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Username - unique and required
    username: Mapped[str] = mapped_column(String, nullable=False, unique=True)

    # Phone number - optional, for notification delivery (e.g., Signal)
    phone_number: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Default group - optional, for filtering homepage events
    default_group: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Timestamps
    ctime: Mapped[float] = mapped_column(Float, nullable=False, default=time_module.time)

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}')>"


class Event(Base):
    """SQLAlchemy ORM model for events"""

    __tablename__ = "events"
    __table_args__ = (
        # Unique constraint to prevent duplicate events - content hash + date
        UniqueConstraint("content_hash", "date", name="uq_event_content_date"),
    )

    # Primary key - using auto-incrementing integer
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Core event fields
    title: Mapped[str] = mapped_column(String, nullable=False)
    date: Mapped[DateType] = mapped_column(Date, nullable=False)  # Proper date type!
    year: Mapped[int] = mapped_column(
        Integer, nullable=False
    )  # Extracted from date for deduplication
    time: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Categories stored as comma-separated string (for now)
    categories: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # URLs and metadata - these should never be empty
    detail_url: Mapped[str] = mapped_column(String, nullable=False)
    scraper: Mapped[str] = mapped_column(String, nullable=False)

    # Deduplication fields
    content_hash: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True
    )  # MD5 of title+location+time
    upstream_id: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )  # Scraper's internal event ID

    # Geolocation
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Multi-day events
    end_date: Mapped[Optional[DateType]] = mapped_column(Date, nullable=True)

    # Cancellation flag
    cancelled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Timestamps
    ctime: Mapped[float] = mapped_column(Float, nullable=False, default=time_module.time)

    # Relationship to event details
    detail: Mapped[Optional["EventDetail"]] = relationship(
        "EventDetail", back_populates="event", uselist=False
    )

    # Relationship to notifications
    notifications: Mapped[list["Notification"]] = relationship(
        "Notification", back_populates="event"
    )

    def __repr__(self):
        return f"<Event(id={self.id}, title='{self.title}', date={self.date})>"

    @property
    def categories_list(self) -> List[str]:
        """Convert comma-separated categories string to list"""
        if not self.categories:
            return []
        return [cat.strip() for cat in self.categories.split(",") if cat.strip()]

    @categories_list.setter
    def categories_list(self, value: List[str]):
        """Convert list of categories to comma-separated string"""
        self.categories = ",".join(value) if value else None

    def contains_date(self, target_date: DateType) -> bool:
        """Check if this event is active on the given date"""
        if self.end_date:
            # Multi-day event: check if target_date is in range
            return self.date <= target_date <= self.end_date
        else:
            # Single-day event: exact match
            return self.date == target_date

    def to_dict(self) -> dict:
        """Serialize event for command/API style JSON output."""
        return {
            "id": self.id,
            "title": self.title,
            "date": self.date.isoformat() if self.date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "time": self.time,
            "location": self.location,
            "body": self.body,
            "scraper": self.scraper,
            "detail_url": self.detail_url,
            "categories": self.categories_list,
            "content_hash": self.content_hash,
            "upstream_id": self.upstream_id,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "cancelled": self.cancelled,
            "ctime": self.ctime,
        }


class EventDetail(Base):
    """SQLAlchemy ORM model for event details/content"""

    __tablename__ = "event_details"

    # Primary key is the detail_url
    url: Mapped[str] = mapped_column(String, primary_key=True)

    # Rich content
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Metadata
    fetched_at: Mapped[float] = mapped_column(Float, nullable=False)
    scraper: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Foreign key relationship to events
    event_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("events.id"), nullable=True
    )
    event: Mapped[Optional[Event]] = relationship("Event", back_populates="detail")

    def __repr__(self):
        return f"<EventDetail(url='{self.url}', scraper='{self.scraper}')>"


@event.listens_for(Event, "before_insert")
@event.listens_for(Event, "before_update")
def _auto_populate_year(mapper, connection, target):
    """Automatically populate year field from date field"""
    target.year = target.date.year


@event.listens_for(Event, "before_insert")
@event.listens_for(Event, "before_update")
def _auto_populate_content_hash(mapper, connection, target):
    """Automatically populate content_hash field from title+location+time"""

    target.content_hash = compute_content_hash(
        target.title, target.location, target.time
    )


class GeocodeCache(Base):
    """SQLAlchemy ORM model for geocoding cache"""

    __tablename__ = "geocode_cache"

    # Primary key is the location query
    location_query: Mapped[str] = mapped_column(String, primary_key=True)

    # Coordinates (nullable for failed lookups)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Whether the geocoding was successful
    found: Mapped[int] = mapped_column(Integer, nullable=False)

    # Timestamp (using SQLAlchemy's DateTime with default)
    timestamp: Mapped[float] = mapped_column(
        Float, nullable=False, default=time_module.time
    )

    def __repr__(self):
        return (
            f"<GeocodeCache(location_query='{self.location_query}', found={self.found})>"
        )


class ScraperStatus(Base):
    """SQLAlchemy ORM model for scraper status tracking"""

    __tablename__ = "scraper_status"

    # Auto-incrementing primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Scraper identification
    scraper_name: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str] = mapped_column(String, nullable=False)

    # Status tracking
    timestamp: Mapped[float] = mapped_column(
        Float, nullable=False, default=time_module.time
    )
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self):
        return (
            f"<ScraperStatus(scraper_name='{self.scraper_name}', "
            f"url='{self.url}', status_code={self.status_code})>"
        )


class Notification(Base):
    """SQLAlchemy ORM model for event notifications"""

    __tablename__ = "notifications"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign keys
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    event_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("events.id"), nullable=False
    )
    subscription_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("event_subscriptions.id"), nullable=True
    )

    # Notification timing
    notify_delta: Mapped[int] = mapped_column(
        Integer, nullable=False, default=259200
    )  # Default: 3 days in seconds
    send_at: Mapped[object] = mapped_column(
        TIMESTAMP, nullable=False
    )  # When to send the notification
    sent_at: Mapped[Optional[object]] = mapped_column(
        TIMESTAMP, nullable=True
    )  # When actually sent

    # Delivery tracking
    status: Mapped[str] = mapped_column(
        String, nullable=False, default="pending"
    )  # pending, sent, failed
    plugin: Mapped[str] = mapped_column(String, nullable=False)  # e.g., "signal"

    # Relationships
    user: Mapped["User"] = relationship("User")
    event: Mapped["Event"] = relationship("Event", back_populates="notifications")

    def calculate_send_at(self, event):
        """
        Calculate when notification should be sent based on event and notify_delta.

        Args:
            event: Event ORM object

        Returns:
            datetime: When the notification should be sent
        """

        # Use event time if available, otherwise default to 10am
        if event.time:
            if isinstance(event.time, str):
                parts = event.time.split(":")
                hour = int(parts[0])
                minute = int(parts[1]) if len(parts) > 1 else 0
                event_time = time_cls(hour, minute)
            else:
                event_time = event.time
        else:
            event_time = time_cls(10, 0)  # 10am default

        # Combine event date with time
        event_datetime = dt.combine(event.date, event_time)

        # Subtract notify_delta to get send_at
        return event_datetime - timedelta(seconds=self.notify_delta)

    def __repr__(self):
        return (
            f"<Notification(id={self.id}, user_id={self.user_id}, "
            f"event_id={self.event_id}, status='{self.status}')>"
        )


class EventSubscription(Base):
    """SQLAlchemy ORM model for event subscriptions"""

    __tablename__ = "event_subscriptions"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign keys
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)

    # Subscription details
    group: Mapped[str] = mapped_column("group", String, nullable=False)
    keyword: Mapped[str] = mapped_column(String, nullable=False)
    title_keyword: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    body_keyword: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")

    # Timestamps
    ctime: Mapped[float] = mapped_column(Float, nullable=False, default=time_module.time)

    # Relationships
    user: Mapped["User"] = relationship("User")

    def __init__(self, **kwargs):
        """Initialize subscription with validation"""
        super().__init__(**kwargs)
        # Validate keyword on creation
        if not self.keyword or not self.keyword.strip():
            raise ValueError("Keyword cannot be empty")

    def __repr__(self):
        return (
            f"<EventSubscription(id={self.id}, user_id={self.user_id}, "
            f"group='{self.group}', keyword='{self.keyword}', status='{self.status}')>"
        )
