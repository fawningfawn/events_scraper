"""Command `runserver`."""

from __future__ import annotations

from argparse import Namespace

from events_scraper.lib.web.app import create_app
from plugins.command_base import CommandPlugin


class RunserverCommand(CommandPlugin):

    def register_subparser(self, subparsers):
        parser = subparsers.add_parser(
            self.name,
            help="Run web server",
            description="Run the events web server.",
        )
        parser.add_argument("-p", "--port", type=int, default=5003)
        parser.add_argument("--host", default="0.0.0.0")
        parser.add_argument("--debug", action="store_true")
        return parser

    def run(self, args: Namespace) -> int:
        app = create_app()
        app.run(debug=args.debug, host=args.host, port=args.port)
        return 0


plugins = [RunserverCommand()]
