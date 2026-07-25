"""Architecture boundary tests for canonical runtime data layer."""

import unittest
from pathlib import Path


class TestArchitectureBoundaries(unittest.TestCase):
    """Prevent regressions to removed legacy data-layer imports."""

    def test_legacy_database_module_removed(self):
        legacy_path = Path("src/events_scraper/lib/database.py")
        self.assertFalse(legacy_path.exists())

    def test_runtime_modules_do_not_import_legacy_database_module(self):
        source_root = Path("src/events_scraper")
        forbidden_patterns = (
            "import events_scraper.lib.database",
            "from events_scraper.lib import database",
            "from events_scraper.lib.database import",
        )

        violations = []
        for path in source_root.rglob("*.py"):
            content = path.read_text(encoding="utf-8")
            for pattern in forbidden_patterns:
                if pattern in content:
                    violations.append(f"{path}: {pattern}")

        self.assertEqual(violations, [])

    def test_scraper_modules_do_not_use_requests_get_directly(self):
        scraper_root = Path("src/events_scraper/lib/scrapers")
        violations = []
        for path in scraper_root.rglob("*.py"):
            content = path.read_text(encoding="utf-8")
            if "requests.get(" in content:
                violations.append(str(path))

        self.assertEqual(
            violations,
            [],
            f"Scraper modules must use centralized HTTP wrappers, found direct requests.get in: {violations}",
        )
