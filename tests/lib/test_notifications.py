"""Test notification sending wrapper"""

import unittest
from datetime import datetime
from datetime import timedelta
from unittest.mock import MagicMock
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from events_scraper.lib import mock_data
from events_scraper.lib.core.orm_models import Base
from events_scraper.lib.notifications import send_pending_notifications
from plugins import load_many


class TestSendPendingNotifications(unittest.TestCase):
    """Test send_pending_notifications wrapper function"""

    def setUp(self):
        """Set up test database"""
        self.engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

    def tearDown(self):
        """Clean up database"""
        self.session.close()
        self.engine.dispose()

    def test_send_pending_notifications_finds_ready_notifications(self):
        """Test that send_pending_notifications finds notifications ready to send"""
        # Create test data
        user = mock_data.get_orm_user(session=self.session, phone_number="+491796994240")
        event = mock_data.get_orm_event(session=self.session)

        # Create notification with send_at in the past
        notification = mock_data.get_orm_notification(
            session=self.session, user=user, event=event
        )
        notification.send_at = datetime.now() - timedelta(hours=1)
        notification.status = "pending"

        self.session.commit()

        # Mock the plugin loader
        with patch("events_scraper.lib.notifications.load_many") as mock_load:
            mock_notifier = MagicMock()
            mock_notifier.name = "signal"
            mock_notifier.send.return_value = True
            mock_load.return_value = [mock_notifier]

            # Send notifications
            result = send_pending_notifications(session=self.session)

            # Should have sent the notification
            self.assertEqual(result, 1)
            mock_notifier.send.assert_called_once()

    def test_send_pending_notifications_skips_future_send_at(self):
        """Test that notifications with future send_at are skipped"""
        user = mock_data.get_orm_user(session=self.session, phone_number="+491796994240")
        event = mock_data.get_orm_event(session=self.session)

        # Create notification with send_at in the future
        notification = mock_data.get_orm_notification(
            session=self.session, user=user, event=event
        )
        notification.send_at = datetime.now() + timedelta(hours=1)
        notification.status = "pending"

        self.session.commit()

        with patch("events_scraper.lib.notifications.load_many") as mock_load:
            mock_notifier = MagicMock()
            mock_load.return_value = [mock_notifier]

            # Send notifications
            result = send_pending_notifications(session=self.session)

            # Should not send
            self.assertEqual(result, 0)
            mock_notifier.send.assert_not_called()

    def test_send_pending_notifications_updates_status_on_success(self):
        """Test that notification status is updated to 'sent' on success"""
        user = mock_data.get_orm_user(session=self.session, phone_number="+491796994240")
        event = mock_data.get_orm_event(session=self.session)

        notification = mock_data.get_orm_notification(
            session=self.session, user=user, event=event
        )
        notification.send_at = datetime.now() - timedelta(hours=1)
        notification.status = "pending"
        notification.sent_at = None

        self.session.commit()
        notif_id = notification.id

        with patch("events_scraper.lib.notifications.load_many") as mock_load:
            mock_notifier = MagicMock()
            mock_notifier.name = "signal"
            mock_notifier.send.return_value = True
            mock_load.return_value = [mock_notifier]

            send_pending_notifications(session=self.session)

            # Reload notification and check status
            updated = (
                self.session.query(notification.__class__).filter_by(id=notif_id).first()
            )
            self.assertEqual(updated.status, "sent")
            self.assertIsNotNone(updated.sent_at)

    def test_send_pending_notifications_updates_status_on_failure(self):
        """Test that notification status is updated to 'failed' on failure"""
        user = mock_data.get_orm_user(session=self.session, phone_number="+491796994240")
        event = mock_data.get_orm_event(session=self.session)

        notification = mock_data.get_orm_notification(
            session=self.session, user=user, event=event
        )
        notification.send_at = datetime.now() - timedelta(hours=1)
        notification.status = "pending"

        self.session.commit()
        notif_id = notification.id

        with patch("events_scraper.lib.notifications.load_many") as mock_load:
            mock_notifier = MagicMock()
            mock_notifier.name = "signal"
            mock_notifier.send.return_value = False
            mock_load.return_value = [mock_notifier]

            send_pending_notifications(session=self.session)

            # Reload notification and check status
            updated = (
                self.session.query(notification.__class__).filter_by(id=notif_id).first()
            )
            self.assertEqual(updated.status, "failed")

    def test_send_pending_notifications_skips_already_sent(self):
        """Test that already sent notifications are skipped"""
        user = mock_data.get_orm_user(session=self.session, phone_number="+491796994240")
        event = mock_data.get_orm_event(session=self.session)

        notification = mock_data.get_orm_notification(
            session=self.session, user=user, event=event
        )
        notification.status = "sent"
        notification.sent_at = datetime.now()

        self.session.commit()

        with patch("events_scraper.lib.notifications.load_many") as mock_load:
            mock_notifier = MagicMock()
            mock_load.return_value = [mock_notifier]

            result = send_pending_notifications(session=self.session)

            # Should not send
            self.assertEqual(result, 0)
            mock_notifier.send.assert_not_called()

    def test_send_pending_notifications_loads_real_plugins(self):
        """Integration test: verify plugin loader can load real plugins"""
        # Test that load_many actually returns signal notifier
        notifiers = {n.name: n for n in load_many("plugins.notifiers")}

        # Must have signal notifier
        self.assertIn("signal", notifiers)

        # Must have send method
        self.assertTrue(hasattr(notifiers["signal"], "send"))
        self.assertTrue(callable(notifiers["signal"].send))

    def test_send_pending_notifications_with_real_plugin_loader(self):
        """Integration test: verify notifications work with real plugin loader"""
        user = mock_data.get_orm_user(session=self.session, phone_number="+491796994240")
        event = mock_data.get_orm_event(session=self.session)

        notification = mock_data.get_orm_notification(
            session=self.session, user=user, event=event
        )
        notification.send_at = datetime.now() - timedelta(hours=1)
        notification.status = "pending"

        self.session.commit()

        # Don't mock load_many - use the real plugin loader
        # Mock only the actual Signal API call
        with patch("requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            # This should actually load the signal notifier plugin
            result = send_pending_notifications(session=self.session)

            # Should have attempted to send
            self.assertEqual(result, 1)
