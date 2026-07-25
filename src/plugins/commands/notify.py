"""Command `notify`."""

from __future__ import annotations

from argparse import Namespace

from events_scraper.lib.notifications import send_pending_notifications
from plugins.command_base import CommandPlugin


class NotifyCommand(CommandPlugin):

    def register_subparser(self, subparsers):
        return subparsers.add_parser(
            self.name,
            help="Send pending notifications",
            description="Send pending notifications to subscribed users.",
        )

    def run(self, args: Namespace) -> int:
        del args
        sent_count = send_pending_notifications()
        print(f"Sent {sent_count} notifications")
        return 0


plugins = [NotifyCommand()]
