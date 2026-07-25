import os
import shutil
import tempfile
import unittest
from dataclasses import asdict

from events_scraper.lib import mock_data
from events_scraper.lib.packages import clear_cache
from events_scraper.lib.packages import load_packages
from events_scraper.lib.scraper_meta import GroupMeta
from events_scraper.lib.scraper_meta import load_group_meta


class TestGroupMeta(unittest.TestCase):
    def test_group_meta_defaults(self):
        meta = GroupMeta(group="testcity")
        self.assertEqual(meta.group, "testcity")
        self.assertEqual(meta.weight, 10)
        self.assertIsNone(meta.display_name)
        self.assertIsNone(meta.nav_label)
        self.assertTrue(meta.feed_enabled)
        self.assertEqual(meta.show_date, "day")
        self.assertEqual(meta.source, "python")

    def test_group_meta_explicit_fields(self):
        meta = GroupMeta(
            group="testcity",
            display_name="Test City",
            nav_label="Test",
            weight=5,
            feed_enabled=False,
            source="yaml",
        )
        self.assertEqual(meta.group, "testcity")
        self.assertEqual(meta.display_name, "Test City")
        self.assertEqual(meta.nav_label, "Test")
        self.assertEqual(meta.weight, 5)
        self.assertFalse(meta.feed_enabled)
        self.assertEqual(meta.source, "yaml")

    def test_group_meta_serializable(self):
        meta = GroupMeta(
            group="testcity",
            display_name="Test City",
            nav_label="Test",
            weight=5,
            feed_enabled=True,
            source="python",
        )
        d = asdict(meta)
        self.assertEqual(d["group"], "testcity")
        self.assertEqual(d["display_name"], "Test City")
        self.assertEqual(d["weight"], 5)


class TestLoadGroupMeta(unittest.TestCase):
    def test_yaml_group_via_test_paths(self):
        tmp = tempfile.mkdtemp()
        try:
            configs = os.path.join(tmp, "festivals", "configs")
            os.makedirs(configs)
            with open(os.path.join(configs, "meta.yaml"), "w") as f:
                f.write(
                    "group: festivals\n"
                    "display_name: Festivals\n"
                    "weight: 5\n"
                    "feed_enabled: true\n"
                    "show_date: all\n"
                )
            clear_cache()
            groups = load_group_meta(test_paths=[tmp])
            fests = [g for g in groups if g.group == "festivals"]
            self.assertEqual(len(fests), 1)
            f = fests[0]
            self.assertEqual(f.source, "yaml")
            self.assertEqual(f.display_name, "Festivals")
            self.assertTrue(f.feed_enabled)
            self.assertEqual(f.show_date, "all")
        finally:
            shutil.rmtree(tmp)
            clear_cache()

    def test_mock_package_loads_via_test_paths(self):

        tmp = tempfile.mkdtemp()
        try:
            mock_data.get_test_package(tmp, "paris", weight=7)
            clear_cache()
            packages = load_packages(test_paths=[tmp])
            self.assertEqual(len(packages), 1)
            self.assertEqual(packages[0].meta.display_name, "Paris")
            self.assertEqual(packages[0].meta.weight, 7)
        finally:
            shutil.rmtree(tmp)
            clear_cache()

    def test_python_group_via_test_paths(self):
        tmp = tempfile.mkdtemp()
        try:
            mock_data.get_test_package(tmp, "festivals")
            clear_cache()
            groups = load_group_meta(test_paths=[tmp])
            python = [g for g in groups if g.source == "python"]
            self.assertGreater(len(python), 0)
            for g in python:
                self.assertIsNotNone(g.group)
                self.assertIsNotNone(g.display_name)
        finally:
            shutil.rmtree(tmp)
            clear_cache()

    def test_yaml_groups_sort_before_python_groups(self):
        groups = load_group_meta()
        for i in range(len(groups) - 1):
            self.assertLessEqual(groups[i].weight, groups[i + 1].weight)

    def test_sorted_by_weight_within_source(self):
        groups = load_group_meta()
        yaml_groups = [g for g in groups if g.source == "yaml"]
        if len(yaml_groups) > 1:
            for i in range(len(yaml_groups) - 1):
                self.assertLessEqual(yaml_groups[i].weight, yaml_groups[i + 1].weight)

        python_groups = [g for g in groups if g.source == "python"]
        if len(python_groups) > 1:
            for i in range(len(python_groups) - 1):
                self.assertLessEqual(
                    python_groups[i].weight, python_groups[i + 1].weight
                )

    def test_test_paths_groups_have_required_fields(self):
        tmp = tempfile.mkdtemp()
        try:
            mock_data.get_test_package(tmp, "festivals")
            clear_cache()
            groups = load_group_meta(test_paths=[tmp])
            self.assertGreater(len(groups), 0)
            for g in groups:
                self.assertIsNotNone(g.group)
                self.assertIsNotNone(g.display_name)
                self.assertIsNotNone(g.source)
                self.assertIn(g.source, ("yaml", "python"))
        finally:
            shutil.rmtree(tmp)
            clear_cache()

    def test_groups_have_valid_weight(self):
        groups = load_group_meta()
        for g in groups:
            self.assertGreaterEqual(g.weight, 0)
            self.assertLessEqual(g.weight, 1000)

    def test_python_groups_default_to_show_date_day(self):
        groups = load_group_meta()
        for g in groups:
            if g.source == "python":
                self.assertEqual(g.show_date, "day")

    def test_show_date_all_via_test_paths(self):
        tmp = tempfile.mkdtemp()
        try:
            configs = os.path.join(tmp, "festivals", "configs")
            os.makedirs(configs)
            with open(os.path.join(configs, "meta.yaml"), "w") as f:
                f.write(
                    "group: festivals\n" "display_name: Festivals\n" "show_date: all\n"
                )
            clear_cache()
            groups = load_group_meta(test_paths=[tmp])
            fests = [g for g in groups if g.group == "festivals"]
            self.assertEqual(len(fests), 1)
            self.assertEqual(fests[0].show_date, "all")
        finally:
            shutil.rmtree(tmp)
            clear_cache()
