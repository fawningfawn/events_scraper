"""Command `scrape`."""

from __future__ import annotations

import json
import logging
import sys
from argparse import Namespace

from events_scraper.lib.config import get_default_group
from events_scraper.lib.config import load_config
from events_scraper.lib.core import configure_database
from events_scraper.lib.core import setup_logging
from events_scraper.lib.core.scraper import clear_http_cache
from events_scraper.lib.manage_helpers import execute_scraping as _execute_scraping
from events_scraper.lib.manage_helpers import parse_date_argument
from events_scraper.lib.scraper_loader import get_available_groups
from plugins.command_base import CommandPlugin

logger = logging.getLogger(__name__)


class ScrapeCommand(CommandPlugin):

    def register_subparser(self, subparsers):
        parser = subparsers.add_parser(
            self.name,
            help="Scrape events and store them in the database",
            description=__doc__,
        )
        parser.add_argument(
            "target",
            nargs="?",
            default=None,
            help="Group or `group.scraper` target override",
        )
        parser.add_argument(
            "--date",
            default="today",
            help="Target date/date-range for scraping",
        )
        parser.add_argument(
            "--group",
            type=str,
            default=None,
            help="Group to scrape (default: <group>)",
        )
        parser.add_argument(
            "--groups-all",
            action="store_true",
            help="Scrape every available group",
        )
        parser.add_argument(
            "--groups-exclude",
            action="append",
            default=[],
            metavar="GROUP",
            help="Group to exclude from scraping (can be given multiple times)",
        )
        parser.add_argument(
            "--scrape",
            action="store_true",
            help="Scrape basic events",
        )
        parser.add_argument(
            "--scrape-details",
            action="store_true",
            help="Scrape with detail-fetch mode enabled",
        )
        parser.add_argument(
            "--scrape-only-new",
            action="store_true",
            help="Only fetch new details where possible",
        )
        parser.add_argument("--clean-cache", action="store_true")
        parser.add_argument(
            "--scrapers",
            nargs="+",
            metavar="SCRAPER",
            help="Scraper filters (e.g. `<group>.garage_sb` or `<group>`)",
        )
        parser.add_argument("--dump", action="store_true")
        parser.add_argument("--database-url")
        parser.add_argument(
            "-v",
            "--verbose",
            action="count",
            default=0,
            help="Increase verbosity (`-v`, `-vv`, `-vvv`)",
        )
        parser.add_argument(
            "--log-level",
            default="INFO",
            choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        )
        parser.add_argument("--log-file")
        return parser

    def run(self, args: Namespace) -> int:
        _apply_target_override(args)
        if not args.scrape and not args.scrape_details and not args.scrape_only_new:
            args.scrape = True

        config = load_config()
        setup_logging(
            verbose_level=args.verbose,
            log_level=args.log_level,
            log_file=args.log_file,
            config=config,
            log_stream=sys.stdout if not args.log_file else None,
        )
        configure_database(database_url=args.database_url, config=config)
        if args.clean_cache:
            clear_http_cache()

        try:
            date_or_range = parse_date_argument(args.date)
        except ValueError as exc:
            print(f"Error: {exc}")
            return 2

        scrapers_to_use = _resolve_scrapers_to_use(args)
        if args.scrape_details:
            events = _execute_scraping(
                scrapers_to_use,
                date_or_range,
                logger,
                only_new=args.scrape_only_new,
                fetch_details=True,
            )
        else:
            events = _execute_scraping(
                scrapers_to_use, date_or_range, logger, only_new=args.scrape_only_new
            )

        if isinstance(date_or_range, tuple):
            date_display = f"{date_or_range[0]}..{date_or_range[1]}"
        else:
            date_display = str(date_or_range)
        scope = "all groups" if args.groups_all else ", ".join(scrapers_to_use)
        print(f"Scraped {len(events)} events for {scope} on {date_display}")

        if args.dump:
            print(json.dumps([_event_json(event) for event in events], indent=2))
        return 0


def _apply_target_override(args: Namespace) -> None:
    if not args.target:
        return
    if "." in args.target:
        args.scrapers = [args.target]
        args.group = args.target.split(".", 1)[0]
        return
    args.group = args.target


def _resolve_scrapers_to_use(args: Namespace) -> list[str]:
    if args.scrapers:
        return _apply_exclusions(args.scrapers, args.groups_exclude)
    if args.groups_all:
        return _apply_exclusions(get_available_groups(), args.groups_exclude)
    if args.group:
        return _apply_exclusions([args.group], args.groups_exclude)
    return _apply_exclusions([args.group or get_default_group()], args.groups_exclude)


def _apply_exclusions(groups: list[str], exclude: list[str]) -> list[str]:
    if not exclude:
        return groups
    return [g for g in groups if g not in exclude]


def _event_json(event) -> dict:
    if hasattr(event, "as_dict"):
        event_data = event.as_dict()
    else:
        event_data = dict(getattr(event, "__dict__", {}))
    for field in ("date", "end_date", "ctime", "time"):
        value = event_data.get(field)
        if value is not None:
            event_data[field] = str(value)
    return event_data


plugins = [ScrapeCommand()]
