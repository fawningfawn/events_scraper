"""Tests for configuration functionality."""

import importlib
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import xdg

from events_scraper.lib import mock_data
from events_scraper.lib.config import apply_config_filters
from events_scraper.lib.config import EventsConfig
from events_scraper.lib.config import get_config_path
from events_scraper.lib.config import load_config
from events_scraper.lib.config import xdg_config_home
from events_scraper.lib.core import EventCollection


class TestXDGPaths(unittest.TestCase):
    """Test XDG path functions."""

    def test_xdg_config_home_default(self):
        """Test XDG config home with default path."""

        with patch.dict(os.environ, {}, clear=True):
            importlib.reload(xdg)

            expected = Path.home() / ".config"
            self.assertEqual(xdg_config_home(), expected)

    def test_xdg_config_home_env_var(self):
        """Test XDG config home with environment variable."""
        custom_path = "/tmp/custom_config"
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": custom_path}):

            importlib.reload(xdg)
            self.assertEqual(xdg_config_home(), Path(custom_path))

    def test_get_config_path(self):
        """Test getting config file path."""
        result = get_config_path()
        expected = xdg_config_home() / "events_scraper" / "events.yaml"
        self.assertEqual(result, expected)


class TestEventsConfig(unittest.TestCase):
    """Test EventsConfig class."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / "test_config.yaml"

    def tearDown(self):
        """Clean up test fixtures."""

        shutil.rmtree(self.temp_dir)

    def test_config_init_no_file_creates_default(self):
        """Test config initialization creates default file when none exists."""
        config = EventsConfig(self.config_path)

        # Should create the file
        self.assertTrue(self.config_path.exists())

        # Should have empty config data initially
        self.assertEqual(config._config_data, {})

    def test_config_init_loads_existing_file(self):
        """Test config initialization loads existing file."""
        # Create a test config file
        test_config = """
filters:
  categories:
    include: ["Sport", "Music"]
    exclude: ["Market"]
  titles:
    exclude_patterns: ["cancelled"]
"""
        self.config_path.write_text(test_config)

        config = EventsConfig(self.config_path)

        # Should load the data
        self.assertEqual(config.get_include_categories(), ["Sport", "Music"])
        self.assertEqual(config.get_exclude_categories(), ["Market"])
        self.assertEqual(config.get_exclude_title_patterns(), ["cancelled"])

    def test_config_init_invalid_yaml(self):
        """Test config initialization with invalid YAML."""
        # Create invalid YAML
        self.config_path.write_text("invalid: yaml: content: [")

        # Should raise exception for invalid YAML
        with self.assertRaises(Exception):
            EventsConfig(self.config_path)

    def test_get_methods_empty_config(self):
        """Test getter methods with empty config."""
        config = EventsConfig(self.config_path)

        self.assertEqual(config.get_include_categories(), [])
        self.assertEqual(config.get_exclude_categories(), [])
        self.assertEqual(config.get_exclude_title_patterns(), [])

    def test_should_include_event_no_filters(self):
        """Test should_include_event with no filters configured."""
        config = EventsConfig(self.config_path)

        # Should include everything when no filters
        self.assertTrue(config.should_include_event("Test Event", "Sport"))
        self.assertTrue(config.should_include_event("Another Event"))

    def test_should_include_event_category_include(self):
        """Test should_include_event with category include list."""
        test_config = """
filters:
  categories:
    include: ["Sport", "Music"]
"""
        self.config_path.write_text(test_config)
        config = EventsConfig(self.config_path)

        # Should include only specified categories
        self.assertTrue(config.should_include_event("Test Event", "Sport"))
        self.assertTrue(config.should_include_event("Test Event", "Music"))
        self.assertFalse(config.should_include_event("Test Event", "Market"))

    def test_should_include_event_category_exclude(self):
        """Test should_include_event with category exclude list."""
        test_config = """
filters:
  categories:
    exclude: ["Market", "Politics"]
"""
        self.config_path.write_text(test_config)
        config = EventsConfig(self.config_path)

        # Should exclude only specified categories
        self.assertTrue(config.should_include_event("Test Event", "Sport"))
        self.assertFalse(config.should_include_event("Test Event", "Market"))
        self.assertFalse(config.should_include_event("Test Event", "Politics"))

    def test_should_include_event_title_exclude_patterns(self):
        """Test should_include_event with title exclude patterns."""
        test_config = """
filters:
  titles:
    exclude_patterns: ["cancelled", "postponed", "\\\\btest\\\\b"]
"""
        self.config_path.write_text(test_config)
        config = EventsConfig(self.config_path)

        # Should exclude matching titles
        self.assertTrue(config.should_include_event("Jazz Concert"))
        self.assertFalse(config.should_include_event("Concert Cancelled"))
        self.assertFalse(config.should_include_event("Event Postponed"))
        self.assertFalse(config.should_include_event("Test Event"))

    def test_should_include_event_location_exclude_patterns(self):
        """Test should_include_event with location exclude patterns."""
        test_config = """
filters:
  locations:
    exclude_patterns: ["online", "world.*web"]
