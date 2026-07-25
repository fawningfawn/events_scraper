"""Command `dump_scrapers`."""

from __future__ import annotations

from argparse import Namespace

from events_scraper.lib.scraper_loader import get_supported_groups
from events_scraper.lib.scraper_loader import load_scrapers
from plugins.command_base import CommandPlugin


class DumpScrapersCommand(CommandPlugin):
    def register_subparser(self, subparsers):
        parser = subparsers.add_parser(
            self.name,
            help="Dump detected scraper plugins",
            description=(
                "Dump currently detected scraper names. "
                "Use `--group` to scope output."
            ),
        )
        parser.add_argument(
            "--group",
            help="Optional group key (e.g. `<group>`, `paris`, `conferences`)",
        )
        return parser

    def run(self, args: Namespace) -> int:
        group = (args.group or "").strip().lower()

        if group:
            names = self._names_for_group(group)
            for name in names:
                print(name)
            print(f"Total: {len(names)}")
            return 0

        all_groups = sorted(get_supported_groups())
        for group_name in all_groups:
            names = self._names_for_group(group_name)
            print(f"{group_name}:")
            for name in names:
                print(f"  {name}")
            print(f"  Total: {len(names)}")
        return 0

    def _names_for_group(self, group: str) -> list[str]:
        return sorted({scraper.scraper_name for scraper in load_scrapers(group)})


plugins = [DumpScrapersCommand()]
