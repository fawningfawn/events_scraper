"""Helpers to present ORM events in web templates and API payloads."""

from __future__ import annotations

from datetime import datetime


def parse_event_time(time_value):
    """Parse event time from string/time-like value."""
    if isinstance(time_value, str):
        time_str = time_value.strip()
        for time_format in ("%H:%M:%S", "%H:%M", "%I:%M %p", "%I:%M:%S %p"):
            try:
                return datetime.strptime(time_str, time_format).time()
            except ValueError:
                continue
        return None
    return time_value


def format_time_for_display(time_value):
    """Format event time as HH:MM for UI display."""
    if not time_value:
        return None
    time_obj = parse_event_time(time_value)
    if time_obj is None:
        return str(time_value)
    return time_obj.strftime("%H:%M")


def event_is_past(event, now, reference_date_str):
    """Determine if event is past relative to reference date string."""
    event_date_str = str(event.date)

    if getattr(event, "end_date", None) and str(event.end_date) != "None":
        return str(event.end_date) < reference_date_str

    if event_date_str < reference_date_str:
        return True
    if event_date_str > reference_date_str:
        return False

    today_str = now.strftime("%Y-%m-%d")
    if reference_date_str == today_str and getattr(event, "time", None):
        event_time = parse_event_time(event.time)
        if event_time is None:
            return False
        event_datetime = datetime.combine(now.date(), event_time)
        return (now - event_datetime).total_seconds() > 3600
    return False


def normalize_categories(event):
    """Return categories as list for template iteration."""
    categories = getattr(event, "categories", None)
    if isinstance(categories, str):
        return [cat.strip() for cat in categories.split(",") if cat.strip()]
    if categories:
        return list(categories)
    if hasattr(event, "categories_list"):
        return event.categories_list or []
    return []


def build_event_view_dict(
    event, now, reference_date_str, subscription_info=None, is_manual=False
):
    """Build template-friendly event payload from ORM event."""
    result = {
        "id": event.id,
        "title": event.title,
        "date": event.date,
        "date_str": str(event.date) if event.date else "",
        "time": event.time,
        "formatted_time": format_time_for_display(getattr(event, "time", None)),
        "location": event.location,
        "venue": event.location,
        "categories": normalize_categories(event),
        "detail_url": event.detail_url,
        "scraper": event.scraper,
        "latitude": event.latitude,
        "longitude": event.longitude,
        "api_url": f"/api/event/{event.id}" if event.id else "",
        "is_past_attr": event_is_past(event, now, reference_date_str),
        "cancelled": getattr(event, "cancelled", False),
    }
    if subscription_info:
        result["subscription_info"] = subscription_info
    if is_manual:
        result["is_manual_subscription"] = True
    return result


def build_subscription_summary(subscription_id, title_keyword, body_keyword):
    """Build a human-readable summary of what a subscription matches."""
    parts = []
    if title_keyword:
        parts.append(f"title: {title_keyword}")
    if body_keyword:
        parts.append(f"body: {body_keyword}")
    return {
        "id": subscription_id,
        "summary": ", ".join(parts) if parts else "(no keywords)",
    }
