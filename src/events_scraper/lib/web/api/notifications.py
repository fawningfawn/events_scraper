"""Notifications API endpoints."""

import logging

from flask import jsonify

from events_scraper.lib.core.orm_models import Event as OrmEvent
from events_scraper.lib.core.orm_models import Notification
from events_scraper.lib.core.orm_models import User
from events_scraper.lib.core.orm_session import get_session


def get_notification_status(event_id):
    """API endpoint to check subscription status."""
    session = get_session()
    try:
        # Check if event exists
        orm_event = session.query(OrmEvent).filter(OrmEvent.id == event_id).first()
        if not orm_event:
            return jsonify({"error": "Event not found"}), 400

        # Get current user (admin for now)
        user = session.query(User).filter_by(username="admin").first()
        if not user:
            return jsonify({"subscribed": False}), 200

        # Check if user has notification for this event
        notification = (
            session.query(Notification)
            .filter_by(user_id=user.id, event_id=event_id)
            .first()
        )

        return jsonify({"subscribed": notification is not None}), 200
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error checking notification status: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


def get_user_notifications():
    """API endpoint to get user's notifications."""
    session = get_session()
    try:
        user = session.query(User).filter_by(username="admin").first()
        if not user:
            return jsonify({"notifications": []}), 200

        notifications = (
            session.query(Notification)
            .filter_by(user_id=user.id)
            .order_by(Notification.send_at.asc())
            .all()
        )

        notification_list = []
        for notif in notifications:
            event = session.query(OrmEvent).filter(OrmEvent.id == notif.event_id).first()
            if event:
                notification_list.append(
                    {
                        "id": notif.id,
                        "event_id": event.id,
                        "event_title": event.title,
                        "event_date": str(event.date),
                        "status": notif.status,
                        "send_at": (
                            notif.send_at.strftime("%Y-%m-%d %H:%M")
                            if notif.send_at
                            else None
                        ),
                        "sent_at": (
                            notif.sent_at.strftime("%Y-%m-%d %H:%M")
                            if notif.sent_at
                            else None
                        ),
                    }
                )

        return jsonify({"notifications": notification_list}), 200
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error fetching notifications: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()
