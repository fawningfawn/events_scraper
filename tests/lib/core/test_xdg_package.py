import os
import shutil
import tempfile
import unittest

from events_scraper.lib import mock_data
from events_scraper.lib.packages import clear_cache
from events_scraper.lib.packages import load_packages


class TestXdgPackageLoading(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        clear_cache()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)
        clear_cache()

    def test_python_scraper_loads(self):
        mock_data.get_test_package(self.tmpdir, "mypkg")
        packages = load_packages(test_paths=[self.tmpdir])
        self.assertEqual(len(packages), 1)
        scrapers = packages[0].load_scrapers()
        self.assertEqual(len(scrapers), 1)

    def test_group_meta_from_xdg(self):
        mock_data.get_test_package(self.tmpdir, "mypkg", display_name="Test Package")
        packages = load_packages(test_paths=[self.tmpdir])
        self.assertEqual(packages[0].meta.display_name, "Test Package")

    def test_yaml_package_loads(self):
        configs = os.path.join(self.tmpdir, "myai", "configs")
        os.makedirs(configs)
        with open(os.path.join(configs, "meta.yaml"), "w") as f:
            f.write("group: myai\ndisplay_name: My AI\nshow_date: all\n")
        with open(os.path.join(configs, "testconf.yaml"), "w") as f:
            f.write("scraper_name: testai\nbase_url: https://example.com\n")
        packages = load_packages(test_paths=[self.tmpdir])
        self.assertEqual(len(packages), 1)
        scrapers = packages[0].load_scrapers()
        self.assertEqual(len(scrapers), 1)
        self.assertEqual(scrapers[0].scraper_name, "myai.testai")

    def test_load_packages_with_test_paths(self):
        configs = os.path.join(self.tmpdir, "testconf", "configs")
        os.makedirs(configs)
        with open(os.path.join(configs, "meta.yaml"), "w") as f:
            f.write("group: testconf\n")
        packages = load_packages(test_paths=[self.tmpdir])
        self.assertGreater(len(packages), 0)
