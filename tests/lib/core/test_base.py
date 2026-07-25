"""Base test class for database-using tests"""

import os
import tempfile
import unittest

from sqlalchemy import text

from events_scraper.lib.core import configure_database
from events_scraper.lib.core.orm_models import Base
from events_scraper.lib.core.orm_session import dispose_engine
from events_scraper.lib.core.orm_session import get_session
from events_scraper.lib.core.orm_session import init_database


class BaseTestCase(unittest.TestCase):
    """Base test case that ensures database connections are cleaned up"""

    def tearDown(self):
        """Clean up database connections after each test"""
        dispose_engine()


class DatabaseTestCase(BaseTestCase):
    """Base test case that provides clean SQLite database for each test"""

    def setUp(self):
        """Set up clean database for each test"""
        # Create a unique temporary file database for each test
        # This ensures complete isolation between tests
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()

        # Configure with the temporary database file
        configure_database(f"sqlite:///{self.temp_db.name}")

    def tearDown(self):
        """Clean up database after each test"""
        super().tearDown()
        if hasattr(self, "temp_db") and os.path.exists(self.temp_db.name):
            try:
                os.unlink(self.temp_db.name)
            except OSError:
                pass


class PostgreSQLTestCase(BaseTestCase):
    """Base test case that provides clean PostgreSQL database for each test"""

    def setUp(self):
        """Set up clean PostgreSQL database for each test"""
        # Use PostgreSQL from docker-compose or environment
        postgres_url = os.getenv(
            "POSTGRES_URL",
            "postgresql://events_user:events_pass@localhost:5432/events_test",
        )

        # Drop and recreate tables to ensure schema is current
        engine = init_database(postgres_url)
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)

        # Configure with PostgreSQL
        configure_database(postgres_url)

    def tearDown(self):
        """Clean up PostgreSQL data after each test"""
        self._cleanup_postgresql_data()
        super().tearDown()

    def _cleanup_postgresql_data(self):
        """Clean up all data from PostgreSQL tables using Django-style TRUNCATE"""
        session = get_session()
        try:
            # Get all table names from SQLAlchemy metadata
            table_names = [table.name for table in Base.metadata.tables.values()]

            if table_names:
                # Use TRUNCATE for faster cleanup (Django TransactionTestCase style)
                tables_str = ", ".join(table_names)
                session.execute(
                    text(f"TRUNCATE TABLE {tables_str} RESTART IDENTITY CASCADE")
                )
                session.commit()
        except Exception:
            session.rollback()
        finally:
            session.close()
