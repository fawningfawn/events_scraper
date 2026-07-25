"""Notification sending wrapper"""

import logging
from datetime import datetime

from events_scraper.lib.core.orm_models import Notification
from events_scraper.lib.core.orm_session import get_session
from plugins import load_many

logger = logging.getLogger(__name__)


def send_pending_notifications(session=None) -> int:
    """
    Send all pending notifications that are ready to be sent.

    Finds notifications where:
    - sent_at IS NULL (not yet sent)
    - send_at <= now (ready to send)

    For each notification, loads the appropriate notifier plugin and calls
    its send() method. Updates notification status based on result.

    Args:
        session: SQLAlchemy session (optional). If not provided, uses get_session().

    Returns:
        int: Number of notifications sent
    """
    should_close_session = False
    if session is None:
        session = get_session()
        should_close_session = True
    try:
        now = datetime.now()

        # Find pending notifications ready to send
        pending = (
            session.query(Notification)
            .filter(
                Notification.sent_at.is_(None),
                Notification.send_at <= now,
            )
            .all()
        )

        logger.info(f"Found {len(pending)} notifications ready to send")

        sent_count = 0

        # Load all available notifier plugins
        notifiers = {n.name: n for n in load_many("plugins.notifiers")}

        # Process each notification
        for notification in pending:
            # Get the appropriate notifier plugin
            notifier_name = notification.plugin
            notifier = notifiers.get(notifier_name)

            if not notifier:
                logger.error(
                    f"Notifier '{notifier_name}' not found for notification {notification.id}"
                )
                notification.status = "failed"
                session.commit()
                continue

            # Try to send
            try:
                success = notifier.send(notification)

                if success:
                    notification.status = "sent"
                    notification.sent_at = now
                    sent_count += 1
                    logger.info(f"Sent notification {notification.id}")
                else:
                    notification.status = "failed"
                    logger.warning(
                        f"Notifier {notifier_name} returned False for notification {notification.id}"
                    )
            except Exception as e:
                notification.status = "failed"
                logger.error(f"Error sending notification {notification.id}: {e}")

            session.commit()

        logger.info(f"Sent {sent_count} notifications")
        return sent_count

    finally:
        # Only close session if we created it
        if should_close_session:
            session.close()
