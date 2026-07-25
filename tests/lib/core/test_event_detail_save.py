"""Test EventDetail.save() method"""

import unittest
from unittest.mock import patch

from events_scraper.lib.core.models import EventDetail
from tests.lib.core.test_base import DatabaseTestCase


class TestEventDetailSave(DatabaseTestCase):
    """Test EventDetail save method"""

    def test_event_detail_has_save_method(self):
        """Test that EventDetail has a save() method"""
        detail = EventDetail(
            url="https://example.com/event/123",
            content="Test event content",
            scraper="test_scraper",
        )

        # Should have a save method
        self.assertTrue(hasattr(detail, "save"))
        self.assertTrue(callable(getattr(detail, "save")))

    def test_event_detail_save_stores_in_database(self):
        """Test that calling save() stores the detail in database"""
        detail = EventDetail(
            url="https://example.com/event/456",
            content="Another test event content",
            scraper="test_scraper",
        )

        # Call save explicitly
        detail.save()

        # Verify it's in database
        retrieved = EventDetail.get_detail("https://example.com/event/456")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.content, "Another test event content")
        self.assertEqual(retrieved.scraper, "test_scraper")

    def test_event_detail_save_is_idempotent(self):
        """Test that calling save() multiple times doesn't cause errors"""
        detail = EventDetail(
            url="https://example.com/event/789",
            content="Idempotent test content",
            scraper="test_scraper",
        )

        # Call save multiple times
        detail.save()
        detail.save()
        detail.save()

        # Should still work and have one entry
        retrieved = EventDetail.get_detail("https://example.com/event/789")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.content, "Idempotent test content")

    def test_get_detail_does_not_trigger_save(self):
        """Regression: reading details must not write back to database."""
        detail = EventDetail(
            url="https://example.com/event/999",
            content="Read path should be side-effect free",
            scraper="test_scraper",
        )
        detail.save()
        with patch("events_scraper.lib.core.models.save_event_detail") as mock_save:
            retrieved = EventDetail.get_detail("https://example.com/event/999")

        self.assertIsNotNone(retrieved)
        mock_save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
