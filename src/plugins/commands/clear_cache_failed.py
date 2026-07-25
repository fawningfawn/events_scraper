"""Command `clear_cache_failed`."""

from __future__ import annotations

from argparse import Namespace

from events_scraper.lib.core.database_maintenance import clear_failed_scrape_caches
from plugins.command_base import CommandPlugin


class ClearCacheFailedCommand(CommandPlugin):

    def register_subparser(self, subparsers):
        return subparsers.add_parser(
            self.name,
            help="Clear failed AI cache entries",
            description="Delete failed AI cache entries.",
        )

    def run(self, args: Namespace) -> int:
        del args
        count = clear_failed_scrape_caches()
        print(f"Cleared {count} failed cache entries")
        return 0


plugins = [ClearCacheFailedCommand()]
