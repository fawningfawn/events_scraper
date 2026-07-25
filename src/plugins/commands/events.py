"""Command `events`."""

from __future__ import annotations

from argparse import Namespace

from events_scraper.lib.core.orm_models import EventSubscription
from events_scraper.lib.core.orm_session import get_session
from events_scraper.lib.notifications import send_pending_notifications
from events_scraper.lib.subscriptions.backfill import (
    backfill_notifications_for_subscription,
)
from plugins.command_base import CommandPlugin


class EventsCommand(CommandPlugin):

    def register_subparser(self, subparsers):
        parser = subparsers.add_parser(
            self.name,
            help="Systemd-friendly wrapper for notify/subscribe",
            description="Compatibility wrapper that supports --notify and --subscribe.",
        )
        parser.add_argument(
            "--notify",
            action="store_true",
            help="Send pending notifications",
        )
        parser.add_argument(
            "--subscribe",
            action="store_true",
            help="Backfill notifications for active subscriptions",
        )
        return parser

    def run(self, args: Namespace) -> int:
        if not args.notify and not args.subscribe:
            print("events requires at least one flag: --notify and/or --subscribe")
            return 2

        if args.subscribe:
            subscribe_exit = _run_subscribe()
            if subscribe_exit != 0:
                return subscribe_exit
        if args.notify:
            notify_exit = _run_notify()
            if notify_exit != 0:
                return notify_exit
        return 0


def _run_subscribe() -> int:
    session = get_session()
    try:
        subscriptions = session.query(EventSubscription).filter_by(status="active").all()
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


def _run_notify() -> int:
    try:
        sent_count = send_pending_notifications()
        print(f"Sent {sent_count} notifications")
        return 0
    except Exception as exc:
        print(f"Error: {exc}")
        return 1


plugins = [EventsCommand()]
