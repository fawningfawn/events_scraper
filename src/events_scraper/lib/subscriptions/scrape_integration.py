"""Integration of subscriptions with event scraping"""

import logging

from events_scraper.lib.core.orm_models import EventSubscription
from events_scraper.lib.core.orm_models import Notification
from events_scraper.lib.notification_defaults import create_notification_deltas
from events_scraper.lib.subscriptions.matching import matches_subscription

logger = logging.getLogger(__name__)


def create_notifications_for_matching_subscriptions(event, session):
    """
    Check subscriptions and create notifications for matching events.

    Called when an event is saved during scraping. Creates notifications for all
    active subscriptions that match the event, with standard notification deltas.

    Args:
        event: Event ORM object that was just saved
        session: SQLAlchemy session

    Returns:
        int: Number of notifications created
    """
    try:
        # Extract group from scraper name (format: "group.scraper_name")
        if not event.scraper or "." not in event.scraper:
            logger.debug(f"Event {event.id} has invalid scraper format: {event.scraper}")
            return 0

        group = event.scraper.split(".")[0]

        # Get all active subscriptions for this group
        subscriptions = (
            session.query(EventSubscription)
            .filter_by(group=group, status="active")
            .all()
        )

        created_count = 0

        # Check each subscription
        for subscription in subscriptions:
            if matches_subscription(event, subscription):
                # Create notifications for this subscription
                created = _create_notifications_for_subscription(
                    event, subscription, session
                )
                created_count += created

        return created_count

    except Exception as e:
        logger.error(
            f"Error checking subscriptions for event {event.id}: {e}",
            exc_info=True,
        )
        return 0


def _create_notifications_for_subscription(event, subscription, session):
    """
    Create notifications for a matching subscription.

    Creates one notification per delta (e.g., 3-day and 3-hour before event).
    Prevents duplicates by checking if notification already exists.

    Args:
        event: Event ORM object
        subscription: EventSubscription ORM object
        session: SQLAlchemy session

    Returns:
        int: Number of notifications created
    """
    created_count = 0

    try:
        # Get notification deltas
        deltas = create_notification_deltas()

        # Create notification for each delta
        for notify_delta, plugin in deltas:
            # Check if notification already exists
            existing = (
                session.query(Notification)
                .filter_by(
                    user_id=subscription.user_id,
                    event_id=event.id,
                    notify_delta=notify_delta,
                )
                .first()
            )

            if existing:
                logger.debug(
                    f"Notification already exists for user {subscription.user_id}, "
                    f"event {event.id}, delta {notify_delta}"
                )
                continue

            # Create new notification
            notification = Notification(
                user_id=subscription.user_id,
                event_id=event.id,
                subscription_id=subscription.id,
                notify_delta=notify_delta,
                status="pending",
                plugin=plugin,
            )
            notification.send_at = notification.calculate_send_at(event)

            session.add(notification)
            created_count += 1

        session.commit()

    except Exception as e:
        logger.error(
            f"Error creating notifications for subscription {subscription.id}: {e}",
            exc_info=True,
        )
        session.rollback()

    return created_count
