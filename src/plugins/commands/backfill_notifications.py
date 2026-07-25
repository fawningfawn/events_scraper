"""Command `backfill_notifications`."""

from __future__ import annotations

from argparse import Namespace

from plugins.command_base import CommandPlugin
from plugins.maintenance.backfill_notifications import plugin


class BackfillNotificationsCommand(CommandPlugin):

    def register_subparser(self, subparsers):
        return subparsers.add_parser(
            self.name,
            help="Backfill notifications for existing subscriptions",
            description="Create missing notifications for existing subscriptions.",
        )

    def run(self, args: Namespace) -> int:
        del args
        plugin.run()
        return 0


plugins = [BackfillNotificationsCommand()]
