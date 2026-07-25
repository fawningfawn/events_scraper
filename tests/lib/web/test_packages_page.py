from unittest.mock import patch

from flask import url_for

from events_scraper.lib import mock_data
from events_scraper.lib.web.app import create_app
from tests.lib.core.test_base import DatabaseTestCase


class TestPackagesPage(DatabaseTestCase):
    @patch("events_scraper.lib.web.app.load_packages")
    def test_packages_page_returns_200(self, mock_lp):
        mock_lp.return_value = [mock_data.get_package("test", ["test.s1"])]
        app = create_app(test_mode=True)
        with app.test_client() as client:
            with app.test_request_context():
                url = url_for("packages_route")
            resp = client.get(url)
            self.assertEqual(resp.status_code, 200)

    @patch("events_scraper.lib.web.app.load_packages")
    def test_packages_page_lists_packages(self, mock_lp):
        mock_lp.return_value = [mock_data.get_package("mypkg", ["mypkg.s1"])]
        app = create_app(test_mode=True)
        with app.test_client() as client:
            with app.test_request_context():
                url = url_for("packages_route")
            resp = client.get(url)
            html = resp.data.decode("utf-8")
            self.assertIn("mypkg", html)

    @patch("events_scraper.lib.web.app.load_packages")
    def test_packages_page_has_scraper_count(self, mock_lp):
        pkg = mock_data.get_package("multi", ["multi.a", "multi.b"])
        mock_lp.return_value = [pkg]
        app = create_app(test_mode=True)
        with app.test_client() as client:
            with app.test_request_context():
                url = url_for("packages_route")
            resp = client.get(url)
            html = resp.data.decode("utf-8")
            self.assertIn("2", html)
