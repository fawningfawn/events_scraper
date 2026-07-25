"""Package discovery and loading."""

import dataclasses
import importlib
import importlib.util
import inspect
import logging
import os
import sys
from pathlib import Path
from typing import List
from typing import Optional

import yaml
from xdg import XDG_CONFIG_HOME
from xdg import XDG_DATA_HOME

from events_scraper.lib.constants import CONFIG_DIR_NAME
from events_scraper.lib.constants import PACKAGES_DIR_NAME

logger = logging.getLogger(__name__)

_packages_cache = None
_packages_cache_key = None


def clear_cache():
    global _packages_cache, _packages_cache_key
    _packages_cache = None
    _packages_cache_key = None


def _get_xdg_paths() -> List[str]:
    return [
        os.path.join(XDG_CONFIG_HOME, CONFIG_DIR_NAME, PACKAGES_DIR_NAME),
        os.path.join(XDG_DATA_HOME, CONFIG_DIR_NAME, PACKAGES_DIR_NAME),
    ]


def _ensure_package_namespace(full_name: str, package_root: str) -> None:
    parts = full_name.split(".")
    for i in range(1, len(parts)):
        parent = ".".join(parts[:i])
        if parent not in sys.modules:
            mod = type(sys)(parent)
            # Set __path__ to the directory containing this module
            if i == 1:
                # Top-level 'packages' module → parent of package_root
                # (package_root is e.g. /.../packages/paris, so parent is /.../packages)
                mod.__path__ = [str(Path(package_root).parent)]
            else:
                # e.g. 'packages.paris' → package_root is paris dir
                mod.__path__ = [package_root]
            sys.modules[parent] = mod


@dataclasses.dataclass
class GroupMeta:
    group: str
    display_name: Optional[str] = None
    nav_label: Optional[str] = None
    weight: int = 10
    feed_enabled: bool = True
    hide_from_status: bool = False
    show_date: str = "day"
    nav_section: Optional[str] = None
    source: str = "python"


@dataclasses.dataclass
class Package:
    name: str
    path: str
    meta: GroupMeta

    @property
    def scraper_count(self):
        return len(self.load_scrapers())

    @property
    def configs_dir(self) -> Optional[Path]:
        """Path to this package's ``configs/`` directory, or None."""
        path = Path(self.path) / "configs"
        return path if path.is_dir() else None

    def config_files(self) -> List[Path]:
        """YAML config files in this package, sorted. Empty list if none."""
        d = self.configs_dir
        return sorted(d.glob("*.yaml")) if d else []

    def load_scrapers(self, target_date=None, only_new=False):
        if hasattr(self, "_scrapers"):
            return self._scrapers
        configs_dir = os.path.join(self.path, "configs")
        scraps_dir = os.path.join(self.path, "scrapers")
        if os.path.isdir(configs_dir):
            from events_scraper.lib.scrapers.yaml_loader import (
                load_yaml_scrapers,  # ap-ignore; ap-ignore
            )

            self._scrapers = load_yaml_scrapers(config_dir=Path(configs_dir))
            for s in self._scrapers:
                if not s.scraper_name.startswith(f"{self.name}."):
                    s._scraper_name_override = f"{self.name}.{s.scraper_name}"
            return self._scrapers
        if os.path.isdir(scraps_dir):
            init_py = os.path.join(scraps_dir, "__init__.py")
            if os.path.isfile(init_py):
                _ensure_package_namespace(
                    ".".join(["packages", self.name, "scrapers"]), self.path
                )
                spec = importlib.util.spec_from_file_location(
                    f"packages.{self.name}.scrapers",
                    init_py,
                    submodule_search_locations=[scraps_dir],
                )
                pkg = importlib.util.module_from_spec(spec)
                pkg.__path__ = [scraps_dir]
                spec.loader.exec_module(pkg)
                if hasattr(pkg, "get_scrapers"):
                    result = pkg.get_scrapers()
                    if result and not inspect.isclass(result[0]):
                        self._scrapers = result
                        return result

                    from events_scraper.lib.scraper_loader import (
                        _instantiate_scrapers,  # ap-ignore; ap-ignore
                    )

                    self._scrapers = _instantiate_scrapers(
                        result, target_date, only_new, self.name
                    )
                    return self._scrapers
        self._scrapers = []
        return []


