"""Regression guardrails for high-risk runtime bugs fixed in `P1` + `P3`."""

import unittest
from pathlib import Path


class TestRuntimeRegressionMatrix(unittest.TestCase):
    """Architecture-level regression checks."""

    def test_eventscli_entrypoint_removed(self):
        """`eventscli` must not exist as active runtime entrypoint."""
        self.assertFalse(Path("src/eventscli.py").exists())

    def test_webevent_adapter_removed(self):
        """Hot web paths should not depend on removed `WebEvent` dataclass adapter."""
        self.assertFalse(Path("src/events_scraper/lib/web/models.py").exists())

    def test_no_eventscli_imports_in_source(self):
        """Source tree should not import the legacy `eventscli` runtime."""
        violations = []
        for path in Path("src").rglob("*.py"):
            content = path.read_text(encoding="utf-8")
            if "from eventscli import" in content or "import eventscli" in content:
                violations.append(str(path))
        self.assertEqual(violations, [])
