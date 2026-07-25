"""Command `dump_events`."""

from __future__ import annotations

import json
import re
from argparse import Namespace
from datetime import date

from events_scraper.lib.core.database import EventCollection
from plugins.command_base import CommandPlugin


class DumpEventsCommand(CommandPlugin):

    def register_subparser(self, subparsers):
        parser = subparsers.add_parser(
            self.name,
            help="Dump events from database with filters",
            description=(
                "Dump events from the configured database using filters like "
                "`--title`, `--group`, `--scraper`, and date bounds."
            ),
        )
        parser.add_argument(
            "--title",
            help="Regex filter applied to event title (case-insensitive)",
        )
        parser.add_argument(
            "--group",
            help="Group key (`<group>`, `paris`, `conferences`, ...)",
        )
        parser.add_argument(
            "--scraper",
            action="append",
            default=[],
            help="Exact scraper name filter (repeatable)",
        )
        parser.add_argument("--date", help="Exact event date in `YYYY-MM-DD`")
        parser.add_argument("--date-from", help="Inclusive start date `YYYY-MM-DD`")
        parser.add_argument("--date-to", help="Inclusive end date `YYYY-MM-DD`")
        parser.add_argument(
            "--limit",
            type=int,
            default=200,
            help="Max rows to return (default: 200)",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Output JSON instead of tab-separated text",
        )
        return parser

    def run(self, args: Namespace) -> int:
        parsed, error = _parse_filters(args)
        if error:
            print(f"Error: {error}")
            return 2

        target_date, date_from, date_to, title_regex = parsed

        event_collection = _load_with_shared_loaders(
            group=args.group,
            scrapers=args.scraper or [],
            target_date=target_date,
            date_from=date_from,
            date_to=date_to,
        )
        event_collection = _apply_title_filter(
            event_collection=event_collection,
            title_regex=title_regex,
        )
        events = _apply_limit(event_collection.events, args.limit)

        if args.json:
            _print_json(events)
            return 0

        _print_table(events)
        return 0


def _parse_date(raw: str) -> date:
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(f"invalid date `{raw}`; expected `YYYY-MM-DD`") from exc


def _parse_filters(args: Namespace):
    try:
        target_date = _parse_date(args.date) if args.date else None
        date_from = _parse_date(args.date_from) if args.date_from else None
        date_to = _parse_date(args.date_to) if args.date_to else None
    except ValueError as exc:
        return None, str(exc)

    if target_date and (date_from or date_to):
        return None, "`--date` cannot be combined with `--date-from`/`--date-to`"

    title_regex = None
    if args.title:
        try:
            title_regex = re.compile(args.title, re.IGNORECASE)
        except re.error as exc:
            return None, f"invalid `--title` regex: {exc}"

    return (target_date, date_from, date_to, title_regex), None


def _load_with_shared_loaders(
    *, group, scrapers: list[str], target_date, date_from, date_to
):
    group_value = (group or "").lower() or None
    single_scraper = scrapers[0] if len(scrapers) == 1 else None

    if target_date is not None:
        collection = EventCollection.from_database(
            target_date=target_date,
            group=group_value,
            scraper=single_scraper,
        )
    else:
        # No date filters means full range.
        collection = EventCollection.from_database_by_date_range(
            start_date=date_from or date(1970, 1, 1),
            end_date=date_to or date(2100, 12, 31),
            group=group_value,
            scraper=single_scraper,
        )

    if len(scrapers) > 1:
        allowed = set(scrapers)
        collection = EventCollection(
            [e for e in collection.events if e.scraper in allowed]
        )

    return collection


def _apply_title_filter(*, event_collection: EventCollection, title_regex):
    if title_regex:
        return event_collection.include_titles([title_regex])
    return event_collection


def _apply_limit(events, limit: int):
    if limit >= 0:
        return events[:limit]
    return events


def _print_json(events):
    print(
        json.dumps(
            [event.to_dict() for event in events],
            indent=2,
            ensure_ascii=False,
        )
    )


def _print_table(events):
    print("id\tdate\tscraper\ttitle\tlocation")
    for event in events:
        title = (event.title or "").replace("\t", " ").replace("\n", " ").strip()
        location = (event.location or "").replace("\t", " ").replace("\n", " ").strip()
        print(f"{event.id}\t{event.date}\t{event.scraper}\t{title}\t{location}")
    print(f"Total: {len(events)}")


plugins = [DumpEventsCommand()]
