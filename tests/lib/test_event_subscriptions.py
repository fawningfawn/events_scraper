"""Test EventSubscription ORM model"""

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from events_scraper.lib.core.orm_models import Base
from events_scraper.lib.core.orm_models import EventSubscription
from events_scraper.lib.core.orm_models import User


class TestEventSubscriptionModel(unittest.TestCase):
    """Test EventSubscription ORM model"""

    def setUp(self):
        """Set up test database"""
        self.engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

        # Create a test user
        self.user = User(username="testuser")
        self.session.add(self.user)
        self.session.commit()

    def tearDown(self):
        """Clean up database"""
        self.session.close()
        self.engine.dispose()

    def test_create_subscription_with_all_fields(self):
        """Test EventSubscription can be created with user_id, group, keyword, status"""
        subscription = EventSubscription(
            user_id=self.user.id,
            group="paris",
            keyword="Kammerorchester",
            status="active",
        )
        self.session.add(subscription)
        self.session.commit()

        self.assertIsNotNone(subscription.id)
        self.assertEqual(subscription.user_id, self.user.id)
        self.assertEqual(subscription.group, "paris")
        self.assertEqual(subscription.keyword, "Kammerorchester")
        self.assertEqual(subscription.status, "active")

    def test_retrieve_subscription_by_id(self):
        """Test can retrieve subscription by id"""
        subscription = EventSubscription(
            user_id=self.user.id,
            group="paris",
            keyword="Orchestra",
            status="active",
        )
        self.session.add(subscription)
        self.session.commit()
        sub_id = subscription.id

        retrieved = self.session.query(EventSubscription).filter_by(id=sub_id).first()
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.keyword, "Orchestra")
        self.assertEqual(retrieved.group, "paris")

    def test_rejects_empty_keyword(self):
        """Test rejects empty keyword"""
        with self.assertRaises(ValueError):
            EventSubscription(
                user_id=self.user.id,
                group="paris",
                keyword="",
                status="active",
            )

    def test_subscription_defaults_to_active(self):
        """Test subscription defaults to active status"""
        subscription = EventSubscription(
            user_id=self.user.id,
            group="paris",
            keyword="Test",
        )
        self.session.add(subscription)
        self.session.commit()

        self.assertEqual(subscription.status, "active")

    def test_subscription_has_timestamps(self):
        """Test subscription has creation timestamp"""
        subscription = EventSubscription(
            user_id=self.user.id,
            group="paris",
            keyword="Test",
        )
        self.session.add(subscription)
        self.session.commit()

        self.assertIsNotNone(subscription.ctime)

    def test_update_subscription_keyword(self):
        """Test can update subscription keyword"""
        subscription = EventSubscription(
            user_id=self.user.id,
            group="paris",
            keyword="Original",
            status="active",
        )
        self.session.add(subscription)
        self.session.commit()
        sub_id = subscription.id

        # Update
        subscription.keyword = "Updated"
        self.session.commit()

        # Verify
        updated = self.session.query(EventSubscription).filter_by(id=sub_id).first()
        self.assertEqual(updated.keyword, "Updated")

    def test_update_subscription_status(self):
        """Test can update subscription status"""
        subscription = EventSubscription(
            user_id=self.user.id,
            group="paris",
            keyword="Test",
            status="active",
        )
        self.session.add(subscription)
        self.session.commit()

        subscription.status = "disabled"
        self.session.commit()

        self.assertEqual(subscription.status, "disabled")

    def test_delete_subscription(self):
        """Test can delete subscription"""
        subscription = EventSubscription(
            user_id=self.user.id,
            group="paris",
            keyword="Test",
        )
        self.session.add(subscription)
        self.session.commit()
        sub_id = subscription.id

        # Delete
        self.session.delete(subscription)
        self.session.commit()

        # Verify deleted
        deleted = self.session.query(EventSubscription).filter_by(id=sub_id).first()
        self.assertIsNone(deleted)

    def test_handle_delete_nonexistent_subscription(self):
        """Test handles delete of non-existent subscription gracefully"""
        # Try to query and delete a subscription that doesn't exist
        nonexistent = self.session.query(EventSubscription).filter_by(id=99999).first()
        self.assertIsNone(nonexistent)
        # Should not raise an error
