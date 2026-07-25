"""Command `migrate`."""

from __future__ import annotations

from argparse import Namespace

from events_scraper.lib.core.migrations_runner import run_migrations
from events_scraper.lib.core.orm_session import get_session
from plugins.command_base import CommandPlugin


class MigrateCommand(CommandPlugin):

    def register_subparser(self, subparsers):
        return subparsers.add_parser(
            self.name,
            help="Run SQL migrations",
            description="Run pending SQL migrations against the configured database.",
        )

    def run(self, args: Namespace) -> int:
        del args
        session = get_session()
        try:
            run_migrations(session)
            print("Migrations completed")
            return 0
        finally:
            session.close()


plugins = [MigrateCommand()]
