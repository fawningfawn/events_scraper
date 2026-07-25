"""
Flask web application for browsing events.

Provides a simple web interface for browsing events using the existing
database-first architecture with API-driven event loading.
"""

import logging
import os
from datetime import date
from datetime import datetime

from flask import abort
from flask import Flask
from flask import jsonify
from flask import redirect
from flask import render_template
from flask import request
from sqlalchemy import func

from events_scraper.lib.config import get_default_group
from events_scraper.lib.config import load_config
from events_scraper.lib.core.database import configure_database
from events_scraper.lib.core.logging import setup_logging
from events_scraper.lib.core.migrations_runner import run_migrations
from events_scraper.lib.core.models import EventDetail
from events_scraper.lib.core.orm_models import Event as OrmEvent
from events_scraper.lib.core.orm_models import Notification
from events_scraper.lib.core.orm_models import ScraperStatus
from events_scraper.lib.core.orm_models import User
from events_scraper.lib.core.orm_session import _engine
from events_scraper.lib.core.orm_session import get_session
from events_scraper.lib.core.year_window import get_target_years
from events_scraper.lib.packages import get_scraper_names_for_group
from events_scraper.lib.packages import load_packages
from events_scraper.lib.scraper_loader import load_scrapers
from events_scraper.lib.scraper_meta import load_group_meta
from events_scraper.lib.web.api import events as events_api
from events_scraper.lib.web.api import feeds
from events_scraper.lib.web.api import groups
from events_scraper.lib.web.api import notifications
from events_scraper.lib.web.api import subscriptions
from events_scraper.lib.web.api import users
from events_scraper.lib.web.event_view import build_event_view_dict
from events_scraper.lib.web.event_view import format_time_for_display
from events_scraper.lib.web.ics import events_to_ical
from events_scraper.lib.web.rescrape import run_scraper

logger = logging.getLogger(__name__)


def _get_or_create_default_user(username: str = "admin"):
    """Get or create default user."""
    session = get_session()
    try:
        user = session.query(User).filter_by(username=username).first()
        if not user:
            user = User(username=username)
            session.add(user)
            session.commit()
        # Access attributes before closing session to load them
        _ = user.username
        return user
    except Exception as e:
        logger.warning(f"Failed to get/create user: {e}")
        # Return a minimal user object for template rendering
        return type("User", (), {"username": username})()
    finally:
        session.close()


def _get_and_validate_group():
    """Get group from user default, config, or request and validate it."""
    user_default = None
    session = get_session()
    try:
        user = session.query(User).filter_by(username="admin").first()
        if user and user.default_group:
            user_default = user.default_group.lower()
    except Exception:
        pass
    finally:
        session.close()

    try:
        load_config()
        config_default = get_default_group()
    except Exception:
        config_default = get_default_group()

    default_group = user_default or config_default

    all_groups = load_group_meta()
    group_names = [g.group for g in all_groups]
    current_group = request.args.get("group", default_group).lower()

    if group_names and current_group not in group_names:
        current_group = group_names[0]

    return current_group, all_groups


def _process_events_for_display(events, hide_past_enabled, target_date):
    """Process events for display with past event filtering."""
    now = datetime.now()
    target_date_str = target_date.strftime("%Y-%m-%d")

    display_events = []
    for event in events:
        if not event.id:
            continue
        display_events.append(build_event_view_dict(event, now, target_date_str))

    if hide_past_enabled:
        today_str = now.strftime("%Y-%m-%d")
        if target_date_str == today_str:
            return [e for e in display_events if not e["is_past_attr"]]

    return display_events


def _get_year_status(session, scraper_name, url, year):
    """Get status for a single year/URL."""
    event_count = (
        session.query(func.count(OrmEvent.id))
        .filter(OrmEvent.scraper == scraper_name)
        .filter(func.strftime("%Y", OrmEvent.date) == str(year))
        .scalar()
        or 0
    )
    latest_status = (
        session.query(ScraperStatus)
        .filter_by(scraper_name=scraper_name, url=url)
        .order_by(ScraperStatus.timestamp.desc())
        .first()
    )
    if latest_status:
        return {
            "url": url,
            "status_code": latest_status.status_code,
            "error": latest_status.error_message,
            "event_count": event_count,
        }
    return {
        "url": url,
        "status_code": None,
        "error": None,
        "event_count": event_count,
    }


