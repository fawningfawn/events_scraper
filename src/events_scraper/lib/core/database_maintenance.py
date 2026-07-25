"""
Database maintenance functions for events_scraper

Provides functions for managing the events database and caches.
"""

from events_scraper.lib.core.ai_cache import AICache
from events_scraper.lib.core.orm_models import Event
from events_scraper.lib.core.orm_models import EventDetail
from events_scraper.lib.core.orm_models import Notification
from events_scraper.lib.core.orm_models import ScraperStatus
from events_scraper.lib.core.orm_session import get_session
from events_scraper.lib.packages import get_scraper_names_for_group
from events_scraper.lib.scraper_loader import get_supported_groups
from events_scraper.lib.scraper_loader import load_scrapers


def delete_group_events(group):
    """Delete all events for a scraper group."""
    names = get_scraper_names_for_group(group)
    if not names:
        return 0
    session = get_session()
    try:
        result = (
            session.query(Event)
            .filter(Event.scraper.in_(names))
            .delete(synchronize_session=False)
        )
        session.commit()
        return result
    finally:
        session.close()


def delete_events_by_scraper(scraper_name: str) -> dict[str, int]:
    """Delete events and related rows for one scraper."""
    session = get_session()
    try:
        event_ids_query = session.query(Event.id).filter(Event.scraper == scraper_name)

        notifications_deleted = (
            session.query(Notification)
            .filter(Notification.event_id.in_(event_ids_query))
            .delete(synchronize_session=False)
        )

        details_by_event_deleted = (
            session.query(EventDetail)
            .filter(EventDetail.event_id.in_(event_ids_query))
            .delete(synchronize_session=False)
        )

        details_by_scraper_deleted = (
            session.query(EventDetail)
            .filter(EventDetail.scraper == scraper_name)
            .delete(synchronize_session=False)
        )

        events_deleted = (
            session.query(Event)
            .filter(Event.scraper == scraper_name)
            .delete(synchronize_session=False)
        )

        status_deleted = (
            session.query(ScraperStatus)
            .filter(ScraperStatus.scraper_name == scraper_name)
            .delete(synchronize_session=False)
        )

        session.commit()
        return {
            "events": events_deleted,
            "notifications": notifications_deleted,
            "event_details": details_by_event_deleted + details_by_scraper_deleted,
            "scraper_status": status_deleted,
        }
    finally:
        session.close()


def delete_group_status(group):
    """Delete all scraper status entries for a group."""
    names = get_scraper_names_for_group(group)
    if not names:
        return 0
    session = get_session()
    try:
        result = (
            session.query(ScraperStatus)
            .filter(ScraperStatus.scraper_name.in_(names))
            .delete(synchronize_session=False)
        )
        session.commit()
        return result
    finally:
        session.close()


def clear_ai_cache(scraper_name=None, db_path=None):
    """Clear the AI cache table, optionally filtered by scraper name"""
    # Initialize cache to ensure table exists and get connection
    cache = AICache(db_path=db_path)

    try:
        if scraper_name:
            # Filter by URL pattern matching scraper name
            cursor = cache.conn.execute(
                "DELETE FROM ai_cache WHERE url LIKE ?",
                (f"%{scraper_name}%",),
            )
            count = cursor.rowcount
            print(f"Cleared {count} AI cache entries for '{scraper_name}'")
        else:
            cursor = cache.conn.execute("DELETE FROM ai_cache")
            count = cursor.rowcount
            print(f"Cleared {count} AI cache entries")
        cache.conn.commit()
        return count
    except Exception as e:
        print(f"Error clearing AI cache: {e}")
        return 0
    finally:
        cache.close()


def clear_failed_scrape_caches(db_path=None):
    """Clear AI cache entries for failed scrapes (non-200 status codes)"""
    session = get_session()
    cache = AICache(db_path=db_path)

    try:
        # Find all failed scrapes (status_code != 200)
        failed_scrapes = (
            session.query(ScraperStatus.url)
            .filter(ScraperStatus.status_code != 200)
            .distinct()
            .all()
        )

        if not failed_scrapes:
            print("No failed scrapes found")
            return 0

        cleared_count = 0
        for (url,) in failed_scrapes:
            cursor = cache.conn.execute("DELETE FROM ai_cache WHERE url = ?", (url,))
            if cursor.rowcount > 0:
                cleared_count += cursor.rowcount

        cache.conn.commit()
        print(f"Cleared {cleared_count} AI cache entries for failed scrapes")
        return cleared_count
    except Exception as e:
        print(f"Error clearing failed scrape caches: {e}")
        return 0
    finally:
        session.close()
        cache.close()


def show_group_stats(group, db_path=None):
    """Show statistics about a scraper group."""
    names = get_scraper_names_for_group(group)
    session = get_session()
    try:
        event_count = (
            (session.query(Event).filter(Event.scraper.in_(names)).count())
            if names
            else 0
        )

        status_count = (
            (
                session.query(ScraperStatus)
                .filter(ScraperStatus.scraper_name.in_(names))
                .count()
            )
            if names
            else 0
        )

        try:
            cache = AICache(db_path=db_path)
            cursor = cache.conn.execute("SELECT COUNT(*) FROM ai_cache")
            cache_count = cursor.fetchone()[0]
            cache.close()
        except Exception:
            cache_count = 0

        return {
            "events": event_count,
            "status": status_count,
            "cache": cache_count,
        }
    finally:
        session.close()


def backfill_scraper_tags():
    """Backfill always_tags from scrapers into existing events"""
    session = get_session()
    try:
        total_updated = 0

        for group in get_supported_groups():
            try:
                scrapers = load_scrapers(group)
                for scraper in scrapers:
                    if not hasattr(scraper, "always_tags") or not scraper.always_tags:
                        continue

                    # Update events for this scraper
                    events = (
                        session.query(Event)
                        .filter(Event.scraper == scraper.scraper_name)
                        .all()
                    )

                    for event in events:
                        # Get existing categories and add always_tags
                        existing = (
                            set(event.categories.split(","))
                            if event.categories
                            else set()
                        )
                        existing.update(scraper.always_tags)
                        event.categories = ",".join(sorted(existing))

                    total_updated += len(events)

            except Exception:
                pass

        session.commit()
        return total_updated

    finally:
        session.close()
