"""Command `package_list`."""

from __future__ import annotations

import json
from argparse import Namespace

from events_scraper.lib.packages import load_packages
from plugins.command_base import CommandPlugin


class PackageListCommand(CommandPlugin):
    def register_subparser(self, subparsers):
        parser = subparsers.add_parser(
            self.name,
            help="List installed scraper packages",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Output as JSON",
        )
        return parser

    def run(self, args: Namespace) -> int:
        packages = load_packages()
        if args.json:

            print(
                json.dumps(
                    [
                        {
                            "name": p.name,
                            "display_name": p.meta.display_name,
                            "source": p.meta.source,
                            "path": p.path,
                            "scraper_count": p.scraper_count,
                            "hide_from_status": p.meta.hide_from_status,
                        }
                        for p in packages
                    ],
                    indent=2,
                )
            )
            return 0

        for pkg in packages:
            print(pkg.name)
        if not packages:
            print("No packages installed.")
        return 0


plugins = [PackageListCommand()]
