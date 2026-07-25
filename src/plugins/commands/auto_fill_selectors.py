"""
Intelligently fill a package's YAML config selectors by testing date parsing
"""

from argparse import Namespace

import requests
import yaml
from bs4 import BeautifulSoup

from events_scraper.lib.core.utils import parse_date_range
from events_scraper.lib.packages import get_package_by_name
from plugins.command_base import CommandPlugin


def get_specific_selector(element):
    """Get specific CSS selector for an element"""
    classes = element.get("class", [])
    if classes:
        return f"{element.name}.{'.'.join(classes)}"
    return element.name


def analyze_site_for_date(url):
    """Find which element contains parseable date"""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, timeout=10, headers=headers, verify=False)
        response.raise_for_status()
    except Exception as e:
        return {"error": str(e)}

    soup = BeautifulSoup(response.content, "html.parser")

    # Get title
    title = soup.find("title")
    title_text = title.get_text(strip=True) if title else "Unknown Conference"

    # Search ALL text elements for parseable dates
    # Priority: time tags, then headings, then divs/spans
    for tag_name in ["time", "h1", "h2", "h3", "div", "span", "p"]:
        for element in soup.find_all(tag_name):
            text = element.get_text(strip=True)
            if not text or len(text) > 200:  # Skip very long text
                continue

            # Try to parse as date
            start, end = parse_date_range(text)
            if start is not None:
                # Found a parseable date!
                return {
                    "title": title_text,
                    "date_selector": get_specific_selector(element),
                    "date_text": text,
                    "location": text if "," in text else None,
                }

    # No parseable date found
    return {"title": title_text, "date_selector": None}


def update_config(config_path, analysis):
    """Update config with intelligent selectors"""
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    if not config or "selectors" not in config:
        return False

    # Update container if still FIXME
    if config["selectors"]["containers"]["css"] in ["FIXME", "NONE"]:
        config["selectors"]["containers"]["css"] = "body"

    # Update title if not already fixed
    if "fixed" not in config["selectors"].get("title", {}):
        config["selectors"]["title"] = {"fixed": analysis["title"]}

    # Update date selector if we found one
    if analysis.get("date_selector"):
        config["selectors"]["date"]["css"] = analysis["date_selector"]

    # Write back
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    return True


def run_auto_fill(package: str) -> int:
    pkg = get_package_by_name(package)
    if pkg is None:
        print(f"Unknown package: {package}")
        return 1
    configs = pkg.config_files()
    if not configs:
        print(f"Package {package} has no YAML configs")
        return 0

    print(f"Processing {len(configs)} configs...")

    updated = 0
    errors = 0

    for config_file in configs:
        with open(config_file, "r") as f:
            config = yaml.safe_load(f)

        if not config or "base_url" not in config:
            continue

        # Skip if date selector is already specific (not generic h1/h2)
        date_css = config.get("selectors", {}).get("date", {}).get("css")
        if date_css and date_css not in ["FIXME", "NONE", "h1", "h2", None]:
            continue

        print(f"\n{config_file.stem}: {config['base_url']}")

        analysis = analyze_site_for_date(config["base_url"])

        if "error" in analysis:
            print(f"  ERROR: {analysis['error']}")
            errors += 1
            continue

        if analysis.get("date_selector"):
            print(f"  Found date: {analysis['date_text']}")
            print(f"  Selector: {analysis['date_selector']}")

            if update_config(config_file, analysis):
                updated += 1
                print("  UPDATED")
        else:
            print("  No parseable date found")

    print(f"\n{'=' * 60}")
    print(f"Updated: {updated}")
    print(f"Errors: {errors}")
    print(f"Total: {len(configs)}")
    return 0


class AutoFillSelectorsCommand(CommandPlugin):

    def register_subparser(self, subparsers):
        return subparsers.add_parser(
            self.name,
            help="Auto-fill selectors in a package's YAML configs",
            description=__doc__,
        ).add_argument(
            "--package",
            required=True,
            help="Package whose configs to process (e.g. `conferences`)",
        )

    def run(self, args: Namespace) -> int:
        return run_auto_fill(args.package)


plugins = [AutoFillSelectorsCommand()]
