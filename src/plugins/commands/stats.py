"""Command `stats`."""

from __future__ import annotations

from argparse import Namespace

from events_scraper.lib.core.database_maintenance import show_group_stats
from plugins.command_base import CommandPlugin


class StatsCommand(CommandPlugin):

    def register_subparser(self, subparsers):
        parser = subparsers.add_parser(
            self.name,
            help="Show scraper group stats",
            description="Print aggregate group scraper and cache statistics.",
        )
        parser.add_argument("--group", required=True, help="Group to show stats for")
        return parser

    def run(self, args: Namespace) -> int:
        print(show_group_stats(args.group))
        return 0


plugins = [StatsCommand()]
