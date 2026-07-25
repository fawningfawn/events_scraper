"""Remove unused `location` field from a package's YAML config files."""

from __future__ import annotations

from argparse import Namespace

import yaml

from events_scraper.lib.packages import get_package_by_name
from plugins.command_base import CommandPlugin


class RemoveConfigLocationCommand(CommandPlugin):

    def register_subparser(self, subparsers):
        parser = subparsers.add_parser(
            self.name,
            help="Remove `location` from a package's configs",
            description=__doc__,
        )
        parser.add_argument(
            "--package",
            required=True,
            help="Package whose configs to edit (e.g. `conferences`)",
        )
        return parser

    def run(self, args: Namespace) -> int:
        pkg = get_package_by_name(args.package)
        if pkg is None:
            print(f"Unknown package: {args.package}")
            return 1
        config_files = pkg.config_files()
        if not config_files:
            print(f"Package {args.package} has no YAML configs")
            return 0

        removed_count = 0
        for config_file in config_files:
            with open(config_file) as f:
                config = yaml.safe_load(f)

            if "location" in config:
                del config["location"]
                removed_count += 1

                with open(config_file, "w") as f:
                    yaml.dump(config, f, default_flow_style=False, sort_keys=False)

                print(f"Removed location from {config_file.name}")

        print(f"\nRemoved location from {removed_count} config files")
        return 0


plugins = [RemoveConfigLocationCommand()]
