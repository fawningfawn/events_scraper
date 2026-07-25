"""Command `info`."""

from __future__ import annotations

from argparse import Namespace

from events_scraper.lib.config import load_config
from events_scraper.lib.core import configure_database
from events_scraper.lib.info_report import collect_runtime_info
from events_scraper.lib.info_report import format_runtime_info
from plugins.command_base import CommandPlugin


class InfoCommand(CommandPlugin):
    def register_subparser(self, subparsers):
        parser = subparsers.add_parser(
            self.name,
            help="Show cache, database, and config information",
            description="Print filesystem and database information for the current environment.",
        )
        parser.add_argument(
            "--database-url",
            help="Override the configured database URL for inspection",
        )
        return parser

    def run(self, args: Namespace) -> int:
        config = load_config()
        configure_database(database_url=args.database_url, config=config)
        info = collect_runtime_info()
        print(format_runtime_info(info))
        return 0


plugins = [InfoCommand()]
