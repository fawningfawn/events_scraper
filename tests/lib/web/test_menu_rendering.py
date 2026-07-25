from unittest.mock import patch

from flask import url_for

from events_scraper.lib import mock_data
from events_scraper.lib.scraper_meta import load_group_meta
from events_scraper.lib.web.app import create_app
from tests.lib.core.test_base import DatabaseTestCase


class TestMenuRendering(DatabaseTestCase):
    @patch("events_scraper.lib.scraper_meta.load_packages")
    @patch("events_scraper.lib.packages.load_packages")
    def test_all_groups_in_nav(self, mock_pkg, mock_meta):
        pkg = mock_data.get_package(
            "testgroup", ["testgroup.s1"], display_name="TestGroup"
        )
        mock_pkg.return_value = [pkg]
        mock_meta.return_value = [pkg]
        app = create_app(test_mode=True)
        with app.test_client() as client:
            with app.test_request_context():
                url = url_for("events_route", group="testgroup")
            resp = client.get(url)
            html = resp.data.decode("utf-8")

        self.assertIn("Events", html)
        self.assertIn("TestGroup", html)

    def test_yaml_before_python_weight_order(self):
        groups = load_group_meta()
        for i in range(len(groups) - 1):
            self.assertLessEqual(groups[i].weight, groups[i + 1].weight)

    def test_nav_includes_static_links(self):
        app = create_app(test_mode=True)
        with app.test_client() as client:
            with app.test_request_context():
                url = url_for("events_route")
            resp = client.get(url)
            html = resp.data.decode("utf-8")

        self.assertIn("Status", html)
        self.assertIn("Scrapers", html)
