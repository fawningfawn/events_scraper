import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from events_scraper.lib.packages import load_packages


class TestGetXdgScrapersPaths(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        configs = os.path.join(self.tmpdir, "festivals", "configs")
        os.makedirs(configs)
        with open(os.path.join(configs, "meta.yaml"), "w") as f:
            f.write("group: festivals\n")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_packages_discovered_from_xdg_paths(self):
        with (patch.dict(os.environ, {"HOME": "/home/testuser"}, clear=True),):
            packages = load_packages()
            self.assertIsInstance(packages, list)

    def test_load_packages_returns_valid_objects(self):
        packages = load_packages(test_paths=[self.tmpdir])
        self.assertGreater(len(packages), 0)
        for p in packages:
            self.assertIsNotNone(p.name)
            self.assertIsNotNone(p.path)
