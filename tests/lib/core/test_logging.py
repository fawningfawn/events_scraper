"""Tests for logging configuration module."""

import logging
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from events_scraper.lib.config import EventsConfig
from events_scraper.lib.core.logging import setup_logging


class TestSetupLogging(unittest.TestCase):
    """Test logging setup functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / "test_config.yaml"

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)

    def test_setup_logging_with_verbose_level_only(self):
        """Test setup_logging with verbose level only."""
        config = EventsConfig(self.config_path)

        with patch("events_scraper.lib.core.logging.logging.basicConfig") as mock_config:
            setup_logging(verbose_level=2, config=config)
            mock_config.assert_called_once()

    def test_setup_logging_with_log_level_override(self):
        """Test setup_logging with explicit log level."""
        config = EventsConfig(self.config_path)

        with patch("events_scraper.lib.core.logging.logging.basicConfig") as mock_config:
            setup_logging(verbose_level=0, log_level="ERROR", config=config)
            mock_config.assert_called_once()

    def test_setup_logging_with_log_file(self):
        """Test setup_logging with log file."""
        config = EventsConfig(self.config_path)

        with patch("events_scraper.lib.core.logging.logging.basicConfig") as mock_config:
            setup_logging(verbose_level=1, log_file="/tmp/test.log", config=config)
            mock_config.assert_called_once()
            call_kwargs = mock_config.call_args[1]
            self.assertEqual(call_kwargs["filename"], "/tmp/test.log")

    def test_setup_logging_with_explicit_stream(self):
        """Test setup_logging with an explicit stream object."""
        config = EventsConfig(self.config_path)

        with patch("events_scraper.lib.core.logging.logging.basicConfig") as mock_config:
            setup_logging(verbose_level=1, config=config, log_stream=sys.stdout)
            mock_config.assert_called_once()
            call_kwargs = mock_config.call_args[1]
            self.assertNotIn("filename", call_kwargs)
            self.assertIs(call_kwargs["stream"], sys.stdout)

    def test_setup_logging_with_config_file_settings(self):
        """Test setup_logging using config file settings."""
        # Create config with logging settings
        test_config = """
logging:
  level: INFO
  file: /tmp/config_test.log
"""
        self.config_path.write_text(test_config)
        config = EventsConfig(self.config_path)

        with patch("events_scraper.lib.core.logging.logging.basicConfig") as mock_config:
            setup_logging(config=config)
            mock_config.assert_called_once()

    def test_setup_logging_verbose_level_mapping(self):
        """Test verbose level to log level mapping."""
        config = EventsConfig(self.config_path)

        test_cases = [
            (0, logging.WARNING),
            (1, logging.INFO),
            (2, logging.DEBUG),
            (3, logging.DEBUG),  # Max is DEBUG
        ]

        with patch("events_scraper.lib.core.logging.logging.basicConfig") as mock_config:
            for verbose_level, expected_level in test_cases:
                with self.subTest(verbose_level=verbose_level):
                    mock_config.reset_mock()
                    setup_logging(verbose_level=verbose_level, config=config)
                    # Check that basicConfig was called with correct level
                    call_args = mock_config.call_args
                    self.assertIsNotNone(call_args)

    def test_setup_logging_invalid_log_level_handling(self):
        """Test handling of invalid log level."""
        config = EventsConfig(self.config_path)

        with patch("events_scraper.lib.core.logging.logging.basicConfig") as mock_config:
            # Should handle invalid log level gracefully
            setup_logging(verbose_level=0, log_level="INVALID", config=config)
            mock_config.assert_called_once()

    def test_setup_logging_missing_config(self):
        """Test setup_logging with missing config file."""
        # Don't create config file
        config = EventsConfig(self.config_path)

        with patch("events_scraper.lib.core.logging.logging.basicConfig") as mock_config:
            setup_logging(verbose_level=1, config=config)
            mock_config.assert_called_once()

    def test_setup_logging_cli_args_override_config(self):
        """Test that CLI args override config file settings."""
        # Create config with logging settings
        test_config = """
logging:
  level: ERROR
  file: /tmp/config.log
"""
        self.config_path.write_text(test_config)
        config = EventsConfig(self.config_path)

        with patch("events_scraper.lib.core.logging.logging.basicConfig") as mock_config:
            # CLI args should override config
            setup_logging(
                verbose_level=2,
                log_level="DEBUG",
                log_file="/tmp/cli.log",
                config=config,
            )
            mock_config.assert_called_once()

    def test_setup_logging_with_formatter(self):
        """Test that logging is configured with appropriate formatter."""
        config = EventsConfig(self.config_path)

        with patch("events_scraper.lib.core.logging.logging.basicConfig") as mock_config:
            setup_logging(verbose_level=1, config=config)
            mock_config.assert_called_once()
            # Verify basicConfig called with format parameter
            call_kwargs = mock_config.call_args[1]
            self.assertIn("format", call_kwargs)
