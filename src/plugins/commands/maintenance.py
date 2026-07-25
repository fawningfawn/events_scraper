"""Command `maintenance`."""

from __future__ import annotations

from argparse import Namespace

from events_scraper.lib.core.database_maintenance import backfill_scraper_tags
from plugins import load_many
from plugins.command_base import CommandPlugin


class MaintenanceCommand(CommandPlugin):

    def register_subparser(self, subparsers):
        return subparsers.add_parser(
            self.name,
            help="Run maintenance plugins",
            description="Run all maintenance plugins and then backfill scraper tags.",
        )

    def run(self, args: Namespace) -> int:
        del args
        modules = list(load_many("plugins.maintenance"))
        for module in modules:
            if hasattr(module, "plugin"):
                module.plugin.run()
        count = backfill_scraper_tags()
        print(f"Backfilled scraper tags for {count} events")
        return 0


plugins = [MaintenanceCommand()]
