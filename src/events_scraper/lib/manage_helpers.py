"""Helpers shared by management CLI commands.

These are the workhorses for `src/manage.py` subcommands that need to
parse flexible date input or run scrapers from the command line.
"""

import logging
from datetime import date

import dateparser

from events_scraper.lib.core.utils import parse_date_range
from events_scraper.lib.scraper_loader import _fetch_from_single_scraper
from events_scraper.lib.scraper_loader import load_scrapers

logger = logging.getLogger(__name__)


def parse_date_argument(date_arg: str):
    """Parse date argument from command line.

    Returns a single date object for a single date, or a
    ``(start_date, end_date)`` tuple for a date range.
    """
    if date_arg.lower() == "today":
        return date.today()

    range_separators = [" - ", " ~ ", " to ", " through ", " until "]
    likely_range = any(sep in date_arg for sep in range_separators)

    if likely_range:
        start_date, end_date = parse_date_range(date_arg)
        if start_date:
            if end_date:
                return (start_date, end_date)
            return start_date

        fallback_result = _try_dateparser_fallback(date_arg)
        if fallback_result:
            return fallback_result

    parsed_date = dateparser.parse(date_arg)
    if parsed_date:
        return parsed_date.date()

    raise ValueError(
        f"Could not parse date or date range: '{date_arg}'. "
        "Supported formats include: 'today', 'tomorrow', 'next week', '2025-07-29', "
        "'Jul 29 ~ Aug 5', 'Aug 1 - Aug 7', 'today - tomorrow', 'today ~ next week', etc."
    )


def _try_dateparser_fallback(date_arg: str):
    """Split on range separators and try dateparser on each half."""
    separators = [" - ", " ~ ", " to ", " through ", " until "]

    for sep in separators:
        if sep in date_arg:
            parts = date_arg.split(sep, 1)
            if len(parts) == 2:
                left_date = dateparser.parse(parts[0].strip())
                right_date = dateparser.parse(parts[1].strip())
                if left_date and right_date:
                    start_date = left_date.date()
                    end_date = right_date.date()
                    if start_date <= end_date:
                        return (start_date, end_date)
                    return (end_date, start_date)
    return None


def execute_scraping(
    scrapers_to_use, date_or_range, logger, only_new=False, fetch_details=False
):
    """Run scrapers for the given targets and date(s).

    Each target may be a city package (``<group>``) or a single scraper
    (``<group>.scraper_name``). Errors are logged and swallowed so one
    broken scraper does not abort the rest.
    """
    all_events = []
    scraper_date = (
        date_or_range if not isinstance(date_or_range, tuple) else date_or_range[0]
    )

    for target in scrapers_to_use:
        try:
            if "." in target:
                group, rest = target.split(".", 1)
                scrapers = load_scrapers(
                    group, target_date=scraper_date, only_new=only_new
                )
                scrapers = [s for s in scrapers if s.scraper_name == target]
                if not scrapers:
                    logger.error(f"Scraper {target} not found in group {group}")
                    continue
            else:
                scrapers = load_scrapers(
                    target, target_date=scraper_date, only_new=only_new
                )

            logger.info(f"Scraping events for {target} ({len(scrapers)} scraper(s))...")
            for scraper in scrapers:
                events = _fetch_scraper(scraper, date_or_range, fetch_details)
                if events:
                    all_events.extend(events)

        except Exception as e:
            logger.error(f"Error scraping {target}: {e}")
            continue

    logger.info(f"Total scraped and saved {len(all_events)} events to database")
    return all_events


def _fetch_scraper(scraper, date_or_range, fetch_details):
    if isinstance(date_or_range, tuple):
        return _fetch_from_single_scraper(
            scraper,
            None,
            date_or_range,
            save_to_database=True,
            fetch_details=fetch_details,
        )
    return _fetch_from_single_scraper(
        scraper,
        date_or_range,
        None,
        save_to_database=True,
        fetch_details=fetch_details,
    )
