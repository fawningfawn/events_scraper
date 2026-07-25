"""Command `subscribe`."""

from __future__ import annotations

from argparse import Namespace

from events_scraper.lib.core.orm_models import EventSubscription
from events_scraper.lib.core.orm_session import get_session
from events_scraper.lib.subscriptions.backfill import (
    backfill_notifications_for_subscription,
)
from plugins.command_base import CommandPlugin


class SubscribeCommand(CommandPlugin):

    def register_subparser(self, subparsers):
        return subparsers.add_parser(
            self.name,
            help="Backfill subscription notifications",
            description="Backfill notifications by matching active subscriptions against future events.",
        )

    def run(self, args: Namespace) -> int:
        del args
        session = get_session()
        try:
            subscriptions = (
                session.query(EventSubscription).filter_by(status="active").all()
            )
            total_created = 0
            for subscription in subscriptions:
                result = backfill_notifications_for_subscription(subscription, session)
                total_created += result["created"]
            print(
                f"Backfill complete: created {total_created} notifications from {len(subscriptions)} subscriptions"
            )
            return 0
        finally:
            session.close()


plugins = [SubscribeCommand()]
