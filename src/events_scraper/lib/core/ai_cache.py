"""
AI response caching with hash-based invalidation

Caches AI responses indefinitely until HTML content changes.
Uses SHA256 hashing to detect content changes.
"""

import hashlib
import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any
from typing import Dict
from typing import Optional

from xdg import xdg_cache_home

from events_scraper.lib.constants import AI_CACHE_FILENAME
from events_scraper.lib.constants import APP_CACHE_DIR_NAME

logger = logging.getLogger(__name__)


class AICache:
    """
    Cache for AI responses with hash-based invalidation

    Stores AI responses keyed by URL, with HTML content hashing
    to automatically invalidate when page content changes.
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize AI cache

        Args:
            db_path: Path to SQLite database, or ":memory:" for in-memory.
                     Defaults to XDG cache directory.
        """
        if db_path is None:
            cache_dir = Path(xdg_cache_home()) / APP_CACHE_DIR_NAME
            cache_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(cache_dir / AI_CACHE_FILENAME)

        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self._create_table()

    def _create_table(self):
        """Create ai_cache table if it doesn't exist"""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS ai_cache (
                url TEXT PRIMARY KEY,
                html_hash TEXT NOT NULL,
                response_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """)
        self.conn.commit()

    def _compute_hash(self, html: str) -> str:
        """Compute SHA256 hash of HTML content"""
        return hashlib.sha256(html.encode("utf-8")).hexdigest()

    def get(
        self, url: str, html: str, metadata: dict = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached AI response if content hash matches

        Args:
            url: Page URL
            html: Current HTML content
            metadata: Additional context (categories, ticket_pages, etc)

        Returns:
            Cached response dict if hash matches, None otherwise
        """
        # Include metadata in hash for cache validation
        content = html
        if metadata:
            content += json.dumps(metadata, sort_keys=True)

        content_hash = self._compute_hash(content)
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT html_hash, response_json FROM ai_cache WHERE url = ?",
            (url,),
        )
        row = cursor.fetchone()

        if row is None:
            logger.debug(f"Cache miss for {url} (no cached entry)")
            return None

        cached_hash, response_json = row

        if cached_hash != content_hash:
            logger.debug(f"Cache miss for {url} (content/metadata changed)")
            return None

        logger.debug(f"Cache hit for {url}")
        return json.loads(response_json)

    def set(self, url: str, html: str, response: Dict[str, Any], metadata: dict = None):
        """
        Store AI response with content hash

        Args:
            url: Page URL
            html: HTML content used for response
            response: AI response dict to cache
            metadata: Additional context that affects response
        """
        # Include metadata in hash so cache invalidates when config changes
        content = html
        if metadata:
            content += json.dumps(metadata, sort_keys=True)

        content_hash = self._compute_hash(content)
        response_json = json.dumps(response)
        created_at = datetime.now().isoformat()

        # Replace existing entry (REPLACE = DELETE + INSERT)
        self.conn.execute(
            """
            REPLACE INTO ai_cache (url, html_hash, response_json, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (url, content_hash, response_json, created_at),
        )
        self.conn.commit()
        logger.debug(f"Cached AI response for {url}")

    def close(self):
        """Close database connection"""
        if self.conn:
            try:
                self.conn.close()
            except Exception:
                pass  # Ignore errors during close

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
