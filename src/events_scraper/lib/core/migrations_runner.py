"""Simple SQL migration runner for database schema updates."""

import logging
from pathlib import Path

from sqlalchemy import text

logger = logging.getLogger(__name__)


def _ensure_migrations_table(session):
    """Create the migrations tracking table if it doesn't exist."""
    try:
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS migrations (
                id INTEGER PRIMARY KEY,
                filename TEXT UNIQUE NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        session.commit()
    except Exception as e:
        logger.warning(f"Could not create migrations table: {e}")


def _migration_already_applied(session, filename):
    """Check if a migration has already been applied."""
    try:
        result = session.execute(
            text("SELECT id FROM migrations WHERE filename = :filename"),
            {"filename": filename},
        )
        return result.fetchone() is not None
    except Exception as e:
        logger.debug(f"Could not check migration status: {e}")
        return False


def _execute_migration_file(session, filename, sql_content):
    """Execute all SQL statements in a migration file."""
    for statement in sql_content.split(";"):
        statement = statement.strip()
        if statement:
            try:
                session.execute(text(statement))
            except Exception as e:
                if "duplicate column" in str(e).lower():
                    logger.info(f"Column already exists (idempotent): {filename}")
                    break
                raise


def _record_migration(session, filename):
    """Record that a migration has been applied."""
    try:
        session.execute(
            text("INSERT INTO migrations (filename) VALUES (:filename)"),
            {"filename": filename},
        )
        session.commit()
        logger.info(f"Migration applied successfully: {filename}")
    except Exception as e:
        logger.warning(f"Could not record migration: {e}")


def run_migrations(session):
    """
    Run all SQL migration files from the migrations directory.

    Migrations are idempotent - they can be run multiple times safely.
    Only migrations that haven't been run are executed.

    Args:
        session: SQLAlchemy session to use for running migrations
    """
    migrations_dir = Path(__file__).parent / "migrations"

    if not migrations_dir.exists():
        logger.debug("No migrations directory found")
        return

    migration_files = sorted(migrations_dir.glob("*.sql"))

    if not migration_files:
        logger.debug("No migration files found")
        return

    _ensure_migrations_table(session)

    for migration_file in migration_files:
        filename = migration_file.name

        if _migration_already_applied(session, filename):
            logger.debug(f"Migration already applied: {filename}")
            continue

        try:
            sql_content = migration_file.read_text()
            logger.info(f"Running migration: {filename}")

            _execute_migration_file(session, filename, sql_content)
            session.commit()
            _record_migration(session, filename)
        except Exception as e:
            logger.error(f"Failed to run migration {filename}: {e}")
            session.rollback()
