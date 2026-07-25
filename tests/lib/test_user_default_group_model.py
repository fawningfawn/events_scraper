"""Test User model default_group field"""

import unittest

from events_scraper.lib.core.orm_models import User
from events_scraper.lib.core.orm_session import get_session
from events_scraper.lib.core.orm_session import init_database


class TestUserDefaultGroupModel(unittest.TestCase):
    """Test User model default_group field"""

    def setUp(self):
        """Set up test database"""
        self.engine = init_database("sqlite:///:memory:")

    def tearDown(self):
        """Clean up test database"""
        self.engine.dispose()

    def test_user_has_default_group_field(self):
        """Test User model has default_group field"""
        session = get_session()
        user = User(username="testuser")
        session.add(user)
        session.commit()

        # Should have default_group attribute
        self.assertTrue(hasattr(user, "default_group"))
        # Should be None by default
        self.assertIsNone(user.default_group)

        session.close()

    def test_user_can_set_default_group(self):
        """Test User can set default_group"""
        session = get_session()
        user = User(username="testuser", default_group="paris")
        session.add(user)
        session.commit()

        # Verify it's stored
        self.assertEqual(user.default_group, "paris")

        # Query it back from database
        queried_user = session.query(User).filter_by(username="testuser").first()
        self.assertEqual(queried_user.default_group, "paris")

        session.close()

    def test_user_can_update_default_group(self):
        """Test User can update default_group"""
        session = get_session()
        user = User(username="testuser", default_group="paris")
        session.add(user)
        session.commit()

        user.default_group = "hamburg"
        session.commit()

        # Verify update
        self.assertEqual(user.default_group, "hamburg")

        # Query it back
        queried_user = session.query(User).filter_by(username="testuser").first()
        self.assertEqual(queried_user.default_group, "hamburg")

        session.close()

    def test_user_can_clear_default_group(self):
        """Test User can clear default_group (set to null)"""
        session = get_session()
        user = User(username="testuser", default_group="munich")
        session.add(user)
        session.commit()

        user.default_group = None
        session.commit()

        # Verify it's cleared
        self.assertIsNone(user.default_group)

        # Query it back
        queried_user = session.query(User).filter_by(username="testuser").first()
        self.assertIsNone(queried_user.default_group)

        session.close()

    def test_default_group_is_optional(self):
        """Test default_group is optional and doesn't break user creation"""
        session = get_session()
        # Create user without default_group
        user = User(username="testuser")
        session.add(user)
        session.commit()

        # Should be created successfully with default_group as None
        queried_user = session.query(User).filter_by(username="testuser").first()
        self.assertIsNotNone(queried_user)
        self.assertIsNone(queried_user.default_group)

        session.close()
