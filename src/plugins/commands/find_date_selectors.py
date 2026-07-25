"""Inspect HTML from a site to find date selectors."""

from __future__ import annotations

from argparse import Namespace

import requests
from bs4 import BeautifulSoup

from plugins.command_base import CommandPlugin


class FindDateSelectorsCommand(CommandPlugin):

    def register_subparser(self, subparsers):
        parser = subparsers.add_parser(
            self.name,
            help="Inspect HTML and find matching elements",
            description=__doc__,
        )
        parser.add_argument("url", help="URL to inspect for date selectors")
        parser.add_argument("search_text", nargs="?", default="Nov 13")
        return parser

    def run(self, args: Namespace) -> int:
        print(f"Fetching {args.url}...")
        response = requests.get(args.url, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(response.text, "html.parser")

        print(f"\nSearching for elements containing '{args.search_text}'...\n")
        matches = soup.find_all(string=lambda text: text and args.search_text in text)

        for i, match in enumerate(matches[:10], 1):
            parent = match.parent
            print(f"Match {i}:")
            print(f"  Text: {match.strip()[:100]}")
            print(f"  Parent tag: <{parent.name}>")
            if parent.get("class"):
                print(f"  Classes: {' '.join(parent.get('class'))}")
            if parent.get("id"):
                print(f"  ID: {parent.get('id')}")
            print(
                f"  CSS selector: {parent.name}"
                + (f".{'.'.join(parent.get('class'))}" if parent.get("class") else "")
            )
            print()
        return 0


plugins = [FindDateSelectorsCommand()]
