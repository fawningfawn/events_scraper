"""Render a web route and dump the response body."""

from __future__ import annotations

from argparse import Namespace
from urllib.parse import urlsplit

from events_scraper.lib.config import load_config
from events_scraper.lib.core.database import configure_database
from events_scraper.lib.web.app import create_app
from plugins.command_base import CommandPlugin


class DumpUrlCommand(CommandPlugin):

    def register_subparser(self, subparsers):
        parser = subparsers.add_parser(
            self.name,
            help="Render a route and print the response body",
            description=__doc__,
        )
        parser.add_argument(
            "url",
            help="Route path or full URL (e.g. `/status` or `http://events.foo:5003/status`)",
        )
        parser.add_argument(
            "-X",
            "--method",
            default="GET",
            help="HTTP method for the internal request (default: GET)",
        )
        parser.add_argument(
            "--show-status",
            action="store_true",
            help="Print response status line before body",
        )
        parser.add_argument(
            "--show-headers",
            action="store_true",
            help="Print response headers before body",
        )
        parser.add_argument(
            "--database-url",
            help="Override database URL before rendering",
        )
        return parser

    def run(self, args: Namespace) -> int:
        config = load_config()
        configure_database(database_url=args.database_url, config=config)

        app = create_app(test_mode=True)
        target_path = _normalize_target(args.url)
        with app.test_client() as client:
            response = client.open(path=target_path, method=args.method.upper())

        if args.show_status:
            print(f"{response.status_code} {response.status}")
        if args.show_headers:
            for name, value in response.headers.items():
                print(f"{name}: {value}")
            print("")

        print(response.get_data(as_text=True), end="")
        return 0


def _normalize_target(url_or_path: str) -> str:
    parsed = urlsplit(url_or_path)
    if parsed.scheme and parsed.netloc:
        path = parsed.path or "/"
        if parsed.query:
            return f"{path}?{parsed.query}"
        return path

    if not url_or_path.startswith("/"):
        return f"/{url_or_path}"
    return url_or_path


plugins = [DumpUrlCommand()]
