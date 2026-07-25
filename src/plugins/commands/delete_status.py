"""Command `delete_status`."""

from __future__ import annotations

from argparse import Namespace

from events_scraper.lib.core.database_maintenance import delete_group_status
from plugins.command_base import CommandPlugin


class DeleteStatusCommand(CommandPlugin):

    def register_subparser(self, subparsers):
        parser = subparsers.add_parser(
            self.name,
            help="Delete scraper status for a group",
            description="Delete scraper status rows for a group.",
        )
        parser.add_argument("--group", required=True, help="Group to delete status for")
        return parser

    def run(self, args: Namespace) -> int:
        count = delete_group_status(args.group)
        print(f"Deleted {count} status rows")
        return 0


plugins = [DeleteStatusCommand()]
