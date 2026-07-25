"""Helpers for the `info` command."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from xdg import xdg_cache_home

from events_scraper.lib import constants
from events_scraper.lib.config import get_config_path
from events_scraper.lib.core.orm_models import Event
from events_scraper.lib.core.orm_models import EventDetail
from events_scraper.lib.core.orm_models import GeocodeCache
from events_scraper.lib.core.orm_models import Notification
from events_scraper.lib.core.orm_models import ScraperStatus
from events_scraper.lib.core.orm_session import get_database_url
from events_scraper.lib.core.orm_session import get_session


@dataclass(frozen=True)
class RuntimeInfo:
    config_path: Path
    database_url: str
    database_path: Optional[Path]
    database_size: Optional[int]
    http_cache_dir: Path
    http_cache_size: Optional[int]
    ai_cache_path: Path
    ai_cache_size: Optional[int]
    counts: dict[str, int]


def _human_size(size: Optional[int]) -> str:
    if size is None:
        return "n/a"
    if size < 1024:
        return f"{size} B"

    units = ["KiB", "MiB", "GiB", "TiB"]
    value = float(size)
    for unit in units:
        value /= 1024.0
        if value < 1024.0:
            return f"{value:.1f} {unit}"
    return f"{value:.1f} PiB"


def _path_size(path: Path) -> Optional[int]:
    if not path.exists():
        return None
    return path.stat().st_size if path.is_file() else _directory_size(path)


def _directory_size(path: Path) -> int:
    total = 0
    for root, _, files in os.walk(path):
        for filename in files:
            file_path = Path(root) / filename
            try:
                total += file_path.stat().st_size
            except OSError:
                continue
    return total


def _sqlite_path_from_url(database_url: str) -> Optional[Path]:
    if not database_url or not database_url.startswith("sqlite:///"):
        return None
    if database_url.endswith(":memory:"):
        return None
    return Path(database_url.replace("sqlite:///", "", 1))


def collect_runtime_info() -> RuntimeInfo:
    """Collect live runtime info from config, caches, and the database."""
    config_path = get_config_path()
    database_url = get_database_url() or "sqlite:///:memory:"
    database_path = _sqlite_path_from_url(database_url)

    http_cache_dir = (
        Path(xdg_cache_home())
        / constants.APP_CACHE_DIR_NAME
        / constants.HTTP_CACHE_DIR_NAME
    )
    ai_cache_path = (
        Path(xdg_cache_home())
        / constants.APP_CACHE_DIR_NAME
        / constants.AI_CACHE_FILENAME
    )

    session = get_session()
    try:
        counts = {
            "events": session.query(Event).count(),
            "event_details": session.query(EventDetail).count(),
            "geocode_cache": session.query(GeocodeCache).count(),
            "scraper_status": session.query(ScraperStatus).count(),
            "notifications": session.query(Notification).count(),
        }
    finally:
        session.close()

    return RuntimeInfo(
        config_path=config_path,
        database_url=database_url,
        database_path=database_path,
        database_size=_path_size(database_path) if database_path else None,
        http_cache_dir=http_cache_dir,
        http_cache_size=_path_size(http_cache_dir),
        ai_cache_path=ai_cache_path,
        ai_cache_size=_path_size(ai_cache_path),
        counts=counts,
    )


def format_runtime_info(info: RuntimeInfo) -> str:
    """Render runtime info as a plain-text report."""
    lines = [
        "Events Info",
        "",
        "Config",
        f"  Path: {info.config_path}",
        "",
        "Database",
        f"  URL: {info.database_url}",
    ]

    if info.database_path is None:
        lines.append("  Path: in-memory")
        lines.append("  Size: n/a")
    else:
        lines.append(f"  Path: {info.database_path}")
        lines.append(f"  Size: {_human_size(info.database_size)}")

    lines.extend(
        [
            "",
            "Caches",
            f"  HTTP cache dir: {info.http_cache_dir}",
            f"  HTTP cache size: {_human_size(info.http_cache_size)}",
            f"  AI cache db: {info.ai_cache_path}",
            f"  AI cache size: {_human_size(info.ai_cache_size)}",
            "",
            "Counts",
        ]
    )

    for name in (
        "events",
        "event_details",
        "geocode_cache",
        "scraper_status",
        "notifications",
    ):
        lines.append(f"  {name}: {info.counts.get(name, 0)}")

    return "\n".join(lines)
