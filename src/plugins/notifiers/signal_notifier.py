"""Signal notifier plugin for sending notifications via Signal"""

import logging

import requests

from events_scraper.lib.config import load_config
from plugins.notifiers._notifier_base import Notifier

logger = logging.getLogger(__name__)


class SignalNotifier(Notifier):
    """Notifier plugin for sending notifications via Signal API"""

    def __init__(self):
        """Initialize Signal notifier with config"""
        try:
            self.config = load_config()
        except Exception as e:
            logger.warning(f"Failed to load config for Signal notifier: {e}")
            self.config = None

    @property
    def name(self) -> str:
        """Plugin name"""
        return "signal"

    @property
    def enabled(self) -> bool:
        """Check if Signal notifier is enabled in config"""
        if not self.config:
            return False

        try:
            plugins_config = self.config._get_section_config("plugins")
            signal_config = plugins_config.get("notifiers", {}).get("signal", {})
            host = signal_config.get("host")
            port = signal_config.get("port")
            sender = signal_config.get("sender")
            return all([host, port, sender])
        except Exception as e:
            logger.warning(f"Error checking Signal notifier enabled status: {e}")
            return False

    def send(self, notification) -> bool:
        """
        Send notification via Signal API.

        Args:
            notification: Notification ORM object with user and event relationships

        Returns:
            bool: True if sent successfully, False otherwise
        """
        # Skip if user has no phone number
        if not notification.user or not notification.user.phone_number:
            logger.debug(f"Skipping notification {notification.id}: no phone number")
            return False

        try:
            # Get Signal config
            plugins_config = self.config._get_section_config("plugins")
            signal_config = plugins_config.get("notifiers", {}).get("signal", {})
            host = signal_config.get("host")
            port = signal_config.get("port")
            sender = signal_config.get("sender")

            # Construct API URL
            api_url = f"{host}:{port}/v2/send"

            # Format message
            event = notification.event
            message = f"{event.title} on {event.date}"

            # Prepare request data
            data = {
                "message": message,
                "number": sender,
                "recipients": [notification.user.phone_number],
            }

            # Send via Signal API
            logger.debug(f"Sending to {api_url}: {data}")
            response = requests.post(api_url, json=data)

            if response.status_code in (200, 201):
                logger.info(
                    f"Successfully sent notification {notification.id} to "
                    f"{notification.user.phone_number}"
                )
                return True
            else:
                logger.error(
                    f"Failed to send notification {notification.id}: "
                    f"HTTP {response.status_code}: {response.text}"
                )
                return False

        except Exception as e:
            logger.error(f"Error sending notification {notification.id}: {e}")
            return False


# Module-level exports for notification system
name = "signal"


def send(notification) -> bool:
    """Send a notification using Signal notifier."""
    return SignalNotifier().send(notification)
