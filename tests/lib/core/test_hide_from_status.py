import os
import shutil
import tempfile
import unittest

from events_scraper.lib.packages import load_packages
from events_scraper.lib.scraper_meta import load_group_meta


class TestHideFromStatus(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self._write_test_meta()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _write_test_meta(self):
        configs = os.path.join(self.tmpdir, "festivals", "configs")
        os.makedirs(configs)
        with open(os.path.join(configs, "meta.yaml"), "w") as f:
            f.write(
                "group: festivals\n"
                "display_name: Festivals\n"
                "hide_from_status: true\n"
            )

    def test_yaml_group_hide_from_status(self):
        groups = load_group_meta(test_paths=[self.tmpdir])
        for g in groups:
            if g.group == "festivals":
                self.assertTrue(g.hide_from_status)
                return
        self.fail("festivals group not found")

    def test_load_packages_respects_hide_from_status(self):
        packages = load_packages(test_paths=[self.tmpdir])
        fests = [p for p in packages if p.name == "festivals"]
        self.assertEqual(len(fests), 1)
        self.assertTrue(fests[0].meta.hide_from_status)
