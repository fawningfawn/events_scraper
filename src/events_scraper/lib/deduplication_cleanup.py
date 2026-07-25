"""
Cleanup utility for removing event duplicates based on content_hash + date.

This module provides functionality to:
1. Identify duplicate events (same content hash on same date)
2. Keep the earliest event (by ctime) and remove others
3. Clean up orphaned EventDetail records
4. Report statistics on cleanup operations
"""

import logging
from collections import defaultdict
from typing import Dict

from events_scraper.lib.core.deduplication import compute_content_hash
from events_scraper.lib.core.orm_models import Event
from events_scraper.lib.core.orm_models import EventDetail
from events_scraper.lib.core.orm_models import Notification
from events_scraper.lib.core.orm_session import get_session

logger = logging.getLogger(__name__)


def _group_events_by_content_hash(all_events):
    """Group events by (content_hash, date) for deduplication."""
    duplicate_groups = defaultdict(list)
    for event in all_events:
        content_hash = compute_content_hash(event.title, event.location, event.time)
        key = (content_hash, event.date)
        duplicate_groups[key].append(event)
    return duplicate_groups


def _find_duplicates_to_remove(duplicate_groups) -> tuple:
    """Find duplicate events to remove, keeping earliest by ctime."""
    duplicates_to_remove = []
    duplicates_found = 0

    for key, events in duplicate_groups.items():
        if len(events) > 1:
            duplicates_found += 1
            events_sorted = sorted(events, key=lambda e: e.ctime or e.id)
            keeper = events_sorted[0]
            removals = events_sorted[1:]

            logger.info(
                f"Found {len(removals)} duplicate(s) of '{keeper.title}' on {keeper.date}; "
                f"keeping event id={keeper.id} (ctime={keeper.ctime}), removing {len(removals)} others"
            )

            duplicates_to_remove.extend(removals)

    return duplicates_to_remove, duplicates_found


def _delete_notifications_for_events(session, event_ids) -> int:
    """Delete notifications that reference events being removed."""
    notifications_to_delete = (
        session.query(Notification).filter(Notification.event_id.in_(event_ids)).all()
    )

    for notification in notifications_to_delete:
        logger.debug(
            f"Removing notification id={notification.id} that referenced deleted event"
        )
        session.delete(notification)

    return len(notifications_to_delete)


def _delete_events(session, events_to_remove) -> int:
    """Delete events from database."""
    for event in events_to_remove:
        logger.debug(
            f"Removing duplicate event: id={event.id}, title='{event.title}', "
            f"date={event.date}, url={event.detail_url}"
        )
        session.delete(event)
    return len(events_to_remove)


def _cleanup_orphaned_event_details(session) -> int:
    """Delete orphaned EventDetail records."""
    orphaned_details = (
        session.query(EventDetail)
        .filter(~EventDetail.event_id.in_(session.query(Event.id)))
        .all()
    )

    orphaned_count = len(orphaned_details)
    if orphaned_count > 0:
        logger.info(f"Found {orphaned_count} orphaned EventDetail record(s)")
        for detail in orphaned_details:
            logger.debug(f"Removing orphaned EventDetail: id={detail.id}")
            session.delete(detail)

    return orphaned_count


def cleanup_duplicates() -> Dict[str, int]:
    """
    Clean up duplicate events in the database.

    Duplicates are identified by (content_hash, date) and kept/removed based on:
    - KEPT: event with earliest ctime (creation time)
    - REMOVED: all other events with same (content_hash, date)

    Also cleans up orphaned EventDetail records that reference deleted events.

    Returns:
        Dict with statistics:
        {
            "duplicates_found": int,        # Number of duplicate groups found
            "duplicates_removed": int,      # Total events removed
            "notifications_removed": int,   # Notifications cleaned up
            "orphaned_details_removed": int # EventDetail records cleaned up
        }
    """
    session = get_session()
    stats = {
        "duplicates_found": 0,
        "duplicates_removed": 0,
        "notifications_removed": 0,
        "orphaned_details_removed": 0,
    }

    try:
        all_events = session.query(Event).all()
        if not all_events:
            logger.info("No events in database to clean up")
            return stats

        duplicate_groups = _group_events_by_content_hash(all_events)
        duplicates_to_remove, duplicates_found = _find_duplicates_to_remove(
            duplicate_groups
        )

        stats["duplicates_found"] = duplicates_found
        stats["duplicates_removed"] = len(duplicates_to_remove)

        if duplicates_to_remove:
            event_ids_to_remove = [event.id for event in duplicates_to_remove]
            stats["notifications_removed"] = _delete_notifications_for_events(
                session, event_ids_to_remove
            )
            _delete_events(session, duplicates_to_remove)
            session.commit()

        stats["orphaned_details_removed"] = _cleanup_orphaned_event_details(session)
        if stats["orphaned_details_removed"] > 0:
            session.commit()

        logger.info(
            f"Cleanup complete: found {stats['duplicates_found']} duplicate groups, "
            f"removed {stats['duplicates_removed']} events, "
            f"removed {stats['notifications_removed']} notifications, "
            f"removed {stats['orphaned_details_removed']} orphaned EventDetail records"
        )

        return stats

    except Exception as e:
        logger.error(f"Error during duplicate cleanup: {e}")
        session.rollback()
        raise

    finally:
        session.close()
