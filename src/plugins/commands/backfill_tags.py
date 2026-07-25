"""Command `backfill_tags`."""

from __future__ import annotations

from argparse import Namespace

from events_scraper.lib.core.database_maintenance import backfill_scraper_tags
from plugins.command_base import CommandPlugin


class BackfillTagsCommand(CommandPlugin):

    def register_subparser(self, subparsers):
        return subparsers.add_parser(
            self.name,
            help="Backfill scraper tags",
            description="Backfill missing scraper tags on stored events.",
        )

    def run(self, args: Namespace) -> int:
        del args
        count = backfill_scraper_tags()
        print(f"Backfilled scraper tags for {count} events")
        return 0


plugins = [BackfillTagsCommand()]