def _load_scraper_status(session, target_years):
    """Load status for all scraper groups (scrapers index page — shows all)."""
    all_data = {}
    for group_meta in load_group_meta():
        try:
            scrapers = load_scrapers(group_meta.group)
            for scraper in scrapers:
                scraper_name = scraper.scraper_name
                if scraper_name not in all_data:
                    all_data[scraper_name] = {}
                    all_data[scraper_name]["_source"] = group_meta.source
                    all_data[scraper_name]["_group"] = group_meta.group
                    scraper_url = (
                        getattr(scraper, "events_url", None)
                        or getattr(scraper, "base_url", None)
                        or getattr(scraper, "url", "")
                    )
                    for year in target_years:
                        all_data[scraper_name][str(year)] = _get_year_status(
                            session, scraper_name, scraper_url, year
                        )
        except Exception as e:
            logger.warning(f"Failed to load scrapers for group {group_meta.group}: {e}")
    return all_data


def _get_all_scraper_status_data(session):
    """Get scraping status data for all scrapers."""
    target_years = _get_status_target_years()
    return _load_scraper_status(session, target_years)


def _get_status_target_years():
    """Get rolling year columns for status pages."""
    try:
        config = load_config()
    except Exception:
        config = None
    return get_target_years(past_years=0, future_years=1, config=config)


def _get_available_scrapers():
    """Get all available scrapers from loaded groups."""
    all_available_scrapers = set()
    for group_meta in load_group_meta():
        if group_meta.hide_from_status:
            continue
        try:
            scrapers = load_scrapers(group_meta.group)
            for s in scrapers:
                all_available_scrapers.add(s.scraper_name)
        except Exception:
            continue
    return all_available_scrapers


def _get_scraper_stats(session, all_available_scrapers):
    """Get scraper statistics from database."""

    raw_stats = (
        session.query(
            func.coalesce(OrmEvent.scraper, "unknown").label("scraper_name"),
            func.count(OrmEvent.id),
        )
        .group_by(func.coalesce(OrmEvent.scraper, "unknown"))
        .order_by(func.count(OrmEvent.id).desc())
        .all()
    )
    logger.info(f"Status page found {len(raw_stats)} scrapers in database")

    db_stats_dict = {scraper_name: count for scraper_name, count in raw_stats}

    for scraper_name in all_available_scrapers:
        if scraper_name not in db_stats_dict:
            db_stats_dict[scraper_name] = 0

    return [(name, count) for name, count in db_stats_dict.items()]


def _group_scraper_stats(raw_stats, future_stats_dict):
    """Group stats by scraper group."""
    all_groups = {g.group: g for g in load_group_meta()}
    grouped_stats = []
    group_totals = {}
    group_futures = {}

    for scraper_name, total_count in raw_stats:
        future_count = future_stats_dict.get(scraper_name, 0)
        if scraper_name == "unknown":
            continue
        group = _find_scraper_group(scraper_name, all_groups)
        if group and all_groups[group].hide_from_status:
            continue
        if group:
            group_totals[group] = group_totals.get(group, 0) + total_count
            group_futures[group] = group_futures.get(group, 0) + future_count
        else:
            grouped_stats.append((scraper_name, total_count, future_count))

    for group in sorted(group_totals):
        grouped_stats.insert(
            0, (group, group_totals[group], group_futures.get(group, 0))
        )

    grouped_stats.sort(key=lambda x: x[1], reverse=True)
    return grouped_stats


def _find_scraper_group(scraper_name, all_groups):
    for group_name, meta in all_groups.items():
        if scraper_name == group_name or scraper_name.startswith(f"{group_name}."):
            return group_name
    return None


def status_route():
    """
    Status page showing basic crawler statistics.
    """

    logger.info(
        f"Status page request - Database: {_engine.url if _engine else 'NOT INITIALIZED'}"
    )

    session = get_session()
    try:
        all_available_scrapers = _get_available_scrapers()
        raw_stats = _get_scraper_stats(session, all_available_scrapers)

        today = date.today()
        future_stats = (
            session.query(
                func.coalesce(OrmEvent.scraper, "unknown").label("scraper_name"),
                func.count(OrmEvent.id),
            )
            .filter(OrmEvent.date >= today)
            .group_by(func.coalesce(OrmEvent.scraper, "unknown"))
            .all()
        )
        future_stats_dict = {scraper_name: count for scraper_name, count in future_stats}

        total_events = session.query(func.count(OrmEvent.id)).scalar() or 0
        future_events = (
            session.query(func.count(OrmEvent.id))
            .filter(OrmEvent.date >= today)
            .scalar()
            or 0
        )

        grouped_stats = _group_scraper_stats(raw_stats, future_stats_dict)

    finally:
        session.close()

    current_user = _get_or_create_default_user()

    return render_template(
        "status.html",
        scraper_stats=grouped_stats,
        total_events=total_events,
        future_events=future_events,
        current_user=current_user,
    )


