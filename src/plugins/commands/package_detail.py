"""Command `package_detail`."""

from __future__ import annotations

import json
from argparse import Namespace

from events_scraper.lib.packages import load_packages
from plugins.command_base import CommandPlugin


class PackageDetailCommand(CommandPlugin):
    def register_subparser(self, subparsers):
        parser = subparsers.add_parser(
            self.name,
            help="Show details for a scraper package",
        )
        parser.add_argument("name", help="Package name")
        parser.add_argument(
            "--json",
            action="store_true",
            help="Output as JSON",
        )
        return parser

    def run(self, args: Namespace) -> int:
        packages = {p.name: p for p in load_packages()}
        pkg = packages.get(args.name)
        if pkg is None:
            print(f"Package '{args.name}' not found.")
            return 1

        if args.json:

            print(
                json.dumps(
                    {
                        "name": pkg.name,
                        "display_name": pkg.meta.display_name,
                        "source": pkg.meta.source,
                        "path": pkg.path,
                        "scraper_count": pkg.scraper_count,
                        "show_date": pkg.meta.show_date,
                        "feed_enabled": pkg.meta.feed_enabled,
                        "hide_from_status": pkg.meta.hide_from_status,
                    },
                    indent=2,
                )
            )
            return 0

        print(f"name: {pkg.name}")
        print(f"display: {pkg.meta.display_name}")
        print(f"source: {pkg.meta.source}")
        print(f"scrapers: {pkg.scraper_count}")
        print(f"path: {pkg.path}")
        return 0


plugins = [PackageDetailCommand()]
