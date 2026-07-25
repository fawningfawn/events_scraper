"""Public ICS calendar feed endpoints."""

import logging
from datetime import date
from datetime import datetime

from flask import jsonify
from flask import request
from flask import Response
from sqlalchemy import func
from sqlalchemy import or_

from events_scraper.lib.core.orm_models import Event as OrmEvent
from events_scraper.lib.core.orm_session import get_session
from events_scraper.lib.packages import get_scraper_names_for_group
from events_scraper.lib.scraper_meta import load_group_meta
from events_scraper.lib.web.ics import events_to_ical

logger = logging.getLogger(__name__)

FEED_HELP = {
    "description": "Public ICS calendar feeds for events",
    "endpoints": {
        "/feeds/help": "This help page",
        "/feeds/help/groups": "List available groups",
        "/feeds/{group}.ics": "ICS feed for a group's events",
    },
    "filters": {
        "search": "Case-insensitive substring match on title and location",
        "location": "Case-insensitive substring match on venue/location",
        "date": "Single date in YYYY-MM-DD format",
        "date_range": "Date range as YYYY-MM-DD..YYYY-MM-DD",
    },
    "examples": [
        "/feeds/<group>.ics",
        "/feeds/<group>.ics?search=jazz",
        "/feeds/group.ics",
        "/feeds/group.ics?search=blockchain",
    ],
}


def feeds_help():
    """JSON help page documenting available feeds and filters."""
    return jsonify(FEED_HELP)


def feeds_help_groups():
    """List groups that have events in the database."""
    session = get_session()
    try:
        scrapers = session.query(OrmEvent.scraper).distinct().all()
        groups = set()
        for (scraper,) in scrapers:
            if "." in scraper:
                groups.add(scraper.split(".")[0])
        return jsonify({"groups": sorted(groups)})
    except Exception as e:
        logger.error(f"Error listing feed groups: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


def feeds_group_ics(group):
    """ICS feed for any group (city or group) with optional filters."""

    group = group.lower()
    groups = {g.group: g for g in load_group_meta()}
    meta = groups.get(group)
    if meta is None:
        return jsonify({"error": f"Unknown group: {group}"}), 404

    session = get_session()
    try:
        query = session.query(OrmEvent).filter(
            OrmEvent.date >= date.today(),
            ~OrmEvent.cancelled,
        )
        if meta.source == "python":
            query = query.filter(OrmEvent.scraper.like(f"{group}.%"))
        else:
            names = get_scraper_names_for_group(group)
            if names:
                query = query.filter(OrmEvent.scraper.in_(names))
        query = _apply_feed_filters(query)
        query = query.order_by(OrmEvent.date.asc(), OrmEvent.time.asc())
        events = query.all()

        name = f"Events - {group}"
        ical_data = events_to_ical(events, name=name)
        return Response(ical_data, mimetype="text/calendar")
    except Exception as e:
        logger.error(f"Error generating feed for {group}: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


def _apply_feed_filters(query):
    """Apply search, location, date, and date_range filters to a query."""
    search = request.args.get("search", "").strip()
    location = request.args.get("location", "").strip()
    date_str = request.args.get("date", "").strip()
    date_range_str = request.args.get("date_range", "").strip()

    if search:
        pattern = f"%{search}%"
        query = query.filter(
            OrmEvent.title.ilike(pattern) | OrmEvent.location.ilike(pattern)
        )

    if location:
        pattern = f"%{location}%"
        query = query.filter(OrmEvent.location.ilike(pattern))

    if date_str:
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            query = query.filter(
                or_(
                    OrmEvent.date == target_date,
                    (OrmEvent.date <= target_date) & (OrmEvent.end_date >= target_date),
                )
            )
        except ValueError:
            pass

    if date_range_str:
        try:
            parts = date_range_str.split("..")
            if len(parts) == 2:
                start = datetime.strptime(parts[0].strip(), "%Y-%m-%d").date()
                end = datetime.strptime(parts[1].strip(), "%Y-%m-%d").date()
                query = query.filter(
                    OrmEvent.date <= end,
                    func.coalesce(OrmEvent.end_date, OrmEvent.date) >= start,
                )
        except ValueError:
            pass

    return query
