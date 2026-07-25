"""Dynamic class discovery for scraper packages.

This module exists primarily to support package-style scraper directories
(``src/packages/<name>/scrapers/``) that return all concrete scraper classes
in one shot via ``get_scrapers()``.
"""

import importlib
import importlib.util
import os
import pkgutil
import sys
from typing import Any
from typing import List


def load_classes_from_package(package_path: str, class_name: str) -> List[Any]:
    """
    Dynamically load all classes with a specific name from a package

    Args:
        package_path: Full package path (e.g., 'lib.scrapers.<group>')
        class_name: Name of the class to look for (e.g., 'EventScraper')

    Returns:
        List of class objects found
    """
    classes = []

    if os.path.isdir(package_path):
        package_dir = package_path
    else:
        try:
            package_spec = importlib.util.find_spec(package_path)
            if package_spec is None or package_spec.submodule_search_locations is None:
                return classes
            package_dir = package_spec.submodule_search_locations[0]
        except (ModuleNotFoundError, AttributeError):
            return classes

    is_fs_path = os.path.isdir(package_path)
    for moduleinfo in pkgutil.iter_modules([package_dir]):
        cls = _try_load_class(
            package_path, moduleinfo.name, package_dir, class_name, is_fs_path
        )
        if cls is not None:
            classes.append(cls)
    return classes


def _try_load_class(package_path, module_name, package_dir, class_name, is_fs_path):
    try:
        full_name = f"{package_path}.{module_name}"
        if is_fs_path:
            file_path = os.path.join(package_dir, f"{module_name}.py")
            spec = importlib.util.spec_from_file_location(
                full_name, file_path, submodule_search_locations=[package_dir]
            )
        else:
            spec = importlib.util.find_spec(full_name)
        if spec is None:
            return None
        module = importlib.util.module_from_spec(spec)
        sys.modules[full_name] = module
        spec.loader.exec_module(module)
        return getattr(module, class_name, None)
    except Exception:
        return None
