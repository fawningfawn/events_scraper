"""Groups API endpoints."""

import logging

from flask import jsonify

from events_scraper.lib.scraper_loader import get_supported_groups


def get_groups():
    """Get list of available groups from scrapers."""
    try:
        groups = get_supported_groups()
        return jsonify({"groups": groups}), 200
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error fetching groups: {e}")
        return jsonify({"error": str(e)}), 500
