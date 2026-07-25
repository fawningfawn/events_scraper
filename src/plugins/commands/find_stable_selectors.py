"""
Use html2text to find dates, then map to stable HTML selectors
"""

import re
from argparse import Namespace

import html2text
import requests
import yaml
from bs4 import BeautifulSoup

from events_scraper.lib.core.utils import parse_date_range
from events_scraper.lib.packages import get_package_by_name
from plugins.command_base import CommandPlugin


def get_stable_selector(element):
    """Get most stable selector for an element"""
    # Priority 1: ID attribute
    if element.get("id"):
        return f"#{element.get('id')}"

    # Priority 2: data-* attributes
    for attr in element.attrs:
        if attr.startswith("data-"):
            return f"{element.name}[{attr}='{element.get(attr)}']"

    # Priority 3: Semantic tags
    if element.name in ["time", "article", "main", "header"]:
        return element.name

    # Priority 4: Simple classes (avoid auto-generated ones)
    classes = element.get("class", [])
    simple_classes = [c for c in classes if not re.search(r"__\w+|--\w+|\d{5,}", c)]
    if simple_classes:
        return f"{element.name}.{'.'.join(simple_classes[:2])}"  # Use first 2 simple classes

    # Fallback: just tag name
    return element.name


def _is_valid_date_line(line, start_date, debug=False):
    """Check if a line contains a valid date"""
    if not start_date or start_date.year < 2025 or start_date.year > 2027:
        return False

    # Validate it's a real date (has month name or numbers)
    if not re.search(
        r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|\d{1,2}.*\d{4})",
        line,
        re.I,
    ):
        if debug:
            print("  -> REJECTED: No month name/year pattern")
        return False

    if debug:
        print("  -> ACCEPTED! Searching HTML for this text...")
    return True


def _find_html_element_for_text(soup, line, debug=False):
    """Find HTML element containing the given text"""
    for element in soup.find_all(["time", "h1", "h2", "h3", "div", "span", "p"]):
        elem_text = element.get_text(strip=True)
        if elem_text == line or (line in elem_text and len(line) > 10):
            selector = get_stable_selector(element)
            if debug:
                print(f"  -> MATCHED HTML element: {element.name}")
                print(f"  -> Selector: {selector}")
            return selector
    return None


def _convert_html_to_text(response_text, debug=False):
    """Convert HTML to plain text using html2text"""
    h = html2text.HTML2Text()
    h.ignore_links = True
    h.ignore_images = True
    text = h.handle(response_text)

    if debug:
        print("\n=== HTML2TEXT OUTPUT (first 50 lines) ===")
        for i, line in enumerate(text.split("\n")[:50], 1):
            print(f"{i:3}: {line[:120]}")

    return text


def find_date_in_html(url, debug=False):
    """Find date element using html2text approach"""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, timeout=15, headers=headers, verify=False)
        response.raise_for_status()
    except Exception as e:
        return {"error": str(e)}

    soup = BeautifulSoup(response.content, "html.parser")
    title = soup.find("title")
    title_text = title.get_text(strip=True) if title else "Unknown"

    text = _convert_html_to_text(response.text, debug)

    # Find lines with parseable dates
    tested = 0
    for line in text.split("\n"):
        line = line.strip()
        if not line or len(line) > 200 or len(line) < 5:
            continue

        tested += 1
        start, end = parse_date_range(line)

        if debug and tested <= 20:
            status = f"FOUND: {start} to {end}" if start else "FAILED"
            print(f"\nTesting: {line[:80]}")
            print(f"  -> {status}")

        if _is_valid_date_line(line, start, debug):
            selector = _find_html_element_for_text(soup, line, debug)
            if selector:
                return {
                    "title": title_text,
                    "date_selector": selector,
                    "date_text": line,
                    "date": f"{start} to {end}" if end else str(start),
                }

    if debug:
        print("\n=== SUMMARY ===")
        print(f"Tested {tested} lines, no valid date found")

    return {"title": title_text, "date_selector": None}


def update_config_with_selector(config_path, selector_info):
    """Update config with stable selector"""
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    if not config or "selectors" not in config:
        return False

    config["selectors"]["containers"]["css"] = "body"
    config["selectors"]["title"] = {"fixed": selector_info["title"]}
    config["selectors"]["date"]["css"] = selector_info["date_selector"]

    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    return True


