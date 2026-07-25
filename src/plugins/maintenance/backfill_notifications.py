"""Maintenance plugin to backfill notifications for all active subscriptions"""

import logging

from events_scraper.lib.config import load_config
from events_scraper.lib.core.database import configure_database
from events_scraper.lib.core.orm_models import EventSubscription
from events_scraper.lib.core.orm_session import get_session
from events_scraper.lib.subscriptions.backfill import (
    backfill_notifications_for_subscription,
)

logger = logging.getLogger(__name__)


class BackfillNotificationsPlugin:
    """Plugin to backfill notifications for all active subscriptions"""

    name = "backfill_notifications"

    def run(self):
        """Run backfill for all active subscriptions"""
        try:
            config = load_config()
            configure_database(config=config)

            session = get_session()
            try:
                # Get all active subscriptions
                subscriptions = (
                    session.query(EventSubscription).filter_by(status="active").all()
                )

                total_created = 0
                total_skipped = 0

                for subscription in subscriptions:
                    result = backfill_notifications_for_subscription(
                        subscription, session
                    )
                    total_created += result.get("created", 0)
                    total_skipped += result.get("skipped", 0)

                    logger.info(
                        f"Subscription {subscription.id} ({subscription.group}): "
                        f"created {result['created']}, skipped {result['skipped']}"
                    )

                logger.info(
                    f"Backfill complete: "
                    f"created {total_created} total, skipped {total_skipped} total"
                )

                return {
                    "status": "success",
                    "created": total_created,
                    "skipped": total_skipped,
                    "subscriptions_processed": len(subscriptions),
                }

            finally:
                session.close()

        except Exception as e:
            logger.error(f"Error during backfill notifications: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
            }


plugin = BackfillNotificationsPlugin()
