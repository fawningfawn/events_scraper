#!/usr/bin/env python3
"""Plugin-driven management command launcher."""

from __future__ import annotations

import sys

from events_scraper.lib.config import load_config
from events_scraper.lib.core.database import configure_database
from plugins.command_registry import run_command


def main() -> int:
    try:
        config = load_config()
        configure_database(config=config)
    except Exception as e:
        print(f"Error loading config: {e}")
        return 1

    return run_command(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
