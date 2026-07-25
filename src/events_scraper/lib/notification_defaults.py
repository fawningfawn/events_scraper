"""Default notification configuration"""

# Default notification deltas (in seconds)
DEFAULT_NOTIFICATION_DELTAS = [
    (259200, "signal"),  # 3 days = 259200 seconds
    (10800, "signal"),  # 3 hours = 10800 seconds
]


def create_notification_deltas(deltas=None):
    """
    Create notification delta configurations.

    Args:
        deltas: Optional list of (seconds, plugin) tuples. Defaults to DEFAULT_NOTIFICATION_DELTAS

    Returns:
        List of (seconds, plugin) tuples
    """
    if deltas is None:
        return DEFAULT_NOTIFICATION_DELTAS.copy()
    return list(deltas)
