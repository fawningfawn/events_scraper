"""Users API endpoints."""

import logging

from flask import jsonify
from flask import request

from events_scraper.lib.core.orm_models import User
from events_scraper.lib.core.orm_session import get_session


def get_user():
    """API endpoint to get current user details."""
    session = get_session()
    try:
        # Get current user (admin for now)
        user = session.query(User).filter_by(username="admin").first()
        if not user:
            return jsonify({"error": "User not found"}), 404

        return (
            jsonify(
                {
                    "username": user.username,
                    "phone_number": user.phone_number,
                    "default_group": user.default_group,
                }
            ),
            200,
        )
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error fetching user: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


def update_user():
    """API endpoint to update user details."""
    session = get_session()
    try:
        # Get current user (admin for now)
        user = session.query(User).filter_by(username="admin").first()
        if not user:
            return jsonify({"error": "User not found"}), 400

        # Get request data
        data = request.get_json() or {}

        # Track if any updates were made
        updated_fields = {}

        # Update phone_number if provided
        if "phone_number" in data:
            user.phone_number = data["phone_number"] or None
            updated_fields["phone_number"] = user.phone_number

        # Update default_group if provided
        if "default_group" in data:
            user.default_group = data["default_group"] or None
            updated_fields["default_group"] = user.default_group

        # If no fields were provided, return error
        if not updated_fields:
            return jsonify({"error": "No data to update"}), 400

        # Commit changes and return updated fields
        session.commit()
        return jsonify({"status": "updated", **updated_fields}), 200
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error updating user: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()