def _debug_url_mode(url):
    """Debug arbitrary URL mode"""
    print(f"Debugging URL: {url}")
    result = find_date_in_html(url, debug=True)
    if "error" in result:
        print(f"\nERROR: {result['error']}")
    elif result.get("date_selector"):
        print("\n=== RESULT ===")
        print(f"Date text: {result['date_text']}")
        print(f"Selector: {result['date_selector']}")
    else:
        print("\nNo date found")


def _debug_config_mode(config_file, debug_mode):
    """Debug single config mode"""
    if not config_file.exists():
        print(f"Config not found: {config_file}")
        return

    with open(config_file, "r") as f:
        config = yaml.safe_load(f)

    url = config["base_url"].replace("{year}", "25")
    print(f"Debugging {config_file.stem}: {url}")

    result = find_date_in_html(url, debug=debug_mode)
    if "error" in result:
        print(f"\nERROR: {result['error']}")
    elif result.get("date_selector"):
        print("\n=== RESULT ===")
        print(f"Date text: {result['date_text']}")
        print(f"Selector: {result['date_selector']}")
    else:
        print("\nNo date found")


def _process_config(config_file, debug_mode):
    """Process a single config file"""
    with open(config_file, "r") as f:
        config = yaml.safe_load(f)

    if not config or "base_url" not in config:
        return None

    scraper_name = config_file.stem
    url = config["base_url"].replace("{year}", "25")

    if debug_mode:
        print(f"\n{'=' * 70}")
        print(f"{scraper_name}: {url}")
        print(f"{'=' * 70}")
    else:
        print(f"\n{scraper_name}: {url}")

    result = find_date_in_html(url, debug=debug_mode)

    status = None
    if "error" in result:
        print(f"  ERROR: {result['error'][:80]}")
        status = "error"
    elif result.get("date_selector"):
        if not debug_mode:
            print(f"  Date: {result['date_text']}")
            print(f"  Selector: {result['date_selector']}")
        if update_config_with_selector(config_file, result):
            print("  UPDATED")
            status = "updated"
    else:
        if not debug_mode:
            print("  No date found")
        status = "no_date"

    return status


def _batch_process_mode(configs, debug_mode):
    """Process all given configs in batch mode"""
    updated = 0
    errors = 0
    no_date = 0

    for config_file in configs:
        status = _process_config(config_file, debug_mode)
        if status == "error":
            errors += 1
        elif status == "updated":
            updated += 1
        elif status == "no_date":
            no_date += 1

    print(f"\n{'=' * 60}")
    print(f"Updated: {updated}")
    print(f"Errors: {errors}")
    print(f"No date: {no_date}")
    print(f"Total: {len(configs)}")


def run_find_stable_selectors(
    package, debug=None, debug_url=None, debug_config=None
) -> int:
    pkg = get_package_by_name(package)
    if pkg is None:
        print(f"Unknown package: {package}")
        return 1
    configs = pkg.config_files()
    if not configs:
        print(f"Package {package} has no YAML configs")
        return 0

    if debug_url:
        _debug_url_mode(debug_url)
        return 0
    if debug_config:
        target = pkg.configs_dir / f"{debug_config}.yaml"
        _debug_config_mode(target, debug=bool(debug))
        return 0
    _batch_process_mode(configs, debug_mode=bool(debug))
    return 0


class FindStableSelectorsCommand(CommandPlugin):

    def register_subparser(self, subparsers):
        parser = subparsers.add_parser(
            self.name,
            help="Find stable CSS selectors for a package's configs",
            description=__doc__,
        )
        parser.add_argument(
            "--package",
            required=True,
            help="Package whose configs to scan (e.g. `conferences`)",
        )
        parser.add_argument(
            "--debug",
            action="store_true",
            help="Debug mode with verbose output",
        )
        parser.add_argument("--debug-url", help="Debug arbitrary URL without config")
        parser.add_argument(
            "--debug-config",
            metavar="NAME",
            help="Debug a single config by name (without `.yaml`)",
        )
        return parser

    def run(self, args: Namespace) -> int:
        return run_find_stable_selectors(
            package=args.package,
            debug=args.debug,
            debug_url=args.debug_url,
            debug_config=args.debug_config,
        )


plugins = [FindStableSelectorsCommand()]
