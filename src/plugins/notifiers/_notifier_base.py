"""Base class for notification plugins"""

import abc


class Notifier(metaclass=abc.ABCMeta):
    """Abstract base class for notification plugins"""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Plugin name (e.g., 'signal')"""

    @property
    @abc.abstractmethod
    def enabled(self) -> bool:
        """Whether the plugin is enabled based on configuration"""

    @abc.abstractmethod
    def send(self, notification) -> bool:
        """
        Send a notification.

        Args:
            notification: Notification ORM object

        Returns:
            bool: True if notification was sent successfully, False otherwise
        """
