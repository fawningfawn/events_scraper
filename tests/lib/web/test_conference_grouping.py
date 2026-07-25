"""
Unit tests for scraper grouping logic in web interface using mock packages.
"""

import unittest
from unittest.mock import patch

from events_scraper.lib import mock_data
from events_scraper.lib.packages import GroupMeta
from events_scraper.lib.web.app import _find_scraper_group
from events_scraper.lib.web.app import _get_available_scrapers
from events_scraper.lib.web.app import _group_scraper_stats


class TestScraperGrouping(unittest.TestCase):
    """Test grouping of scrapers by package in status page."""

    def test_find_scraper_group_matches_prefix(self):
        groups = {
            "paris": GroupMeta(group="paris"),
            "conferences": GroupMeta(group="conferences"),
        }
        self.assertEqual(_find_scraper_group("paris.garage", groups), "paris")
        self.assertEqual(
            _find_scraper_group("conferences.btcprague", groups), "conferences"
        )
        self.assertIsNone(_find_scraper_group("unknown.scraper", groups))

    def test_find_scraper_group_matches_exact_name(self):
        groups = {"conferences": GroupMeta(group="conferences")}
        self.assertEqual(_find_scraper_group("conferences", groups), "conferences")

    def test_group_scraper_stats_groups_by_prefix(self):
        raw_stats = [
            ("conferences.scraper1", 5),
            ("conferences.scraper2", 3),
            ("paris.garage", 10),
            ("paris.staatstheater", 8),
        ]
        future_stats = {}

        with patch("events_scraper.lib.web.app.load_group_meta") as mock_lgm:
            mock_lgm.return_value = [
                GroupMeta(group="paris", display_name="Paris"),
                GroupMeta(group="conferences", display_name="Conferences"),
            ]
            grouped = _group_scraper_stats(raw_stats, future_stats)

        group_names = [g[0] for g in grouped]
        self.assertIn("paris", group_names)
        self.assertIn("conferences", group_names)

    def test_get_available_scrapers_excludes_hidden_groups(self):
        pkg = mock_data.get_package("hidden", ["hidden.s1"], hide_from_status=True)
        visible = mock_data.get_package("visible", ["visible.s1"])

        with patch("events_scraper.lib.scraper_meta.load_packages") as mock_meta:
            with patch("events_scraper.lib.packages.load_packages") as mock_pkg:
                mock_meta.return_value = [visible, pkg]
                mock_pkg.return_value = [visible, pkg]
                scrapers = _get_available_scrapers()

        self.assertIn("visible.s1", scrapers)
        self.assertNotIn("hidden.s1", scrapers)
