"""Test notification defaults configuration"""

import unittest

from events_scraper.lib.notification_defaults import create_notification_deltas
from events_scraper.lib.notification_defaults import DEFAULT_NOTIFICATION_DELTAS


class TestNotificationDefaults(unittest.TestCase):
    """Test notification defaults"""

    def test_default_notification_deltas_contains_3day_and_3hour(self):
        """Test create_notification_deltas returns list with 3-day and 3-hour deltas using config"""
        deltas = create_notification_deltas()

        self.assertEqual(len(deltas), 2)
        # Check 3 days (259200 seconds)
        self.assertIn((259200, "signal"), deltas)
        # Check 3 hours (10800 seconds)
        self.assertIn((10800, "signal"), deltas)

    def test_default_notification_deltas_uses_config(self):
        """Test deltas use configured constants"""
        deltas = create_notification_deltas()
        self.assertEqual(deltas, DEFAULT_NOTIFICATION_DELTAS)

    def test_create_notification_deltas_with_custom_deltas(self):
        """Test can provide custom deltas"""
        custom_deltas = [(86400, "test"), (3600, "test")]
        deltas = create_notification_deltas(custom_deltas)

        self.assertEqual(len(deltas), 2)
        self.assertEqual(deltas, custom_deltas)

    def test_default_deltas_not_modified_by_create(self):
        """Test DEFAULT_NOTIFICATION_DELTAS is not modified when creating deltas"""
        original_count = len(DEFAULT_NOTIFICATION_DELTAS)
        deltas = create_notification_deltas()
        deltas.append((1000, "test"))

        self.assertEqual(len(DEFAULT_NOTIFICATION_DELTAS), original_count)
        self.assertNotEqual(deltas, DEFAULT_NOTIFICATION_DELTAS)
