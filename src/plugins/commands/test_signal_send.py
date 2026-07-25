"""Command `test_signal_send`."""

from __future__ import annotations

from argparse import Namespace
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from events_scraper.lib.config import load_config
from events_scraper.lib.core.orm_models import Base
from events_scraper.lib.core.orm_models import Event
from events_scraper.lib.core.orm_models import Notification
from events_scraper.lib.core.orm_models import User
from plugins.command_base import CommandPlugin
from plugins.notifiers.signal_notifier import SignalNotifier


class TestSignalSendCommand(CommandPlugin):

    def register_subparser(self, subparsers):
        return subparsers.add_parser(
            self.name,
            help="Send Signal test notification",
            description="Create test notification data and send one Signal notification.",
        )

    def run(self, args: Namespace) -> int:
        del args
        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(engine)
        session = sessionmaker(bind=engine)()

        try:
            config = load_config()
            plugins_config = config._get_section_config("plugins")
            signal_config = plugins_config.get("notifiers", {}).get("signal", {})
            sender_phone = signal_config.get("sender")

            user = User(username="test_user", phone_number=sender_phone)
            event = Event(
                title="Test Event",
                date=date(2025, 2, 14),
                time="18:00",
                detail_url="http://localhost/event/1",
                scraper="test",
            )
            session.add_all([user, event])
            session.commit()

            notification = Notification(
                user_id=user.id,
                event_id=event.id,
                notify_delta=259200,
                plugin="signal",
                status="pending",
            )
            notification.send_at = notification.calculate_send_at(event)
            session.add(notification)
            session.commit()

            notifier = SignalNotifier()
            result = notifier.send(notification)
            print(f"Signal send result: {result}")
            return 0 if result else 1
        finally:
            session.close()
            engine.dispose()


plugins = [TestSignalSendCommand()]
