"""Tests for web app database initialization"""

import unittest
from unittest.mock import patch

from events_scraper.lib.web.app import create_app
from tests.lib.core.test_base import DatabaseTestCase


class WebDatabaseInitializationTestCase(DatabaseTestCase):
    """Test database initialization in web app"""

    def setUp(self):
        """Set up test environment with clean database"""
        super().setUp()

    def test_create_app_in_test_mode_skips_config_loading(self):
        """Test that create_app() in test mode skips config loading"""

        with patch("events_scraper.lib.web.app.load_config") as mock_load_config:
            app = create_app(test_mode=True)

            # Verify config loading was NOT called in test mode
            mock_load_config.assert_not_called()
            self.assertIsNotNone(app)
            self.assertTrue(app.config["TESTING"])

    @patch("events_scraper.lib.web.app.setup_logging")
    @patch("events_scraper.lib.web.app.configure_database")
    @patch("events_scraper.lib.web.app.load_config")
    def test_create_app_loads_config_in_production_mode(
        self, mock_load_config, mock_configure_db, mock_setup_logging
    ):
        """Test that create_app() loads config in production mode"""

        mock_config = {"database": {"url": "sqlite:///test.db"}}
        mock_load_config.return_value = mock_config

        app = create_app(test_mode=False)

        # Verify config loading and setup were called
        mock_load_config.assert_called_once()
        mock_configure_db.assert_called_once_with(config=mock_config)
        mock_setup_logging.assert_called_once_with(config=mock_config)
        self.assertIsNotNone(app)
        self.assertFalse(app.config.get("TESTING", False))

    @patch("events_scraper.lib.web.app.load_config")
    def test_create_app_handles_config_loading_failure(self, mock_load_config):
        """Test that create_app() handles config loading failures gracefully"""

        # Mock config loading to raise an exception
        mock_load_config.side_effect = RuntimeError("Config loading failed")

        # App creation should raise the exception (fail fast)
        with self.assertRaises(RuntimeError) as context:
            create_app(test_mode=False)

        self.assertIn("Config loading failed", str(context.exception))

    def test_index_route_with_empty_database(self):
        """Test that index route redirects to /events/"""

        app = create_app(test_mode=True)
        with app.test_client() as client:
            response = client.get("/")

            # Index route redirects to /events/
            self.assertEqual(response.status_code, 302)
            self.assertIn("/events/", response.location)

    def test_events_route_handles_empty_database(self):
        """Test that events route handles empty database gracefully"""

        app = create_app(test_mode=True)
        with app.test_client() as client:
            # Follow the redirect from index to events
            response = client.get("/", follow_redirects=True)

            # Should succeed even with empty events
            self.assertEqual(response.status_code, 200)

    @patch("events_scraper.lib.web.app.setup_logging")
    @patch("events_scraper.lib.web.app.configure_database")
    @patch("events_scraper.lib.web.app.load_config")
    def test_app_uses_config_file_database(
        self, mock_load_config, mock_configure_db, mock_setup_logging
    ):
        """Test that the app uses config file database settings"""

        mock_config = {"database": {"url": "sqlite:///events.db"}}
        mock_load_config.return_value = mock_config

        create_app(test_mode=False)

        # Verify config was loaded and database/logging configured
        mock_load_config.assert_called_once()
        mock_configure_db.assert_called_once_with(config=mock_config)
        mock_setup_logging.assert_called_once_with(config=mock_config)


if __name__ == "__main__":
    unittest.main()
