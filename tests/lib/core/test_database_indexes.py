#!/usr/bin/env python3
"""
Test database query correctness
"""

import unittest

from events_scraper.lib import mock_data
from events_scraper.lib.core import configure_database
from events_scraper.lib.core import load_events_from_database
from events_scraper.lib.core.orm_models import Event as OrmEvent
from events_scraper.lib.core.orm_session import dispose_engine
from events_scraper.lib.core.orm_session import get_session


class TestDatabaseIndexes(unittest.TestCase):
    """Test database query correctness"""

    def setUp(self):
        """Set up test database with sample data"""
        configure_database(":memory:")

        # Use consistent test date for all events
        self.test_date = mock_data.get_date()

        # Create sample events for testing
        self.test_events = []
        for i in range(100):
            event = mock_data.get_event(
                date=self.test_date.strftime("%Y-%m-%d"),
                categories=[f"Category {i % 3}", f"Category {(i + 1) % 3}"],
                scraper=f"scraper{i % 2}.com",
            )
            self.test_events.append(event)

        # Store test events
        for event in self.test_events:
            event.save()

    def tearDown(self):
        """Clean up database connections"""
        dispose_engine()

    def test_query_correctness_by_date(self):
        """Test query correctness for date-based queries"""
        events = load_events_from_database(self.test_date)

        # Should find all 100 test events
        self.assertEqual(len(events), 100)

    def test_composite_query_correctness(self):
        """Test correctness of composite queries"""
        session = get_session()
        try:
            # Query using ORM - date and scraper filters
            results = (
                session.query(OrmEvent)
                .filter(
                    OrmEvent.date == self.test_date,
                    OrmEvent.scraper == "scraper0.com",
                )
                .all()
            )

            # Should find ~50 events (half have scraper0.com)
            self.assertGreater(len(results), 40)
            self.assertLess(len(results), 60)

        finally:
            session.close()

    def test_category_query_correctness(self):
        """Test correctness of category filtering queries"""
        session = get_session()
        try:
            # Query by category using ORM
            results = (
                session.query(OrmEvent)
                .filter(OrmEvent.categories.like("%Category 0%"))
                .all()
            )

            # Should find events with "Category 0"
            self.assertGreater(len(results), 30)

        finally:
            session.close()

    def test_location_query_correctness(self):
        """Test correctness of location-based queries"""
        session = get_session()
        try:
            # Get a location from one of our test events
            test_location = self.test_events[0].location

            # Test location query using ORM
            results = (
                session.query(OrmEvent).filter(OrmEvent.location == test_location).all()
            )

            # Should find at least 1 event (the one we used for the location)
            self.assertGreaterEqual(len(results), 1)

        finally:
            session.close()

    def test_orm_query_compilation(self):
        """Test that ORM queries compile and execute correctly"""
        session = get_session()
        try:
            # Test that we can create and execute ORM queries successfully
            results = (
                session.query(OrmEvent).filter(OrmEvent.date == self.test_date).all()
            )

            # Should find our test events
            self.assertEqual(len(results), 100)

            # Test composite query compilation
            results = (
                session.query(OrmEvent)
                .filter(
                    OrmEvent.date == self.test_date,
                    OrmEvent.scraper == "scraper0.com",
                )
                .all()
            )

            # Should find subset of events
            self.assertGreater(len(results), 40)
            self.assertLess(len(results), 60)

        finally:
            session.close()
