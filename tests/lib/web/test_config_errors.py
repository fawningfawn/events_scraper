"""Tests for web app configuration errors"""

import unittest
from unittest.mock import patch

from events_scraper.lib.web.app import create_app
from tests.lib.core.test_base import DatabaseTestCase


class WebConfigErrorTestCase(DatabaseTestCase):
    """Test configuration error handling in web app"""

    def setUp(self):
        """Set up test environment with clean database"""
        super().setUp()

    @patch("events_scraper.lib.web.app.setup_logging")
    @patch("events_scraper.lib.web.app.configure_database")
    @patch("events_scraper.lib.web.app.load_config")
    def test_direct_config_usage_no_cli_args(
        self, mock_load_config, mock_configure_db, mock_setup_logging
    ):
        """Test that web app uses config directly without CLI args"""

        mock_config = {"database": {"url": "sqlite:///test.db"}}
        mock_load_config.return_value = mock_config

        app = create_app(test_mode=False)

        # Verify direct config usage without args
        mock_load_config.assert_called_once()
        mock_configure_db.assert_called_once_with(config=mock_config)
        mock_setup_logging.assert_called_once_with(config=mock_config)
        self.assertIsNotNone(app)

    @patch("events_scraper.lib.web.app.configure_database")
    @patch("events_scraper.lib.web.app.load_config")
    def test_configure_database_error(self, mock_load_config, mock_configure_db):
        """Test that configure_database errors are handled"""

        mock_config = {"database": {"url": "sqlite:///test.db"}}
        mock_load_config.return_value = mock_config

        # Mock configure_database to raise RuntimeError
        mock_configure_db.side_effect = RuntimeError("Database connection failed")

        # Should raise the RuntimeError (fail fast)
        with self.assertRaises(RuntimeError) as context:
            create_app(test_mode=False)

        self.assertIn("Database connection failed", str(context.exception))

    def test_test_mode_bypasses_config_setup(self):
        """Test that test mode bypasses config setup entirely"""

        # Should not raise any errors since config setup is skipped
        app = create_app(test_mode=True)

        self.assertIsNotNone(app)
        self.assertTrue(app.config["TESTING"])

    @patch("events_scraper.lib.web.app.setup_logging")
    @patch("events_scraper.lib.web.app.configure_database")
    @patch("events_scraper.lib.web.app.load_config")
    def test_setup_logging_error(
        self, mock_load_config, mock_configure_db, mock_setup_logging
    ):
        """Test that setup_logging errors are handled"""

        mock_config = {"logging": {"level": "DEBUG"}}
        mock_load_config.return_value = mock_config

        # Mock setup_logging to raise an error
        mock_setup_logging.side_effect = ValueError("Invalid log level")

        # Should raise the ValueError (fail fast)
        with self.assertRaises(ValueError) as context:
            create_app(test_mode=False)

        self.assertIn("Invalid log level", str(context.exception))

    @patch("events_scraper.lib.web.app.setup_logging")
    @patch("events_scraper.lib.web.app.configure_database")
    @patch("events_scraper.lib.web.app.load_config")
    def test_web_app_no_cli_args_dependency(
        self, mock_load_config, mock_configure_db, mock_setup_logging
    ):
        """Test that web app works independently of CLI args system"""

        mock_config = {
            "database": {"url": "sqlite:///events.db"},
            "logging": {"level": "INFO"},
        }
        mock_load_config.return_value = mock_config

        # Web app should work without any CLI args
        app = create_app(test_mode=False)

        # Verify it uses config directly, no args involved
        mock_load_config.assert_called_once()
        mock_configure_db.assert_called_once_with(config=mock_config)
        mock_setup_logging.assert_called_once_with(config=mock_config)

        # Verify no argparse.Namespace objects were created
        # (This is implicit - the mocks would fail if args were passed)
        self.assertIsNotNone(app)


if __name__ == "__main__":
    unittest.main()
