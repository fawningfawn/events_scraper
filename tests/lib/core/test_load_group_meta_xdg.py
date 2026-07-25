import os
import shutil
import tempfile
import unittest

from events_scraper.lib.scraper_meta import load_group_meta


class TestLoadGroupMetaXdg(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _write_meta_yaml(self, subdir, content):
        path = os.path.join(self.tmpdir, subdir)
        os.makedirs(path, exist_ok=True)
        with open(os.path.join(path, "meta.yaml"), "w") as f:
            f.write(content)

    def _write_configs_meta_yaml(self, subdir, content):
        path = os.path.join(self.tmpdir, subdir, "configs")
        os.makedirs(path, exist_ok=True)
        with open(os.path.join(path, "meta.yaml"), "w") as f:
            f.write(content)

    def test_xdg_group_appears_in_results(self):
        self._write_meta_yaml(
            "mycity",
            "group: mycity\ndisplay_name: My City\nnav_label: MyCity\nweight: 5\n",
        )
        groups = load_group_meta(test_paths=[self.tmpdir])
        mycity = [g for g in groups if g.group == "mycity"]
        self.assertEqual(len(mycity), 1)
        self.assertEqual(mycity[0].display_name, "My City")
        self.assertEqual(mycity[0].weight, 5)

    def test_duplicate_group_name_raises(self):
        self._write_meta_yaml(
            "dup_a",
            "group: festivals\ndisplay_name: A\n",
        )
        self._write_meta_yaml(
            "dup_b",
            "group: festivals\ndisplay_name: B\n",
        )
        with self.assertRaises(ValueError) as ctx:
            load_group_meta(test_paths=[self.tmpdir])
        self.assertIn("festivals", str(ctx.exception))

    def test_empty_xdg_path_has_no_effect(self):
        groups_before = load_group_meta()
        groups_after = load_group_meta(test_paths=[self.tmpdir])
        self.assertEqual(
            [g.group for g in groups_before],
            [g.group for g in groups_after],
        )

    def test_xdg_dir_with_no_meta_is_skipped(self):
        os.makedirs(os.path.join(self.tmpdir, "empty"))
        groups = load_group_meta(test_paths=[self.tmpdir])
        self.assertEqual(
            [g.group for g in load_group_meta()],
            [g.group for g in groups],
        )

    def test_configs_subdir_meta_yaml_found(self):
        self._write_configs_meta_yaml(
            "newconf",
            "group: newconf\ndisplay_name: New Conf\n",
        )
        groups = load_group_meta(test_paths=[self.tmpdir])
        self.assertIn("newconf", [g.group for g in groups])