"""
        self.config_path.write_text(test_config)
        config = EventsConfig(self.config_path)

        # Should exclude matching locations
        self.assertTrue(
            config.should_include_event("Test Event", location="Concert Hall")
        )
        self.assertFalse(config.should_include_event("Test Event", location="online"))
        self.assertFalse(
            config.should_include_event("Test Event", location="world wide web")
        )
        self.assertFalse(
            config.should_include_event("Test Event", location="world_wide_web")
        )

    def test_get_exclude_location_patterns(self):
        """Test getting location exclude patterns from config."""
        test_config = """
filters:
  locations:
    exclude_patterns: ["online", "remote"]
"""
        self.config_path.write_text(test_config)
        config = EventsConfig(self.config_path)

        patterns = config.get_exclude_location_patterns()
        self.assertEqual(patterns, ["online", "remote"])

    def test_get_exclude_location_patterns_by_group(self):
        """Test group-level filter merging with global patterns."""
        test_config = """
filters:
  locations:
    exclude_patterns: ["online"]
  by_group:
    paris:
      locations:
        exclude_patterns: ["remote"]
"""
        self.config_path.write_text(test_config)
        config = EventsConfig(self.config_path)

        # Global patterns
        global_patterns = config.get_exclude_location_patterns()
        self.assertEqual(global_patterns, ["online"])

        # Group patterns (should include both global and group-specific)
        group_patterns = config.get_exclude_location_patterns(group="paris")
        self.assertEqual(sorted(group_patterns), sorted(["online", "remote"]))

        # Different group (should use global only)
        other_group_patterns = config.get_exclude_location_patterns(group="london")
        self.assertEqual(other_group_patterns, ["online"])

    def test_get_exclude_location_patterns_by_scraper(self):
        """Test scraper-level filter merging with global and group patterns."""
        test_config = """
filters:
  locations:
    exclude_patterns: ["online"]
  by_group:
    paris:
      locations:
        exclude_patterns: ["remote"]
  by_scraper:
    alte_oper:
      locations:
        exclude_patterns: ["studio"]
