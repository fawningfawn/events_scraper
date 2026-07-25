"""Tests for runtime info reporting."""

from __future__ import annotations

import importlib
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import xdg

from events_scraper.lib import mock_data
from events_scraper.lib.core.orm_session import get_session
from events_scraper.lib.info_report import collect_runtime_info
from events_scraper.lib.info_report import format_runtime_info
from tests.lib.core.test_base import DatabaseTestCase


class TestInfoReport(DatabaseTestCase):
    def test_collect_runtime_info_reports_paths_sizes_and_counts(self):
        with (
            tempfile.TemporaryDirectory() as cache_home,
            tempfile.TemporaryDirectory() as config_home,
        ):
            cache_root = Path(cache_home) / "events_scraper"
            http_cache_dir = cache_root / "http_cache"
            http_cache_dir.mkdir(parents=True, exist_ok=True)
            (http_cache_dir / "cache-entry").write_bytes(b"x" * 1024)

            ai_cache_path = cache_root / "ai_cache.db"
            ai_cache_path.write_bytes(b"y" * 2048)

            config_path = Path(config_home) / "events_scraper" / "events.yaml"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(
                "database:\n  url: sqlite:///ignored.db\n", encoding="utf-8"
            )

            with patch.dict(
                os.environ,
                {"XDG_CACHE_HOME": cache_home, "XDG_CONFIG_HOME": config_home},
                clear=False,
            ):
                session = get_session()
                try:
                    event = mock_data.get_orm_event(session=session)
                    detail_url = event.detail_url
                    scraper_status = mock_data.get_scraper_status()
                    session.add(scraper_status)
                    user = mock_data.get_orm_user(session=session)
                    mock_data.get_orm_notification(
                        session=session, user=user, event=event
                    )
                    session.commit()
                finally:
                    session.close()

                detail = mock_data.get_event_detail(url=detail_url)
                detail.save()

                importlib.reload(xdg)
                info = collect_runtime_info()
                report = format_runtime_info(info)

        self.assertEqual(info.config_path, config_path)
        self.assertEqual(info.database_path, Path(self.temp_db.name))
        self.assertEqual(info.counts["events"], 1)
        self.assertEqual(info.counts["event_details"], 1)
        self.assertEqual(info.counts["scraper_status"], 1)
        self.assertEqual(info.counts["notifications"], 1)
        self.assertIn("Events Info", report)
        self.assertIn(f"  Path: {config_path}", report)
        self.assertIn("HTTP cache size: 1.0 KiB", report)
        self.assertIn("AI cache size: 2.0 KiB", report)
        self.assertIn("  events: 1", report)
        self.assertIn("  event_details: 1", report)
