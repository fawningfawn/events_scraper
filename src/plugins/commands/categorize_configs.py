"""
Auto-categorize a package's YAML configs.

Adds a `categories:` list to YAML configs that don't have one yet, using
simple heuristics based on the URL(s) and scraper_name. The goal is to
tag non-bitcoin-only events as `crypto` (default), tag mining-focused
events as `mining`, finance-focused as `finance`, and developer-centric
general tech as `programming` where appropriate.

Rules:
- If categories already exist, leave as-is.
- If name or URLs contain 'bitcoin', leave untagged unless mining keywords match.
- mining: mining, wdms, nicehash, pow, hash
- finance: fintech, money20, moneylive, investor, finance, bank, liquidity, stmoritz, omfif
- programming: djangocon, chainreact, developerweek, btcplusplus, devday
- crypto (default for non-bitcoin): blockchain, web3, crypto, defi, token,
  ecosystem chains (ethereum, solana, algorand, near, hedera, polygon,
  avalanche, binance, pulsechain), nft, metaverse, webx

Dry-run: pass --dry-run to preview without writing.
"""

from __future__ import annotations

import re
from argparse import Namespace
from typing import Dict
from typing import List
from typing import Optional

import yaml

from events_scraper.lib.packages import get_package_by_name
from plugins.command_base import CommandPlugin


def load_yaml(path) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def dump_yaml(path, data: Dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)


def normalize_text(*parts: Optional[str]) -> str:
    s = " ".join(p for p in parts if isinstance(p, str))
    s = s.lower()
    return s


def guess_categories(name: str, base_url: str, events_url: str) -> List[str]:
    text = normalize_text(name, base_url, events_url)

    cats: List[str] = []
    # Early: mining (specific)
    if re.search(r"\b(mining|wdms|nicehash|pow|hash|miningdisrupt)\b", text):
        cats.append("mining")

    # Programming: general dev conferences we want tagged as programming
    if re.search(r"djangocon|chainreact|developerweek|btcplusplus|btc\+\+|devday", text):
        cats.append("programming")

    # Finance
    if re.search(
        r"fintech|money20|moneylive|invest(or|ment)?|finance|bank|liquidity|stmoritz|omfif|realvision|moderninvestor|cfc-stmoritz|abs-?fintech|fintechconnect|digital\s*euro|insurtech|forex|wallstreetbets|\bwsb\b|wsblive",
        text,
    ):
        if "finance" not in cats:
            cats.append("finance")

    # Crypto ecosystems / web3
    is_bitcoin = "bitcoin" in text
    crypto_match = re.search(
        r"blockchain|web3|\bw3|crypto|defi|token|token2049|proofoftalk|stablecon|buidl|conf3rence|algorand|ethereum|\beth[a-z]|solana|near|hedera|polygon|avalanche|binance|pulsechain|oasis\s*on\s*chain|nft|metaverse|metav|webx|teamz|octaloop|nextblockexpo|blockworks|gbbc|blocksphere|rareevo|wikiexpo|houseofblock|icbta",
        text,
    )
    if (not is_bitcoin) and crypto_match:
        cats.append("crypto")

    # Deduplicate while preserving order
    out: List[str] = []
    for c in cats:
        if c and c not in out:
            out.append(c)
    return out


def run_categorize(package: str, dry_run: bool = False) -> int:
    pkg = get_package_by_name(package)
    if pkg is None:
        print(f"Unknown package: {package}")
        return 1
    configs = pkg.config_files()
    if not configs:
        print(f"Package {package} has no YAML configs")
        return 0

    updated = 0
    examined = 0
    for path in configs:
        try:
            data = load_yaml(path)
        except Exception:
            continue

        examined += 1
        if not isinstance(data, dict):
            continue
        if data.get("categories"):
            continue

        name = str(data.get("scraper_name", ""))
        base = str(data.get("base_url", ""))
        events = str(data.get("events_url", ""))

        cats = guess_categories(name, base, events)
        if cats:
            data["categories"] = cats
            updated += 1
            if not dry_run:
                dump_yaml(path, data)
            print(f"Tagged {path.name}: {cats}")

    print(f"Examined: {examined} files; Updated: {updated}")
    return 0


class CategorizeConfigsCommand(CommandPlugin):

    def register_subparser(self, subparsers):
        parser = subparsers.add_parser(
            self.name,
            help="Auto-categorize a package's YAML config files",
            description=__doc__,
        )
        parser.add_argument(
            "--package",
            required=True,
            help="Package whose configs to categorize (e.g. `conferences`)",
        )
        parser.add_argument(
            "--dry-run", action="store_true", help="Preview changes only"
        )
        return parser

    def run(self, args: Namespace) -> int:
        return run_categorize(args.package, dry_run=args.dry_run)


plugins = [CategorizeConfigsCommand()]
