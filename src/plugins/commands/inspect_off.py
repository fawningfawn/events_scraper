"""Inspect Oslo Freedom Forum HTML structure."""

from __future__ import annotations

from argparse import Namespace

import requests
from bs4 import BeautifulSoup

from plugins.command_base import CommandPlugin


class InspectOffCommand(CommandPlugin):

    def register_subparser(self, subparsers):
        return subparsers.add_parser(
            self.name,
            help="Inspect Oslo Freedom Forum HTML structure",
            description=__doc__,
        )

    def run(self, args: Namespace) -> int:
        del args
        url = "https://oslofreedomforum.com/"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(r.text, "html.parser")

        ticker = soup.find("div", class_="premium-post-ticker__post-title")
        if ticker:
            print("Found ticker element:")
            print(f"  Text: {ticker.get_text(strip=True)}")

            parent = ticker.parent
            print(f"\nParent: {parent.name}")
            print(f"  Classes: {parent.get('class')}")

            if parent.parent:
                grandparent = parent.parent
                print(f"\nGrandparent: {grandparent.name}")
                print(f"  Classes: {grandparent.get('class')}")
                print("\nFull grandparent:")
                print(grandparent)
        else:
            print("No ticker element found")
        return 0


plugins = [InspectOffCommand()]
