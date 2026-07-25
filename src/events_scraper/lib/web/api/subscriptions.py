"""Subscriptions API endpoints."""

import logging

from flask import jsonify
from flask import request

from events_scraper.lib.core.orm_models import Event as OrmEvent
from events_scraper.lib.core.orm_models import EventSubscription
from events_scraper.lib.core.orm_models import Notification
from events_scraper.lib.core.orm_models import User
from events_scraper.lib.core.orm_session import get_session
from events_scraper.lib.scraper_loader import get_supported_groups
from events_scraper.lib.subscriptions.backfill import (
    backfill_notifications_for_subscription,
)


def list_subscriptions():
    """API endpoint to list user's subscriptions."""
    session = get_session()
    try:
        # Get current user (admin for now)
        user = session.query(User).filter_by(username="admin").first()
        if not user:
            return jsonify({"subscriptions": []}), 200

        # Get all subscriptions for this user
        subscriptions = (
            session.query(EventSubscription)
            .filter_by(user_id=user.id)
            .order_by(EventSubscription.group, EventSubscription.keyword)
            .all()
        )

        subscription_list = []
        for sub in subscriptions:
            # Count pending notifications for this subscription
            try:
                pending_count = (
                    session.query(Notification)
                    .filter_by(subscription_id=sub.id, status="pending")
                    .count()
                )
            except Exception:
                # Column may not exist yet if migrations haven't run
                pending_count = 0

            subscription_list.append(
                {
                    "id": sub.id,
                    "group": sub.group,
                    "keyword": sub.keyword,
                    "title_keyword": sub.title_keyword,
                    "body_keyword": sub.body_keyword,
                    "status": sub.status,
                    "pending_notifications": pending_count,
                }
            )

        return jsonify({"subscriptions": subscription_list}), 200
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error fetching subscriptions: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


def create_subscription():
    """API endpoint to create subscription."""
    session = get_session()
    try:
        # Get current user (admin for now)
        user = session.query(User).filter_by(username="admin").first()
        if not user:
            user = User(username="admin")
            session.add(user)
            session.commit()

        # Get request data
        data = request.get_json() or {}
        title_keyword = (
            data.get("title_keyword", "").strip() if data.get("title_keyword") else None
        )
        body_keyword = (
            data.get("body_keyword", "").strip() if data.get("body_keyword") else None
        )
        groups = data.get("groups", [])

        # Validate at least one keyword
        if not title_keyword and not body_keyword:
            return jsonify({"error": "At least one keyword is required"}), 400

        # Validate groups
        if not groups or not isinstance(groups, list):
            return jsonify({"error": "Groups must be a non-empty list"}), 400

        # Create subscription for each group
        subscriptions = []
        supported = get_supported_groups()
        for group in groups:
            if group not in supported:
                return jsonify({"error": f"Invalid group: {group}"}), 400

            subscription = EventSubscription(
                user_id=user.id,
                group=group,
                keyword=f"{title_keyword or ''} {body_keyword or ''}".strip(),
                title_keyword=title_keyword,
                body_keyword=body_keyword,
                status="active",
            )
            session.add(subscription)
            subscriptions.append(subscription)

        session.commit()

        # Backfill notifications for each created subscription
        logger = logging.getLogger(__name__)
        for subscription in subscriptions:
            result = backfill_notifications_for_subscription(subscription, session)
            logger.info(
                f"Backfill for subscription {subscription.id}: "
                f"created {result['created']}, skipped {result['skipped']}"
            )

        # Get the last created subscription ID
        created = (
            session.query(EventSubscription)
            .filter_by(user_id=user.id)
            .order_by(EventSubscription.id.desc())
            .first()
        )

        return jsonify({"id": created.id if created else None}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error creating subscription: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


def _check_subscription_changes(subscription, data):
    """Check if subscription needs re-backfill due to keyword/group changes."""
    needs_rebackfill = False

    if "title_keyword" in data:
        title_keyword = data["title_keyword"].strip() if data["title_keyword"] else None
        if title_keyword != subscription.title_keyword:
            needs_rebackfill = True

    if "body_keyword" in data:
        body_keyword = data["body_keyword"].strip() if data["body_keyword"] else None
        if body_keyword != subscription.body_keyword:
            needs_rebackfill = True

    if "group" in data:
        new_group = data["group"].strip() if data["group"] else None
        if new_group and new_group != subscription.group:
            needs_rebackfill = True

    return needs_rebackfill


def _update_subscription_fields(subscription, data, user):
    """Update subscription fields from request data."""
    if "title_keyword" in data:
        title_keyword = data["title_keyword"].strip() if data["title_keyword"] else None
        subscription.title_keyword = title_keyword

    if "body_keyword" in data:
        body_keyword = data["body_keyword"].strip() if data["body_keyword"] else None
        subscription.body_keyword = body_keyword

    if "group" in data:
        new_group = data["group"].strip() if data["group"] else None
        if new_group:
            supported = get_supported_groups()
            if new_group not in supported:
                raise ValueError(f"Invalid group: {new_group}")
            subscription.group = new_group

    if "status" in data:
        subscription.status = data["status"]


def _rebackfill_subscription(subscription, user, session):
    """Delete old notifications and re-backfill with new criteria."""
    logger = logging.getLogger(__name__)
    # Delete existing notifications for this subscription's events
    session.query(Notification).filter_by(user_id=user.id).filter(
        Notification.event_id.in_(
            session.query(OrmEvent.id).filter(
                OrmEvent.scraper.startswith(f"{subscription.group}.")
            )
        )
    ).delete()
    session.commit()

    # Re-backfill with new criteria
    result = backfill_notifications_for_subscription(subscription, session)
    logger.info(
        f"Re-backfill for subscription {subscription.id}: "
        f"created {result['created']}, skipped {result['skipped']}"
    )


def update_subscription(subscription_id):
    """API endpoint to update subscription."""
    session = get_session()
    try:
        # Get current user
        user = session.query(User).filter_by(username="admin").first()
        if not user:
            return jsonify({"error": "User not found"}), 404

        # Get subscription
        subscription = (
            session.query(EventSubscription)
            .filter_by(id=subscription_id, user_id=user.id)
            .first()
        )
        if not subscription:
            return jsonify({"error": "Subscription not found"}), 404

        # Get request data
        data = request.get_json() or {}

        # Track if we need to re-backfill
        needs_rebackfill = _check_subscription_changes(subscription, data)

        # Update subscription fields
        try:
            _update_subscription_fields(subscription, data, user)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        # Validate at least one keyword is provided
        has_title = subscription.title_keyword and subscription.title_keyword.strip()
        has_body = subscription.body_keyword and subscription.body_keyword.strip()
        if not has_title and not has_body:
            return jsonify({"error": "At least one keyword is required"}), 400

        session.commit()

        # Re-backfill if needed
        if needs_rebackfill:
            _rebackfill_subscription(subscription, user, session)

        return jsonify({"status": "updated"}), 200
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error updating subscription: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


def delete_subscription(subscription_id):
    """API endpoint to delete subscription."""
    session = get_session()
    try:
        # Get current user
        user = session.query(User).filter_by(username="admin").first()
        if not user:
            return jsonify({"error": "User not found"}), 404

        # Get and delete subscription
        subscription = (
            session.query(EventSubscription)
            .filter_by(id=subscription_id, user_id=user.id)
            .first()
        )
        if not subscription:
            return jsonify({"error": "Subscription not found"}), 404

        session.delete(subscription)
        session.commit()

        return jsonify({"status": "deleted"}), 200
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error deleting subscription: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()