def status_scrapers_route():
    """
    Index page listing all scrapers with links to their detail pages.
    Displays full status table for all scrapers (all) with filter toggles.
    """
    session = get_session()
    try:
        all_scraper_status = _get_all_scraper_status_data(session)
    finally:
        session.close()
    year_labels = [str(year) for year in _get_status_target_years()]

    current_user = _get_or_create_default_user()

    errors_filter = request.args.get("errors", "off").lower() == "on"
    zero_filter = request.args.get("zero", "off").lower() == "on"
    group_filter = request.args.get("group", "")

    if group_filter:
        all_scraper_status = {
            name: data
            for name, data in all_scraper_status.items()
            if data.get("_group") == group_filter
        }

    all_groups = load_group_meta()

    return render_template(
        "scrapers_index.html",
        scraper_status=all_scraper_status,
        year_labels=year_labels,
        current_user=current_user,
        errors_filter=errors_filter,
        zero_filter=zero_filter,
        group_filter=group_filter,
        all_groups=all_groups,
    )


def scraper_detail_route(scraper_name):
    """
    Generic scraper detail page showing detailed status for any scraper.
    Handles all scrapers.
    """
    session = get_session()
    try:
        all_scraper_status = _get_all_scraper_status_data(session)
    finally:
        session.close()
    year_labels = [str(year) for year in _get_status_target_years()]

    # Check if scraper exists
    if scraper_name not in all_scraper_status:
        abort(404)

    current_user = _get_or_create_default_user()

    # Fetch events for this scraper
    session = get_session()
    try:
        events = (
            session.query(OrmEvent)
            .filter_by(scraper=scraper_name)
            .order_by(OrmEvent.date)
            .all()
        )
    finally:
        session.close()

    return render_template(
        "scraper_detail.html",
        scraper_name=scraper_name,
        scraper_status=all_scraper_status,
        year_labels=year_labels,
        current_user=current_user,
        events=events,
    )


def _validate_rescrape_request(scraper_name, all_scraper_status, year, target_url):
    """Validate rescrape request and return normalized year/url values."""
    if scraper_name not in all_scraper_status:
        abort(404)

    normalized_year = None
    if year:
        try:
            normalized_year = str(int(year))
        except ValueError:
            raise ValueError(f"Invalid year: {year}")

    if target_url:
        known_urls = {
            status.get("url")
            for status in all_scraper_status.get(scraper_name, {}).values()
            if isinstance(status, dict)
        }
        if target_url not in known_urls:
            raise ValueError("Invalid url for scraper")

    return normalized_year, target_url


def _resolve_target_url(all_scraper_status, scraper_name, normalized_year, target_url):
    """Resolve concrete URL target for rescrape."""
    if target_url:
        return target_url
    if normalized_year:
        status = all_scraper_status.get(scraper_name, {}).get(normalized_year, {})
        return status.get("url")
    return None


