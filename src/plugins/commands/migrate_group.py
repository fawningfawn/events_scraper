"""Command `migrate_group`."""

from __future__ import annotations

from argparse import Namespace

from sqlalchemy import func

from events_scraper.lib.core.orm_models import Event
from events_scraper.lib.core.orm_models import EventDetail
from events_scraper.lib.core.orm_models import ScraperStatus
from events_scraper.lib.core.orm_session import get_session
from events_scraper.lib.packages import get_scraper_names_for_group
from plugins.command_base import CommandPlugin


def _old_names(from_group, to_group):
    """Derive old scraper names from the --to group's current names."""
    new_names = get_scraper_names_for_group(to_group)
    return [
        n.replace(to_group, from_group, 1) if n.startswith(to_group) else n
        for n in new_names
    ]


def _migrate_table(session, model, col, old, new, filter_exp):
    return (
        session.query(model)
        .filter(filter_exp)
        .update({col: func.replace(col, old, new)}, synchronize_session=False)
    )


class MigrateGroupCommand(CommandPlugin):

    def register_subparser(self, subparsers):
        parser = subparsers.add_parser(
            self.name,
            help="Migrate scraper names from one group to another",
            description="Rename scraper name prefixes in the database.",
        )
        parser.add_argument(
            "--from", dest="from_group", required=True, help="Old group name"
        )
        parser.add_argument(
            "--to", dest="to_group", required=True, help="New group name"
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Migrate all events with the old prefix, not just known scrapers",
        )
        return parser

    def run(self, args: Namespace) -> int:
        old = args.from_group
        new = args.to_group
        session = get_session()
        try:
            if args.all:
                event_filter = Event.scraper.like(f"{old}.%")
                status_filter = ScraperStatus.scraper_name.like(f"{old}.%")
                detail_filter = EventDetail.scraper.like(f"{old}.%")
            else:
                names = _old_names(old, new)
                if not names:
                    print(f"No scrapers found in group '{new}'")
                    return 1
                event_filter = Event.scraper.in_(names)
                status_filter = ScraperStatus.scraper_name.in_(names)
                detail_filter = EventDetail.scraper.in_(names)

            events = _migrate_table(
                session, Event, Event.scraper, old, new, event_filter
            )
            status = _migrate_table(
                session,
                ScraperStatus,
                ScraperStatus.scraper_name,
                old,
                new,
                status_filter,
            )
            details = _migrate_table(
                session, EventDetail, EventDetail.scraper, old, new, detail_filter
            )
            session.commit()
            print(f"Migrated {events} events, {status} status rows, {details} details")
        finally:
            session.close()
        return 0


plugins = [MigrateGroupCommand()]
