"""Command `delete_all`."""

from __future__ import annotations

from argparse import Namespace

from events_scraper.lib.core.database_maintenance import clear_ai_cache
from events_scraper.lib.core.database_maintenance import delete_group_events
from events_scraper.lib.core.database_maintenance import delete_group_status
from plugins.command_base import CommandPlugin


class DeleteAllCommand(CommandPlugin):

    def register_subparser(self, subparsers):
        parser = subparsers.add_parser(
            self.name,
            help="Delete all scraper data for a group",
            description="Delete events, status rows, and AI cache for a group.",
        )
        parser.add_argument("--group", required=True, help="Group to delete")
        return parser

    def run(self, args: Namespace) -> int:
        delete_group_events(args.group)
        delete_group_status(args.group)
        clear_ai_cache()
        print("Deleted all data")
        return 0


plugins = [DeleteAllCommand()]