def scraper_rescrape_route(scraper_name):
    """API endpoint to trigger re-scraping of a scraper."""
    session = get_session()
    try:
        all_scraper_status = _get_all_scraper_status_data(session)
    finally:
        session.close()

    year = request.args.get("year", None)
    target_url = request.args.get("url", None)
    # Backward compatibility for stale frontend JS that still sends URL via `year`.
    if (
        target_url is None
        and isinstance(year, str)
        and (year.startswith("http://") or year.startswith("https://"))
    ):
        target_url = year
        year = None

    try:
        normalized_year, validated_url = _validate_rescrape_request(
            scraper_name, all_scraper_status, year, target_url
        )
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400

    try:
        resolved_url = _resolve_target_url(
            all_scraper_status, scraper_name, normalized_year, validated_url
        )
        result = run_scraper(
            scraper_name=scraper_name, target_url=resolved_url, save=True
        )
        scraped_count = result.scraped_count
        saved_count = result.saved_count
        http_status = result.http_status
        error_message = result.error_message
        resolved_url = result.url

        if http_status == -1 or (http_status >= 400):
            return (
                jsonify(
                    {
                        "status": "error",
                        "scraper_name": scraper_name,
                        "year": normalized_year,
                        "url": resolved_url,
                        "http_status": http_status,
                        "message": error_message or f"HTTP error {http_status}",
                    }
                ),
                500,
            )

        return jsonify(
            {
                "status": "success",
                "scraper_name": scraper_name,
                "year": normalized_year,
                "url": resolved_url,
                "event_count": saved_count,
                "scraped_count": scraped_count,
                "http_status": http_status,
                "error_message": error_message,
                "message": f"Saved {saved_count} events (scraped {scraped_count})",
            }
        )

    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 404
    except Exception as e:
        logger.error(f"Error rescraping {scraper_name}: {e}")
        return (
            jsonify(
                {
                    "status": "error",
                    "scraper_name": scraper_name,
                    "year": year,
                    "url": target_url,
                    "message": f"Scraping failed: {str(e)}",
                }
            ),
            500,
        )


def packages_route():

    current_user = _get_or_create_default_user()
    return render_template(
        "packages.html",
        packages=load_packages(),
        current_user=current_user,
    )


def user_profile_route():
    """User profile page for editing user details"""
    session = get_session()
    try:
        user = session.query(User).filter_by(username="admin").first()
        if not user:
            abort(404)

        groups = load_group_meta()
        return render_template(
            "user_profile.html",
            current_user=user,
            all_groups=groups,
        )
    finally:
        session.close()


def index_route():
    """Redirect to /events/ from /"""
    return redirect("/events/")


def events_route():
    """Main page showing list of events with tabs - events loaded via API."""
    current_group, all_groups = _get_and_validate_group()

    available_scrapers = set()
    try:
        group_scrapers = load_scrapers(current_group)
        for s in group_scrapers:
            available_scrapers.add(s.scraper_name)
    except Exception:
        pass
    available_scrapers = sorted(list(available_scrapers))

    current_user = _get_or_create_default_user()

    date_param = request.args.get("date")
    if date_param:
        try:
            target_date = datetime.strptime(date_param, "%Y-%m-%d").date()
        except ValueError:
            target_date = date.today()
    else:
        target_date = date.today()

    group_meta = next((g for g in all_groups if g.group == current_group), None)
    show_date = group_meta.show_date if group_meta else "day"
    display_name = group_meta.display_name if group_meta else current_group
    formatted_date = target_date.strftime("%a %b %d").lstrip("0")
    if show_date == "all":
        page_title = display_name
    else:
        page_title = f"{display_name}, {formatted_date}"

    filters_param = request.args.get("filters", "on").lower()
    filters_enabled = filters_param != "off"
    hide_past_param = request.args.get("hide_past", "on").lower()
    hide_past_enabled = hide_past_param != "off"
    scraper_filter = request.args.get("scraper", "")

    date_str = target_date.strftime("%Y-%m-%d")
    base_params = f"?group={current_group}&date={date_str}"
    filter_toggle_url = (
        f"/events/{base_params}&filters={'off' if filters_enabled else 'on'}"
        f"&hide_past={hide_past_param}"
    )
    hide_past_toggle_url = (
        f"/events/{base_params}&filters={filters_param}"
        f"&hide_past={'off' if hide_past_enabled else 'on'}"
    )

    return render_template(
        "events.html",
        current_group=current_group,
        default_group=get_default_group(),
        show_date=show_date,
        supported_groups=[g.group for g in all_groups],
        all_groups=all_groups,
        available_scrapers=available_scrapers,
        current_user=current_user,
        page_title=page_title,
        target_date_str=date_str,
        filters_param=filters_param,
        filters_enabled=filters_enabled,
        filter_state="ON" if filters_enabled else "OFF",
        filter_toggle_url=filter_toggle_url,
        hide_past_param=hide_past_param,
        hide_past_enabled=hide_past_enabled,
        hide_past_state="ON" if hide_past_enabled else "OFF",
        hide_past_toggle_url=hide_past_toggle_url,
        scraper_filter=scraper_filter,
    )


