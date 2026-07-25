"""Command `cleanup_duplicates`."""

from __future__ import annotations

from argparse import Namespace

from events_scraper.lib.deduplication_cleanup import cleanup_duplicates
from plugins.command_base import CommandPlugin


class CleanupDuplicatesCommand(CommandPlugin):

    def register_subparser(self, subparsers):
        return subparsers.add_parser(
            self.name,
            help="Cleanup duplicate events and orphaned details",
            description="Remove duplicate events and clean orphaned event details.",
        )

    def run(self, args: Namespace) -> int:
        del args
        stats = cleanup_duplicates()
        print(
            "Cleanup complete: "
            f"{stats['duplicates_removed']} events removed, "
            f"{stats['notifications_removed']} notifications removed, "
            f"{stats['orphaned_details_removed']} orphaned details cleaned"
        )
        return 0


plugins = [CleanupDuplicatesCommand()]
