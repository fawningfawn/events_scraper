"""Backfill notifications for subscriptions"""

import logging
from datetime import date

from events_scraper.lib.core.orm_models import Event
from events_scraper.lib.core.orm_models import EventDetail
from events_scraper.lib.core.orm_models import Notification
from events_scraper.lib.subscriptions.matching import matches_subscription
from events_scraper.lib.subscriptions.scrape_integration import (
    _create_notifications_for_subscription,
)

logger = logging.getLogger(__name__)


def backfill_notifications_for_subscription(subscription, session):
    """
    Create notifications for a subscription by matching against existing future events.

    Called when subscription is created or modified. Finds all future events in the
    subscription's city and creates notifications for those matching the subscription.

    Args:
        subscription: EventSubscription ORM object
        session: SQLAlchemy session

    Returns:
        dict: Result with keys:
            - created: Number of notifications created
            - skipped: Number of duplicates skipped
            - subscription_id: ID of subscription
            - error: Error message if operation failed (optional)
    """
    result = {
        "created": 0,
        "skipped": 0,
        "subscription_id": subscription.id,
    }

    try:
        # Query future events in this group
        today = date.today()
        events = (
            session.query(Event)
            .filter(
                Event.date >= today,
                Event.scraper.startswith(f"{subscription.group}."),
            )
            .all()
        )

        logger.info(
            f"Found {len(events)} future events in {subscription.group} "
            f"for subscription {subscription.id}"
        )

        # Process each event
        for event in events:
            # Get event body content (from event.body or EventDetail)
            event_body = event.body
            if not event_body and event.detail_url:
                # Try to get body from EventDetail
                event_detail = (
                    session.query(EventDetail).filter_by(url=event.detail_url).first()
                )
                if event_detail:
                    event_body = event_detail.content

            if matches_subscription(event, subscription, event_body=event_body):
                # Check for existing notifications
                existing_count = (
                    session.query(Notification)
                    .filter_by(
                        user_id=subscription.user_id,
                        event_id=event.id,
                    )
                    .count()
                )

                if existing_count > 0:
                    result["skipped"] += existing_count
                    logger.debug(
                        f"Skipping {existing_count} existing notifications for "
                        f"user {subscription.user_id}, event {event.id}"
                    )
                    continue

                # Create notifications for this event
                try:
                    created = _create_notifications_for_subscription(
                        event, subscription, session
                    )
                    result["created"] += created
                except Exception as e:
                    logger.error(
                        f"Error creating notifications for event {event.id}: {e}",
                        exc_info=True,
                    )
                    # Continue with next event instead of failing entire backfill
                    continue

        logger.info(
            f"Backfill complete: created {result['created']}, "
            f"skipped {result['skipped']} for subscription {subscription.id}"
        )

    except Exception as e:
        logger.error(
            f"Error backfilling notifications for subscription {subscription.id}: {e}",
            exc_info=True,
        )
        result["error"] = str(e)
        result["created"] = 0

    return result
