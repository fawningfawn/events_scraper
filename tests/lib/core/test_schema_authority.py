"""Schema authority and drift guardrails for CI."""

import tempfile
import unittest
from pathlib import Path

from sqlalchemy import inspect
from sqlalchemy import text

from events_scraper.lib.core.database import configure_database
from events_scraper.lib.core.migrations_runner import run_migrations
from events_scraper.lib.core.orm_models import Event
from events_scraper.lib.core.orm_session import dispose_engine
from events_scraper.lib.core.orm_session import get_session


class TestSchemaAuthorityGuardrails(unittest.TestCase):
    """Guard schema authority and migration determinism."""

    def tearDown(self):
        dispose_engine()

    def test_migrations_apply_once_and_record_all_files(self):
        db_url = self._build_temp_sqlite_url()
        configure_database(db_url)

        session = get_session()
        try:
            run_migrations(session)
            run_migrations(session)
            migration_files = sorted(
                (Path("src/events_scraper/lib/core/migrations")).glob("*.sql")
            )
            expected_count = len(migration_files)
            if expected_count == 0:
                # No migrations to apply; verify the runner is a no-op.
                self.assertFalse(
                    inspect(session.bind).has_table("migrations"),
                    "migrations table should not be created when there are no files",
                )
                return
            actual_count = (
                session.execute(text("SELECT COUNT(*) FROM migrations")).scalar() or 0
            )
            self.assertEqual(actual_count, expected_count)
        finally:
            session.close()

    def test_events_table_schema_matches_orm_metadata(self):
        db_url = self._build_temp_sqlite_url()
        configure_database(db_url)

        session = get_session()
        try:
            run_migrations(session)
            inspector = inspect(session.bind)

            db_columns = {
                column["name"] for column in inspector.get_columns(Event.__tablename__)
            }
            model_columns = {column.name for column in Event.__table__.columns}
            self.assertEqual(db_columns, model_columns)

            db_unique_sets = {
                tuple(sorted(constraint.get("column_names") or []))
                for constraint in inspector.get_unique_constraints(Event.__tablename__)
            }
            model_unique_sets = {
                tuple(sorted(column.name for column in constraint.columns))
                for constraint in Event.__table__.constraints
                if constraint.__class__.__name__ == "UniqueConstraint"
            }
            self.assertEqual(db_unique_sets, model_unique_sets)
        finally:
            session.close()

    def test_clean_startup_schema_is_deterministic(self):
        snapshot_a = self._snapshot_for_new_database()
        snapshot_b = self._snapshot_for_new_database()
        self.assertEqual(snapshot_a, snapshot_b)

    def _snapshot_for_new_database(self):
        db_url = self._build_temp_sqlite_url()
        configure_database(db_url)
        session = get_session()
        try:
            run_migrations(session)
            inspector = inspect(session.bind)
            columns = [column["name"] for column in inspector.get_columns("events")]
            unique = sorted(
                tuple(sorted(constraint.get("column_names") or []))
                for constraint in inspector.get_unique_constraints("events")
            )
            return {"columns": columns, "unique": unique}
        finally:
            session.close()

    def _build_temp_sqlite_url(self) -> str:
        temp_dir = tempfile.mkdtemp(prefix="events_schema_guard_")
        db_path = Path(temp_dir) / "events.db"
        return f"sqlite:///{db_path}"
