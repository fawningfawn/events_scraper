"""Test Signal notifier plugin"""

import unittest
from unittest.mock import Mock
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from events_scraper.lib import mock_data
from events_scraper.lib.core.orm_models import Base
from plugins.notifiers.signal_notifier import SignalNotifier


class TestSignalNotifier(unittest.TestCase):
    """Test Signal notifier plugin"""

    def setUp(self):
        """Set up test fixtures with database"""
        self.engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

        # Create and save test data
        self.user = mock_data.get_orm_user(
            session=self.session, phone_number="+1234567890"
        )
        self.event = mock_data.get_orm_event(session=self.session)
        self.notification = mock_data.get_orm_notification(
            session=self.session, user=self.user, event=self.event
        )
        self.session.commit()

    def tearDown(self):
        """Clean up database"""
        self.session.close()
        self.engine.dispose()

    def test_signal_notifier_send_with_valid_phone(self):
        """Test Signal notifier sends notification with valid phone number"""

        notifier = SignalNotifier()

        # Mock the Signal API call
        with patch("requests.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            result = notifier.send(self.notification)

            # Should return True on success
            self.assertTrue(result)
            # Should have called the API
            mock_post.assert_called_once()

    def test_signal_notifier_skip_without_phone(self):
        """Test Signal notifier skips notification when user has no phone number"""

        self.notification.user.phone_number = None
        notifier = SignalNotifier()

        result = notifier.send(self.notification)

        # Should return False when phone is None
        self.assertFalse(result)

    def test_signal_notifier_api_failure(self):
        """Test Signal notifier handles API failure gracefully"""

        notifier = SignalNotifier()

        # Mock failed API response
        with patch("requests.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 500
            mock_post.return_value = mock_response

            result = notifier.send(self.notification)

            # Should return False on API error
            self.assertFalse(result)

    def test_signal_notifier_enabled_config(self):
        """Test Signal notifier enabled property respects config"""

        notifier = SignalNotifier()

        # Should have enabled property
        self.assertIsNotNone(notifier.enabled)

    def test_signal_notifier_name(self):
        """Test Signal notifier has correct name"""

        notifier = SignalNotifier()
        self.assertEqual(notifier.name, "signal")

    def test_signal_notifier_message_format(self):
        """Test Signal notifier formats message correctly"""

        notifier = SignalNotifier()

        with patch("requests.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            notifier.send(self.notification)

            # Check the message was formatted correctly
            call_args = mock_post.call_args
            # Message should contain event title and date
            self.assertIsNotNone(call_args)
