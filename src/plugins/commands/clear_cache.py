"""Command `clear_cache`."""

from __future__ import annotations

from argparse import Namespace

from events_scraper.lib.core.database_maintenance import clear_ai_cache
from plugins.command_base import CommandPlugin


class ClearCacheCommand(CommandPlugin):

    def register_subparser(self, subparsers):
        parser = subparsers.add_parser(
            self.name,
            help="Clear AI cache (optional scraper name)",
            description="Clear AI cache entries, optionally only for one scraper.",
        )
        parser.add_argument("scraper_name", nargs="?", default=None)
        return parser

    def run(self, args: Namespace) -> int:
        count = clear_ai_cache(args.scraper_name)
        print(f"Cleared {count} cache entries")
        return 0


plugins = [ClearCacheCommand()]