def load_packages(test_paths: Optional[List[str]] = None) -> List[Package]:
    global _packages_cache, _packages_cache_key
    if test_paths is not None:
        search_paths = list(test_paths)
    else:
        search_paths = _get_xdg_paths()
        builtin = Path(__file__).parent.parent.parent / "packages"
        if builtin.is_dir():
            search_paths.append(str(builtin))
    cache_key = tuple(sorted(search_paths))
    if _packages_cache is not None and _packages_cache_key == cache_key:
        return _packages_cache

    packages = []
    for path in search_paths:
        if not os.path.isdir(path):
            continue
        for item in sorted(os.listdir(path)):
            item_path = os.path.join(path, item)
            if not os.path.isdir(item_path) or item.startswith("__"):
                continue
            for meta in _read_package_metas(item_path, item):
                packages.append(Package(name=meta.group, path=item_path, meta=meta))
    _packages_cache = packages
    _packages_cache_key = cache_key
    return packages


def get_scraper_names_for_group(group: str) -> List[str]:
    pkg = _find_package(group)
    if pkg is None:
        return []
    scrapers = pkg.load_scrapers()
    return [s.scraper_name for s in scrapers]


def get_package_by_name(name: str) -> Optional[Package]:
    """Look up a loaded package by name. Returns None if not found."""
    for pkg in load_packages():
        if pkg.name == name:
            return pkg
    return None


def get_ai_scraper_names() -> List[str]:
    """Return scraper names for all AIScraper instances across packages."""
    from events_scraper.lib.scrapers.ai_scraper import AIScraper

    names = []
    for pkg in load_packages():
        for s in pkg.load_scrapers():
            if isinstance(s, AIScraper):
                names.append(s.scraper_name)
    return names


def _find_package(group: str) -> Optional[Package]:
    for pkg in load_packages():
        groups = {pkg.meta.group}
        if pkg.meta.source == "python" and group == pkg.meta.group:
            groups.add(group)
        if group in groups:
            return pkg
    return None


def _read_package_metas(path: str, pkg_name: str) -> List[GroupMeta]:
    metas = []
    scraps_meta = os.path.join(path, "scrapers", "metadata.py")
    for yaml_path in (
        os.path.join(path, "meta.yaml"),
        os.path.join(path, "configs", "meta.yaml"),
    ):
        if os.path.exists(yaml_path):
            with open(yaml_path) as f:
                data = yaml.safe_load(f) or {}
                display_name = data.get("display_name")
                nav_label = data.get("nav_label") or display_name
                metas.append(
                    GroupMeta(
                        group=data.get("group", pkg_name),
                        display_name=display_name,
                        nav_label=nav_label,
                        weight=data.get("weight", 10),
                        feed_enabled=data.get("feed_enabled", True),
                        hide_from_status=data.get("hide_from_status", False),
                        show_date=data.get("show_date", "day"),
                        nav_section=data.get("nav_section"),
                        source="yaml",
                    )
                )
    if os.path.exists(scraps_meta):
        groups = _load_python_group_meta(pkg_name, scraps_meta)
        metas.extend(groups)
    return metas


def _load_python_group_meta(dir_name: str, metadata_path: str) -> List[GroupMeta]:
    spec = importlib.util.spec_from_file_location(
        f"events_scraper.lib.scrapers.{dir_name}.metadata", metadata_path
    )
    metadata = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(metadata)

    weight = getattr(metadata, "WEIGHT", 10)
    nav_label = getattr(metadata, "NAV_LABEL", None)
    nav_section = getattr(metadata, "NAV_SECTION", None)
    show_date = getattr(metadata, "SHOW_DATE", "day")
    hide_from_status = getattr(metadata, "HIDE_FROM_STATUS", False)
    display_name = None

    if hasattr(metadata, "SUPPORTED_CITIES") and metadata.SUPPORTED_CITIES:
        first = metadata.SUPPORTED_CITIES[0]
        if isinstance(first, dict):
            display_name = first.get("display_name") or first.get("name", dir_name)
            if not nav_label:
                nav_label = display_name
        elif isinstance(first, str):
            display_name = first
            if not nav_label:
                nav_label = first

    if not display_name:
        display_name = dir_name
    if not nav_label:
        nav_label = display_name

    return [
        GroupMeta(
            group=dir_name,
            display_name=display_name,
            nav_label=nav_label,
            weight=weight,
            feed_enabled=True,
            hide_from_status=hide_from_status,
            show_date=show_date,
            nav_section=nav_section,
            source="python",
        )
    ]
