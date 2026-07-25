"""Command `dbshell`."""

from __future__ import annotations

import subprocess
from argparse import Namespace

from events_scraper.lib.core.orm_session import get_database_url
from plugins.command_base import CommandPlugin


class DbshellCommand(CommandPlugin):

    def register_subparser(self, subparsers):
        parser = subparsers.add_parser(
            self.name,
            help="Open sqlite3 shell for configured database",
            description="Open sqlite3 against the configured database, or run one SQL statement.",
        )
        parser.add_argument(
            "sql", nargs="?", default=None, help="Optional SQL statement"
        )
        return parser

    def run(self, args: Namespace) -> int:
        db_url = get_database_url()
        if not db_url or not db_url.startswith("sqlite:///"):
            raise RuntimeError("`dbshell` currently supports SQLite file databases only")

        db_path = db_url.replace("sqlite:///", "", 1)
        cmd = ["sqlite3", db_path]
        if args.sql:
            cmd.append(args.sql)
        subprocess.run(cmd, check=False)
        return 0


plugins = [DbshellCommand()]
