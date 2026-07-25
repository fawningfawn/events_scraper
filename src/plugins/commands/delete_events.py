"""Command `delete_events`."""

from __future__ import annotations

from argparse import ArgumentParser
from argparse import Namespace

from events_scraper.lib.core.database_maintenance import delete_events_by_scraper
from events_scraper.lib.core.database_maintenance import delete_group_events
from events_scraper.lib.core.orm_models import Event
from events_scraper.lib.core.orm_models import ScraperStatus
from events_scraper.lib.core.orm_session import get_session
from events_scraper.lib.scraper_loader import get_all_scraper_names
from plugins.command_base import CommandPlugin


class DeleteEventsCommand(CommandPlugin):

    def register_subparser(self, subparsers):
        parser: ArgumentParser = subparsers.add_parser(
            self.name,
            help="Delete events from database",
            description=(
                "Delete events by scope. Use `--group` for a group "
                "or `--scraper` for a single scraper name."
            ),
        )
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            "--group",
            help="Delete all events for a group (e.g. conferences, festivals).",
        )
        group.add_argument(
            "--scraper",
            help="Delete one scraper's events (e.g. paris.garage_sb).",
        )
        return parser

    def run(self, args: Namespace) -> int:
        if args.scraper:
            if not _scraper_exists_or_has_data(args.scraper):
                print(f"Error: scraper '{args.scraper}' does not exist")
                return 1

            counts = delete_events_by_scraper(args.scraper)
            print(
                f"Deleted scraper '{args.scraper}': "
                f"{counts['events']} events, "
                f"{counts['notifications']} notifications, "
                f"{counts['event_details']} event_details, "
                f"{counts['scraper_status']} status rows"
            )
            return 0

        count = delete_group_events(args.group)
        print(f"Deleted {count} events")
        return 0


plugins = [DeleteEventsCommand()]


def _scraper_exists_or_has_data(scraper_name: str) -> bool:
    """Return True if scraper is known or already has persisted data."""
    known_scrapers = set(get_all_scraper_names())
    if scraper_name in known_scrapers:
        return True

    session = get_session()
    try:
        has_events = (
            session.query(Event.id).filter(Event.scraper == scraper_name).first()
            is not None
        )
        has_status = (
            session.query(ScraperStatus.id)
            .filter(ScraperStatus.scraper_name == scraper_name)
            .first()
            is not None
        )
        return has_events or has_status
    finally:
        session.close()
