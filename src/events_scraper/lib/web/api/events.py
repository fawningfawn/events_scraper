"""Events API endpoints."""

import logging
from collections import defaultdict
from datetime import date
from datetime import datetime

from flask import jsonify
from flask import render_template
from flask import request

from events_scraper.lib.config import apply_config_filters
from events_scraper.lib.config import get_default_group
from events_scraper.lib.core.database import EventCollection
from events_scraper.lib.core.orm_models import Event as OrmEvent
from events_scraper.lib.core.orm_models import EventSubscription
from events_scraper.lib.core.orm_models import Notification
from events_scraper.lib.core.orm_models import User
from events_scraper.lib.core.orm_session import get_session
from events_scraper.lib.packages import get_scraper_names_for_group
from events_scraper.lib.scraper_meta import load_group_meta
from events_scraper.lib.web.event_view import build_event_view_dict
from events_scraper.lib.web.event_view import build_subscription_summary
from events_scraper.lib.web.event_view import format_time_for_display


def get_event_detail(event_id):
    """API endpoint to get event details."""
    session = get_session()
    try:
        orm_event = session.query(OrmEvent).filter(OrmEvent.id == event_id).first()
        if not orm_event:
            return jsonify({"error": "Event not found"}), 404

        event_view = build_event_view_dict(
            orm_event, now=datetime.now(), reference_date_str=date.today().isoformat()
        )
        return (
            jsonify(
                {
                    "id": event_view["id"],
                    "title": event_view["title"],
                    "date": str(event_view["date"]),
                    "time": format_time_for_display(event_view["time"]),
                    "location": event_view["location"],
                    "body": getattr(orm_event, "body", None),
                    "detail_url": event_view["detail_url"],
                }
            ),
            200,
        )
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error fetching event: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


def list_subscribed_events():
    """API endpoint to get events the user has subscribed to for notifications."""
    session = get_session()
    try:
        user = session.query(User).filter_by(username="admin").first()
        if not user:
            return jsonify({"events": [], "pagination": None})

        group = request.args.get("group", "")

        query = (
            session.query(OrmEvent)
            .join(Notification, OrmEvent.id == Notification.event_id)
            .filter(Notification.user_id == user.id, OrmEvent.date >= date.today())
        )

        if group:
            names = get_scraper_names_for_group(group)
            if not names:
                return jsonify({"events": [], "pagination": None})
            query = query.filter(OrmEvent.scraper.in_(names))

        orm_events = query.distinct().order_by(OrmEvent.date.asc()).all()

        if not orm_events:
            return jsonify({"events": [], "pagination": None})

        # Build event_id -> [subscription_summary, ...] lookup
        event_ids = [e.id for e in orm_events]
        subscription_map = _get_subscription_map(session, user.id, event_ids)

        # Also detect manually-subscribed events (notifications without subscription_id)
        manual_event_ids = _get_manual_subscription_event_ids(
            session, user.id, event_ids
        )

        # Process events for display
        now = datetime.now()
        target_date_str = date.today().strftime("%Y-%m-%d")
        events_html = []

        for orm_event in orm_events:
            try:
                web_event = build_event_view_dict(
                    orm_event,
                    now,
                    target_date_str,
                    subscription_info=subscription_map.get(orm_event.id),
                    is_manual=orm_event.id in manual_event_ids,
                )
                event_html = render_template(
                    "event_item.html",
                    event=web_event,
                    current_group="all",
                    target_date_str=target_date_str,
                )
                events_html.append(event_html)
            except ValueError:
                continue

        return jsonify({"events": events_html, "pagination": None})
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error fetching subscribed events: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


def _get_subscription_map(session, user_id, event_ids):
    """Return {event_id: [subscription_summary, ...]} for matching subscriptions."""
    if not event_ids:
        return {}
    rows = (
        session.query(
            Notification.event_id,
            EventSubscription.id,
            EventSubscription.title_keyword,
            EventSubscription.body_keyword,
        )
        .outerjoin(
            EventSubscription,
            Notification.subscription_id == EventSubscription.id,
        )
        .filter(
            Notification.user_id == user_id,
            Notification.event_id.in_(event_ids),
            Notification.subscription_id.isnot(None),
        )
        .distinct()
        .all()
    )
    result = defaultdict(list)
    for event_id, sub_id, title_kw, body_kw in rows:
        summary = build_subscription_summary(sub_id, title_kw, body_kw)
        result[event_id].append(summary)
    return result


def _get_manual_subscription_event_ids(session, user_id, event_ids):
    """Return set of event_ids that have manual (no subscription) notifications."""
    if not event_ids:
        return set()
    rows = (
        session.query(Notification.event_id)
        .filter(
            Notification.user_id == user_id,
            Notification.event_id.in_(event_ids),
            Notification.subscription_id.is_(None),
        )
        .distinct()
        .all()
    )
    return {row[0] for row in rows}


def list_all_events():  # noqa: C901
    """API endpoint to get all events with pagination."""
    page = int(request.args.get("page", 1))
    per_page = 100

    group = request.args.get("group", get_default_group()).lower()
    scraper = request.args.get("scraper", "").strip()
    filters_enabled = request.args.get("filters", "on").lower() != "off"
    hide_past_enabled = request.args.get("hide_past", "on").lower() != "off"

    date_param = request.args.get("date")
    if date_param:
        try:
            target_date = datetime.strptime(date_param, "%Y-%m-%d").date()
        except ValueError:
            target_date = date.today()
    else:
        target_date = date.today()

    if date_param or not scraper:

        group_meta = {g.group: g for g in load_group_meta()}.get(group)
        show_all = group_meta.show_date == "all" if group_meta else False
        use_date = None if (show_all and not date_param) else target_date
        show_cancelled = bool(scraper)
        event_collection = EventCollection.from_database(
            target_date=use_date,
            group=group,
            scraper=scraper,
            include_cancelled=show_cancelled,
        )
    else:
        event_collection = EventCollection.from_database_by_scraper(
            scraper=scraper,
            page=page,
            per_page=per_page,
            include_past=not hide_past_enabled,
        )

    event_collection = apply_config_filters(
        event_collection,
        filters_enabled=filters_enabled,
        group=group,
        scraper=scraper,
    )

    now = datetime.now()
    target_date_str = target_date.strftime("%Y-%m-%d")
    events = []
    for event in event_collection.events:
        if not event.id:
            continue
        try:
            web_event = build_event_view_dict(event, now, target_date_str)
            if hide_past_enabled and web_event["is_past_attr"]:
                continue
            events.append(web_event)
        except ValueError:
            continue

    events_html = []
    for event in events:
        event_html = render_template(
            "event_item.html",
            event=event,
            current_group=group,
            target_date_str=target_date_str,
        )
        events_html.append(event_html)

    pagination = getattr(event_collection, "pagination", None)

    return jsonify({"events": events_html, "pagination": pagination})
