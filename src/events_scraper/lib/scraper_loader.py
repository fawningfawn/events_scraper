"""Scraper loading and event fetching."""

import logging
from datetime import date
from typing import List
from typing import Optional

from events_scraper.lib.core import EventCollection
from events_scraper.lib.packages import _find_package
from events_scraper.lib.scraper_meta import load_group_meta

logger = logging.getLogger(__name__)


def _instantiate_scrapers(scraper_classes, target_date, only_new, group):
    scrapers = []
    for cls in scraper_classes:
        try:
            scraper = cls(target_date=target_date, only_new=only_new)
            module_name = cls.__module__.split(".")[-1]
            scraper._scraper_name_override = f"{group}.{module_name}"
            scrapers.append(scraper)
        except Exception as e:
            logger.error(f"Failed to instantiate {cls.__name__}: {e}")
    return scrapers


def load_scrapers(
    city_name: str,
    target_date: Optional[date] = None,
    only_new: bool = False,
) -> List:
    name = city_name.lower().strip()
    pkg = _find_package(name)
    if pkg is not None:
        return pkg.load_scrapers(target_date, only_new)
    return []


def get_available_groups() -> List[str]:
    return sorted([p.name for p in _load_all_packages()])


def get_all_scraper_names() -> List[str]:
    """Return every known scraper name across all packages."""
    names = []
    for pkg in _load_all_packages():
        for s in pkg.load_scrapers():
            names.append(s.scraper_name)
    return names


def fetch_all_events(
    city_name: str,
    target_date: Optional[date] = None,
    date_range: Optional[tuple[date, date]] = None,
    save_to_database: bool = True,
    only_new: bool = False,
    fetch_details: bool = False,
) -> EventCollection:
    _validate_date_parameters(target_date, date_range)

    scraper_date = target_date if target_date is not None else date_range[0]
    if only_new:
        scrapers = load_scrapers(city_name, scraper_date, only_new=only_new)
    else:
        scrapers = load_scrapers(city_name, scraper_date)
    all_events = []

    for scraper in scrapers:
        events = _fetch_from_single_scraper(
            scraper,
            target_date,
            date_range,
            save_to_database,
            fetch_details=fetch_details,
        )
        if events:
            all_events.extend(events)

    save_msg = (
        "saved to database"
        if save_to_database
        else "not saved to database (threading mode)"
    )
    logger.info(f"Total events from all scrapers: {len(all_events)} ({save_msg})")
    return EventCollection(all_events)


def _load_all_packages():
    from events_scraper.lib.packages import load_packages

    return load_packages()


def _validate_date_parameters(
    target_date: Optional[date], date_range: Optional[tuple[date, date]]
) -> None:
    if target_date is not None and date_range is not None:
        raise ValueError("Cannot specify both target_date and date_range")
    if target_date is None and date_range is None:
        raise ValueError("Must specify either target_date or date_range")


def _fetch_from_single_scraper(
    scraper,
    target_date: Optional[date],
    date_range: Optional[tuple[date, date]],
    save_to_database: bool,
    fetch_details: bool = False,
) -> List:
    """Fetch events from a single scraper and optionally save to database."""
    try:
        logger.info(f"Fetching events from {scraper.scraper_name}")

        if date_range is not None:
            start_date, end_date = date_range
            events = scraper.fetch_date_range(start_date, end_date)
        else:
            events = scraper.fetch()

        event_list = events.to_list()
        _populate_upstream_ids(event_list, scraper)

        if save_to_database:
            _save_events_to_database(event_list, scraper=scraper)

        if fetch_details and save_to_database:
            _fetch_detail_pages(event_list, scraper)

        logger.info(f"Got {len(event_list)} events from {scraper.scraper_name}")
        return event_list

    except Exception as e:
        logger.error(f"Failed to fetch from {scraper.scraper_name}: {e}")
        return []


def _fetch_detail_pages(events: List, scraper) -> None:
    fetch_detail_content = getattr(scraper, "fetch_detail_content", None)
    if not callable(fetch_detail_content):
        return

    reraise_if_network_blocked = getattr(scraper, "_reraise_if_network_blocked", None)

    fetched_count = 0
    for event in events:
        detail_url = getattr(event, "detail_url", None)
        if not detail_url:
            continue

        try:
            detail = fetch_detail_content(detail_url)
            if detail:
                fetched_count += 1
        except Exception as e:
            if callable(reraise_if_network_blocked):
                reraise_if_network_blocked(e)
            logger.debug(f"Failed to fetch detail for {detail_url}: {e}")

    if fetched_count:
        logger.info(f"Fetched {fetched_count} detail pages for {scraper.scraper_name}")


def _populate_upstream_ids(events: List, scraper) -> None:
    get_upstream_id = getattr(scraper, "get_upstream_id", None)
    if not callable(get_upstream_id):
        return

    for event in events:
        if getattr(event, "upstream_id", None) is not None:
            continue
        detail_url = getattr(event, "detail_url", None)
        if not detail_url:
            continue
        event.upstream_id = get_upstream_id(detail_url)


def _save_events_to_database(events: List, scraper=None) -> None:
    for event in events:
        try:
            if scraper is not None and hasattr(scraper, "scraper_name"):
                event.scraper = scraper.scraper_name
            event.save()
            logger.debug(f"Successfully saved event: {event.title}")
        except Exception as save_error:
            logger.error(f"Failed to save event '{event.title}': {save_error}")


def get_supported_groups() -> List[str]:
    return [g.group for g in load_group_meta()]
