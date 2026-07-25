"""Load scrapers from YAML configuration files."""

import logging
import os
from datetime import date
from glob import glob
from pathlib import Path
from typing import List
from typing import Optional

import yaml

from events_scraper.lib.scrapers.ai_scraper import AIScraper
from events_scraper.lib.scrapers.config_processor import expand_url_variables

logger = logging.getLogger(__name__)


def load_yaml_scrapers(
    config_dir: Optional[Path] = None,
    date_range: Optional[tuple[date, date]] = None,
) -> List[AIScraper]:
    if config_dir is None:
        return []
    config_files = sorted(
        glob(str(config_dir / "*.yaml")), key=os.path.getmtime, reverse=True
    )

    scrapers = []
    for config_file in config_files:
        try:
            with open(config_file, "r") as f:
                config = yaml.safe_load(f)

            if config.get("disabled", False):
                continue

            scraper_name = config.get("scraper_name")
            url = config.get("events_url") or config.get("base_url")

            if not scraper_name and os.path.basename(config_file) == "meta.yaml":
                continue
            if not scraper_name or not url:
                logger.warning(f"Skipping {config_file}: missing scraper_name or URL")
                continue

            expanded_urls = expand_url_variables(url, date_range)
            multiple_events = config.get("multiple_events", False)
            categories = config.get("categories", [])
            use_playwright = config.get("use_playwright", False)
            llm_hints = config.get("llm_hints", [])
            selector_remove = config.get("selector_remove", [])
            selector_keep = config.get("selector_keep", [])

            for expanded_url in expanded_urls:
                scraper = AIScraper(
                    expanded_url,
                    scraper_name,
                    multiple_events=multiple_events,
                    categories=categories,
                    use_playwright=use_playwright,
                    llm_hints=llm_hints,
                    selector_remove=selector_remove,
                    selector_keep=selector_keep,
                )
                scrapers.append(scraper)
        except Exception as e:
            logger.warning(f"Failed to load config {config_file}: {e}")

    logger.info(f"Loaded {len(scrapers)} YAML scrapers")
    return scrapers


def get_disabled_yaml_configs(config_dir: Optional[Path] = None) -> List[str]:
    if config_dir is None:
        return []
    config_files = glob(str(config_dir / "*.yaml"))

    disabled_files = []
    for config_file in config_files:
        try:
            with open(config_file, "r") as f:
                config = yaml.safe_load(f)
            if config.get("disabled", False):
                disabled_files.append(config_file)
        except Exception:
            pass

    return disabled_files
