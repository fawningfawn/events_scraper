"""
Dynamic scraper loading functionality
"""

import logging
import os
from typing import List

import yaml

from events_scraper.lib.packages import _load_python_group_meta
from events_scraper.lib.packages import GroupMeta
from events_scraper.lib.packages import load_packages

logger = logging.getLogger(__name__)


def load_group_meta(test_paths=None) -> List[GroupMeta]:
    all_packages = list(load_packages())
    if test_paths:
        extra = load_packages(test_paths=test_paths)
        builtin_names = {p.name for p in load_packages()}
        extra_names = {p.name for p in extra}
        dupes = builtin_names & extra_names
        if dupes:
            raise ValueError(f"Duplicate group names: {sorted(dupes)}")
        all_names = [p.name for p in all_packages + extra]
        seen = set()
        for name in all_names:
            if name in seen:
                raise ValueError(f"Duplicate group name: {name}")
            seen.add(name)
        all_packages.extend(extra)
    groups = [pkg.meta for pkg in all_packages]
    return sorted(groups, key=lambda g: g.weight)


def _scan_scrapers_dir(scrapers_dir) -> List[GroupMeta]:
    groups = []
    for item in sorted(os.listdir(scrapers_dir)):
        item_path = os.path.join(scrapers_dir, item)
        if not os.path.isdir(item_path) or item.startswith("__"):
            continue

        meta_yaml_path = os.path.join(item_path, "meta.yaml")
        configs_meta_path = os.path.join(item_path, "configs", "meta.yaml")
        found_meta = False
        if os.path.exists(meta_yaml_path):
            groups.extend(_load_yaml_group_meta(item_path, item, meta_yaml_path))
            found_meta = True
        elif os.path.exists(configs_meta_path):
            groups.extend(_load_yaml_group_meta(item_path, item, configs_meta_path))
            found_meta = True

        if not found_meta:
            metadata_py_path = os.path.join(item_path, "metadata.py")
            if os.path.exists(metadata_py_path):
                groups.extend(_load_python_group_meta(item, metadata_py_path))
    return groups


def _load_yaml_group_meta(
    dir_path: str, dir_name: str, meta_path: str
) -> List[GroupMeta]:
    with open(meta_path) as f:
        data = yaml.safe_load(f) or {}
    return [
        GroupMeta(
            group=data.get("group", dir_name),
            display_name=data.get("display_name"),
            nav_label=data.get("nav_label"),
            weight=data.get("weight", 10),
            feed_enabled=data.get("feed_enabled", True),
            show_date=data.get("show_date", "day"),
            source="yaml",
        )
    ]
