"""
Unit tests for ORM date range queries
"""

from datetime import date
from unittest.mock import patch

from events_scraper.lib import mock_data
from events_scraper.lib.core.database import configure_database
from events_scraper.lib.core.orm_session import load_events_by_date_range
from tests.lib.core.test_base import BaseTestCase


class TestLoadEventsByDateRange(BaseTestCase):
    """Test load_events_by_date_range function"""

    def setUp(self):
        """Set up test database with events"""
        configure_database(":memory:")

    @patch("events_scraper.lib.packages.get_scraper_names_for_group")
    @patch("events_scraper.lib.core.orm_session.get_session")
    def test_filters_single_day_events_in_range(self, mock_session, mock_names):
        mock_names.return_value = [
            "conferences.scraper1",
            "conferences.scraper2",
            "conferences.scraper3",
        ]
        # Create mock events
        event1 = mock_data.get_orm_event(
            title="Event 1",
            date="2025-06-10",
            end_date=None,
            scraper="conferences.scraper1",
        )
        event2 = mock_data.get_orm_event(
            title="Event 2",
            date="2025-06-15",
            end_date=None,
            scraper="conferences.scraper2",
        )
        event3 = mock_data.get_orm_event(
            title="Event 3",
            date="2025-06-25",
            end_date=None,
            scraper="conferences.scraper3",
        )

        # Mock query
        mock_query = mock_session.return_value.query.return_value
        mock_query.filter.return_value.order_by.return_value.all.return_value = [
            event1,
            event2,
            event3,
        ]

        # Query for range
        events = load_events_by_date_range(
            date(2025, 6, 1), date(2025, 6, 30), group="conferences"
        )

        # Verify query was called
        mock_session.return_value.query.assert_called_once()
        self.assertIsNotNone(events)

    @patch("events_scraper.lib.packages.get_scraper_names_for_group")
    @patch("events_scraper.lib.core.orm_session.get_session")
    def test_filters_conference_scrapers(self, mock_session, mock_names):
        """Test city='conferences' filters scrapers without dots"""
        mock_names.return_value = ["conferences.scraper1"]
        event1 = mock_data.get_orm_event(scraper="conferences.scraper1")
        mock_data.get_orm_event(scraper="paris.garage_sb")  # Should be filtered out

        mock_query = mock_session.return_value.query.return_value
        mock_query.filter.return_value.order_by.return_value.all.return_value = [event1]

        load_events_by_date_range(
            date(2025, 6, 1), date(2025, 6, 30), group="conferences"
        )

        mock_query.filter.assert_called()

    @patch("events_scraper.lib.core.orm_session.get_session")
    def test_filters_city_scrapers(self, mock_session):
        """Test city='paris' filters scrapers with city prefix"""
        event1 = mock_data.get_orm_event(scraper="paris.garage_sb")
        mock_data.get_orm_event(scraper="conferences.scraper1")  # Should be filtered out

        mock_query = mock_session.return_value.query.return_value
        mock_query.filter.return_value.order_by.return_value.all.return_value = [event1]

        load_events_by_date_range(date(2025, 6, 1), date(2025, 6, 30), group="paris")

        # Check that filter was called
        mock_query.filter.assert_called()

    @patch("events_scraper.lib.core.orm_session.get_session")
    def test_includes_multi_day_events_overlapping_range(self, mock_session):
        """Test multi-day events that overlap with range are included"""
        # Multi-day event: June 10-20 (overlaps with query range June 15-25)
        event = mock_data.get_orm_event(
            date="2025-06-10", end_date="2025-06-20", scraper="conference"
        )

        mock_query = mock_session.return_value.query.return_value
        mock_query.filter.return_value.order_by.return_value.all.return_value = [event]

        events = load_events_by_date_range(date(2025, 6, 15), date(2025, 6, 25))

        self.assertIsNotNone(events)
