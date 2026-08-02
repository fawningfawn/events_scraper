"""
SQLAlchemy session management - replaces DatabaseManager
"""

import logging
import os
from datetime import date
from typing import List
from typing import Optional

from sqlalchemy import and_
from sqlalchemy import create_engine
from sqlalchemy import or_
from sqlalchemy.orm import Session as SqlSession
from sqlalchemy.orm import sessionmaker

from events_scraper.lib.core.deduplication import compute_content_hash
from events_scraper.lib.core.orm_models import Base
from events_scraper.lib.core.orm_models import Event
from events_scraper.lib.core.orm_models import EventDetail
from events_scraper.lib.scraper_meta import load_group_meta
from events_scraper.lib.subscriptions.scrape_integration import (
    create_notifications_for_matching_subscriptions,
)

logger = logging.getLogger(__name__)


# Global variables for session management
_engine = None
_SessionLocal = None


def init_database(database_url: str = "sqlite:///:memory:"):
    """
    Initialize database with SQLAlchemy engine and create all tables.
    Replaces DatabaseManager.__init__ and _init_db.

    Args:
        database_url: SQLAlchemy database URL (e.g., "sqlite:///events.db", "sqlite:///:memory:")

    Returns:
        SQLAlchemy engine instance
    """
    global _engine, _SessionLocal

    # Create directory for file-based SQLite databases
    if database_url.startswith("sqlite:///") and not database_url.endswith(":memory:"):
        # Extract file path from sqlite:///path/to/file.db
        db_file_path = database_url[10:]  # Remove "sqlite:///" prefix
        db_dir = os.path.dirname(db_file_path)
        if db_dir:  # Only create directory if there is one
            os.makedirs(db_dir, exist_ok=True)

    # Create engine
    _engine = create_engine(
        database_url,
        echo=False,
        connect_args=(
            {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        ),
    )

    # Create all tables from ORM models
    Base.metadata.create_all(_engine)

    # Create session factory
    _SessionLocal = sessionmaker(bind=_engine)

    return _engine


def get_session() -> SqlSession:
    """
    Get a new SQLAlchemy session. Database must be initialized first via configure_database().
    Replaces DatabaseManager.get_connection().

    Returns:
        New SQLAlchemy session instance
    """
    if _SessionLocal is None:
        raise RuntimeError(
            "Database not initialized. Call configure_database() first, or use init_database() directly."
        )
    return _SessionLocal()


def dispose_engine():
    """
    Dispose of the engine's connection pool. Useful for tests to clean up connections.
    """
    if _engine is not None:
        _engine.dispose()


def load_events_by_date(
    target_date: Optional[date] = None,
    group: str = None,
    scraper: str = None,
    include_cancelled: bool = False,
) -> List[Event]:
    """
    Load events from database using ORM for a specific date.

    Args:
        target_date: Date to load events for
        group: Optional group filter (e.g. '<group>')
        scraper: Optional scraper filter (filters by exact scraper name)
        include_cancelled: If False, exclude cancelled events from results

    Returns:
        List of Event ORM objects
    """
    group_names = None
    if group:
        groups = {g.group: g for g in load_group_meta()}
        meta = groups.get(group)
        if meta is None or meta.source == "python":
            group_names = f"{group}.%"
        else:
            from events_scraper.lib.packages import (  # noqa: E501  # ap-ignore
                get_scraper_names_for_group,
            )

            group_names = get_scraper_names_for_group(group)
            if not group_names:
                return []

    session = get_session()

    try:
        query = session.query(Event)
        if target_date is not None:
            query = query.filter(
                or_(
                    Event.date == target_date,
                    and_(
                        Event.end_date.isnot(None),
                        Event.date <= target_date,
                        Event.end_date >= target_date,
                    ),
                )
            )

        if not include_cancelled:
            query = query.filter(~Event.cancelled)

        if group:
            if isinstance(group_names, str):
                query = query.filter(Event.scraper.like(group_names))
            else:
                query = query.filter(Event.scraper.in_(group_names))

        if scraper:
            query = query.filter(Event.scraper == scraper)

        query = query.order_by(Event.date, Event.time)

        return query.all()

    finally:
        session.close()


def load_events_by_date_range(
    start_date: date,
    end_date: date,
    group: str = None,
    scraper: str = None,
    include_cancelled: bool = False,
) -> List[Event]:
    """
    Load events from database for a date range.

    Args:
        start_date: Start date of range (inclusive)
        end_date: End date of range (inclusive)
        group: Optional group filter (e.g. '<group>')
        scraper: Optional scraper filter (filters by exact scraper name)
        include_cancelled: If False, exclude cancelled events from results

    Returns:
        List of Event ORM objects
    """
    group_names = None
    if group:
        groups = {g.group: g for g in load_group_meta()}
        meta = groups.get(group)
        if meta is None or meta.source == "python":
            group_names = f"{group}.%"
        else:
            from events_scraper.lib.packages import (  # noqa: E501  # ap-ignore
                get_scraper_names_for_group,
            )

            group_names = get_scraper_names_for_group(group)
            if not group_names:
                return []

    session = get_session()

    try:
        query = session.query(Event).filter(
            or_(
                and_(
                    Event.end_date.is_(None),
                    Event.date >= start_date,
                    Event.date <= end_date,
                ),
                and_(
                    Event.end_date.isnot(None),
                    Event.date <= end_date,
                    Event.end_date >= start_date,
                ),
            )
        )

        if not include_cancelled:
            query = query.filter(~Event.cancelled)

        if group:
            if isinstance(group_names, str):
                query = query.filter(Event.scraper.like(group_names))
            else:
                query = query.filter(Event.scraper.in_(group_names))

        if scraper:
            query = query.filter(Event.scraper == scraper)

        query = query.order_by(Event.date, Event.time)

        return query.all()

    finally:
        session.close()


def _build_scraper_query(session: SqlSession, scraper: str, include_past: bool = False):
    """
    Build base query for events from a scraper (lazy - doesn't execute).

    Args:
        scraper: Scraper name to filter by
        include_past: If True, include past events; if False, only show future events

    Returns:
        SQLAlchemy query object (not executed)
    """
    query = session.query(Event).filter(Event.scraper == scraper)

    # Filter by date if not including past events
    if not include_past:
        today = date.today()
        query = query.filter(
            or_(
                # Single-day events in the future
                Event.date >= today,
                # Multi-day events that are still active
                and_(
                    Event.end_date.isnot(None),
                    Event.end_date >= today,
                ),
            ),
        )

    return query.order_by(Event.date, Event.time)


def load_events_by_scraper_paginated(
    scraper: str, page: int = 1, per_page: int = 100, include_past: bool = False
) -> List[Event]:
    """
    Load events from database for a specific scraper with pagination.

    Args:
        scraper: Scraper name to filter by
        page: Page number (1-based)
        per_page: Number of events per page
        include_past: If True, include past events; if False, only show future events

    Returns:
        List of Event ORM objects
    """
    session = get_session()

    try:
        query = _build_scraper_query(session, scraper, include_past)

        # Apply pagination
        offset = (page - 1) * per_page
        query = query.offset(offset).limit(per_page)

        return query.all()

    finally:
        session.close()


def count_events_by_scraper(scraper: str, include_past: bool = False) -> int:
    """
    Count total events for a scraper (for pagination).

    Args:
        scraper: Scraper name to filter by
        include_past: If True, include past events; if False, only count future events

    Returns:
        Total count of events
    """
    session = get_session()

    try:
        query = _build_scraper_query(session, scraper, include_past)
        return query.count()

    finally:
        session.close()


def _match_subscriptions(event, session):
    """Match a saved event against active subscriptions."""
    created = create_notifications_for_matching_subscriptions(event, session)
    if created:
        logger.info(f"Created {created} notifications for '{event.title}'")


def upsert_event(event: Event) -> None:
    """
    Insert or update an Event in database, handling duplicates gracefully.
    Deduplicates based on content (title + location + time) + date, not URL.

    Args:
        event: Event ORM object to upsert
    """

    session = get_session()

    try:
        # Compute content hash for deduplication
        content_hash = compute_content_hash(event.title, event.location, event.time)

        # Check if event already exists based on content hash + date
        # (same event on same day = duplicate, even with different URLs)
        existing = (
            session.query(Event)
            .filter(
                Event.content_hash == content_hash,
                Event.date == event.date,
            )
            .first()
        )

        if existing:
            logger.info(
                "Duplicate event merged at save boundary: title=%s date=%s scraper=%s",
                event.title,
                event.date,
                event.scraper,
            )
            # Update existing event with new data (keep original ctime)
            existing.title = event.title
            existing.date = event.date
            existing.time = event.time
            existing.location = event.location
            existing.categories = event.categories
            existing.scraper = event.scraper
            existing.latitude = event.latitude
            existing.longitude = event.longitude
            existing.end_date = event.end_date
            existing.detail_url = event.detail_url
            existing.upstream_id = event.upstream_id
            # Note: don't update ctime or cancelled - keep original values
            saved_event = existing
        else:
            # Add new event
            session.add(event)
            saved_event = event

        session.commit()

        # Match against subscriptions to create notifications
        _match_subscriptions(saved_event, session)

    finally:
        session.close()


def save_event_detail(event_detail: EventDetail) -> None:
    """
    Save an EventDetail to database using ORM session.

    Args:
        event_detail: EventDetail ORM object to save
    """
    session = get_session()

    try:
        session.merge(event_detail)  # Use merge for upsert behavior
        session.commit()

    finally:
        session.close()


def get_database_url() -> Optional[str]:
    """
    Get the current database URL.
    Replaces DatabaseManager.get_database_path().

    Returns:
        Database URL string if engine is initialized, None otherwise
    """
    if _engine is None:
        return None

    return str(_engine.url)