"""
        self.config_path.write_text(test_config)
        config = EventsConfig(self.config_path)

        # Global patterns
        global_patterns = config.get_exclude_location_patterns()
        self.assertEqual(global_patterns, ["online"])

        # Group patterns (global + group)
        group_patterns = config.get_exclude_location_patterns(group="paris")
        self.assertEqual(sorted(group_patterns), sorted(["online", "remote"]))

        # Scraper patterns (global + scraper)
        scraper_patterns = config.get_exclude_location_patterns(scraper="alte_oper")
        self.assertEqual(sorted(scraper_patterns), sorted(["online", "studio"]))

        # Group + scraper patterns (global + group + scraper)
        full_patterns = config.get_exclude_location_patterns(
            group="paris", scraper="alte_oper"
        )
        self.assertEqual(sorted(full_patterns), sorted(["online", "remote", "studio"]))

    @patch("events_scraper.lib.config.yaml", None)
    def test_config_without_yaml(self):
        """Test config functionality when PyYAML is not available."""
        config = EventsConfig(self.config_path)

        # Should have empty config
        self.assertEqual(config._config_data, {})
        self.assertEqual(config.get_include_categories(), [])


class TestApplyConfigFilters(unittest.TestCase):
    """Test apply_config_filters function."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / "test_config.yaml"

        # Create test events using fully random mock_data
        self.events = [
            mock_data.get_event(),
            mock_data.get_event(),
            mock_data.get_event(),
            mock_data.get_event(),
        ]
        self.event_collection = EventCollection(self.events)

    def tearDown(self):
        """Clean up test fixtures."""

        shutil.rmtree(self.temp_dir)

    def test_apply_config_filters_no_config(self):
        """Test apply_config_filters with no config file."""
        # Use a custom config path that doesn't interfere with other tests
        temp_config_path = Path(self.temp_dir) / "empty_config.yaml"
        config = EventsConfig(temp_config_path)

        result = apply_config_filters(self.event_collection, config=config)

        # Should return all events when no filters
        result_events = result.to_list()
        self.assertEqual(
            len(result_events),
            4,
            f"Expected 4 events, got {len(result_events)}: {[e.title for e in result_events]}",
        )

    def test_apply_config_filters_disabled(self):
        """Test apply_config_filters with filters disabled."""
        # Create config with filters
        test_config = """
filters:
  categories:
    include: ["Music"]
"""
        self.config_path.write_text(test_config)
        config = EventsConfig(self.config_path)

        result = apply_config_filters(
            self.event_collection, config=config, filters_enabled=False
        )

        # Should return all events when filters disabled
        self.assertEqual(len(result.to_list()), 4)

    def test_apply_config_filters_config_only(self):
        """Test apply_config_filters with config file only."""
        test_config = """
filters:
  categories:
    include: ["Music"]
"""
        self.config_path.write_text(test_config)
        config = EventsConfig(self.config_path)

        result = apply_config_filters(self.event_collection, config=config)

        # Should filter to events with categories containing "Music"
        filtered_events = result.to_list()
        # Count events that have "Music" in their categories
        expected_count = len(
            [
                e
                for e in self.events
                if any("music" in cat.lower() for cat in e.categories)
            ]
        )
        self.assertEqual(len(filtered_events), expected_count)

        # Verify all filtered events have "Music" in categories
        for event in filtered_events:
            has_music = any("music" in cat.lower() for cat in event.categories)
            self.assertTrue(
                has_music, f"Event should have Music in categories: {event.categories}"
            )

    def test_apply_config_filters_cli_override(self):
        """Test apply_config_filters with CLI args overriding config."""
        test_config = """
filters:
  categories:
    include: ["Music"]
"""
        self.config_path.write_text(test_config)
        config = EventsConfig(self.config_path)

        result = apply_config_filters(
            self.event_collection,
            config=config,
            cli_include_categories=["Sport"],  # Override config
        )

        # Should use CLI args, not config - filter for "Sport" category
        filtered_events = result.to_list()
        expected_count = len(
            [
                e
                for e in self.events
                if any("sport" in cat.lower() for cat in e.categories)
            ]
        )
        self.assertEqual(len(filtered_events), expected_count)

        # Verify all filtered events have "Sport" in categories
        for event in filtered_events:
            has_sport = any("sport" in cat.lower() for cat in event.categories)
            self.assertTrue(
                has_sport, f"Event should have Sport in categories: {event.categories}"
            )

    def test_apply_config_filters_mixed_filters(self):
        """Test apply_config_filters with both category and title filters."""
        test_config = """
filters:
  categories:
    exclude: ["Culture"]
  titles:
    exclude_patterns: ["cancelled"]
"""
        self.config_path.write_text(test_config)
        config = EventsConfig(self.config_path)

        result = apply_config_filters(self.event_collection, config=config)

        # Should exclude events with categories containing "Culture" and titles containing "cancelled"
        filtered_events = result.to_list()

        # Verify filtering logic: no events should have "Culture" in categories or "cancelled" in title
        for event in filtered_events:
            has_culture = any("culture" in cat.lower() for cat in event.categories)
            has_cancelled = "cancelled" in event.title.lower()
            self.assertFalse(
                has_culture,
                f"Event should not have Culture category: {event.categories}",
            )
            self.assertFalse(
                has_cancelled,
                f"Event title should not contain 'cancelled': {event.title}",
            )

        # Count should be the number of events that don't match exclusion criteria
        expected_count = len(
            [
                e
                for e in self.events
                if not any("culture" in cat.lower() for cat in e.categories)
                and "cancelled" not in e.title.lower()
            ]
        )
        self.assertEqual(len(filtered_events), expected_count)

    def test_apply_config_filters_location_exclude(self):
        """Test apply_config_filters with location exclude patterns."""
        test_config = """
filters:
  locations:
    exclude_patterns: ["online", "remote"]
"""
        self.config_path.write_text(test_config)
        config = EventsConfig(self.config_path)

        result = apply_config_filters(self.event_collection, config=config)

        # Should exclude events with locations matching the patterns
        filtered_events = result.to_list()

        # Verify no events have "online" or "remote" in location
        for event in filtered_events:
            if event.location:
                has_online = "online" in event.location.lower()
                has_remote = "remote" in event.location.lower()
                self.assertFalse(
                    has_online or has_remote,
                    f"Event location should not contain 'online' or 'remote': {event.location}",
                )

    def test_load_config_function(self):
        """Test standalone load_config function."""
        test_config = """
filters:
  categories:
    include: ["Test"]
"""
        self.config_path.write_text(test_config)

        config = load_config(self.config_path)

        self.assertIsInstance(config, EventsConfig)
        self.assertEqual(config.get_include_categories(), ["Test"])

    def test_load_config_invalid_yaml(self):
        """Test load_config with invalid YAML always raises exception."""
        # Create invalid YAML
        self.config_path.write_text("invalid: yaml: content: [")

        with self.assertRaises(Exception):
            load_config(self.config_path)


class TestConfigIntegration(unittest.TestCase):
    """Test config integration with EventCollection."""

    def test_event_collection_with_config_filters(self):
        """Test EventCollection filtering integrates with config system."""
        # Create random events for testing
        events = [
            mock_data.get_event(),
            mock_data.get_event(),
            mock_data.get_event(),
        ]
        collection = EventCollection(events)

        # Test that EventCollection methods work with config system
        # Test category filtering with exact match
        if events and events[0].categories:
            test_category = events[0].categories[0]
            events_with_category = [e for e in events if test_category in e.categories]
            filtered_events = collection.include_categories([test_category])
            self.assertEqual(len(filtered_events.to_list()), len(events_with_category))

        # Test title filtering - use a common letter that likely appears in titles
        events_with_e_in_title = [e for e in events if "e" in e.title.lower()]
        title_filtered_events = collection.include_titles(["e"])
        self.assertEqual(
            len(title_filtered_events.to_list()), len(events_with_e_in_title)
        )

        # Verify filtering logic works correctly
        for event in title_filtered_events.to_list():
            self.assertIn(
                "e",
                event.title.lower(),
                f"Event title should contain 'e': {event.title}",
            )