def event_detail_route(event_id):
    """API endpoint to get event details by event ID"""

    session = get_session()
    try:
        orm_event = session.query(OrmEvent).filter(OrmEvent.id == event_id).first()
        if not orm_event:
            return jsonify({"error": "Event not found"}), 404
    finally:
        session.close()

    description = None
    # Get pre-scraped event details from database
    event_detail = EventDetail.get_detail(orm_event.detail_url)
    if event_detail and event_detail.content:
        description = event_detail.content

    # Prepare event detail data
    event_data = {
        "id": orm_event.id,
        "title": orm_event.title,
        "date": orm_event.date.isoformat() if orm_event.date else "",
        "time": format_time_for_display(orm_event.time),
        "location": orm_event.location,
        "description": description,
        "categories": orm_event.categories.split(",") if orm_event.categories else [],
        "detail_url": orm_event.detail_url,
        "latitude": orm_event.latitude,
        "longitude": orm_event.longitude,
        "cancelled": orm_event.cancelled,
    }

    return jsonify(event_data)


def event_cancel_route(event_id):
    """API endpoint to toggle event cancelled status"""

    session = get_session()
    try:
        orm_event = session.query(OrmEvent).filter(OrmEvent.id == event_id).first()
        if not orm_event:
            return jsonify({"error": "Event not found"}), 404

        orm_event.cancelled = not orm_event.cancelled
        session.commit()

        return (
            jsonify(
                {
                    "status": "success",
                    "event_id": event_id,
                    "cancelled": orm_event.cancelled,
                }
            ),
            200,
        )
    except Exception as e:
        logger.error(f"Error toggling cancelled for event {event_id}: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


def notification_subscribe_route(event_id):
    """API endpoint to subscribe to event notifications"""

    session = get_session()
    try:
        # Check if event exists
        orm_event = session.query(OrmEvent).filter(OrmEvent.id == event_id).first()
        if not orm_event:
            return jsonify({"error": "Event not found"}), 400

        # Get or create current user (for now, use default admin user)
        user = session.query(User).filter_by(username="admin").first()
        if not user:
            user = User(username="admin")
            session.add(user)
            session.commit()  # Commit to ensure user is saved

        # Check if notifications already exist (only if both do)
        existing_count = (
            session.query(Notification)
            .filter_by(user_id=user.id, event_id=event_id)
            .count()
        )
        if existing_count >= 2:
            return jsonify({"status": "subscribed"}), 200

        # Create two notifications: 3 days before and 3 hours before
        notify_deltas = [
            (259200, "signal"),  # 3 days = 259200 seconds
            (10800, "signal"),  # 3 hours = 10800 seconds
        ]

        for notify_delta, plugin in notify_deltas:
            # Check if this specific notification already exists
            existing = (
                session.query(Notification)
                .filter_by(
                    user_id=user.id,
                    event_id=event_id,
                    notify_delta=notify_delta,
                )
                .first()
            )
            if not existing:
                notification = Notification(
                    user_id=user.id,
                    event_id=event_id,
                    notify_delta=notify_delta,
                    status="pending",
                    plugin=plugin,
                )
                notification.send_at = notification.calculate_send_at(orm_event)
                session.add(notification)

        session.commit()

        return jsonify({"status": "subscribed"}), 200
    except Exception as e:
        logger.error(f"Error subscribing to notifications: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


def notification_unsubscribe_route(event_id):
    """API endpoint to unsubscribe from event notifications"""

    session = get_session()
    try:
        # Check if event exists
        orm_event = session.query(OrmEvent).filter(OrmEvent.id == event_id).first()
        if not orm_event:
            return jsonify({"error": "Event not found"}), 400

        # Get or create current user (for now, use default admin user)
        user = session.query(User).filter_by(username="admin").first()
        if not user:
            user = User(username="admin")
            session.add(user)
            session.commit()  # Commit to ensure user is saved

        # Delete notification
        session.query(Notification).filter_by(
            user_id=user.id, event_id=event_id
        ).delete()
        session.commit()

        return jsonify({"status": "unsubscribed"}), 200
    except Exception as e:
        logger.error(f"Error unsubscribing from notifications: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


def _get_subscribed_events(session, user_id, group=None):
    """Get future events the user has subscribed to (via notifications).

    Args:
        session: SQLAlchemy session
        user_id: User ID
        group: Optional group filter  (e.g. '<group>')
    """
    today = date.today()
    events = (
        session.query(OrmEvent)
        .join(Notification, Notification.event_id == OrmEvent.id)
        .filter(
            Notification.user_id == user_id,
            OrmEvent.date >= today,
            ~OrmEvent.cancelled,
        )
        .all()
    )

    if group:

        groups = {g.group: g for g in load_group_meta()}
        meta = groups.get(group)
        if meta and meta.source == "python":
            return [e for e in events if e.scraper.startswith(f"{group}.")]
        names = get_scraper_names_for_group(group)
        return [e for e in events if e.scraper in names]
    return events


def user_events_feed(user_id):
    """ICS feed of subscribed events grouped by scraper group."""
    session = get_session()
    try:
        user = session.get(User, user_id)
        if not user:
            abort(404)
        group = request.args.get("group")
        events = _get_subscribed_events(session, user_id, group=group)
        name = "Subscribed Events"
        if group:
            name += f" - {group}"
        ical_data = events_to_ical(events, name=name)
        response = Flask.response_class(ical_data, mimetype="text/calendar")
        response.headers["ETag"] = str(hash(ical_data))
        return response
    finally:
        session.close()


def create_app(test_mode=False):
    """
    Create and configure Flask application.

    Args:
        test_mode (bool): Whether to configure app for testing

    Returns:
        Flask: Configured Flask application
    """
    # Get the directory containing this file
    app_dir = os.path.dirname(os.path.abspath(__file__))

    # Create Flask app with proper template and static directories
    app = Flask(
        __name__,
        template_folder=os.path.join(app_dir, "templates"),
        static_folder=os.path.join(app_dir, "static"),
    )

    # Configure app
    if test_mode:
        app.config["TESTING"] = True
    else:
        # Load config file and setup database/logging directly
        config = load_config()

        # Configure database using config file
        configure_database(config=config)

        # Setup logging using config file
        setup_logging(config=config)

        session = get_session()
        try:
            run_migrations(session)
        finally:
            session.close()

    app.route("/")(index_route)
    app.route("/events/")(events_route)
    app.route("/events/subscribed")(events_route)
    app.route("/packages")(packages_route)
    app.route("/user")(user_profile_route)
    app.route("/user/<int:user_id>/feeds/events.ics")(user_events_feed)

    app.route("/feeds/help")(feeds.feeds_help)
    app.route("/feeds/help/groups")(feeds.feeds_help_groups)
    app.route("/feeds/<group>.ics")(feeds.feeds_group_ics)
    app.route("/status")(status_route)
    app.route("/status/scrapers")(status_scrapers_route)
    app.route("/status/scraper/<scraper_name>")(scraper_detail_route)

    app.route("/api/scraper/<scraper_name>/rescrape", methods=["POST"])(
        scraper_rescrape_route
    )
    app.route("/api/event/<int:event_id>", methods=["GET"])(event_detail_route)
    app.route("/api/event/<int:event_id>/cancel", methods=["POST"])(event_cancel_route)
    app.route("/api/events/all", methods=["GET"])(events_api.list_all_events)
    app.route("/api/events/subscribed", methods=["GET"])(
        events_api.list_subscribed_events
    )
    app.route("/api/user", methods=["GET"])(users.get_user)
    app.route("/api/user/update", methods=["POST"])(users.update_user)
    app.route("/api/user/notifications", methods=["GET"])(
        notifications.get_user_notifications
    )
    app.route("/api/groups", methods=["GET"])(groups.get_groups)

    # Notification API routes
    app.route("/api/events/<int:event_id>/notifications/subscribe", methods=["POST"])(
        notification_subscribe_route
    )
    app.route("/api/events/<int:event_id>/notifications", methods=["DELETE"])(
        notification_unsubscribe_route
    )
    app.route("/api/events/<int:event_id>/notifications/status", methods=["GET"])(
        notifications.get_notification_status
    )

    # Subscription API routes
    app.route("/api/subscriptions", methods=["GET"])(subscriptions.list_subscriptions)
    app.route("/api/subscriptions", methods=["POST"])(subscriptions.create_subscription)
    app.route("/api/subscriptions/<int:subscription_id>", methods=["PUT"])(
        subscriptions.update_subscription
    )
    app.route("/api/subscriptions/<int:subscription_id>", methods=["DELETE"])(
        subscriptions.delete_subscription
    )

    @app.context_processor
    def inject_groups():
        try:
            return {"all_groups": load_group_meta()}
        except Exception:
            return {"all_groups": []}

    @app.errorhandler(404)
    def page_not_found(error):
        current_user = _get_or_create_default_user()
        return render_template("404.html", current_user=current_user), 404

    return app
